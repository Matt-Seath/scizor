from typing import List, Dict
from datetime import datetime
import pandas as pd
import numpy as np
import structlog

from app.strategies.base import BaseStrategy, StrategyParameters, StrategySignal
from app.utils.logging import get_trading_logger

logger = structlog.get_logger(__name__)
trading_logger = get_trading_logger(__name__)


class MomentumBreakoutParameters(StrategyParameters):
    """Parameters specific to momentum breakout strategy"""
    
    def __init__(self, **kwargs):
        # Default momentum-specific parameters
        defaults = {
            'name': 'momentum_breakout',
            'lookback_period': 20,
            'volume_multiplier': 1.5,
            'rsi_threshold': 50,
            'price_change_threshold': 0.02,  # 2% minimum price change
            'atr_expansion_threshold': 1.2,  # ATR should be 20% above average
            'min_confidence': 0.7,
            'max_positions': 3,
            'risk_per_trade': 0.02,
            'stop_loss_method': 'atr',
            'stop_loss_multiplier': 2.5,
            'take_profit_ratio': 2.0,
            'min_liquidity': 1000000  # $1M daily volume for momentum plays
        }
        
        # Update with provided kwargs
        defaults.update(kwargs)
        super().__init__(**defaults)
        
        # Momentum-specific attributes
        self.lookback_period = defaults['lookback_period']
        self.volume_multiplier = defaults['volume_multiplier']
        self.rsi_threshold = defaults['rsi_threshold']
        self.price_change_threshold = defaults['price_change_threshold']
        self.atr_expansion_threshold = defaults['atr_expansion_threshold']
        self.min_confidence = defaults['min_confidence']


