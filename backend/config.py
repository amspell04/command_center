import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://command_center:command_center@localhost:5432/command_center"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e2b"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765
    mcp_url: str = "http://127.0.0.1:8765/mcp"

    agent_timeout_seconds: float = 180

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "command-center"


settings = Settings()


def configure_tracing() -> None:
    """Export LangSmith settings to the environment, where the langsmith SDK reads them.

    pydantic-settings loads `.env` into `settings` only, not `os.environ`. Tracing stays off without an API key.
    """
    enabled = settings.langsmith_tracing and bool(settings.langsmith_api_key)
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"
    if enabled:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


configure_tracing()
