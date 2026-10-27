from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Follows 12-factor application design principles.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment & Server
    ENVIRONMENT: str = "development"
    PORT: int = 8000

    # CORS configuration
    # Comma-separated list of permitted origins
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # External Provider: Duffel API (placeholder for future milestone)
    # Never exposed in responses or client code
    DUFFEL_API_KEY: str = ""

    @property
    def cors_origins(self) -> List[str]:
        """
        Parses ALLOWED_ORIGINS comma-separated string into a cleaned list of origin URLs.
        """
        origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        if not origins:
            origins = ["http://localhost:5173"]

        # Security check: Never permit wildcard '*' in production
        if self.is_production and "*" in origins:
            raise ValueError(
                "Wildcard '*' origin is strictly prohibited in production for security. "
                "Specify explicit origin domains in ALLOWED_ORIGINS."
            )
        return origins

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Returns cached instance of application settings."""
    return Settings()
