"""
config.py - Application Configuration

This module handles all configuration using Pydantic Settings.
It reads from environment variables and provides type-safe access
to configuration values throughout the application.

Key concepts:
- `BaseSettings` automatically reads from environment variables
- `model_config` specifies the .env file location
- Default values are used if env vars are not set
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        app_name: Name of the application (for display purposes)
        debug: Enable debug mode (more verbose logging)
        
        # Database
        database_url: PostgreSQL connection string (async driver)
        
        # JWT Authentication
        secret_key: Secret key for signing JWT tokens (CHANGE IN PRODUCTION!)
        algorithm: JWT signing algorithm (HS256 is standard)
        access_token_expire_minutes: How long access tokens are valid
        refresh_token_expire_days: How long refresh tokens are valid
        
        # AI / Gemini
        gemini_api_key: Google Gemini API key for AI features
    """
    
    # Application
    app_name: str = "Flashcard Generator"
    debug: bool = True
    
    # Database - asyncpg driver for async PostgreSQL
    # Format: postgresql+asyncpg://user:password@host:port/database
    database_url: str = "postgresql+asyncpg://admin:password@localhost:5432/flashcard_gen"
    
    # JWT Authentication
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # AI / Gemini
    gemini_api_key: str = ""
    
    # Tell Pydantic to read from .env file
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignore extra env vars not defined here
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Using @lru_cache ensures we only read the .env file once,
    improving performance. The settings object is reused across
    all requests.
    
    Returns:
        Settings: The application settings
    """
    return Settings()