class MomentumBreakoutStrategy(BaseStrategy):
    """
    Momentum Breakout Strategy for ASX200
    
    Entry Criteria:
    - Price breaks above 20-day high
    - Volume > 1.5x average volume
    - RSI > 50 (trending market)
    - Price > 20-day SMA (uptrend confirmation)
    - ATR expansion (increased volatility)
    
    Exit Criteria:
    - ATR-based stop loss (2.5x ATR)
    - Time-based exit (14 days max)
    - Take profit at 2:1 risk-reward ratio
    """
    
    def __init__(self, parameters: MomentumBreakoutParameters = None):
        if parameters is None:
            parameters = MomentumBreakoutParameters()
        
        super().__init__(parameters)
        self.momentum_params = parameters
        
        logger.info("Momentum breakout strategy initialized",
                   lookback_period=parameters.lookback_period,
                   volume_multiplier=parameters.volume_multiplier,
                   min_confidence=parameters.min_confidence)
    
    def generate_entry_signals(self, data: Dict[str, pd.DataFrame], 
                              current_date: datetime) -> List[StrategySignal]:
        """Generate momentum breakout entry signals"""
        signals = []
        
        for symbol, df in data.items():
            try:
                if len(df) < self.momentum_params.lookback_period + 10:
                    continue  # Insufficient data
                
                # Get latest data point
                latest = df.iloc[-1]
                recent_data = df.tail(self.momentum_params.lookback_period)
                
                # Calculate breakout conditions
                signal_strength = self._calculate_breakout_strength(df, latest, recent_data)
                
                if signal_strength >= self.momentum_params.min_confidence:
                    # Calculate position metrics
                    position_metrics = self.calculate_position_metrics(symbol, latest['close'], df)
                    
                    # Create signal
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_type="BUY",
                        price=latest['close'],
                        confidence=signal_strength,
                        strategy_name=self.parameters.name,
                        generated_at=current_date,
                        stop_loss=position_metrics['stop_loss'],
                        take_profit=position_metrics['take_profit'],
                        metadata={
                            'breakout_type': 'momentum',
                            'volume_ratio': latest.get('volume_ratio', 1.0),
                            'rsi': latest.get('rsi', 50),
                            'atr_percent': latest.get('atr_percent', 2.0),
                            'position_size': position_metrics['position_size'],
                            'risk_amount': position_metrics['risk_amount'],
                            'reward_amount': position_metrics['reward_amount']
                        }
                    )
                    
                    signals.append(signal)
                    
                    logger.debug("Momentum breakout signal generated",
                               symbol=symbol,
                               price=latest['close'],
                               confidence=signal_strength,
                               volume_ratio=latest.get('volume_ratio', 1.0))
                
            except Exception as e:
                logger.error("Error generating momentum signal", 
                           symbol=symbol, error=str(e))
                continue
        
        # Sort by confidence and return top signals
        signals.sort(key=lambda x: x.confidence, reverse=True)
        max_signals = self.parameters.max_positions - self.position_count
        
        return signals[:max_signals]
    
    def generate_exit_signals(self, data: Dict[str, pd.DataFrame], 
                             current_date: datetime) -> List[StrategySignal]:
        """Generate momentum breakout exit signals"""
        signals = []
        
        # Check time-based exits
        symbols_to_close = self.check_time_based_exits(current_date)
        
        for symbol in symbols_to_close:
            if symbol in data:
                latest_price = data[symbol].iloc[-1]['close']
                
                signal = StrategySignal(
                    symbol=symbol,
                    signal_type="CLOSE",
                    price=latest_price,
                    confidence=1.0,
                    strategy_name=self.parameters.name,
                    generated_at=current_date,
                    metadata={'exit_reason': 'time_limit'}
                )
                
                signals.append(signal)
        
        # Check for momentum reversal exits
        for symbol in self.active_positions.keys():
            if symbol in data:
                try:
                    df = data[symbol]
                    latest = df.iloc[-1]
                    
                    # Check for momentum failure
                    if self._check_momentum_failure(df, latest):
                        signal = StrategySignal(
                            symbol=symbol,
                            signal_type="CLOSE",
                            price=latest['close'],
                            confidence=0.8,
                            strategy_name=self.parameters.name,
                            generated_at=current_date,
                            metadata={'exit_reason': 'momentum_failure'}
                        )
                        
                        signals.append(signal)
                        
                        logger.debug("Momentum failure exit signal",
                                   symbol=symbol,
                                   price=latest['close'])
                
                except Exception as e:
                    logger.error("Error checking momentum exit", 
                               symbol=symbol, error=str(e))
        
        return signals
    
    def _calculate_breakout_strength(self, df: pd.DataFrame, latest: pd.Series, 
                                   recent_data: pd.DataFrame) -> float:
        """Calculate the strength of a momentum breakout signal"""
        try:
            score = 0.0
            max_score = 6.0  # Total possible score
            
            # 1. Price breakout above 20-day high (25% weight)
            if 'channel_upper' in latest.index:
                if latest['close'] >= latest['channel_upper']:
                    score += 1.5
                elif latest['close'] >= latest['channel_upper'] * 0.995:  # Within 0.5%
                    score += 1.0
            else:
                # Fallback: 20-day high
                twenty_day_high = recent_data['high'].max()
                if latest['close'] >= twenty_day_high:
                    score += 1.5
                elif latest['close'] >= twenty_day_high * 0.995:
                    score += 1.0
            
            # 2. Volume confirmation (20% weight)
            if 'volume_ratio' in latest.index:
                volume_ratio = latest['volume_ratio']
                if volume_ratio >= self.momentum_params.volume_multiplier:
                    score += 1.2
                elif volume_ratio >= self.momentum_params.volume_multiplier * 0.8:
                    score += 0.8
            
            # 3. RSI trend confirmation (15% weight)
            if 'rsi' in latest.index:
                rsi = latest['rsi']
                if rsi > self.momentum_params.rsi_threshold + 10:
                    score += 0.9
                elif rsi > self.momentum_params.rsi_threshold:
                    score += 0.6
            
            # 4. Price above moving average (15% weight)
            if 'sma_20' in latest.index:
                if latest['close'] > latest['sma_20']:
                    score += 0.9
                    # Extra points if well above
                    if latest['close'] > latest['sma_20'] * 1.02:
                        score += 0.3
            
            # 5. ATR expansion (volatility increase) (15% weight)
            if 'atr_percent' in latest.index and len(df) >= 20:
                current_atr = latest['atr_percent']
                avg_atr = df['atr_percent'].tail(20).mean()
                
                if current_atr > avg_atr * self.momentum_params.atr_expansion_threshold:
                    score += 0.9
                elif current_atr > avg_atr * 1.1:
                    score += 0.6
            
            # 6. Price momentum (10% weight)
            if len(recent_data) >= 5:
                price_change = (latest['close'] - recent_data['close'].iloc[-5]) / recent_data['close'].iloc[-5]
                if price_change > self.momentum_params.price_change_threshold:
                    score += 0.6
                elif price_change > 0:
                    score += 0.3
            
            # Normalize to 0-1 scale
            strength = min(score / max_score, 1.0)
            
            return strength
            
        except Exception as e:
            logger.error("Error calculating breakout strength", error=str(e))
            return 0.0
    
    def _check_momentum_failure(self, df: pd.DataFrame, latest: pd.Series) -> bool:
        """Check if momentum is failing and position should be closed"""
        try:
            # 1. RSI overbought and declining
            if 'rsi' in latest.index and len(df) >= 3:
                current_rsi = latest['rsi']
                prev_rsi = df['rsi'].iloc[-2]
                
                if current_rsi > 70 and current_rsi < prev_rsi:
                    return True
            
            # 2. Volume drying up
            if 'volume_ratio' in latest.index:
                if latest['volume_ratio'] < 0.5:  # Below half average volume
                    return True
            
            # 3. Price below 5-day SMA (short-term trend break)
            if 'close' in latest.index and len(df) >= 5:
                sma_5 = df['close'].tail(5).mean()
                if latest['close'] < sma_5 * 0.98:  # 2% below 5-day average
                    return True
            
            # 4. MACD bearish divergence
            if all(col in latest.index for col in ['macd', 'macd_signal']):
                if latest['macd'] < latest['macd_signal']:
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Error checking momentum failure", error=str(e))
            return False
    
    def get_strategy_description(self) -> str:
        """Get human-readable strategy description"""
        return f"""
        Momentum Breakout Strategy for ASX200
        
        Entry Criteria:
        - Price breaks above {self.momentum_params.lookback_period}-day high
        - Volume > {self.momentum_params.volume_multiplier}x average
        - RSI > {self.momentum_params.rsi_threshold} (trending market)
        - Price above 20-day SMA (uptrend confirmation)
        - ATR expansion > {self.momentum_params.atr_expansion_threshold}x average
        - Minimum confidence: {self.momentum_params.min_confidence}
        
        Risk Management:
        - Stop loss: {self.momentum_params.stop_loss_multiplier}x ATR
        - Take profit: {self.momentum_params.take_profit_ratio}:1 risk-reward
        - Max holding: {self.parameters.max_holding_days} days
        - Max positions: {self.parameters.max_positions}
        
        Exit Criteria:
        - RSI overbought + declining
        - Volume below 50% average
        - Price below 5-day SMA
        - MACD bearish crossover
        - Time limit reached
        """
    
    def optimize_parameters(self, historical_data: Dict[str, pd.DataFrame], 
                           start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """
        Optimize strategy parameters using historical data
        Returns best parameter set based on Sharpe ratio
        """
        # TODO: Implement parameter optimization
        # This would test different combinations of:
        # - lookback_period (15, 20, 25)
        # - volume_multiplier (1.2, 1.5, 2.0)
        # - rsi_threshold (45, 50, 55)
        # - stop_loss_multiplier (2.0, 2.5, 3.0)
        
        logger.info("Parameter optimization not yet implemented")
        return {
            'lookback_period': self.momentum_params.lookback_period,
            'volume_multiplier': self.momentum_params.volume_multiplier,
            'rsi_threshold': self.momentum_params.rsi_threshold
        }