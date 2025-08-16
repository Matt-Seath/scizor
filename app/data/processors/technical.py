import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)


class TechnicalIndicators:
    """
    Technical analysis indicators for ASX200 trading strategies
    Optimized for swing trading timeframes (daily data)
    """
    
    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index (RSI)
        
        Args:
            prices: Price series (typically close prices)
            period: Lookback period (default 14)
            
        Returns:
            RSI values (0-100)
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """
        Bollinger Bands
        
        Args:
            prices: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower' bands
        """
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Average True Range (ATR)
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Lookback period
            
        Returns:
            ATR values
        """
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence)
        
        Args:
            prices: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period
            
        Returns:
            Dictionary with 'macd', 'signal', 'histogram'
        """
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """
        Stochastic Oscillator
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: %K period
            d_period: %D period
            
        Returns:
            Dictionary with '%K' and '%D' values
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            '%K': k_percent,
            '%D': d_percent
        }
    
    @staticmethod
    def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
        """Volume Simple Moving Average"""
        return volume.rolling(window=period).mean()
    
    @staticmethod
    def price_channels(high: pd.Series, low: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """
        Price Channels (Donchian Channels)
        
        Args:
            high: High price series
            low: Low price series
            period: Lookback period
            
        Returns:
            Dictionary with 'upper' and 'lower' channels
        """
        upper_channel = high.rolling(window=period).max()
        lower_channel = low.rolling(window=period).min()
        
        return {
            'upper': upper_channel,
            'lower': lower_channel
        }
    
    @staticmethod
    def momentum(prices: pd.Series, period: int = 10) -> pd.Series:
        """
        Price Momentum
        
        Args:
            prices: Price series
            period: Lookback period
            
        Returns:
            Momentum values (current price / price n periods ago)
        """
        return prices / prices.shift(period)
    
    @staticmethod
    def rate_of_change(prices: pd.Series, period: int = 10) -> pd.Series:
        """
        Rate of Change (ROC)
        
        Args:
            prices: Price series
            period: Lookback period
            
        Returns:
            ROC percentage values
        """
        return ((prices / prices.shift(period)) - 1) * 100


class ASXTechnicalAnalyzer:
    """
    ASX-specific technical analysis with market characteristics
    Optimized for Australian market conditions and trading hours
    """
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
        
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators for a stock
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            
        Returns:
            DataFrame with all technical indicators added
        """
        result = df.copy()
        
        try:
            # Price-based indicators
            result['rsi'] = self.indicators.rsi(df['close'])
            result['rsi_14'] = self.indicators.rsi(df['close'], 14)
            result['rsi_21'] = self.indicators.rsi(df['close'], 21)
            
            # Moving averages
            result['sma_10'] = self.indicators.sma(df['close'], 10)
            result['sma_20'] = self.indicators.sma(df['close'], 20)
            result['sma_50'] = self.indicators.sma(df['close'], 50)
            result['ema_12'] = self.indicators.ema(df['close'], 12)
            result['ema_26'] = self.indicators.ema(df['close'], 26)
            
            # Bollinger Bands
            bb = self.indicators.bollinger_bands(df['close'])
            result['bb_upper'] = bb['upper']
            result['bb_middle'] = bb['middle']
            result['bb_lower'] = bb['lower']
            result['bb_width'] = (bb['upper'] - bb['lower']) / bb['middle']
            result['bb_position'] = (df['close'] - bb['lower']) / (bb['upper'] - bb['lower'])
            
            # ATR for volatility and stops
            result['atr'] = self.indicators.atr(df['high'], df['low'], df['close'])
            result['atr_percent'] = result['atr'] / df['close'] * 100
            
            # MACD
            macd = self.indicators.macd(df['close'])
            result['macd'] = macd['macd']
            result['macd_signal'] = macd['signal']
            result['macd_histogram'] = macd['histogram']
            
            # Stochastic
            stoch = self.indicators.stochastic(df['high'], df['low'], df['close'])
            result['stoch_k'] = stoch['%K']
            result['stoch_d'] = stoch['%D']
            
            # Volume indicators
            result['volume_sma'] = self.indicators.volume_sma(df['volume'])
            result['volume_ratio'] = df['volume'] / result['volume_sma']
            
            # Price channels for breakouts
            channels = self.indicators.price_channels(df['high'], df['low'], 20)
            result['channel_upper'] = channels['upper']
            result['channel_lower'] = channels['lower']
            
            # Momentum indicators
            result['momentum_10'] = self.indicators.momentum(df['close'], 10)
            result['roc_10'] = self.indicators.rate_of_change(df['close'], 10)
            
            logger.debug("Technical indicators calculated", 
                        indicators=len([col for col in result.columns if col not in df.columns]))
            
        except Exception as e:
            logger.error("Error calculating technical indicators", error=str(e))
            return df
        
        return result
    
    def identify_breakout_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Identify momentum breakout signals
        
        Returns:
            Series with signal strength (0-1) where >0.7 is strong signal
        """
        signals = pd.Series(index=df.index, data=0.0)
        
        try:
            # 20-day high breakout
            breakout_condition = df['close'] >= df['channel_upper']
            
            # Volume confirmation (above average)
            volume_condition = df['volume_ratio'] >= 1.5
            
            # RSI trend confirmation (above 50)
            rsi_condition = df['rsi'] > 50
            
            # Price above 20-day SMA
            trend_condition = df['close'] > df['sma_20']
            
            # ATR expansion (volatility increase)
            atr_condition = df['atr_percent'] > df['atr_percent'].rolling(10).mean()
            
            # Combine conditions
            conditions = [breakout_condition, volume_condition, rsi_condition, trend_condition]
            signal_strength = sum(conditions) / len(conditions)
            
            # Boost signal if ATR is expanding
            signal_strength = signal_strength * 1.2 if atr_condition else signal_strength
            
            signals = signal_strength.clip(0, 1)
            
        except Exception as e:
            logger.error("Error identifying breakout signals", error=str(e))
        
        return signals
    
    def identify_mean_reversion_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Identify mean reversion signals
        
        Returns:
            Series with signal strength (0-1) where >0.7 is strong signal
        """
        signals = pd.Series(index=df.index, data=0.0)
        
        try:
            # RSI oversold
            rsi_condition = df['rsi'] <= 30
            
            # Price at or below lower Bollinger Band
            bb_condition = df['close'] <= df['bb_lower']
            
            # Stochastic oversold
            stoch_condition = df['stoch_k'] <= 20
            
            # Volume above average (selling pressure)
            volume_condition = df['volume_ratio'] >= 1.2
            
            # Price still above longer-term trend (20-day SMA)
            trend_condition = df['close'] > df['sma_50']
            
            # Combine conditions
            conditions = [rsi_condition, bb_condition, stoch_condition, volume_condition, trend_condition]
            signal_strength = sum(conditions) / len(conditions)
            
            signals = signal_strength.clip(0, 1)
            
        except Exception as e:
            logger.error("Error identifying mean reversion signals", error=str(e))
        
        return signals
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: float, 
                           method: str = "atr", multiplier: float = 2.0) -> float:
        """
        Calculate dynamic stop loss based on ATR or other methods
        
        Args:
            df: DataFrame with technical indicators
            entry_price: Entry price for the position
            method: 'atr', 'percent', or 'support'
            multiplier: ATR multiplier for stop distance
            
        Returns:
            Stop loss price
        """
        try:
            if method == "atr":
                latest_atr = df['atr'].iloc[-1]
                stop_loss = entry_price - (latest_atr * multiplier)
            
            elif method == "percent":
                # Fixed percentage stop
                stop_loss = entry_price * (1 - multiplier / 100)
            
            elif method == "support":
                # Support level based on recent lows
                lookback_period = 20
                recent_low = df['low'].tail(lookback_period).min()
                stop_loss = min(recent_low * 0.98, entry_price * 0.95)  # 2% below support or 5% max
            
            else:
                # Default to 3% stop
                stop_loss = entry_price * 0.97
            
            return max(stop_loss, entry_price * 0.90)  # Maximum 10% stop loss
            
        except Exception as e:
            logger.error("Error calculating stop loss", error=str(e))
            return entry_price * 0.95  # Default 5% stop
    
    def calculate_take_profit(self, df: pd.DataFrame, entry_price: float, 
                             stop_loss: float, risk_reward_ratio: float = 2.0) -> float:
        """
        Calculate take profit level based on risk-reward ratio
        
        Args:
            df: DataFrame with technical indicators
            entry_price: Entry price for the position
            stop_loss: Stop loss price
            risk_reward_ratio: Target risk-reward ratio
            
        Returns:
            Take profit price
        """
        try:
            risk_amount = entry_price - stop_loss
            reward_amount = risk_amount * risk_reward_ratio
            take_profit = entry_price + reward_amount
            
            # Check for resistance levels
            lookback_period = 50
            resistance_level = df['high'].tail(lookback_period).max()
            
            # Don't set take profit beyond strong resistance
            if take_profit > resistance_level:
                take_profit = resistance_level * 0.99  # Just below resistance
            
            return take_profit
            
        except Exception as e:
            logger.error("Error calculating take profit", error=str(e))
            return entry_price * 1.06  # Default 6% target
    
    def get_market_regime(self, df: pd.DataFrame) -> str:
        """
        Determine current market regime for strategy selection
        
        Returns:
            'trending_up', 'trending_down', 'sideways', 'volatile'
        """
        try:
            # Use multiple timeframes to determine regime
            short_trend = df['close'].iloc[-10:].mean() / df['close'].iloc[-20:-10].mean()
            medium_trend = df['close'].iloc[-20:].mean() / df['close'].iloc[-50:-20].mean()
            
            # Volatility measure
            recent_volatility = df['atr_percent'].tail(20).mean()
            historical_volatility = df['atr_percent'].mean()
            
            if short_trend > 1.02 and medium_trend > 1.01:
                return 'trending_up'
            elif short_trend < 0.98 and medium_trend < 0.99:
                return 'trending_down'
            elif recent_volatility > historical_volatility * 1.5:
                return 'volatile'
            else:
                return 'sideways'
                
        except Exception as e:
            logger.error("Error determining market regime", error=str(e))
            return 'sideways'