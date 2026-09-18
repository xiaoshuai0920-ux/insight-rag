"""Application configuration loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://insightrag:insightrag@localhost:5433/insightrag"

    # Auth
    JWT_SECRET: str = "PLEASE_CHANGE_ME"
    JWT_EXPIRE_MINUTES: int = 1440
    JWT_REMEMBER_EXPIRE_MINUTES: int = 60 * 24 * 14

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:7b"

    # OpenAI Compatible provider
    OPENAI_COMPATIBLE_BASE_URL: str = ""
    OPENAI_COMPATIBLE_API_KEY: str = ""
    OPENAI_COMPATIBLE_LLM_MODEL: str = ""

    # Embedding
    EMBEDDING_PROVIDER: str = "ollama"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OPENAI_COMPATIBLE_EMBEDDING_MODEL: str = ""

    # Reranker
    RERANKER_PROVIDER: str = "local"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # Storage
    UPLOAD_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    MAX_UPLOAD_MB: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
