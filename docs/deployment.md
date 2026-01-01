# Deployment Guide

## Prerequisites

### Required Access
- AWS Account with admin permissions
- GitHub repository access
- Docker Hub account
- Domain name and DNS control

### Required Tools
```bash
# Install required CLI tools
brew install kubectl helm terraform aws-cli docker

# Verify installations
kubectl version --client
helm version
terraform version
aws --version
docker --version
```

### Required Knowledge
- Kubernetes administration
- AWS services (EKS, RDS, S3, CloudFront)
- Infrastructure as Code (Terraform)
- CI/CD pipelines (GitHub Actions)

---

## Phase 1: Foundation (Weeks 1-4)

### Week 1: Infrastructure Provisioning

#### Step 1: Configure AWS Credentials
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

#### Step 2: Deploy Kubernetes Cluster
```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -out=eks-cluster.tfplan

# Apply configuration
terraform apply eks-cluster.tfplan

# Configure kubectl
aws eks update-kubeconfig --name enterprise-automation-cluster --region us-east-1

# Verify cluster
kubectl get nodes
kubectl get namespaces
```

#### Step 3: Deploy Database Layer
```bash
# PostgreSQL (Primary Database)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgresql bitnami/postgresql \
  --set primary.persistence.size=1Ti \
  --set replication.enabled=true \
  --set replication.readReplicas=2

# Redis (Caching)
helm install redis bitnami/redis \
  --set master.persistence.size=500Gi \
  --set replica.replicaCount=3

# Elasticsearch (Logging)
helm repo add elastic https://helm.elastic.co
helm install elasticsearch elastic/elasticsearch \
  --set volumeClaimTemplate.resources.requests.storage=2Ti \
  --set replicas=7

# MongoDB (Document Store)
helm install mongodb bitnami/mongodb \
  --set persistence.size=500Gi \
  --set replicaSet.enabled=true
```

### Week 2: Monitoring Stack

#### Step 1: Prometheus + Grafana
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi
```

#### Step 2: ELK Stack
```bash
helm install logstash elastic/logstash
helm install kibana elastic/kibana
```

#### Step 3: Jaeger Tracing
```bash
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger
```

### Week 3-4: Orchestration Layer

```bash
# Deploy orchestration services
kubectl apply -f k8s/orchestration/

# Verify deployments
kubectl get pods -n production
kubectl get services -n production
```

---

## Phase 2: Integration (Weeks 5-8)

### Week 5-6: System Integrations

#### Finance Integration
```bash
kubectl create secret generic finance-credentials \
  --from-literal=api-key=YOUR_API_KEY \
  --from-literal=api-secret=YOUR_API_SECRET

kubectl apply -f k8s/integrations/finance/
```

#### HR Integration
```bash
kubectl create secret generic hr-credentials \
  --from-literal=workday-user=YOUR_USER \
  --from-literal=workday-password=YOUR_PASSWORD

kubectl apply -f k8s/integrations/hr/
```

#### Operations Integration
```bash
kubectl apply -f k8s/integrations/operations/
```

### Week 7-8: Agent Deployment

```bash
# Deploy all 15+ specialized agents
for agent in agents/*/; do
  kubectl apply -f "$agent/deployment.yaml"
done

# Verify agent health
kubectl get pods -l app=agent -n production
```

---

## Phase 3: Validation (Weeks 9-12)

### Week 9: Pilot Workflows

#### Deploy 5 Test Workflows
1. Invoice Processing
2. Employee Onboarding
3. Expense Approval
4. Report Generation
5. Customer Support Ticket Routing

```bash
kubectl apply -f workflows/pilot/
```

### Week 10-11: Performance Testing

```bash
# Load testing
cd tests/load
./run-load-tests.sh

# Stress testing
./run-stress-tests.sh

# Chaos engineering
./run-chaos-tests.sh
```

### Week 12: Production Hardening

- Security scanning
- Penetration testing
- Documentation review
- Runbook validation
- Disaster recovery drill

---

## Phase 4: Rollout (Week 13+)

### Week 13: Initial Production (20% Traffic)
```bash
# Update traffic routing
kubectl apply -f k8s/ingress/production-20.yaml

# Monitor metrics
kubectl port-forward -n monitoring svc/grafana 3000:80
# Open http://localhost:3000
```

### Week 14: Increase to 40%
```bash
kubectl apply -f k8s/ingress/production-40.yaml
```

### Week 15: Increase to 60%
```bash
kubectl apply -f k8s/ingress/production-60.yaml
```

### Week 16: Increase to 80%
```bash
kubectl apply -f k8s/ingress/production-80.yaml
```

### Week 17: Full Production (100%)
```bash
kubectl apply -f k8s/ingress/production-100.yaml
```

---

## Verification Procedures

### Health Checks
```bash
# System health
curl https://api.yourdomain.com/health

# Component health
kubectl get pods --all-namespaces
kubectl top nodes
kubectl top pods

# Database connectivity
kubectl exec -it postgresql-0 -- psql -U postgres -c "SELECT 1;"
```

### Performance Validation
```bash
# Run benchmark suite
cd tests/benchmarks
./run-all-benchmarks.sh

# Expected results:
# - P95 latency: <150ms
# - Success rate: >97%
# - Throughput: >15,000 tokens/sec
```

---

## Rollback Procedures

### Emergency Rollback
```bash
# Revert to previous version
kubectl rollout undo deployment/orchestrator -n production

# Verify rollback
kubectl rollout status deployment/orchestrator -n production
```

### Database Rollback
```bash
# Restore from backup
aws s3 cp s3://backup-bucket/postgres-backup-latest.sql .
kubectl exec -it postgresql-0 -- psql -U postgres < postgres-backup-latest.sql
```

---

## Monitoring & Alerting

### Access Dashboards
- **Grafana**: https://grafana.yourdomain.com
- **Kibana**: https://kibana.yourdomain.com
- **Jaeger**: https://jaeger.yourdomain.com

### Configure Alerts
```bash
kubectl apply -f monitoring/alerts/critical.yaml
kubectl apply -f monitoring/alerts/high.yaml
kubectl apply -f monitoring/alerts/medium.yaml
```

---

## Troubleshooting

### Common Issues

**Issue**: Pods not starting
```bash
kubectl describe pod <pod-name> -n production
kubectl logs <pod-name> -n production --previous
```

**Issue**: High latency
```bash
# Check resource utilization
kubectl top pods -n production

# Scale up if needed
kubectl scale deployment/orchestrator --replicas=20 -n production
```

**Issue**: Database connection errors
```bash
# Test connectivity
kubectl exec -it <app-pod> -- nc -zv postgresql 5432

# Check credentials
kubectl get secret postgres-credentials -o yaml
```

---

## Support

**On-Call**: 24/7/365  
**Escalation**: PagerDuty  
**Documentation**: https://www.notion.so/2db024e8799b81ab9786de4ab76f697a  
**Repository**: https://github.com/Garrettc123/enterprise-automation-system

---

**Document Version**: 1.0  
**Last Updated**: January 1, 2026  
**Owner**: Garrett Wayne
