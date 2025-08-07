"""
Example strategies for demonstration and testing.

This module contains simple example strategies to showcase the backtesting framework.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import pandas as pd

from ...shared.strategy.base import BaseStrategy, StrategySignal, StrategyConfig, SignalType, OrderType
from ...shared.strategy.indicators import TechnicalIndicators


logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Simple moving average crossover strategy.
    
    Generates buy signals when short MA crosses above long MA,
    and sell signals when short MA crosses below long MA.
    """
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.short_window = config.parameters.get('short_window', 20)
        self.long_window = config.parameters.get('long_window', 50)
        self.position_size_pct = config.parameters.get('position_size_pct', 0.1)
        
        # Track moving averages
        self.ma_short: Dict[str, float] = {}
        self.ma_long: Dict[str, float] = {}
        self.previous_ma_short: Dict[str, float] = {}
        self.previous_ma_long: Dict[str, float] = {}
        
    def initialize(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """Initialize the strategy."""
        super().initialize(symbols, start_date, end_date)
        
        # Initialize tracking dictionaries
        for symbol in symbols:
            self.ma_short[symbol] = 0.0
            self.ma_long[symbol] = 0.0
            self.previous_ma_short[symbol] = 0.0
            self.previous_ma_long[symbol] = 0.0
        
        logger.info(f"Initialized MA Crossover strategy with {self.short_window}/{self.long_window} windows")
    
    def generate_signals(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                        portfolio_state: Dict) -> List[StrategySignal]:
        """Generate trading signals based on moving average crossover."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in data or data[symbol].empty:
                continue
            
            df = data[symbol]
            
            # Need enough data for long MA
            if len(df) < self.long_window:
                continue
            
            # Calculate moving averages
            short_ma = TechnicalIndicators.sma(df['close'], self.short_window)
            long_ma = TechnicalIndicators.sma(df['close'], self.long_window)
            
            if short_ma.empty or long_ma.empty:
                continue
            
            current_short = short_ma.iloc[-1]
            current_long = long_ma.iloc[-1]
            
            # Store previous values
            self.previous_ma_short[symbol] = self.ma_short[symbol]
            self.previous_ma_long[symbol] = self.ma_long[symbol]
            
            # Update current values
            self.ma_short[symbol] = current_short
            self.ma_long[symbol] = current_long
            
            # Check for crossover
            current_price = df['close'].iloc[-1]
            
            # Bullish crossover: short MA crosses above long MA
            if (self.previous_ma_short[symbol] <= self.previous_ma_long[symbol] and 
                current_short > current_long and
                symbol not in [pos['symbol'] for pos in portfolio_state.get('positions', {}).keys()]):
                
                # Calculate position size
                portfolio_value = portfolio_state.get('total_value', 100000)
                position_value = portfolio_value * self.position_size_pct
                quantity = int(position_value / current_price)
                
                if quantity > 0:
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=Decimal(str(current_price)),
                        quantity=quantity,
                        timestamp=timestamp,
                        confidence=0.7,
                        order_type=OrderType.MARKET,
                        reason=f"MA crossover: {current_short:.2f} > {current_long:.2f}"
                    )
                    signals.append(signal)
                    logger.debug(f"Generated BUY signal for {symbol}: {signal.reason}")
            
            # Bearish crossover: short MA crosses below long MA
            elif (self.previous_ma_short[symbol] >= self.previous_ma_long[symbol] and 
                  current_short < current_long and
                  symbol in [pos for pos in portfolio_state.get('positions', {}).keys()]):
                
                # Sell entire position
                position_qty = portfolio_state['positions'][symbol].get('quantity', 0)
                
                if position_qty > 0:
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=Decimal(str(current_price)),
                        quantity=position_qty,
                        timestamp=timestamp,
                        confidence=0.7,
                        order_type=OrderType.MARKET,
                        reason=f"MA crossover: {current_short:.2f} < {current_long:.2f}"
                    )
                    signals.append(signal)
                    logger.debug(f"Generated SELL signal for {symbol}: {signal.reason}")
        
        return signals
    
    def update_state(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                    portfolio_state: Dict):
        """Update strategy state."""
        super().update_state(data, timestamp, portfolio_state)
        
        # Update metrics
        total_positions = len(portfolio_state.get('positions', {}))
        self.metrics.signals_generated += len(self.generate_signals(data, timestamp, portfolio_state))
        self.metrics.custom_metrics['total_positions'] = total_positions
        self.metrics.custom_metrics['short_window'] = self.short_window
        self.metrics.custom_metrics['long_window'] = self.long_window


class MeanReversionStrategy(BaseStrategy):
    """
    Simple mean reversion strategy using RSI.
    
    Buys when RSI is oversold (< 30) and sells when RSI is overbought (> 70).
    """
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.rsi_period = config.parameters.get('rsi_period', 14)
        self.oversold_threshold = config.parameters.get('oversold_threshold', 30)
        self.overbought_threshold = config.parameters.get('overbought_threshold', 70)
        self.position_size_pct = config.parameters.get('position_size_pct', 0.05)
        
        # Track RSI values
        self.rsi_values: Dict[str, float] = {}
    
    def initialize(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """Initialize the strategy."""
        super().initialize(symbols, start_date, end_date)
        
        # Initialize tracking dictionaries
        for symbol in symbols:
            self.rsi_values[symbol] = 50.0  # Neutral RSI
        
        logger.info(f"Initialized Mean Reversion strategy with RSI period {self.rsi_period}")
    
    def generate_signals(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                        portfolio_state: Dict) -> List[StrategySignal]:
        """Generate trading signals based on RSI mean reversion."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in data or data[symbol].empty:
                continue
            
            df = data[symbol]
            
            # Need enough data for RSI calculation
            if len(df) < self.rsi_period + 1:
                continue
            
            # Calculate RSI
            rsi_series = TechnicalIndicators.rsi(df['close'], self.rsi_period)
            
            if rsi_series.empty:
                continue
            
            current_rsi = rsi_series.iloc[-1]
            self.rsi_values[symbol] = current_rsi
            
            current_price = df['close'].iloc[-1]
            
            # Oversold condition - generate buy signal
            if (current_rsi < self.oversold_threshold and
                symbol not in [pos for pos in portfolio_state.get('positions', {}).keys()]):
                
                # Calculate position size
                portfolio_value = portfolio_state.get('total_value', 100000)
                position_value = portfolio_value * self.position_size_pct
                quantity = int(position_value / current_price)
                
                if quantity > 0:
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=Decimal(str(current_price)),
                        quantity=quantity,
                        timestamp=timestamp,
                        confidence=0.6,
                        order_type=OrderType.MARKET,
                        reason=f"RSI oversold: {current_rsi:.2f} < {self.oversold_threshold}"
                    )
                    signals.append(signal)
                    logger.debug(f"Generated BUY signal for {symbol}: {signal.reason}")
            
            # Overbought condition - generate sell signal
            elif (current_rsi > self.overbought_threshold and
                  symbol in [pos for pos in portfolio_state.get('positions', {}).keys()]):
                
                # Sell entire position
                position_qty = portfolio_state['positions'][symbol].get('quantity', 0)
                
                if position_qty > 0:
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=Decimal(str(current_price)),
                        quantity=position_qty,
                        timestamp=timestamp,
                        confidence=0.6,
                        order_type=OrderType.MARKET,
                        reason=f"RSI overbought: {current_rsi:.2f} > {self.overbought_threshold}"
                    )
                    signals.append(signal)
                    logger.debug(f"Generated SELL signal for {symbol}: {signal.reason}")
        
        return signals
    
    def update_state(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                    portfolio_state: Dict):
        """Update strategy state."""
        super().update_state(data, timestamp, portfolio_state)
        
        # Update metrics
        avg_rsi = sum(self.rsi_values.values()) / len(self.rsi_values) if self.rsi_values else 50
        self.metrics.custom_metrics['avg_rsi'] = avg_rsi
        self.metrics.custom_metrics['rsi_period'] = self.rsi_period
        self.metrics.custom_metrics['oversold_threshold'] = self.oversold_threshold
        self.metrics.custom_metrics['overbought_threshold'] = self.overbought_threshold


