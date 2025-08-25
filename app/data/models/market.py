from sqlalchemy import Column, Integer, String, DECIMAL, BIGINT, Date, DateTime, Boolean, Text, Index
from sqlalchemy.sql import func
from app.config.database import Base


class DailyPrice(Base):
    """Daily OHLCV price data for ASX stocks"""
    __tablename__ = "daily_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(DECIMAL(12, 4), nullable=False)
    high = Column(DECIMAL(12, 4), nullable=False)
    low = Column(DECIMAL(12, 4), nullable=False)
    close = Column(DECIMAL(12, 4), nullable=False)
    volume = Column(BIGINT, nullable=False)
    adj_close = Column(DECIMAL(12, 4), nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_daily_prices_symbol_date', 'symbol', 'date', unique=True),
        Index('idx_daily_prices_date', 'date'),
    )


class IntradayPrice(Base):
    """Intraday OHLCV data for higher frequency strategies"""
    __tablename__ = "intraday_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False)
    datetime = Column(DateTime, nullable=False)
    open = Column(DECIMAL(12, 4), nullable=False)
    high = Column(DECIMAL(12, 4), nullable=False)
    low = Column(DECIMAL(12, 4), nullable=False)
    close = Column(DECIMAL(12, 4), nullable=False)
    volume = Column(BIGINT, nullable=False)
    timeframe = Column(String(10), nullable=False)  # '4H', '1H', '15m'
    created_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_intraday_symbol_datetime_timeframe', 'symbol', 'datetime', 'timeframe', unique=True),
        Index('idx_intraday_datetime', 'datetime'),
    )


class ApiRequest(Base):
    """API request tracking for rate limiting and monitoring"""
    __tablename__ = "api_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(String(50), nullable=False)  # MARKET_DATA, HISTORICAL_DATA, ORDER_PLACEMENT
    req_id = Column(Integer)
    symbol = Column(String(10))
    timestamp = Column(DateTime, default=func.current_timestamp())
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED, TIMEOUT, RATE_LIMITED
    error_code = Column(Integer)
    error_message = Column(Text)
    response_time_ms = Column(Integer)
    client_id = Column(Integer)
    
    __table_args__ = (
        Index('idx_api_requests_type_timestamp', 'request_type', 'timestamp'),
        Index('idx_api_requests_status_timestamp', 'status', 'timestamp'),
        Index('idx_api_requests_symbol_timestamp', 'symbol', 'timestamp'),
    )


class ConnectionState(Base):
    """Connection state management"""
    __tablename__ = "connection_state"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False, unique=True)
    status = Column(String(20), nullable=False)  # CONNECTED, DISCONNECTED, RECONNECTING, ERROR
    last_heartbeat = Column(DateTime, default=func.current_timestamp())
    error_count = Column(Integer, default=0)
    last_error_code = Column(Integer)
    last_error_message = Column(Text)
    connection_started_at = Column(DateTime)
    last_data_received_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_connection_status', 'status'),
        Index('idx_connection_last_heartbeat', 'last_heartbeat'),
    )


class RateLimit(Base):
    """Rate limiting tracking and enforcement"""
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(String(50), nullable=False)  # GENERAL, HISTORICAL, MARKET_DATA
    client_id = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False, default=1)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    limit_exceeded = Column(Boolean, default=False)
    reset_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_rate_limits_client_type_window', 'client_id', 'request_type', 'window_start'),
        Index('idx_rate_limits_window_end', 'window_end'),
    )


