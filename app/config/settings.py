from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    async_database_url: str = Field(..., env="ASYNC_DATABASE_URL")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    
    # IBKR TWS API Configuration
    ibkr_host: str = Field(default="127.0.0.1", env="IBKR_HOST")
    ibkr_port: int = Field(default=7497, env="IBKR_PORT")
    ibkr_client_id: int = Field(default=1, env="IBKR_CLIENT_ID")
    ibkr_paper_port: int = Field(default=7496, env="IBKR_PAPER_PORT")
    
    # Trading Configuration
    max_positions: int = Field(default=5, env="MAX_POSITIONS")
    max_risk_per_trade: float = Field(default=0.02, env="MAX_RISK_PER_TRADE")
    daily_loss_limit: float = Field(default=0.03, env="DAILY_LOSS_LIMIT")
    max_portfolio_allocation: float = Field(default=0.20, env="MAX_PORTFOLIO_ALLOCATION")
    position_sizing_method: str = Field(default="kelly_fraction", env="POSITION_SIZING_METHOD")
    
    # API Security
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Application Settings
    app_name: str = Field(default="ASX200 Trading System", env="APP_NAME")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    
    # Market Data Configuration
    default_market_data_type: int = Field(default=3, env="DEFAULT_MARKET_DATA_TYPE")
    enable_live_data: bool = Field(default=False, env="ENABLE_LIVE_DATA")
    data_collection_delay_minutes: int = Field(default=10, env="DATA_COLLECTION_DELAY_MINUTES")
    
    # Risk Management
    enable_risk_controls: bool = Field(default=True, env="ENABLE_RISK_CONTROLS")
    max_drawdown_limit: float = Field(default=0.15, env="MAX_DRAWDOWN_LIMIT")
    correlation_limit: float = Field(default=0.70, env="CORRELATION_LIMIT")
    var_confidence_level: float = Field(default=0.95, env="VAR_CONFIDENCE_LEVEL")
    
    # Monitoring
    prometheus_port: int = Field(default=8001, env="PROMETHEUS_PORT")
    health_check_interval: int = Field(default=60, env="HEALTH_CHECK_INTERVAL")
    
    # Timezone
    default_timezone: str = Field(default="Australia/Sydney", env="DEFAULT_TIMEZONE")
    
    # Development
    testing: bool = Field(default=False, env="TESTING")
    mock_ibkr_api: bool = Field(default=False, env="MOCK_IBKR_API")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()