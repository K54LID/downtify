from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    BOT_USERNAME: str = "Downtify_Bot"
    ADMIN_IDS: str = ""

    SUBSCRIPTION_STARS: int = 100
    SUBSCRIPTION_DAYS: int = 30

    DAILY_FREE_USES: int = 3

    REFERRAL_REWARD_DAYS: int = 3
    REFERRAL_BONUS_DAYS: int = 1

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

    TELEGRAM_API_ROOT: str = ""

    @property
    def admin_ids(self) -> list[int]:
        return [
            int(x.strip())
            for x in self.ADMIN_IDS.split(",")
            if x.strip()
        ]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return (
            f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        )


settings = Settings()