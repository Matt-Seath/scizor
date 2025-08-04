"""
Data providers for market data.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd


class DataProvider(ABC):
    """Abstract base class for data providers."""
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Get historical market data."""
        pass
    
    @abstractmethod
    async def get_latest_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Get latest market data for multiple symbols."""
        pass
    
    @abstractmethod
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol."""
        pass


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance data provider using yfinance."""
    
    def __init__(self, cache_duration: int = 3600):
        self.cache_duration = cache_duration
        self._cache = {}
        self._cache_timestamps = {}
        
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Get historical data from Yahoo Finance."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True
            )
            
            if data.empty:
                raise ValueError(f"No data found for symbol {symbol}")
                
            return data
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch data for {symbol}: {e}")
    
    async def get_latest_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Get latest data for multiple symbols."""
        result = {}
        
        for symbol in symbols:
            # Check cache first
            if self._is_cached(symbol):
                result[symbol] = self._cache[symbol]
                continue
                
            try:
                # Get last 30 days of data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                
                data = await self.get_historical_data(symbol, start_date, end_date)
                
                # Update cache
                self._cache[symbol] = data
                self._cache_timestamps[symbol] = datetime.now()
                
                result[symbol] = data
                
            except Exception as e:
                print(f"Warning: Failed to get data for {symbol}: {e}")
                continue
                
        return result
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price is None:
                # Fallback to historical data
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    
            return float(price) if price is not None else None
            
        except Exception:
            return None
    
    def _is_cached(self, symbol: str) -> bool:
        """Check if symbol data is cached and still valid."""
        if symbol not in self._cache or symbol not in self._cache_timestamps:
            return False
            
        cache_age = datetime.now() - self._cache_timestamps[symbol]
        return cache_age.total_seconds() < self.cache_duration


class MockDataProvider(DataProvider):
    """Mock data provider for testing."""
    
    def __init__(self):
        self._mock_prices = {
            'AAPL': 150.0,
            'GOOGL': 2500.0,
            'MSFT': 300.0,
            'TSLA': 800.0
        }
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Generate mock historical data."""
        import numpy as np
        
        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate mock OHLCV data
        base_price = self._mock_prices.get(symbol, 100.0)
        
        # Random walk for prices
        np.random.seed(hash(symbol) % 2**32)  # Consistent seed per symbol
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices = [base_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        # Create OHLCV data
        data = pd.DataFrame({
            'Open': [p * np.random.uniform(0.98, 1.02) for p in prices],
            'High': [p * np.random.uniform(1.00, 1.05) for p in prices],
            'Low': [p * np.random.uniform(0.95, 1.00) for p in prices],
            'Close': prices,
            'Volume': [np.random.randint(1000000, 10000000) for _ in prices]
        }, index=dates)
        
        return data
    
    async def get_latest_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Get mock latest data."""
        result = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        for symbol in symbols:
            result[symbol] = await self.get_historical_data(symbol, start_date, end_date)
            
        return result
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get mock latest price."""
        return self._mock_prices.get(symbol)
