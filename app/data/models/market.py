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
    """IBKR contract details cache"""
    __tablename__ = "contract_details"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False)
    con_id = Column(BIGINT, nullable=False, unique=True)
    sec_type = Column(String(10), nullable=False)  # STK, OPT, FUT, etc.
    currency = Column(String(10), nullable=False)
    exchange = Column(String(20), nullable=False)
    primary_exchange = Column(String(20))
    local_symbol = Column(String(20))
    trading_class = Column(String(20))
    min_tick = Column(DECIMAL(10, 8))
    market_rule_ids = Column(Text)  # JSON array of market rule IDs
    contract_month = Column(String(10))
    last_trading_day = Column(Date)
    time_zone_id = Column(String(50))
    updated_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_contracts_symbol_exchange', 'symbol', 'exchange'),
        Index('idx_contracts_updated_at', 'updated_at'),
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