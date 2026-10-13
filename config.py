from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    # Stored as a raw string from the env var; parsed to list by the validator below
    allowed_origins: str
    allowed_seller_uid: str
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> object:
        # Leave non-string values (already a list from programmatic construction) as-is
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a parsed list of strings."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
