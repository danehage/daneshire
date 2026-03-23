from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    neon_database_url: str = ""

    # Market data
    fmp_api_key: str = ""

    # Notifications
    pushover_user_key: str = ""
    pushover_api_token: str = ""

    # Internal auth
    scheduler_secret: str = ""

    # Environment
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
