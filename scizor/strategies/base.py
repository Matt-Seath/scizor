"""
Base strategy class for implementing trading strategies.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from scizor.data.providers import DataProvider
from scizor.portfolio.manager import PortfolioManager


class Signal:
    """Represents a trading signal."""
    
    def __init__(
        self,
        symbol: str,
        action: str,  # 'buy', 'sell', 'hold'
        quantity: float = 0,
        price: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.action = action
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp or datetime.now()
        self.confidence = confidence
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'price': self.price,
            'timestamp': self.timestamp,
            'confidence': self.confidence,
            'metadata': self.metadata
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.parameters = parameters or {}
        self.data_provider = None
        self.portfolio_manager = None
        self._indicators = {}
        
    def set_data_provider(self, data_provider: DataProvider):
        """Set the data provider for the strategy."""
        self.data_provider = data_provider
        
    def set_portfolio_manager(self, portfolio_manager: PortfolioManager):
        """Set the portfolio manager for the strategy."""
        self.portfolio_manager = portfolio_manager
    
    @abstractmethod
    def get_required_symbols(self) -> List[str]:
        """
        Return list of symbols required by this strategy.
        
        Returns:
            List of symbol strings
        """
        pass
    
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate technical indicators from market data.
        
        Args:
            data: Market data DataFrame with OHLCV columns
            
        Returns:
            Dictionary of calculated indicators
        """
        pass
    
    @abstractmethod
    def generate_signals(
        self, 
        market_data: Dict[str, pd.DataFrame], 
        current_time: datetime
    ) -> List[Signal]:
        """
        Generate trading signals based on market data and indicators.
        
        Args:
            market_data: Dictionary mapping symbols to DataFrames
            current_time: Current timestamp
            
        Returns:
            List of trading signals
        """
        pass
    
    def get_position_size(self, symbol: str, signal_strength: float = 1.0) -> float:
        """
        Calculate position size based on risk management rules.
        
        Args:
            symbol: Trading symbol
            signal_strength: Strength of the signal (0-1)
            
        Returns:
            Position size as number of shares
        """
        if not self.portfolio_manager:
            return 0
            
        # Get current portfolio value
        portfolio_value = self.portfolio_manager.get_total_value()
        
        # Get maximum position size from risk settings
        max_position_value = portfolio_value * 0.1  # Default 10%
        
        # Get current price for the symbol
        current_price = self._get_current_price(symbol)
        if current_price is None:
            return 0
            
        # Calculate base position size
        base_shares = max_position_value / current_price
        
        # Adjust by signal strength
        adjusted_shares = base_shares * signal_strength
        
        return int(adjusted_shares)
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        if not self.data_provider:
            return None
            
        try:
            latest_data = self.data_provider.get_latest_price(symbol)
            return latest_data
        except Exception:
            return None
    
    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate a trading signal before execution.
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            True if signal is valid, False otherwise
        """
        # Basic validation
        if signal.action not in ['buy', 'sell', 'hold']:
            return False
            
        if signal.action != 'hold' and signal.quantity <= 0:
            return False
            
        # Check portfolio constraints
        if self.portfolio_manager and signal.action == 'buy':
            current_position = self.portfolio_manager.get_position(signal.symbol)
            max_position_value = self.portfolio_manager.get_total_value() * 0.1
            signal_value = signal.quantity * (signal.price or self._get_current_price(signal.symbol) or 0)
            
            if current_position.value + signal_value > max_position_value:
                return False
                
        return True
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get information about the strategy."""
        return {
            'name': self.name,
            'parameters': self.parameters,
            'required_symbols': self.get_required_symbols(),
            'indicators': list(self._indicators.keys())
        }
