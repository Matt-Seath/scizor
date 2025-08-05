"""Configuration management for Scizor services."""

import os
from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """Base configuration class."""
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://scizor_user:scizor_password@localhost:5432/scizor",
        env="DATABASE_URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # IBKR Configuration (Gateway settings)
    ibkr_host: str = Field(default="127.0.0.1", env="IBKR_HOST")
    ibkr_port: int = Field(default=4001, env="IBKR_PORT")  # Gateway port
    ibkr_client_id: int = Field(default=1, env="IBKR_CLIENT_ID")
    ibkr_read_only: bool = Field(default=True, env="IBKR_READ_ONLY")  # Match your read-only setting
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Security
    jwt_secret_key: str = Field(default="your-secret-key-here", env="JWT_SECRET_KEY")
    api_key: str = Field(default="your-api-key-here", env="API_KEY")
    
    # Risk Management
    max_position_size: float = Field(default=10000.0, env="MAX_POSITION_SIZE")
    max_daily_loss: float = Field(default=1000.0, env="MAX_DAILY_LOSS")
    max_exposure_pct: float = Field(default=0.8, env="MAX_EXPOSURE_PCT")
    
    # Development
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class DataFarmerConfig(BaseConfig):
    """Data Farmer service configuration."""
    
    port: int = Field(default=8000, env="DATA_FARMER_PORT")
    
    # Data collection settings
    max_concurrent_requests: int = Field(default=50, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="RETRY_DELAY")
    
    # Data storage settings
    batch_size: int = Field(default=1000, env="BATCH_SIZE")
    data_retention_days: int = Field(default=365, env="DATA_RETENTION_DAYS")
    
    # Rate limiting
    requests_per_second: int = Field(default=50, env="REQUESTS_PER_SECOND")
    
    
class BacktesterConfig(BaseConfig):
    """Backtester service configuration."""
    
    port: int = Field(default=8001, env="BACKTESTER_PORT")
    
    # Service URLs
    data_farmer_url: str = Field(default="http://localhost:8000", env="DATA_FARMER_URL")
    
    # Backtest settings
    max_concurrent_backtests: int = Field(default=5, env="MAX_CONCURRENT_BACKTESTS")
    backtest_timeout: int = Field(default=3600, env="BACKTEST_TIMEOUT")  # 1 hour
    
    # Performance calculation
    risk_free_rate: float = Field(default=0.02, env="RISK_FREE_RATE")  # 2%
    benchmark_symbol: str = Field(default="SPY", env="BENCHMARK_SYMBOL")
    
    # Optimization
    optimization_trials: int = Field(default=100, env="OPTIMIZATION_TRIALS")
    optimization_timeout: int = Field(default=7200, env="OPTIMIZATION_TIMEOUT")  # 2 hours


class AlgoTraderConfig(BaseConfig):
    """Algo Trader service configuration."""
    
    port: int = Field(default=8002, env="ALGO_TRADER_PORT")
    
    # Service URLs
    data_farmer_url: str = Field(default="http://localhost:8000", env="DATA_FARMER_URL")
    backtester_url: str = Field(default="http://localhost:8001", env="BACKTESTER_URL")
    
    # Trading settings
    paper_trading: bool = Field(default=True, env="PAPER_TRADING")
    max_concurrent_strategies: int = Field(default=10, env="MAX_CONCURRENT_STRATEGIES")
    order_timeout: int = Field(default=60, env="ORDER_TIMEOUT")
    
    # Risk management
    daily_loss_limit: float = Field(default=5000.0, env="DAILY_LOSS_LIMIT")
    position_size_limit: float = Field(default=100000.0, env="POSITION_SIZE_LIMIT")
    max_drawdown_limit: float = Field(default=0.20, env="MAX_DRAWDOWN_LIMIT")  # 20%
    
    # Notifications
    twilio_sid: Optional[str] = Field(default=None, env="TWILIO_SID")
    twilio_token: Optional[str] = Field(default=None, env="TWILIO_TOKEN")
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    
    # Monitoring
    check_interval: int = Field(default=5, env="CHECK_INTERVAL")  # seconds
    heartbeat_interval: int = Field(default=30, env="HEARTBEAT_INTERVAL")  # seconds


def get_config(service: str = "base") -> BaseConfig:
    """Get configuration for a specific service."""
    
    configs = {
        "base": BaseConfig,
        "data-farmer": DataFarmerConfig,
        "backtester": BacktesterConfig,
        "algo-trader": AlgoTraderConfig,
    }
    
    config_class = configs.get(service, BaseConfig)
    return config_class()


def get_env_var(key: str, default: Any = None) -> Any:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def set_env_var(key: str, value: str) -> None:
    """Set environment variable."""
    os.environ[key] = value


def load_env_file(file_path: str = ".env") -> Dict[str, str]:
    """Load environment variables from file."""
    env_vars = {}
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
                    os.environ[key.strip()] = value.strip()
    
    return env_vars
