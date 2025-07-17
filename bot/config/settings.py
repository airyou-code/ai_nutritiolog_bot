from pydantic import Field, computed_field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Bot configuration
    bot_token: str = Field(..., description="Telegram bot token")
    
    # Database configuration
    database_url: Optional[str] = Field(None, description="PostgreSQL database URL")
    database_echo: bool = Field(False, description="SQLAlchemy echo mode")
    
    # Individual PostgreSQL settings (for Docker environments)
    postgres_db: Optional[str] = Field(None, description="PostgreSQL database name")
    postgres_user: Optional[str] = Field(None, description="PostgreSQL username")
    postgres_password: Optional[str] = Field(None, description="PostgreSQL password")
    postgres_host: Optional[str] = Field(None, description="PostgreSQL host")
    postgres_port: Optional[str] = Field(None, description="PostgreSQL port")
    
    # Redis configuration
    redis_url: str = Field("redis://localhost:6379/0", description="Redis URL")
    
    # OpenAI configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field("gpt-4o", description="OpenAI model to use")
    
    # Application settings
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Logging level")
    
    # Nutrition analysis settings
    max_photo_size: int = Field(20 * 1024 * 1024, description="Max photo size in bytes (20MB)")
    
    @computed_field
    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL, either from database_url or constructed from postgres_* fields"""
        if self.database_url:
            return self.database_url
        
        # Construct from individual postgres fields
        if all([self.postgres_db, self.postgres_user, self.postgres_password, self.postgres_host]):
            port = self.postgres_port or "5432"
            return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{port}/{self.postgres_db}"
        
        raise ValueError("Either database_url or all postgres_* fields must be provided")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings() 