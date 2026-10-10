from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://command_center:command_center@localhost:5432/command_center"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:2b"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765
    mcp_url: str = "http://127.0.0.1:8765/mcp"

    agent_timeout_seconds: float = 180


settings = Settings()
