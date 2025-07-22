from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Bot configuration
    bot_token: str = Field(..., description="Telegram bot token")

    # Database configuration
    database_url: str | None = Field(None, description="PostgreSQL database URL")
    database_echo: bool = Field(False, description="SQLAlchemy echo mode")

    # Individual PostgreSQL settings (for Docker environments)
    postgres_db: str | None = Field(None, description="PostgreSQL database name")
    postgres_user: str | None = Field(None, description="PostgreSQL username")
    postgres_password: str | None = Field(None, description="PostgreSQL password")
    postgres_host: str | None = Field(None, description="PostgreSQL host")
    postgres_port: str | None = Field(None, description="PostgreSQL port")

    # Redis configuration
    redis_url: str = Field("redis://localhost:6379/0", description="Redis URL")

    # OpenAI configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field("gpt-4o", description="OpenAI model to use")

    # Application settings
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Logging level")

    # Nutrition analysis settings
    max_photo_size: int = Field(
        20 * 1024 * 1024, description="Max photo size in bytes (20MB)"
    )

    # Chat memory settings
    chat_memory_ttl_hours: int = Field(
        168, description="Chat memory TTL in hours (default: 7 days)"
    )
    max_chat_topics_per_user: int = Field(
        20, description="Max recent topics to remember per user"
    )
    chat_cleanup_interval_hours: int = Field(
        24, description="How often to run chat cleanup (hours)"
    )
    enable_chat_persistence: bool = Field(
        True, description="Enable chat memory persistence"
    )

    @computed_field
    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL, either from database_url or constructed from postgres_* fields"""
        if self.database_url:
            # Ensure async driver is used
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            elif self.database_url.startswith("postgresql+psycopg2://"):
                return self.database_url.replace(
                    "postgresql+psycopg2://", "postgresql+asyncpg://", 1
                )
            return self.database_url

        # Construct from individual postgres fields with async driver
        if all(
            [
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
                self.postgres_host,
            ]
        ):
            port = self.postgres_port or "5432"
            return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{port}/{self.postgres_db}"

        raise ValueError(
            "Either database_url or all postgres_* fields must be provided"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings()