class ContractDetail(Base):
    """IBKR contract details cache with comprehensive IBKR API data"""
    __tablename__ = "contract_details"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core contract identification
    symbol = Column(String(10), nullable=False)
    con_id = Column(BIGINT, nullable=False, unique=True)
    sec_type = Column(String(10), nullable=False)  # STK, OPT, FUT, etc.
    currency = Column(String(10), nullable=False)
    exchange = Column(String(20), nullable=False)
    primary_exchange = Column(String(20))
    local_symbol = Column(String(20))
    trading_class = Column(String(20))
    
    # Company information
    long_name = Column(String(200))  # Full company name from IBKR
    market_name = Column(String(50))  # Market display name
    
    # Industry classification
    industry = Column(String(100))  # e.g., "Basic Materials", "Financial"
    category = Column(String(100))  # e.g., "Mining", "Banks"
    subcategory = Column(String(100))  # e.g., "Diversified Minerals", "Commercial Banks Non-US"
    
    # Trading specifications
    min_tick = Column(DECIMAL(10, 8))  # Minimum price increment
    price_magnifier = Column(Integer, default=1)  # Price magnifier for display
    md_size_multiplier = Column(Integer, default=1)  # Market data size multiplier
    
    # Market rules and trading
    market_rule_ids = Column(Text)  # JSON array of market rule IDs
    order_types = Column(Text)  # Supported order types (comma-separated)
    valid_exchanges = Column(Text)  # Valid exchanges for routing (comma-separated)
    
    # Trading hours (IBKR format: YYYYMMDD:HHMM-YYYYMMDD:HHMM;...)
    trading_hours = Column(Text)  # Regular trading hours schedule
    liquid_hours = Column(Text)  # Liquid trading hours schedule
    time_zone_id = Column(String(50))  # Exchange timezone
    
    # Security identifiers
    sec_id_list = Column(Text)  # JSON array of security IDs (ISIN, CUSIP, etc.)
    stock_type = Column(String(20))  # COMMON, PREFERRED, etc.
    cusip = Column(String(20))  # CUSIP identifier
    
    # Contract specifications (futures/options)
    contract_month = Column(String(10))  # Contract month for derivatives
    last_trading_day = Column(Date)  # Last trading day
    real_expiration_date = Column(String(10))  # Real expiration date
    last_trade_time = Column(String(20))  # Last trade time
    
    # Bond/Fixed Income fields
    bond_type = Column(String(50))  # Bond type classification
    coupon_type = Column(String(50))  # Coupon type
    coupon = Column(DECIMAL(10, 4))  # Coupon rate
    callable = Column(Boolean, default=False)  # Callable bond flag
    putable = Column(Boolean, default=False)  # Putable bond flag
    convertible = Column(Boolean, default=False)  # Convertible security flag
    maturity = Column(String(20))  # Maturity date
    issue_date = Column(String(20))  # Issue date
    ratings = Column(String(100))  # Credit ratings
    
    # Options fields
    next_option_date = Column(String(20))  # Next option date
    next_option_type = Column(String(20))  # Next option type
    next_option_partial = Column(Boolean, default=False)  # Partial option flag
    
    # Underlying contract (for derivatives)
    under_con_id = Column(BIGINT)  # Underlying contract ID
    under_symbol = Column(String(20))  # Underlying symbol
    under_sec_type = Column(String(10))  # Underlying security type
    
    # Additional metadata
    agg_group = Column(Integer)  # Aggregation group
    ev_rule = Column(Text)  # Economic value rule
    ev_multiplier = Column(DECIMAL(10, 4))  # Economic value multiplier
    desc_append = Column(Text)  # Description appendix
    notes = Column(Text)  # Additional notes
    
    # System fields
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_contracts_symbol_exchange', 'symbol', 'exchange'),
        Index('idx_contracts_long_name', 'long_name'),
        Index('idx_contracts_industry_category', 'industry', 'category'),
        Index('idx_contracts_stock_type', 'stock_type'),
        Index('idx_contracts_trading_hours', 'time_zone_id'),
        Index('idx_contracts_updated_at', 'updated_at'),
        Index('idx_contracts_under_con_id', 'under_con_id'),
        Index('idx_contracts_sec_type_currency', 'sec_type', 'currency'),
    )


class MarketDataSubscription(Base):
    """Market data subscriptions tracking"""
    __tablename__ = "market_data_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    req_id = Column(Integer, nullable=False, unique=True)
    symbol = Column(String(10), nullable=False)
    con_id = Column(BIGINT)
    subscription_type = Column(String(20), nullable=False)  # LIVE, DELAYED, SNAPSHOT
    generic_tick_list = Column(String(100))
    status = Column(String(20), nullable=False)  # ACTIVE, CANCELLED, ERROR
    subscribed_at = Column(DateTime, default=func.current_timestamp())
    cancelled_at = Column(DateTime)
    last_update_at = Column(DateTime)
    error_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_subscriptions_symbol_status', 'symbol', 'status'),
        Index('idx_subscriptions_subscribed_at', 'subscribed_at'),
    )