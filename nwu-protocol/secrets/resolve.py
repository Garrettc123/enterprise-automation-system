from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path.home() / .garcar.env

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding=utf-8,
        extra=ignore
    )
    database_url: str = 
    supabase_url: str = 
    supabase_key: str = 
    stripe_secret_key: str = 
    web3_rpc_url: str = 
    private_key: str = 
    nwu_protocol_address: str = 
    nwu_data_token_address: str = 
    nwu_governance_address: str = 
    railway_environment: str = production

@lru_cache()
def get_settings():
    return Settings()
