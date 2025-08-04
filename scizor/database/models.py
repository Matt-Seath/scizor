"""
Database models for stock market data.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Index, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class StockData(Base):
    """Stock OHLCV data model."""
    
    __tablename__ = 'stock_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    adjusted_close = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_symbol_date', 'symbol', 'date'),
    )
    
    def __repr__(self):
        return f"<StockData(symbol='{self.symbol}', date='{self.date}', close={self.close})>"


class Symbol(Base):
    """Symbol metadata and info."""
    
    __tablename__ = 'symbols'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100))
    sector = Column(String(50))
    industry = Column(String(100))
    market_cap = Column(Float)
    exchange = Column(String(20))
    currency = Column(String(3), default='USD')
    
    # Status tracking
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Symbol(symbol='{self.symbol}', name='{self.name}')>"


class DataUpdateLog(Base):
    """Log of data update operations."""
    
    __tablename__ = 'data_update_log'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    update_type = Column(String(20), nullable=False)  # 'historical', 'realtime', 'backfill'
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    records_processed = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    status = Column(String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    error_message = Column(Text)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    def __repr__(self):
        return f"<DataUpdateLog(symbol='{self.symbol}', type='{self.update_type}', status='{self.status}')>"


class TechnicalIndicator(Base):
    """Pre-calculated technical indicators."""
    
    __tablename__ = 'technical_indicators'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    indicator_name = Column(String(50), nullable=False, index=True)
    indicator_value = Column(Float, nullable=False)
    
    # Parameters used for calculation
    parameters = Column(Text)  # JSON string of parameters
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_symbol_date_indicator', 'symbol', 'date', 'indicator_name'),
    )
    
    def __repr__(self):
        return f"<TechnicalIndicator(symbol='{self.symbol}', indicator='{self.indicator_name}', value={self.indicator_value})>"


class MarketCalendar(Base):
    """Market trading calendar."""
    
    __tablename__ = 'market_calendar'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True, nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default='NYSE')
    is_trading_day = Column(Boolean, nullable=False)
    market_open = Column(DateTime)
    market_close = Column(DateTime)
    early_close = Column(Boolean, default=False)
    holiday_name = Column(String(100))
    
    def __repr__(self):
        return f"<MarketCalendar(date='{self.date}', trading_day={self.is_trading_day})>"


def create_database(database_url: str = "sqlite:///scizor_data.db"):
    """Create database tables."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(database_url: str = "sqlite:///scizor_data.db"):
    """Get database session."""
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == "__main__":
    # Create database with default SQLite
    engine = create_database()
    print("Database tables created successfully!")
    
    # Create a test session
    session = get_session()
    
    # Add some sample symbols
    symbols = [
        Symbol(symbol='AAPL', name='Apple Inc.', sector='Technology', exchange='NASDAQ'),
        Symbol(symbol='GOOGL', name='Alphabet Inc.', sector='Technology', exchange='NASDAQ'),
        Symbol(symbol='MSFT', name='Microsoft Corporation', sector='Technology', exchange='NASDAQ'),
        Symbol(symbol='TSLA', name='Tesla, Inc.', sector='Automotive', exchange='NASDAQ'),
        Symbol(symbol='SPY', name='SPDR S&P 500 ETF Trust', sector='ETF', exchange='NYSE'),
    ]
    
    for symbol in symbols:
        existing = session.query(Symbol).filter_by(symbol=symbol.symbol).first()
        if not existing:
            session.add(symbol)
    
    session.commit()
    session.close()
    
    print("Sample symbols added to database!")
