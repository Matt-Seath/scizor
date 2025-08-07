"""
Technical indicators for strategy development.

This module provides common technical analysis indicators that strategies can use.
All indicators are implemented using vectorized operations for performance.
"""

import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple
from decimal import Decimal


class TechnicalIndicators:
    """
    Collection of technical analysis indicators.
    
    All methods are static and accept pandas Series or numpy arrays.
    """
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average.
        
        Args:
            data: Price series
            period: Number of periods
            
        Returns:
            SMA series
        """
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average.
        
        Args:
            data: Price series
            period: Number of periods
            
        Returns:
            EMA series
        """
        return data.ewm(span=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index.
        
        Args:
            data: Price series (typically close prices)
            period: RSI period (default 14)
            
        Returns:
            RSI series (0-100)
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(data: pd.Series, 
             fast_period: int = 12, 
             slow_period: int = 26, 
             signal_period: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
            
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = TechnicalIndicators.ema(data, fast_period)
        ema_slow = TechnicalIndicators.ema(data, slow_period)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: pd.Series, 
                       period: int = 20, 
                       std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Bollinger Bands.
        
        Args:
            data: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Tuple of (Upper band, Middle band/SMA, Lower band)
        """
        sma = TechnicalIndicators.sma(data, period)
        std = data.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def stochastic(high: pd.Series, 
                  low: pd.Series, 
                  close: pd.Series, 
                  k_period: int = 14, 
                  d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic Oscillator.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: %K period
            d_period: %D period
            
        Returns:
            Tuple of (%K, %D)
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return k_percent, d_percent
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Average True Range.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period
            
        Returns:
            ATR series
        """
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def williams_r(high: pd.Series, 
                  low: pd.Series, 
                  close: pd.Series, 
                  period: int = 14) -> pd.Series:
        """
        Williams %R.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Period for calculation
            
        Returns:
            Williams %R series (-100 to 0)
        """
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))
        
        return williams_r
    
    @staticmethod
    def roc(data: pd.Series, period: int = 12) -> pd.Series:
        """
        Rate of Change.
        
        Args:
            data: Price series
            period: ROC period
            
        Returns:
            ROC series (percentage change)
        """
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    @staticmethod
    def momentum(data: pd.Series, period: int = 10) -> pd.Series:
        """
        Momentum indicator.
        
        Args:
            data: Price series
            period: Momentum period
            
        Returns:
            Momentum series
        """
        return data - data.shift(period)
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On Balance Volume.
        
        Args:
            close: Close price series
            volume: Volume series
            
        Returns:
            OBV series
        """
        price_change = close.diff()
        obv = volume.copy()
        
        obv[price_change < 0] = -volume[price_change < 0]
        obv[price_change == 0] = 0
        
        return obv.cumsum()
    
    @staticmethod
    def adx(high: pd.Series, 
           low: pd.Series, 
           close: pd.Series, 
           period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Average Directional Index.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ADX period
            
        Returns:
            Tuple of (ADX, +DI, -DI)
        """
        # Calculate True Range
        atr_values = TechnicalIndicators.atr(high, low, close, period)
        
        # Calculate Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=high.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=high.index)
        
        # Calculate Directional Indicators
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_values)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_values)
        
        # Calculate ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Volume Weighted Average Price.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            volume: Volume series
            
        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        volume_price = typical_price * volume
        
        return volume_price.cumsum() / volume.cumsum()
    
    @staticmethod
    def pivot_points(high: pd.Series, 
                    low: pd.Series, 
                    close: pd.Series) -> dict:
        """
        Calculate pivot points and support/resistance levels.
        
        Args:
            high: Previous period high
            low: Previous period low
            close: Previous period close
            
        Returns:
            Dictionary with pivot point levels
        """
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    
    @staticmethod
    def ichimoku(high: pd.Series, 
                low: pd.Series, 
                close: pd.Series,
                tenkan_period: int = 9,
                kijun_period: int = 26,
                senkou_period: int = 52) -> dict:
        """
        Ichimoku Cloud components.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            tenkan_period: Tenkan-sen period
            kijun_period: Kijun-sen period
            senkou_period: Senkou span B period
            
        Returns:
            Dictionary with Ichimoku components
        """
        # Tenkan-sen (Conversion Line)
        tenkan_high = high.rolling(window=tenkan_period).max()
        tenkan_low = low.rolling(window=tenkan_period).min()
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # Kijun-sen (Base Line)
        kijun_high = high.rolling(window=kijun_period).max()
        kijun_low = low.rolling(window=kijun_period).min()
        kijun_sen = (kijun_high + kijun_low) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)
        
        # Senkou Span B (Leading Span B)
        senkou_high = high.rolling(window=senkou_period).max()
        senkou_low = low.rolling(window=senkou_period).min()
        senkou_b = ((senkou_high + senkou_low) / 2).shift(kijun_period)
        
        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-kijun_period)
        
        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
            'chikou_span': chikou_span
        }
    
    @staticmethod
    def support_resistance(data: pd.Series, window: int = 20, min_touches: int = 2) -> Tuple[pd.Series, pd.Series]:
        """
        Identify support and resistance levels.
        
        Args:
            data: Price series
            window: Window for finding local extremes
            min_touches: Minimum touches to confirm level
            
        Returns:
            Tuple of (support levels, resistance levels)
        """
        # Find local maxima and minima
        rolling_max = data.rolling(window=window, center=True).max()
        rolling_min = data.rolling(window=window, center=True).min()
        
        resistance = pd.Series(np.where(data == rolling_max, data, np.nan), index=data.index)
        support = pd.Series(np.where(data == rolling_min, data, np.nan), index=data.index)
        
        return support, resistance
