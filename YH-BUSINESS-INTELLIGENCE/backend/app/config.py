from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "YH BUSINESS INTELLIGENCE"
    app_env: str = "development"
    database_url: str = "sqlite:///./yhbi.db"
    jwt_secret: str = "replace-with-a-long-random-secret-before-use"
    jwt_issuer: str = "yh-business-intelligence"
    access_token_minutes: int = 30
    auto_create_schema: bool = True
    cors_origins: str = "http://localhost:5173,http://tauri.localhost"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
