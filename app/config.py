"""
WENDRINK ERP - Application Configuration
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )
    
    app_env: str = "development"
    debug: bool = True
    app_name: str = "WENDRINK ERP"
    app_version: str = "0.1.0"
    
    database_url: str = "sqlite+aiosqlite:///./wendrink.db"
    
    @property
    def async_database_url(self) -> str:
        return self.database_url
    
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+aiosqlite", "")

@lru_cache
def get_settings() -> Settings:
    return Settings()
