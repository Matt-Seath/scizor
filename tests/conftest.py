import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import asyncio

from app.main import app
from app.config.database import Base, get_async_db
from app.config.settings import settings
from app.data.collectors.asx_contracts import get_liquid_stocks


# Test database configuration
TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Test engines
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
test_async_engine = create_async_engine(TEST_ASYNC_DATABASE_URL, connect_args={"check_same_thread": False})

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
AsyncTestSessionLocal = async_sessionmaker(bind=test_async_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session():
    """Create a test database session."""
    # Create tables
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with AsyncTestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
    
    # Drop tables after test
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    """Create a test client for FastAPI app."""
    def override_get_db():
        try:
            db = TestSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_async_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_price_data():
    """Generate sample OHLCV price data for testing."""
    np.random.seed(42)  # For reproducible tests
    
    # Generate 100 days of data
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    # Generate realistic price data
    start_price = 50.0
    daily_returns = np.random.normal(0.001, 0.02, 100)  # 0.1% daily return, 2% volatility
    
    prices = [start_price]
    for return_val in daily_returns[1:]:
        new_price = prices[-1] * (1 + return_val)
        prices.append(max(new_price, 1.0))  # Minimum $1
    
    # Generate OHLC
    opens = prices[:-1]
    closes = prices[1:]
    
    highs = []
    lows = []
    volumes = []
    
    for i in range(len(closes)):
        open_price = opens[i]
        close_price = closes[i]
        
        # Generate high/low with some spread
        daily_range = abs(close_price - open_price) + np.random.uniform(0.01, 0.1)
        high = max(open_price, close_price) + np.random.uniform(0, daily_range * 0.3)
        low = min(open_price, close_price) - np.random.uniform(0, daily_range * 0.3)
        
        highs.append(high)
        lows.append(max(low, 1.0))  # Minimum $1
        volumes.append(np.random.randint(100000, 1000000))
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    }, index=dates[:len(closes)])
    
    return df


@pytest.fixture
def multiple_stock_data(sample_price_data):
    """Generate price data for multiple stocks."""
    symbols = ['BHP', 'CBA', 'CSL', 'ANZ', 'WBC']
    data = {}
    
    for i, symbol in enumerate(symbols):
        # Slightly modify the data for each stock
        df = sample_price_data.copy()
        multiplier = 0.8 + (i * 0.1)  # Different price levels
        
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col] * multiplier
        
        data[symbol] = df
    
    return data


@pytest.fixture
def sample_signals():
    """Generate sample trading signals for testing."""
    from app.strategies.base import StrategySignal
    
    signals = []
    base_date = datetime(2023, 6, 15)
    
    # Buy signal
    signals.append(StrategySignal(
        symbol='BHP',
        signal_type='BUY',
        price=45.50,
        confidence=0.75,
        strategy_name='momentum',
        generated_at=base_date,
        stop_loss=43.00,
        take_profit=50.00,
        metadata={'volume_ratio': 1.8, 'rsi': 65}
    ))
    
    # Sell signal
    signals.append(StrategySignal(
        symbol='CBA',
        signal_type='SELL',
        price=102.30,
        confidence=0.85,
        strategy_name='mean_reversion',
        generated_at=base_date + timedelta(days=1),
        metadata={'rsi': 75, 'bb_position': 0.95}
    ))
    
    return signals


@pytest.fixture
def mock_ibkr_client():
    """Mock IBKR client for testing."""
    class MockIBKRClient:
        def __init__(self):
            self.is_connected = True
            self.next_valid_order_id = 1000
            self.market_data_callbacks = {}
            self.historical_data_callbacks = {}
            self.request_counter = 1000
        
        def connect_to_tws(self):
            return True
        
        def disconnect_from_tws(self):
            self.is_connected = False
        
        def get_next_request_id(self):
            self.request_counter += 1
            return self.request_counter
        
        def request_market_data(self, contract, callback):
            req_id = self.get_next_request_id()
            self.market_data_callbacks[req_id] = callback
            return req_id
        
        def request_historical_data(self, contract, duration, bar_size, callback):
            req_id = self.get_next_request_id()
            self.historical_data_callbacks[req_id] = callback
            return req_id
        
        def get_connection_status(self):
            return {
                'connected': self.is_connected,
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 1,
                'retry_count': 0,
                'pending_requests': len(self.market_data_callbacks),
                'rate_limiter_tokens': 40,
                'historical_limiter_tokens': 48
            }
    
    return MockIBKRClient()


@pytest.fixture
def backtest_config():
    """Sample backtest configuration."""
    from app.backtest.engine import BacktestConfig
    
    return BacktestConfig(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=100000.0,
        commission_per_share=0.002,
        slippage_bps=5.0,
        max_positions=5,
        position_sizing_method="equal_weight",
        risk_per_trade=0.02
    )


@pytest.fixture
def momentum_strategy():
    """Create momentum strategy for testing."""
    from app.strategies.momentum import MomentumBreakoutStrategy, MomentumBreakoutParameters
    
    params = MomentumBreakoutParameters(
        max_positions=3,
        risk_per_trade=0.02,
        min_confidence=0.7,
        lookback_period=20,
        volume_multiplier=1.5
    )
    
    return MomentumBreakoutStrategy(params)


@pytest.fixture
def mean_reversion_strategy():
    """Create mean reversion strategy for testing."""
    from app.strategies.mean_reversion import MeanReversionStrategy, MeanReversionParameters
    
    params = MeanReversionParameters(
        max_positions=4,
        risk_per_trade=0.015,
        min_confidence=0.6,
        rsi_oversold=30,
        bollinger_std=2.0
    )
    
    return MeanReversionStrategy(params)


# Test data constants
TEST_SYMBOLS = ['BHP', 'CBA', 'CSL', 'ANZ', 'WBC']
TEST_DATE_RANGE = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')


# Helper functions for tests
def create_test_trade_data(num_trades: int = 10):
    """Create sample trade data for testing."""
    from app.backtest.engine import BacktestTrade
    
    trades = []
    base_date = datetime(2023, 6, 1)
    
    for i in range(num_trades):
        trade = BacktestTrade(
            symbol=f'TEST{i % 3}',
            strategy='test_strategy',
            side='LONG',
            entry_date=base_date + timedelta(days=i*2),
            exit_date=base_date + timedelta(days=i*2 + 5),
            entry_price=50.0 + i,
            exit_price=50.0 + i + np.random.uniform(-2, 3),
            quantity=100,
            commission=0.20,
            pnl=np.random.uniform(-200, 400),
            return_pct=np.random.uniform(-4, 8),
            holding_days=5,
            exit_reason='signal' if i % 2 == 0 else 'stop_loss'
        )
        trades.append(trade)
    
    return trades


def assert_dataframe_has_indicators(df: pd.DataFrame, required_indicators: List[str]):
    """Assert that DataFrame contains required technical indicators."""
    for indicator in required_indicators:
        assert indicator in df.columns, f"Missing indicator: {indicator}"
        assert not df[indicator].isna().all(), f"Indicator {indicator} has all NaN values"


def assert_signal_is_valid(signal):
    """Assert that a trading signal is valid."""
    from app.strategies.base import StrategyValidator
    
    assert StrategyValidator.validate_signal(signal), "Signal validation failed"
    assert signal.symbol is not None, "Signal missing symbol"
    assert signal.price > 0, "Signal price must be positive"
    assert 0 <= signal.confidence <= 1, "Signal confidence must be between 0 and 1"