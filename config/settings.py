"""config/settings.py — Application settings from environment variables."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aars:aars_dev@localhost:5432/aars"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://aars:aars_dev@localhost:5432/aars"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480  # 8 hours

    # S3 / MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_RECORDINGS: str = "recordings"
    S3_BUCKET_TRAINING: str = "training-content"

    # Channel Providers
    VOICE_PROVIDER: str = "mock"  # "mock", "sarvam"
    WHATSAPP_PROVIDER: str = "mock"  # "mock", "meta"

    # WhatsApp — Meta Cloud API
    META_WHATSAPP_API_VERSION: str = "v21.0"
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_ACCESS_TOKEN: str = ""
    META_WHATSAPP_VERIFY_TOKEN: str = ""
    META_WHATSAPP_APP_SECRET: str = ""

    # Voice Provider Config
    VOICE_API_KEY: str = ""
    VOICE_API_URL: str = ""
    VOICE_WEBHOOK_SECRET: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # Environment
    ENV: str = "development"  # development, staging, production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env"}


settings = Settings()
