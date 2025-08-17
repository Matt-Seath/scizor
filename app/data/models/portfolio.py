from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.config.database import Base


class Position(Base):
    """Portfolio positions"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False)
    strategy = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # LONG, SHORT
    entry_price = Column(DECIMAL(12, 4), nullable=False)
    current_price = Column(DECIMAL(12, 4))
    quantity = Column(Integer, nullable=False)
    stop_loss = Column(DECIMAL(12, 4))
    take_profit = Column(DECIMAL(12, 4))
    unrealized_pnl = Column(DECIMAL(12, 4))
    realized_pnl = Column(DECIMAL(12, 4), default=0)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    status = Column(String(20), default='OPEN')  # OPEN, CLOSED, PARTIAL
    position_metadata = Column(JSONB)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_positions_symbol_status', 'symbol', 'status'),
        Index('idx_positions_strategy_status', 'strategy', 'status'),
        Index('idx_positions_opened_at', 'opened_at'),
    )


class Order(Base):
    """Order tracking"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey('positions.id'))
    signal_id = Column(Integer, ForeignKey('signals.id'))
    symbol = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)  # MARKET, LIMIT, STOP, STOP_LIMIT
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(12, 4))
    stop_price = Column(DECIMAL(12, 4))
    filled_quantity = Column(Integer, default=0)
    avg_fill_price = Column(DECIMAL(12, 4))
    commission = Column(DECIMAL(8, 4), default=0)
    status = Column(String(20), default='PENDING')  # PENDING, FILLED, PARTIAL, CANCELLED, REJECTED
    broker_order_id = Column(String(50))
    submitted_at = Column(DateTime, default=func.current_timestamp())
    filled_at = Column(DateTime)
    order_metadata = Column(JSONB)
    
    __table_args__ = (
        Index('idx_orders_symbol_status', 'symbol', 'status'),
        Index('idx_orders_broker_order_id', 'broker_order_id'),
        Index('idx_orders_submitted_at', 'submitted_at'),
    )


class RiskMetric(Base):
    """Risk metrics tracking"""
    __tablename__ = "risk_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, unique=True)
    total_exposure = Column(DECIMAL(12, 4), nullable=False)
    portfolio_value = Column(DECIMAL(12, 4), nullable=False)
    daily_pnl = Column(DECIMAL(12, 4), nullable=False)
    drawdown = Column(DECIMAL(8, 4), nullable=False)
    var_95 = Column(DECIMAL(12, 4))  # Value at Risk 95%
    sharpe_ratio = Column(DECIMAL(8, 4))
    max_positions = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_risk_metrics_date', 'date'),
    )


class PerformanceMetric(Base):
    """System performance metrics"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(DECIMAL(12, 4), nullable=False)
    metric_metadata = Column(JSONB)
    timestamp = Column(DateTime, default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_performance_metric_timestamp', 'metric_name', 'timestamp'),
    )