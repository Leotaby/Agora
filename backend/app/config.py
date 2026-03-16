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

    # LLM
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.anthropic.com/v1"
    LLM_MODEL_NAME: str = "claude-sonnet-4-6"
    ANTHROPIC_API_KEY: str = ""

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

    # Database
    DATABASE_URL: str = "sqlite:///./nexus.db"


settings = Settings()
