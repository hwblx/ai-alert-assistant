from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
       env_file=BASE_DIR / ".env",
       extra="ignore"
    )
    ALERT_DEDUPLICATION_WINDOW_MINUTES: int = 15

    DATABASE_URL: str = "sqlite+aiosqlite:///./alerts.db"  # Development
    # DATABASE_URL: str = "sqlite+aiosqlite:////app/data/alerts.db"  # Production/Docker

    HOOKDECK_API_KEY: str | None = None
    HOOKDECK_API_URL: str | None = None
    HOOKDECK_SIGNING_SECRET: str | None = None

    HTTP_TIMEOUT: float = 300.0

    INFERENCE_PROVIDER: int = 1

    MULTIPASS_AGENT: bool = False

    PROVIDER_NAME_1: str = "openrouter"
    PROVIDER_MODEL_1: str | None = "openai/gpt-4o-mini"
    PROVIDER_URL_1: str | None = None
    PROVIDER_KEY_1: str | None = None

    PROVIDER_NAME_2: str = "ollama"
    PROVIDER_MODEL_2: str | None = "qwen2.5:0.5b-instruct"
    PROVIDER_URL_2: str | None = "http://localhost:11434/v1"
    PROVIDER_KEY_2: str | None = None


settings = Settings()  # type: ignore

