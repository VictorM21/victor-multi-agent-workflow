"""
Application configuration using Pydantic Settings.
Reads from environment variables or .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ─── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Anthropic API key (required)")

    # ─── Agent models ──────────────────────────────────────────────────────────
    supervisor_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model used by the Supervisor"
    )
    worker_model: str = Field(
        default="claude-3-haiku-20240307",
        description="Claude model used by Worker agents"
    )

    # ─── Concurrency ───────────────────────────────────────────────────────────
    max_workers: int = Field(default=3, description="Max concurrent worker agents")

    # ─── Human-in-the-loop ─────────────────────────────────────────────────────
    checkpoint_timeout: int = Field(
        default=300,
        description="Seconds to await human approval before timeout"
    )
    require_approval: bool = Field(
        default=False,
        description="Pause for approval after every worker step"
    )

    # ─── Storage ───────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379")
    database_url: str = Field(default="sqlite:///./data/audit.db")

    # ─── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # ─── Observability ─────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}


settings = Settings()
