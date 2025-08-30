from typing import Optional
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database Configuration - Individual Components (Required)
    postgres_host: str = Field(..., env="POSTGRES_HOST")
    postgres_port: int = Field(..., env="POSTGRES_PORT") 
    postgres_db: str = Field(..., env="POSTGRES_DB")
    postgres_user: str = Field(..., env="POSTGRES_USER")
    postgres_password: str = Field(..., env="POSTGRES_PASSWORD")
    
    # Database URLs - Optional explicit override, otherwise auto-constructed
    database_url_override: Optional[str] = Field(default=None, env="DATABASE_URL")
    async_database_url_override: Optional[str] = Field(default=None, env="ASYNC_DATABASE_URL")
    
    @computed_field
    @property  
    def database_url(self) -> str:
        """Sync database URL - uses override or auto-constructs from components"""
        if self.database_url_override:
            return self.database_url_override
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @computed_field
    @property
    def async_database_url(self) -> str:
        """Async database URL - uses override or auto-constructs from components""" 
        if self.async_database_url_override:
            return self.async_database_url_override
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    
    # IBKR TWS API Configuration
    ibkr_host: str = Field(..., env="IBKR_HOST")
    ibkr_port: int = Field(..., env="IBKR_PORT")
    ibkr_client_id: int = Field(..., env="IBKR_CLIENT_ID")
    ibkr_paper_port: int = Field(default=4002, env="IBKR_PAPER_PORT")
    ibkr_live_port: int = Field(default=4001, env="IBKR_LIVE_PORT")
    ibkr_paper_trading: bool = Field(default=True, env="IBKR_PAPER_TRADING")
    ibkr_debug_mode: bool = Field(default=False, env="IBKR_DEBUG_MODE")
    ibkr_connection_timeout: int = Field(default=30, env="IBKR_CONNECTION_TIMEOUT")
    ibkr_request_timeout: int = Field(default=10, env="IBKR_REQUEST_TIMEOUT")
    
    # IBKR Rate Limiting Configuration
    ibkr_general_rate_limit: int = Field(default=40, env="IBKR_GENERAL_RATE_LIMIT")
    ibkr_general_window_seconds: int = Field(default=1, env="IBKR_GENERAL_WINDOW_SECONDS")
    ibkr_historical_rate_limit: int = Field(default=60, env="IBKR_HISTORICAL_RATE_LIMIT")
    ibkr_historical_window_seconds: int = Field(default=600, env="IBKR_HISTORICAL_WINDOW_SECONDS")
    ibkr_market_data_rate_limit: int = Field(default=100, env="IBKR_MARKET_DATA_RATE_LIMIT")
    ibkr_market_data_window_seconds: int = Field(default=60, env="IBKR_MARKET_DATA_WINDOW_SECONDS")
    ibkr_identical_request_window_seconds: int = Field(default=15, env="IBKR_IDENTICAL_REQUEST_WINDOW_SECONDS")
    ibkr_rate_violation_penalty_seconds: int = Field(default=60, env="IBKR_RATE_VIOLATION_PENALTY_SECONDS")
    
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
    app_name: str = Field(default="Scizor Trading System", env="APP_NAME")
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