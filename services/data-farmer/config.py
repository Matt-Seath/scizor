"""Configuration management for Data Farmer service."""

import os
from typing import Optional

from pydantic import BaseSettings, Field


class DataFarmerSettings(BaseSettings):
    """Data Farmer service configuration."""
    
    # Service configuration
    service_name: str = Field(default="data-farmer", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="DATA_FARMER_HOST")
    port: int = Field(default=8001, env="DATA_FARMER_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database configuration
    database_url: str = Field(
        default="postgresql+asyncpg://scizor:scizor123@localhost:5432/scizor",
        env="DATABASE_URL"
    )
    
    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # IBKR configuration
    ibkr_host: str = Field(default="127.0.0.1", env="IBKR_HOST")
    ibkr_port: int = Field(default=7497, env="IBKR_PORT")
    ibkr_client_id: int = Field(default=1, env="IBKR_CLIENT_ID")
    
    # Data collection configuration
    max_concurrent_collections: int = Field(default=10, env="MAX_CONCURRENT_COLLECTIONS")
    collection_batch_size: int = Field(default=100, env="COLLECTION_BATCH_SIZE")
    collection_timeout: int = Field(default=30, env="COLLECTION_TIMEOUT")
    
    # Data retention configuration
    data_retention_days: int = Field(default=365, env="DATA_RETENTION_DAYS")
    cleanup_interval_hours: int = Field(default=24, env="CLEANUP_INTERVAL_HOURS")
    
    # API configuration
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: list = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # Performance configuration
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = DataFarmerSettings()


def get_settings() -> DataFarmerSettings:
    """Get the current settings instance."""
    return settings


def update_settings(**kwargs) -> DataFarmerSettings:
    """Update settings with new values."""
    global settings
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return settings
