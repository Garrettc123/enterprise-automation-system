import hashlib, hmac, json, os
import httpx
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Garcar Automation Router", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
NOTION_TOKEN         = os.getenv("NOTION_TOKEN", "")
STRIPE_WEBHOOK_SEC   = os.getenv("STRIPE_WEBHOOK_SECRET", "")
GITHUB_WEBHOOK_SEC   = os.getenv("GITHUB_WEBHOOK_SECRET", "")
NOTION_DB_REVENUE    = os.getenv("NOTION_DB_REVENUE", "")
NOTION_DB_DEPLOYS    = os.getenv("NOTION_DB_DEPLOYS", "")
NOTION_DB_LEADS      = os.getenv("NOTION_DB_LEADS", "")

async def notion_create_page(database_id: str, properties: dict, content: list | None = None):
    if not NOTION_TOKEN or not database_id:
        return
    body: dict[str, Any] = {"parent": {"database_id": database_id}, "properties": properties}
    if content:
        body["children"] = content
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post("https://api.notion.com/v1/pages",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28",
                     "Content-Type": "application/json"}, json=body)
        r.raise_for_status()
        return r.json()

async def supabase_insert(table: str, record: dict):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_SERVICE_KEY,
                     "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"}, json=record)
        r.raise_for_status()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "garcar-automation-router",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connections": {"supabase": bool(SUPABASE_URL), "notion": bool(NOTION_TOKEN),
                            "stripe": bool(STRIPE_WEBHOOK_SEC), "github": bool(GITHUB_WEBHOOK_SEC)}}

@app.post("/webhook/github")
async def webhook_github(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    sig  = request.headers.get("X-Hub-Signature-256")
    if GITHUB_WEBHOOK_SEC and sig:
        expected = "sha256=" + hmac.new(GITHUB_WEBHOOK_SEC.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=401, detail="Invalid signature")
    event   = request.headers.get("X-GitHub-Event", "unknown")
    payload = json.loads(body)
    background_tasks.add_task(supabase_insert, "github_events",
        {"event_type": event, "repository": payload.get("repository", {}).get("full_name"),
         "sender": payload.get("sender", {}).get("login"), "payload": payload,
         "created_at": datetime.now(timezone.utc).isoformat()})
    if event == "push" and payload.get("ref") == "refs/heads/main":
        repo = payload.get("repository", {}).get("name", "unknown")
        pusher = payload.get("pusher", {}).get("name", "unknown")
        msgs = " | ".join(c.get("message","") for c in payload.get("commits",[])[:3])
        background_tasks.add_task(notion_create_page, NOTION_DB_DEPLOYS, {
            "Name":       {"title": [{"text": {"content": f"Deploy: {repo} @ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"}}]},
            "Repository": {"rich_text": [{"text": {"content": repo}}]},
            "Pushed By":  {"rich_text": [{"text": {"content": pusher}}]},
            "Commits":    {"rich_text": [{"text": {"content": msgs}}]},
            "Status":     {"select": {"name": "Deployed"}},
            "Timestamp":  {"date": {"start": datetime.now(timezone.utc).isoformat()}}})
        return {"status": "deploy logged", "repo": repo}
    return {"status": "received", "event": event}

@app.post("/webhook/stripe")
async def webhook_stripe(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    payload    = json.loads(body)
    event_type = payload.get("type", "unknown")
    data_obj   = payload.get("data", {}).get("object", {})
    background_tasks.add_task(supabase_insert, "stripe_events",
        {"event_type": event_type, "stripe_id": data_obj.get("id"),
         "amount": data_obj.get("amount", data_obj.get("amount_paid", 0)),
         "currency": data_obj.get("currency", "usd"), "customer_id": data_obj.get("customer"),
         "payload": payload, "created_at": datetime.now(timezone.utc).isoformat()})
    tracked = {"payment_intent.succeeded","customer.subscription.created",
               "customer.subscription.deleted","invoice.paid","invoice.payment_failed"}
    if event_type in tracked:
        amt = data_obj.get("amount", data_obj.get("amount_paid", 0)) / 100
        background_tasks.add_task(notion_create_page, NOTION_DB_REVENUE, {
            "Name":       {"title": [{"text": {"content": f"{event_type} — ${amt:.2f}"}}]},
            "Event Type": {"select": {"name": event_type}},
            "Amount USD": {"number": amt},
            "Customer":   {"rich_text": [{"text": {"content": data_obj.get("customer","")}}]},
            "Stripe ID":  {"rich_text": [{"text": {"content": data_obj.get("id","")}}]},
            "Timestamp":  {"date": {"start": datetime.now(timezone.utc).isoformat()}}})
    return {"status": "received", "event_type": event_type}

class SupabaseEvent(BaseModel):
    type: str
    table: str
    record: dict | None = None
    old_record: dict | None = None

@app.post("/webhook/supabase")
async def webhook_supabase(payload: SupabaseEvent, background_tasks: BackgroundTasks):
    record = payload.record or {}
    if payload.table == "leads" and payload.type == "INSERT":
        background_tasks.add_task(notion_create_page, NOTION_DB_LEADS, {
            "Name":      {"title": [{"text": {"content": record.get("name","Unknown Lead")}}]},
            "Email":     {"email": record.get("email","")},
            "Source":    {"select": {"name": record.get("source","Unknown")}},
            "Phone":     {"phone_number": record.get("phone","")},
            "Status":    {"select": {"name": "New"}},
            "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}}})
        return {"status": "lead synced to Notion"}
    if payload.table == "revenue_events" and payload.type == "INSERT":
        background_tasks.add_task(notion_create_page, NOTION_DB_REVENUE, {
            "Name":       {"title": [{"text": {"content": record.get("description","Revenue Event")}}]},
            "Amount USD": {"number": float(record.get("amount_usd", 0))},
            "Source":     {"select": {"name": record.get("source","System")}},
            "Timestamp":  {"date": {"start": datetime.now(timezone.utc).isoformat()}}})
        return {"status": "revenue synced to Notion"}
    return {"status": "received", "table": payload.table, "event": payload.type}

class NotionPush(BaseModel):
    database: str
    properties: dict
    content: list | None = None

@app.post("/sync/notion")
async def sync_notion(payload: NotionPush, background_tasks: BackgroundTasks):
    aliases = {"revenue": NOTION_DB_REVENUE, "deploys": NOTION_DB_DEPLOYS, "leads": NOTION_DB_LEADS}
    db_id = aliases.get(payload.database, payload.database)
    if not db_id:
        raise HTTPException(status_code=400, detail=f"Unknown database '{payload.database}'")
    background_tasks.add_task(notion_create_page, db_id, payload.properties, payload.content)
    return {"status": "queued", "database": payload.database}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
