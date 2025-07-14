from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Bot configuration
    bot_token: str = Field(..., description="Telegram bot token")
    
    # Database configuration
    database_url: str = Field(..., description="PostgreSQL database URL")
    database_echo: bool = Field(False, description="SQLAlchemy echo mode")
    
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings() 