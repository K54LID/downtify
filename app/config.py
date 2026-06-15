from __future__ import annotations
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    BOT_USERNAME: str = "Downtify_Bot"
    ADMIN_IDS: List[int] = Field(default_factory=list)

    SUBSCRIPTION_STARS: int = 100
    SUBSCRIPTION_DAYS: int = 30

    # Daily free usage for non-subscribers
    DAILY_FREE_USES: int = 3

    # Referral system: days of Premium granted to BOTH referrer and the
    # referred user once the referred user is verified (e.g. on first download).
    REFERRAL_REWARD_DAYS: int = 3
    REFERRAL_BONUS_DAYS: int = 1  # extra days for the new (referred) user

    # Daily spin wheel
    SPIN_COOLDOWN_HOURS: int = 24

    POSTGRES_USER: str = "Downtify"
    POSTGRES_PASSWORD: str = "Downtify"
    POSTGRES_DB: str = "Downtify"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    RATE_LIMIT_PER_MINUTE: int = 30
    DOWNLOAD_MAX_FILESIZE_MB: int = 1024

    LOG_LEVEL: str = "INFO"

    WEBHOOK_URL: str = ""
    WEBHOOK_PATH: str = "/webhook"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080
    WEBHOOK_SECRET: str = ""

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def _split_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v or []

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
