"""
Moving Average Crossover Strategy
"""

from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from scizor.strategies.base import BaseStrategy, Signal


class MovingAverageCrossover(BaseStrategy):
    """
    Simple moving average crossover strategy.
    
    Generates buy signals when short MA crosses above long MA,
    and sell signals when short MA crosses below long MA.
    """
    
    def __init__(self, short_window: int = 10, long_window: int = 20, symbols: List[str] = None):
        parameters = {
            'short_window': short_window,
            'long_window': long_window,
            'symbols': symbols or ['AAPL']
        }
        super().__init__("MovingAverageCrossover", parameters)
        
        self.short_window = short_window
        self.long_window = long_window
        self.symbols = symbols or ['AAPL']
        
    def get_required_symbols(self) -> List[str]:
        """Return symbols required by this strategy."""
        return self.symbols
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate moving averages."""
        indicators = {}
        
        # Calculate short and long moving averages
        indicators['short_ma'] = data['Close'].rolling(window=self.short_window).mean()
        indicators['long_ma'] = data['Close'].rolling(window=self.long_window).mean()
        
        # Calculate crossover signals
        indicators['signal'] = np.where(
            indicators['short_ma'] > indicators['long_ma'], 1, 0
        )
        indicators['positions'] = indicators['signal'].diff()
        
        return indicators
    
    def generate_signals(
        self, 
        market_data: Dict[str, pd.DataFrame], 
        current_time: datetime
    ) -> List[Signal]:
        """Generate trading signals based on MA crossover."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in market_data:
                continue
                
            data = market_data[symbol]
            if len(data) < self.long_window:
                continue
                
            # Calculate indicators
            indicators = self.calculate_indicators(data)
            
            # Get the latest position change
            latest_position = indicators['positions'].iloc[-1]
            current_price = data['Close'].iloc[-1]
            
            # Generate signal based on position change
            if latest_position == 1:  # Buy signal
                quantity = self.get_position_size(symbol)
                if quantity > 0:
                    signal = Signal(
                        symbol=symbol,
                        action='buy',
                        quantity=quantity,
                        price=current_price,
                        timestamp=current_time,
                        confidence=self._calculate_confidence(indicators),
                        metadata={
                            'short_ma': indicators['short_ma'].iloc[-1],
                            'long_ma': indicators['long_ma'].iloc[-1],
                            'strategy': 'MovingAverageCrossover'
                        }
                    )
                    signals.append(signal)
                    
            elif latest_position == -1:  # Sell signal
                if self.portfolio_manager:
                    current_position = self.portfolio_manager.get_position(symbol)
                    if current_position.quantity > 0:
                        signal = Signal(
                            symbol=symbol,
                            action='sell',
                            quantity=current_position.quantity,
                            price=current_price,
                            timestamp=current_time,
                            confidence=self._calculate_confidence(indicators),
                            metadata={
                                'short_ma': indicators['short_ma'].iloc[-1],
                                'long_ma': indicators['long_ma'].iloc[-1],
                                'strategy': 'MovingAverageCrossover'
                            }
                        )
                        signals.append(signal)
        
        return signals
    
    def _calculate_confidence(self, indicators: Dict[str, Any]) -> float:
        """
        Calculate confidence score for the signal.
        
        Higher confidence when MAs are further apart.
        """
        short_ma = indicators['short_ma'].iloc[-1]
        long_ma = indicators['long_ma'].iloc[-1]
        
        if pd.isna(short_ma) or pd.isna(long_ma):
            return 0.5
            
        # Calculate percentage difference
        pct_diff = abs(short_ma - long_ma) / long_ma
        
        # Map to confidence score (0.5 to 1.0)
        confidence = min(0.5 + pct_diff * 10, 1.0)
        
        return confidence
