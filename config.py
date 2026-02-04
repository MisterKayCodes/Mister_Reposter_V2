"""
CONFIG: THE DNA
Centralized configuration management. (Rule 13, 14)
Uses Pydantic to validate that all required keys exist at startup.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    """
    Validates environment variables. 
    If a variable is missing, the 'Skeleton' won't boot.
    """
    # Telegram Bot API 
    BOT_TOKEN: SecretStr
    
    # Telegram App API 
    API_ID: int
    API_HASH: str
    
    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///data/reposter.db"

    # Pydantic configuration to read from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Global instance to be imported by the Skeleton (main.py)
config = Settings()