class BuyAndHoldStrategy(BaseStrategy):
    """
    Simple buy and hold strategy for benchmarking.
    
    Buys equal amounts of all symbols at the beginning and holds until the end.
    """
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.initial_buy_done = False
        self.allocation_per_symbol = config.parameters.get('allocation_per_symbol', 0.9)  # 90% of capital
    
    def initialize(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """Initialize the strategy."""
        super().initialize(symbols, start_date, end_date)
        self.initial_buy_done = False
        logger.info(f"Initialized Buy and Hold strategy for {len(symbols)} symbols")
    
    def generate_signals(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                        portfolio_state: Dict) -> List[StrategySignal]:
        """Generate initial buy signals."""
        signals = []
        
        # Only buy at the beginning
        if self.initial_buy_done:
            return signals
        
        portfolio_value = portfolio_state.get('total_value', 100000)
        allocation_per_symbol = (portfolio_value * self.allocation_per_symbol) / len(self.symbols)
        
        for symbol in self.symbols:
            if symbol not in data or data[symbol].empty:
                continue
            
            current_price = data[symbol]['close'].iloc[-1]
            quantity = int(allocation_per_symbol / current_price)
            
            if quantity > 0:
                signal = StrategySignal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=Decimal(str(current_price)),
                    quantity=quantity,
                    timestamp=timestamp,
                    confidence=1.0,
                    order_type=OrderType.MARKET,
                    reason="Initial buy and hold allocation"
                )
                signals.append(signal)
        
        self.initial_buy_done = True
        logger.info(f"Generated initial buy signals for {len(signals)} symbols")
        
        return signals
    
    def update_state(self, data: Dict[str, pd.DataFrame], timestamp: datetime, 
                    portfolio_state: Dict):
        """Update strategy state."""
        super().update_state(data, timestamp, portfolio_state)
        
        # Update metrics
        total_positions = len(portfolio_state.get('positions', {}))
        self.metrics.custom_metrics['total_positions'] = total_positions
        self.metrics.custom_metrics['allocation_per_symbol'] = self.allocation_per_symbol
