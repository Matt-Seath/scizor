from typing import List, Dict
from datetime import datetime
import pandas as pd
import numpy as np
import structlog

from app.strategies.base import BaseStrategy, StrategyParameters, StrategySignal
from app.utils.logging import get_trading_logger

logger = structlog.get_logger(__name__)
trading_logger = get_trading_logger(__name__)


class MeanReversionParameters(StrategyParameters):
    """Parameters specific to mean reversion strategy"""
    
    def __init__(self, **kwargs):
        # Base strategy parameters
        base_params = {
            'name': 'mean_reversion',
            'max_positions': kwargs.get('max_positions', 4),
            'risk_per_trade': kwargs.get('risk_per_trade', 0.015),
            'stop_loss_method': kwargs.get('stop_loss_method', 'percent'),
            'stop_loss_multiplier': kwargs.get('stop_loss_multiplier', 5.0),
            'take_profit_ratio': kwargs.get('take_profit_ratio', 1.5),
            'min_liquidity': kwargs.get('min_liquidity', 750000),
            'max_holding_days': kwargs.get('max_holding_days', 10)
        }
        
        # Initialize base class
        super().__init__(**base_params)
        
        # Mean reversion specific attributes
        self.rsi_oversold = kwargs.get('rsi_oversold', 30)
        self.rsi_exit = kwargs.get('rsi_exit', 70)
        self.bollinger_period = kwargs.get('bollinger_period', 20)
        self.bollinger_std = kwargs.get('bollinger_std', 2.0)
        self.stoch_oversold = kwargs.get('stoch_oversold', 20)
        self.stoch_exit = kwargs.get('stoch_exit', 80)
        self.volume_multiplier = kwargs.get('volume_multiplier', 1.2)
        self.trend_filter_period = kwargs.get('trend_filter_period', 50)
        self.min_confidence = kwargs.get('min_confidence', 0.6)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy
    
    Entry Criteria:
    - RSI <= 30 (oversold)
    - Price at or below lower Bollinger Band
    - Stochastic <= 20 (oversold)
    - Volume > 1.2x average (selling pressure)
    - Price still above 50-day SMA (long-term uptrend)
    - No recent earnings events (avoid fundamental moves)
    
    Exit Criteria:
    - RSI >= 70 (overbought)
    - Stochastic >= 80 (overbought)
    - Price above upper Bollinger Band
    - Time-based exit (10 days max)
    - 5% stop loss (protect against continued decline)
    """
    
    def __init__(self, parameters: MeanReversionParameters = None):
        if parameters is None:
            parameters = MeanReversionParameters()
        
        super().__init__(parameters)
        self.mean_rev_params = parameters
        
        logger.info("Mean reversion strategy initialized",
                   rsi_oversold=parameters.rsi_oversold,
                   bollinger_std=parameters.bollinger_std,
                   min_confidence=parameters.min_confidence)
    
    def generate_entry_signals(self, data: Dict[str, pd.DataFrame], 
                              current_date: datetime) -> List[StrategySignal]:
        """Generate mean reversion entry signals"""
        signals = []
        
        for symbol, df in data.items():
            try:
                if len(df) < max(self.mean_rev_params.bollinger_period, 
                               self.mean_rev_params.trend_filter_period) + 10:
                    continue  # Insufficient data
                
                # Get latest data point
                latest = df.iloc[-1]
                
                # Calculate mean reversion signal strength
                signal_strength = self._calculate_mean_reversion_strength(df, latest)
                
                if signal_strength >= self.mean_rev_params.min_confidence:
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
                            'entry_type': 'mean_reversion',
                            'rsi': latest.get('rsi', 50),
                            'bb_position': latest.get('bb_position', 0.5),
                            'stoch_k': latest.get('stoch_k', 50),
                            'volume_ratio': latest.get('volume_ratio', 1.0),
                            'position_size': position_metrics['position_size'],
                            'risk_amount': position_metrics['risk_amount'],
                            'reward_amount': position_metrics['reward_amount']
                        }
                    )
                    
                    signals.append(signal)
                    
                    logger.debug("Mean reversion signal generated",
                               symbol=symbol,
                               price=latest['close'],
                               confidence=signal_strength,
                               rsi=latest.get('rsi', 50))
                
            except Exception as e:
                logger.error("Error generating mean reversion signal", 
                           symbol=symbol, error=str(e))
                continue
        
        # Sort by confidence and return top signals
        signals.sort(key=lambda x: x.confidence, reverse=True)
        max_signals = self.parameters.max_positions - self.position_count
        
        return signals[:max_signals]
    
    def generate_exit_signals(self, data: Dict[str, pd.DataFrame], 
                             current_date: datetime) -> List[StrategySignal]:
        """Generate mean reversion exit signals"""
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
        
        # Check for mean reversion target hits (overbought exits)
        for symbol in self.active_positions.keys():
            if symbol in data:
                try:
                    df = data[symbol]
                    latest = df.iloc[-1]
                    
                    # Check for overbought exit conditions
                    exit_strength = self._calculate_exit_strength(df, latest)
                    
                    if exit_strength >= 0.7:  # Strong exit signal
                        signal = StrategySignal(
                            symbol=symbol,
                            signal_type="CLOSE",
                            price=latest['close'],
                            confidence=exit_strength,
                            strategy_name=self.parameters.name,
                            generated_at=current_date,
                            metadata={
                                'exit_reason': 'target_reached',
                                'rsi': latest.get('rsi', 50),
                                'bb_position': latest.get('bb_position', 0.5)
                            }
                        )
                        
                        signals.append(signal)
                        
                        logger.debug("Mean reversion target exit",
                                   symbol=symbol,
                                   price=latest['close'],
                                   rsi=latest.get('rsi', 50))
                
                except Exception as e:
                    logger.error("Error checking mean reversion exit", 
                               symbol=symbol, error=str(e))
        
        return signals
    
    def _calculate_mean_reversion_strength(self, df: pd.DataFrame, latest: pd.Series) -> float:
        """Calculate the strength of a mean reversion signal"""
        try:
            score = 0.0
            max_score = 5.0  # Total possible score
            
            # 1. RSI oversold condition (30% weight)
            if 'rsi' in latest.index:
                rsi = latest['rsi']
                if rsi <= self.mean_rev_params.rsi_oversold:
                    # More oversold = stronger signal
                    oversold_strength = max(0, (self.mean_rev_params.rsi_oversold - rsi) / 10)
                    score += min(1.5, 1.0 + oversold_strength * 0.5)
                elif rsi <= self.mean_rev_params.rsi_oversold + 5:
                    score += 0.8
            
            # 2. Bollinger Band position (25% weight)
            if 'bb_position' in latest.index:
                bb_pos = latest['bb_position']
                if bb_pos <= 0.1:  # At or below lower band
                    score += 1.25
                elif bb_pos <= 0.2:  # Close to lower band
                    score += 1.0
                elif bb_pos <= 0.3:
                    score += 0.6
            
            # 3. Stochastic oversold (20% weight)
            if 'stoch_k' in latest.index:
                stoch = latest['stoch_k']
                if stoch <= self.mean_rev_params.stoch_oversold:
                    score += 1.0
                elif stoch <= self.mean_rev_params.stoch_oversold + 10:
                    score += 0.6
            
            # 4. Volume confirmation (15% weight)
            if 'volume_ratio' in latest.index:
                volume_ratio = latest['volume_ratio']
                if volume_ratio >= self.mean_rev_params.volume_multiplier:
                    score += 0.75
                elif volume_ratio >= 1.0:
                    score += 0.5
            
            # 5. Trend filter - must be above long-term SMA (10% weight)
            if f'sma_{self.mean_rev_params.trend_filter_period}' in latest.index:
                long_sma = latest[f'sma_{self.mean_rev_params.trend_filter_period}']
                if latest['close'] > long_sma:
                    score += 0.5
                else:
                    # Penalize if below long-term trend
                    score *= 0.5
            elif 'sma_50' in latest.index:
                # Fallback to 50-day SMA
                if latest['close'] > latest['sma_50']:
                    score += 0.5
                else:
                    score *= 0.5
            
            # Normalize to 0-1 scale
            strength = min(score / max_score, 1.0)
            
            return strength
            
        except Exception as e:
            logger.error("Error calculating mean reversion strength", error=str(e))
            return 0.0
    
    def _calculate_exit_strength(self, df: pd.DataFrame, latest: pd.Series) -> float:
        """Calculate the strength of a mean reversion exit signal"""
        try:
            score = 0.0
            max_score = 3.0
            
            # 1. RSI overbought (40% weight)
            if 'rsi' in latest.index:
                rsi = latest['rsi']
                if rsi >= self.mean_rev_params.rsi_exit:
                    score += 1.2
                elif rsi >= self.mean_rev_params.rsi_exit - 5:
                    score += 0.8
            
            # 2. Stochastic overbought (30% weight)
            if 'stoch_k' in latest.index:
                stoch = latest['stoch_k']
                if stoch >= self.mean_rev_params.stoch_exit:
                    score += 0.9
                elif stoch >= self.mean_rev_params.stoch_exit - 10:
                    score += 0.6
            
            # 3. Bollinger Band position (30% weight)
            if 'bb_position' in latest.index:
                bb_pos = latest['bb_position']
                if bb_pos >= 0.9:  # At or above upper band
                    score += 0.9
                elif bb_pos >= 0.8:
                    score += 0.6
            
            # Normalize to 0-1 scale
            strength = min(score / max_score, 1.0)
            
            return strength
            
        except Exception as e:
            logger.error("Error calculating exit strength", error=str(e))
            return 0.0
    
    def _check_earnings_avoidance(self, symbol: str, current_date: datetime) -> bool:
        """
        Check if we should avoid the stock due to upcoming earnings
        
        Returns:
            True if should avoid, False if safe to trade
        """
        # TODO: Implement earnings calendar check
        # For now, return False (no earnings avoidance)
        # In production, this would check:
        # - Earnings announcement dates
        # - Ex-dividend dates
        # - Other corporate events
        
        return False
    
    def _check_sector_rotation(self, symbol: str, df: pd.DataFrame) -> float:
        """
        Check if sector is in rotation (negative for the stock)
        
        Returns:
            Adjustment factor (0.5-1.5) for signal strength
        """
        try:
            # TODO: Implement sector analysis
            # For now, use relative strength vs market
            
            if len(df) < 20:
                return 1.0
            
            # Simple relative strength calculation
            stock_return = (df['close'].iloc[-1] / df['close'].iloc[-20]) - 1
            
            # TODO: Compare to market/sector return
            # For now, assume neutral
            
            if stock_return > 0.05:  # Strong relative performance
                return 1.2
            elif stock_return < -0.15:  # Weak relative performance
                return 0.8
            else:
                return 1.0
                
        except Exception as e:
            logger.error("Error checking sector rotation", error=str(e))
            return 1.0
    
    def get_strategy_description(self) -> str:
        """Get human-readable strategy description"""
        return f"""
        Mean Reversion Strategy
        
        Entry Criteria:
        - RSI <= {self.mean_rev_params.rsi_oversold} (oversold)
        - Price at/below lower Bollinger Band ({self.mean_rev_params.bollinger_std} std)
        - Stochastic <= {self.mean_rev_params.stoch_oversold} (oversold)
        - Volume > {self.mean_rev_params.volume_multiplier}x average
        - Price above {self.mean_rev_params.trend_filter_period}-day SMA (trend filter)
        - Minimum confidence: {self.mean_rev_params.min_confidence}
        
        Risk Management:
        - Stop loss: {self.mean_rev_params.stop_loss_multiplier}% fixed
        - Take profit: {self.mean_rev_params.take_profit_ratio}:1 risk-reward
        - Max holding: {self.parameters.max_holding_days} days
        - Max positions: {self.parameters.max_positions}
        
        Exit Criteria:
        - RSI >= {self.mean_rev_params.rsi_exit} (overbought)
        - Stochastic >= {self.mean_rev_params.stoch_exit} (overbought)
        - Price above upper Bollinger Band
        - Time limit reached
        """
    
    def optimize_parameters(self, historical_data: Dict[str, pd.DataFrame], 
                           start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """
        Optimize strategy parameters using historical data
        Returns best parameter set based on Sharpe ratio and win rate
        """
        # TODO: Implement parameter optimization
        # This would test different combinations of:
        # - rsi_oversold (25, 30, 35)
        # - bollinger_std (1.5, 2.0, 2.5)
        # - stoch_oversold (15, 20, 25)
        # - volume_multiplier (1.0, 1.2, 1.5)
        
        logger.info("Parameter optimization not yet implemented")
        return {
            'rsi_oversold': self.mean_rev_params.rsi_oversold,
            'bollinger_std': self.mean_rev_params.bollinger_std,
            'stoch_oversold': self.mean_rev_params.stoch_oversold
        }