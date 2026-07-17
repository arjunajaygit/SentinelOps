import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings, automatically loaded from environment variables or a .env file.
    """
    # GitHub Settings
    GITHUB_TOKEN: str = ""
    WEBHOOK_SECRET: str = ""
    
    # LLM Settings
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str | None = None
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    
    # General Settings
    APP_NAME: str = "SentinelOps"
    DEBUG: bool = False
    
    # We allow these to be empty strings by default so the app doesn't crash on import, 
    # but they should be validated or checked when needed.
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate the settings so it can be imported across the app
settings = Settings()
