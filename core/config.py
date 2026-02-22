from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Gene Summary API"
    app_version: str = "1.0.0"

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 86400  # 24 hours

    # UniProt
    uniprot_base_url: str = "https://rest.uniprot.org/uniprotkb/search"
    uniprot_timeout: int = 20
    uniprot_retries: int = 2

    # Rate limiting
    rate_limit: str = "30/minute"

    # Human organism
    human_organism_id: int = 9606

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
