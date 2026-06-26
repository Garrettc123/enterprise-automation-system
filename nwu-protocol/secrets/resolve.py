from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    stripe_secret_key: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    web3_rpc_url: str = ""
    private_key: str = ""
    nwu_protocol_address: str = ""
    nwu_data_token_address: str = ""
    nwu_governance_address: str = ""
    database_url: str = ""
    railway_environment: str = "production"

    class Config:
        env_file = os.path.expanduser("~/.garcar.env")
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
