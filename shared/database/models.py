"""Database models for the Scizor trading system."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from .connection import Base


class SecurityType(str, Enum):
    """Security types supported by IBKR."""
    
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    BOND = "BOND"
    COMMODITY = "CMDTY"
    CFD = "CFD"
    ETF = "ETF"


class OrderStatus(str, Enum):
    """Order status values."""
    
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    PARTIALLY_FILLED = "PartiallyFilled"


class StrategyStatus(str, Enum):
    """Strategy status values."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPLOYED = "deployed"
    STOPPED = "stopped"
    ERROR = "error"


# Symbol tracking table - Simplified for manual population
class Symbol(Base):
    """Simplified symbol tracking for ASX stocks - manual population friendly."""
    
    __tablename__ = "symbols"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, unique=True, index=True)  # e.g., "CBA"
    company_name = Column(String(200), nullable=False)  # e.g., "Commonwealth Bank of Australia"
    exchange = Column(String(20), nullable=False, index=True, default="ASX")  # e.g., "ASX"
    currency = Column(String(10), nullable=False, default="AUD")  # e.g., "AUD"
    security_type = Column(SQLEnum(SecurityType), nullable=False, default=SecurityType.STOCK)
    
    # Essential Market Information
    sector = Column(String(100))  # e.g., "Financials", "Materials"
    market_cap_category = Column(String(20))  # e.g., "Large", "Mid", "Small"
    
    # IBKR Integration (optional - can be populated later via API)
    contract_id = Column(Integer, unique=True, index=True)  # IBKR conId (optional)
    local_symbol = Column(String(50))  # e.g., "CBA.AX" for IBKR
    
    # Trading Configuration
    active = Column(Boolean, default=True, index=True)
    is_asx200 = Column(Boolean, default=False, index=True)  # ASX 200 constituent
    priority = Column(Integer, default=100)  # Lower number = higher priority for data collection
    
    # Basic Market Data Settings
    min_tick = Column(Numeric(10, 6), default=0.01)  # Minimum price increment (default ASX)
    tradeable = Column(Boolean, default=True)  # Is currently tradeable
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_verified = Column(DateTime)  # Last time contract was verified with IBKR
    
    # Relationships
    market_data = relationship("MarketData", back_populates="symbol")
    trades = relationship("Trade", back_populates="symbol")
    positions = relationship("Position", back_populates="symbol")
    watchlist_entries = relationship("Watchlist", back_populates="symbol")
    
    def __repr__(self):
        return f"<Symbol(symbol='{self.symbol}', name='{self.company_name}', exchange='{self.exchange}')>"


# Market data table
class MarketData(Base):
    """Time-series market data storage."""
    
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    timeframe = Column(String(20), nullable=False, index=True)  # 1min, 5min, 1hour, 1day
    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    volume = Column(Integer, default=0)
    wap = Column(Numeric(10, 4))  # Weighted average price
    bar_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    symbol = relationship("Symbol", back_populates="market_data")


# Collection tracking
class CollectionLog(Base):
    """Track data collection jobs and status."""
    
    __tablename__ = "collection_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    collection_type = Column(String(50), nullable=False)  # historical, realtime
    timeframe = Column(String(20), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text)
    records_collected = Column(Integer, default=0)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)


# Watchlist for tracking specific symbols for intraday data
class Watchlist(Base):
    """Track symbols for enhanced data collection (5min bars, etc.)."""
    
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # watchlist name/category
    priority = Column(Integer, default=1)  # collection priority (1=highest)
    collect_5min = Column(Boolean, default=True)  # collect 5min bars
    collect_1min = Column(Boolean, default=False)  # collect 1min bars
    collect_tick = Column(Boolean, default=False)  # collect tick data
    start_date = Column(DateTime, default=func.now())  # when to start collecting
    end_date = Column(DateTime)  # when to stop (null = indefinite)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    notes = Column(Text)  # user notes about why this symbol is watched
    
    # Relationships
    symbol = relationship("Symbol", back_populates="watchlist_entries")
    
    def __repr__(self):
        return f"<Watchlist(symbol='{self.symbol.symbol}', name='{self.name}', priority={self.priority})>"


# IBKR connection monitoring
class IBKRConnection(Base):
    """Monitor IBKR API connections."""
    
    __tablename__ = "ibkr_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False)
    service_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    connection_time = Column(DateTime, default=func.now())
    disconnect_time = Column(DateTime)
    server_version = Column(String(20))
    connection_time_str = Column(String(50))
    error_message = Column(Text)


