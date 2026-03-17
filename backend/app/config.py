"""
NEXUS configuration - all env vars via pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM backend
    LLM_CLI: str = "claude"
    LLM_CLI_ARGS: str = "-p"
    MODEL_NAME: str = "claude-haiku-4-5-20251001"

    # Memory
    ZEP_API_KEY: str = ""

    # Simulation
    NUM_HOUSEHOLD_AGENTS: int = 1000
    NUM_ROUNDS: int = 10
    RANDOM_SEED: int = 42

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 5001
    FRONTEND_PORT: int = 3000

    # World engine
    TICK_INTERVAL_SECONDS: float = 1.0
    DAYS_PER_TICK: int = 1
    MAX_EVENT_LOG: int = 10_000
    WORLD_ENGINE_CONCURRENCY: int = 10

    # Database
    DATABASE_URL: str = "sqlite:///./nexus.db"


settings = Settings()
