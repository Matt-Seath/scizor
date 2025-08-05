"""Configuration management for Backtester service."""

import os
from typing import Optional, List

from pydantic import BaseSettings, Field


class BacktesterSettings(BaseSettings):
    """Backtester service configuration."""
    
    # Service configuration
    service_name: str = Field(default="backtester", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="BACKTESTER_HOST")
    port: int = Field(default=8002, env="BACKTESTER_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database configuration
    database_url: str = Field(
        default="postgresql+asyncpg://scizor:scizor123@localhost:5432/scizor",
        env="DATABASE_URL"
    )
    
    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        env="REDIS_URL"
    )
    
    # Backtesting configuration
    max_concurrent_backtests: int = Field(default=5, env="MAX_CONCURRENT_BACKTESTS")
    default_initial_capital: float = Field(default=100000.0, env="DEFAULT_INITIAL_CAPITAL")
    default_commission: float = Field(default=0.001, env="DEFAULT_COMMISSION")
    default_slippage: float = Field(default=0.0001, env="DEFAULT_SLIPPAGE")
    
    # Performance calculation settings
    risk_free_rate: float = Field(default=0.02, env="RISK_FREE_RATE")  # 2% annual
    benchmark_symbol: str = Field(default="SPY", env="BENCHMARK_SYMBOL")
    
    # Data settings
    min_data_points: int = Field(default=100, env="MIN_DATA_POINTS")
    max_backtest_duration_days: int = Field(default=365 * 5, env="MAX_BACKTEST_DURATION_DAYS")  # 5 years
    
    # Engine configuration
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    memory_limit_mb: int = Field(default=2048, env="MEMORY_LIMIT_MB")
    
    # API configuration
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    # Results storage
    results_retention_days: int = Field(default=90, env="RESULTS_RETENTION_DAYS")
    max_results_per_strategy: int = Field(default=100, env="MAX_RESULTS_PER_STRATEGY")
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # Performance optimization
    use_vectorized_calculations: bool = Field(default=True, env="USE_VECTORIZED_CALCULATIONS")
    parallel_processing: bool = Field(default=True, env="PARALLEL_PROCESSING")
    cache_market_data: bool = Field(default=True, env="CACHE_MARKET_DATA")
    
    # Strategy validation
    max_strategy_file_size_mb: int = Field(default=10, env="MAX_STRATEGY_FILE_SIZE_MB")
    allowed_strategy_imports: List[str] = Field(
        default=["numpy", "pandas", "ta", "talib", "scipy", "sklearn"],
        env="ALLOWED_STRATEGY_IMPORTS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = BacktesterSettings()


def get_settings() -> BacktesterSettings:
    """Get the current settings instance."""
    return settings


def update_settings(**kwargs) -> BacktesterSettings:
    """Update settings with new values."""
    global settings
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return settings
