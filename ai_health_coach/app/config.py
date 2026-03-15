from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    DATABASE_URL: str = "sqlite+aiosqlite:////data/health_coach.db"
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    CONSENT_CHECK_ENABLED: bool = True
    API_KEY: str  # required — no insecure default

    # LLM models
    CONVERSATION_MODEL: str = "claude-sonnet-4-20250514"
    SAFETY_MODEL: str = "claude-haiku-4-5-20251001"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