# Strategy definitions
class Strategy(Base):
    """Trading strategy definitions."""
    
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    code = Column(Text, nullable=False)  # Python strategy code
    parameters = Column(Text)  # JSON string of parameters
    created_by = Column(String(100))
    status = Column(SQLEnum(StrategyStatus), default=StrategyStatus.INACTIVE)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    backtest_jobs = relationship("BacktestJob", back_populates="strategy")
    live_strategies = relationship("LiveStrategy", back_populates="strategy")
    risk_limits = relationship("RiskLimit", back_populates="strategy")


# Backtest jobs
class BacktestJob(Base):
    """Backtest job configurations and results."""
    
    __tablename__ = "backtest_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    symbol_list = Column(Text, nullable=False)  # JSON array of symbols
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Numeric(12, 2), default=100000)
    parameters = Column(Text)  # JSON string of strategy parameters
    status = Column(String(20), default="pending")
    
    # Results
    total_return = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))
    win_rate = Column(Numeric(10, 4))
    total_trades = Column(Integer)
    profit_factor = Column(Numeric(10, 4))
    
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="backtest_jobs")
    trades = relationship("Trade", back_populates="backtest_job")


# Live strategy instances
class LiveStrategy(Base):
    """Live trading strategy instances."""
    
    __tablename__ = "live_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    account = Column(String(50), nullable=False)
    symbol_list = Column(Text, nullable=False)  # JSON array of symbols
    parameters = Column(Text)  # JSON string of parameters
    risk_limits = Column(Text)  # JSON string of risk limits
    status = Column(SQLEnum(StrategyStatus), default=StrategyStatus.INACTIVE)
    paper_trading = Column(Boolean, default=True)
    
    # Performance tracking
    pnl_realized = Column(Numeric(12, 2), default=0)
    pnl_unrealized = Column(Numeric(12, 2), default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    max_drawdown = Column(Numeric(10, 4), default=0)
    
    deployed_at = Column(DateTime)
    stopped_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    strategy = relationship("Strategy", back_populates="live_strategies")
    trades = relationship("Trade", back_populates="live_strategy")


# Trade records
class Trade(Base):
    """Trade execution records."""
    
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    backtest_job_id = Column(Integer, ForeignKey("backtest_jobs.id"), nullable=True)
    live_strategy_id = Column(Integer, ForeignKey("live_strategies.id"), nullable=True)
    
    # Order details
    order_id = Column(Integer)
    perm_id = Column(Integer)
    client_id = Column(Integer)
    exec_id = Column(String(50))
    
    # Trade details
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 4), nullable=False)
    commission = Column(Numeric(10, 4), default=0)
    realized_pnl = Column(Numeric(12, 2))
    
    # Timing
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    
    # Classification
    trade_type = Column(String(20), default="live")  # live, backtest, paper
    account = Column(String(50))
    exchange = Column(String(50))
    
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    symbol = relationship("Symbol", back_populates="trades")
    backtest_job = relationship("BacktestJob", back_populates="trades")
    live_strategy = relationship("LiveStrategy", back_populates="trades")


# Portfolio positions
class Position(Base):
    """Current portfolio positions."""
    
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    account = Column(String(50), nullable=False)
    
    # Position details
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Numeric(10, 4), nullable=False)
    current_price = Column(Numeric(10, 4))
    market_value = Column(Numeric(12, 2))
    unrealized_pnl = Column(Numeric(12, 2))
    realized_pnl = Column(Numeric(12, 2))
    
    # Timestamps
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    symbol = relationship("Symbol", back_populates="positions")


# Risk events and alerts
class RiskEvent(Base):
    """Risk management events and alerts."""
    
    __tablename__ = "risk_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)  # position_limit, loss_limit, etc.
    severity = Column(String(20), nullable=False)  # info, warning, critical
    message = Column(Text, nullable=False)
    
    # Associated entities
    live_strategy_id = Column(Integer, ForeignKey("live_strategies.id"), nullable=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=True)
    account = Column(String(50))
    
    # Event data
    current_value = Column(Numeric(12, 2))
    threshold_value = Column(Numeric(12, 2))
    action_taken = Column(String(100))
    
    # Status
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime)


class RiskLimit(Base):
    """Risk limits for strategies and positions."""
    
    __tablename__ = "risk_limits"
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    
    # Limit details
    limit_type = Column(String(50), nullable=False)  # max_position_size, max_daily_loss, etc.
    limit_value = Column(Float, nullable=False)
    current_value = Column(Float, default=0.0)
    threshold_warning = Column(Float, nullable=True)  # Warning threshold
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    strategy = relationship("Strategy", back_populates="risk_limits")
