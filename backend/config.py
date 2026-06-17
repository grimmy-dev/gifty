from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider toggle: fast tier = retrieval/prep, smart tier = recommendation.
    llm_provider: Literal["claude", "gemini"] = "claude"

    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    tavily_api_key: str = ""

    claude_fast: str = "claude-haiku-4-5"
    claude_smart: str = "claude-sonnet-4-6"
    gemini_fast: str = "gemini-3.1-flash-lite"
    gemini_smart: str = "gemini-3.5-flash"

    db_path: str = "gifty.db"
    search_max_results: int = 6
    batch_size: int = 4
    max_concurrency: int = 3


settings = Settings()
