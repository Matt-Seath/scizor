"""Configuration management for Algo Trader service."""

import os
from typing import Optional, List

from pydantic import BaseSettings, Field


class AlgoTraderSettings(BaseSettings):
    """Algo Trader service configuration."""
    
    # Service configuration
    service_name: str = Field(default="algo-trader", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="ALGO_TRADER_HOST")
    port: int = Field(default=8003, env="ALGO_TRADER_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database configuration
    database_url: str = Field(
        default="postgresql+asyncpg://scizor:scizor123@localhost:5432/scizor",
        env="DATABASE_URL"
    )
    
    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/2",
        env="REDIS_URL"
    )
    
    # IBKR configuration
    ibkr_host: str = Field(default="127.0.0.1", env="IBKR_HOST")
    ibkr_port: int = Field(default=7497, env="IBKR_PORT")
    ibkr_client_id: int = Field(default=2, env="IBKR_CLIENT_ID")
    
    # Trading configuration
    max_concurrent_orders: int = Field(default=20, env="MAX_CONCURRENT_ORDERS")
    default_order_timeout: int = Field(default=60, env="DEFAULT_ORDER_TIMEOUT")  # seconds
    max_position_size: float = Field(default=100000.0, env="MAX_POSITION_SIZE")  # USD
    
    # Risk management
    max_daily_loss: float = Field(default=5000.0, env="MAX_DAILY_LOSS")  # USD
    max_portfolio_risk: float = Field(default=0.02, env="MAX_PORTFOLIO_RISK")  # 2%
    position_size_limit: float = Field(default=0.1, env="POSITION_SIZE_LIMIT")  # 10% of portfolio
    
    # Strategy execution
    max_active_strategies: int = Field(default=10, env="MAX_ACTIVE_STRATEGIES")
    strategy_allocation_method: str = Field(default="equal", env="STRATEGY_ALLOCATION_METHOD")
    rebalance_frequency: str = Field(default="daily", env="REBALANCE_FREQUENCY")
    
    # Order management
    default_order_type: str = Field(default="MKT", env="DEFAULT_ORDER_TYPE")
    use_adaptive_orders: bool = Field(default=True, env="USE_ADAPTIVE_ORDERS")
    order_retry_attempts: int = Field(default=3, env="ORDER_RETRY_ATTEMPTS")
    
    # Performance monitoring
    pnl_calculation_frequency: int = Field(default=60, env="PNL_CALCULATION_FREQUENCY")  # seconds
    risk_check_frequency: int = Field(default=30, env="RISK_CHECK_FREQUENCY")  # seconds
    
    # API configuration
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    # Data and backtesting service URLs
    data_farmer_url: str = Field(default="http://localhost:8001", env="DATA_FARMER_URL")
    backtester_url: str = Field(default="http://localhost:8002", env="BACKTESTER_URL")
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # Security settings
    enable_paper_trading: bool = Field(default=True, env="ENABLE_PAPER_TRADING")
    require_confirmation: bool = Field(default=True, env="REQUIRE_CONFIRMATION")
    max_order_value: float = Field(default=50000.0, env="MAX_ORDER_VALUE")  # USD
    
    # Performance optimization
    use_async_order_processing: bool = Field(default=True, env="USE_ASYNC_ORDER_PROCESSING")
    order_batch_size: int = Field(default=10, env="ORDER_BATCH_SIZE")
    position_update_interval: int = Field(default=30, env="POSITION_UPDATE_INTERVAL")  # seconds
    
    # Alert configuration
    enable_email_alerts: bool = Field(default=False, env="ENABLE_EMAIL_ALERTS")
    enable_slack_alerts: bool = Field(default=False, env="ENABLE_SLACK_ALERTS")
    alert_threshold_loss: float = Field(default=1000.0, env="ALERT_THRESHOLD_LOSS")  # USD
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = AlgoTraderSettings()


def get_settings() -> AlgoTraderSettings:
    """Get the current settings instance."""
    return settings


def update_settings(**kwargs) -> AlgoTraderSettings:
    """Update settings with new values."""
    global settings
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return settings
