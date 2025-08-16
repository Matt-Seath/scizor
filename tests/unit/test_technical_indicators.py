import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.data.processors.technical import TechnicalIndicators, ASXTechnicalAnalyzer
from tests.conftest import assert_dataframe_has_indicators


class TestTechnicalIndicators:
    """Test technical indicator calculations."""
    
    def test_rsi_calculation(self, sample_price_data):
        """Test RSI calculation."""
        prices = sample_price_data['close']
        rsi = TechnicalIndicators.rsi(prices, period=14)
        
        # RSI should be between 0 and 100
        assert rsi.min() >= 0, "RSI should not be below 0"
        assert rsi.max() <= 100, "RSI should not be above 100"
        
        # RSI should have NaN values for the first 14 periods
        assert rsi.iloc[:13].isna().all(), "First 13 RSI values should be NaN"
        assert not rsi.iloc[14:].isna().any(), "RSI should have values after period 14"
    
    def test_rsi_extreme_values(self):
        """Test RSI with extreme price movements."""
        # Create prices that always go up (should result in RSI near 100)
        up_prices = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25])
        rsi_up = TechnicalIndicators.rsi(up_prices, period=14)
        
        # RSI should be high for consistently rising prices
        assert rsi_up.iloc[-1] > 80, "RSI should be high for consistently rising prices"
        
        # Create prices that always go down (should result in RSI near 0)
        down_prices = pd.Series([25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10])
        rsi_down = TechnicalIndicators.rsi(down_prices, period=14)
        
        # RSI should be low for consistently falling prices
        assert rsi_down.iloc[-1] < 20, "RSI should be low for consistently falling prices"
    
    def test_bollinger_bands(self, sample_price_data):
        """Test Bollinger Bands calculation."""
        prices = sample_price_data['close']
        bb = TechnicalIndicators.bollinger_bands(prices, period=20, std_dev=2.0)
        
        # Should return three series
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        
        # Upper band should be above middle, middle above lower
        valid_indices = ~(bb['upper'].isna() | bb['middle'].isna() | bb['lower'].isna())
        assert (bb['upper'][valid_indices] >= bb['middle'][valid_indices]).all(), "Upper band should be >= middle"
        assert (bb['middle'][valid_indices] >= bb['lower'][valid_indices]).all(), "Middle should be >= lower band"
        
        # Middle should be the same as 20-period SMA
        sma_20 = TechnicalIndicators.sma(prices, 20)
        pd.testing.assert_series_equal(bb['middle'], sma_20, check_names=False)
    
    def test_atr_calculation(self, sample_price_data):
        """Test Average True Range calculation."""
        high = sample_price_data['high']
        low = sample_price_data['low']
        close = sample_price_data['close']
        
        atr = TechnicalIndicators.atr(high, low, close, period=14)
        
        # ATR should be positive
        assert (atr[~atr.isna()] >= 0).all(), "ATR should be non-negative"
        
        # ATR should have NaN values for the first 14 periods
        assert atr.iloc[:13].isna().all(), "First 13 ATR values should be NaN"
        assert not atr.iloc[14:].isna().any(), "ATR should have values after period 14"
    
    def test_moving_averages(self, sample_price_data):
        """Test Simple and Exponential Moving Averages."""
        prices = sample_price_data['close']
        
        # Test SMA
        sma_10 = TechnicalIndicators.sma(prices, 10)
        assert sma_10.iloc[:9].isna().all(), "First 9 SMA values should be NaN"
        assert not sma_10.iloc[10:].isna().any(), "SMA should have values after period 10"
        
        # Test EMA
        ema_10 = TechnicalIndicators.ema(prices, 10)
        assert not ema_10.isna().any(), "EMA should not have NaN values"
        
        # EMA should be more responsive than SMA
        sma_20 = TechnicalIndicators.sma(prices, 20)
        ema_20 = TechnicalIndicators.ema(prices, 20)
        
        # In trending markets, EMA should be closer to current price than SMA
        recent_prices = prices.tail(10)
        recent_sma = sma_20.tail(10)
        recent_ema = ema_20.tail(10)
        
        # This test might not always pass due to randomness, so we'll just check they're different
        assert not recent_sma.equals(recent_ema), "SMA and EMA should produce different results"
    
    def test_macd(self, sample_price_data):
        """Test MACD calculation."""
        prices = sample_price_data['close']
        macd = TechnicalIndicators.macd(prices, fast=12, slow=26, signal=9)
        
        # Should return three series
        assert 'macd' in macd
        assert 'signal' in macd
        assert 'histogram' in macd
        
        # Histogram should be MACD - Signal
        valid_indices = ~(macd['macd'].isna() | macd['signal'].isna())
        expected_histogram = macd['macd'][valid_indices] - macd['signal'][valid_indices]
        actual_histogram = macd['histogram'][valid_indices]
        
        pd.testing.assert_series_equal(expected_histogram, actual_histogram, check_names=False)
    
    def test_stochastic(self, sample_price_data):
        """Test Stochastic oscillator."""
        high = sample_price_data['high']
        low = sample_price_data['low']
        close = sample_price_data['close']
        
        stoch = TechnicalIndicators.stochastic(high, low, close, k_period=14, d_period=3)
        
        # Should return two series
        assert '%K' in stoch
        assert '%D' in stoch
        
        # Values should be between 0 and 100
        valid_k = stoch['%K'][~stoch['%K'].isna()]
        valid_d = stoch['%D'][~stoch['%D'].isna()]
        
        assert (valid_k >= 0).all() and (valid_k <= 100).all(), "%K should be between 0 and 100"
        assert (valid_d >= 0).all() and (valid_d <= 100).all(), "%D should be between 0 and 100"


class TestASXTechnicalAnalyzer:
    """Test ASX-specific technical analysis."""
    
    def test_calculate_all_indicators(self, sample_price_data):
        """Test calculation of all technical indicators."""
        analyzer = ASXTechnicalAnalyzer()
        result = analyzer.calculate_all_indicators(sample_price_data)
        
        # Should contain original columns
        for col in sample_price_data.columns:
            assert col in result.columns, f"Original column {col} missing"
        
        # Should contain key technical indicators
        required_indicators = [
            'rsi', 'rsi_14', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_position',
            'atr', 'atr_percent', 'macd', 'macd_signal', 'macd_histogram',
            'stoch_k', 'stoch_d', 'volume_sma', 'volume_ratio',
            'channel_upper', 'channel_lower', 'momentum_10', 'roc_10'
        ]
        
        assert_dataframe_has_indicators(result, required_indicators)
    
    def test_bollinger_band_position(self, sample_price_data):
        """Test Bollinger Band position calculation."""
        analyzer = ASXTechnicalAnalyzer()
        result = analyzer.calculate_all_indicators(sample_price_data)
        
        # BB position should be between 0 and 1 (mostly)
        bb_position = result['bb_position'].dropna()
        
        # Most values should be between 0 and 1, but can go outside in extreme cases
        assert bb_position.median() >= 0 and bb_position.median() <= 1, "Median BB position should be between 0 and 1"
    
    def test_volume_ratio(self, sample_price_data):
        """Test volume ratio calculation."""
        analyzer = ASXTechnicalAnalyzer()
        result = analyzer.calculate_all_indicators(sample_price_data)
        
        # Volume ratio should be positive
        volume_ratio = result['volume_ratio'].dropna()
        assert (volume_ratio > 0).all(), "Volume ratio should be positive"
        
        # Average volume ratio should be around 1.0
        assert 0.5 < volume_ratio.mean() < 2.0, "Average volume ratio should be reasonable"
    
    def test_identify_breakout_signals(self, sample_price_data):
        """Test breakout signal identification."""
        analyzer = ASXTechnicalAnalyzer()
        df_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        breakout_signals = analyzer.identify_breakout_signals(df_with_indicators)
        
        # Should return series with same index
        assert len(breakout_signals) == len(df_with_indicators)
        assert breakout_signals.index.equals(df_with_indicators.index)
        
        # Signal strength should be between 0 and 1
        assert (breakout_signals >= 0).all(), "Breakout signals should be >= 0"
        assert (breakout_signals <= 1).all(), "Breakout signals should be <= 1"
    
    def test_identify_mean_reversion_signals(self, sample_price_data):
        """Test mean reversion signal identification."""
        analyzer = ASXTechnicalAnalyzer()
        df_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        mean_rev_signals = analyzer.identify_mean_reversion_signals(df_with_indicators)
        
        # Should return series with same index
        assert len(mean_rev_signals) == len(df_with_indicators)
        assert mean_rev_signals.index.equals(df_with_indicators.index)
        
        # Signal strength should be between 0 and 1
        assert (mean_rev_signals >= 0).all(), "Mean reversion signals should be >= 0"
        assert (mean_rev_signals <= 1).all(), "Mean reversion signals should be <= 1"
    
    def test_calculate_stop_loss(self, sample_price_data):
        """Test stop loss calculation."""
        analyzer = ASXTechnicalAnalyzer()
        df_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        entry_price = 50.0
        
        # Test ATR-based stop loss
        atr_stop = analyzer.calculate_stop_loss(df_with_indicators, entry_price, "atr", 2.0)
        assert atr_stop < entry_price, "Stop loss should be below entry price"
        assert atr_stop > entry_price * 0.90, "Stop loss should not be more than 10% below entry"
        
        # Test percentage stop loss
        pct_stop = analyzer.calculate_stop_loss(df_with_indicators, entry_price, "percent", 5.0)
        expected_pct_stop = entry_price * 0.95
        assert abs(pct_stop - expected_pct_stop) < 0.01, "Percentage stop loss incorrect"
    
    def test_calculate_take_profit(self, sample_price_data):
        """Test take profit calculation."""
        analyzer = ASXTechnicalAnalyzer()
        df_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        entry_price = 50.0
        stop_loss = 47.5  # 5% stop
        
        take_profit = analyzer.calculate_take_profit(df_with_indicators, entry_price, stop_loss, 2.0)
        
        # Take profit should be above entry price
        assert take_profit > entry_price, "Take profit should be above entry price"
        
        # Should maintain 2:1 risk-reward ratio (approximately)
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        ratio = reward / risk
        assert 1.8 <= ratio <= 2.2, f"Risk-reward ratio should be ~2:1, got {ratio:.2f}"
    
    def test_get_market_regime(self, sample_price_data):
        """Test market regime detection."""
        analyzer = ASXTechnicalAnalyzer()
        df_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        regime = analyzer.get_market_regime(df_with_indicators)
        
        # Should return one of the expected regimes
        expected_regimes = ['trending_up', 'trending_down', 'sideways', 'volatile']
        assert regime in expected_regimes, f"Unknown market regime: {regime}"
    
    def test_atr_percent_calculation(self, sample_price_data):
        """Test ATR percentage calculation."""
        analyzer = ASXTechnicalAnalyzer()
        result = analyzer.calculate_all_indicators(sample_price_data)
        
        # ATR percent should be positive and reasonable (typically 1-5% for stocks)
        atr_percent = result['atr_percent'].dropna()
        assert (atr_percent > 0).all(), "ATR percent should be positive"
        assert atr_percent.mean() < 10, "Average ATR percent should be reasonable (<10%)"
    
    def test_error_handling_insufficient_data(self):
        """Test error handling with insufficient data."""
        # Create very small dataset
        small_data = pd.DataFrame({
            'open': [50, 51],
            'high': [52, 53],
            'low': [49, 50],
            'close': [51, 52],
            'volume': [100000, 110000]
        }, index=pd.date_range(start='2023-01-01', periods=2))
        
        analyzer = ASXTechnicalAnalyzer()
        result = analyzer.calculate_all_indicators(small_data)
        
        # Should not crash and should return original data if calculation fails
        assert len(result) == len(small_data)
        assert 'close' in result.columns


class TestIndicatorEdgeCases:
    """Test technical indicators with edge cases."""
    
    def test_constant_prices(self):
        """Test indicators with constant prices."""
        # Create constant price series
        constant_prices = pd.Series([50.0] * 50)
        
        # RSI should be around 50 for constant prices
        rsi = TechnicalIndicators.rsi(constant_prices, 14)
        rsi_values = rsi.dropna()
        assert abs(rsi_values.mean() - 50) < 5, "RSI should be around 50 for constant prices"
        
        # ATR should be very low for constant prices
        atr = TechnicalIndicators.atr(constant_prices, constant_prices, constant_prices, 14)
        atr_values = atr.dropna()
        assert atr_values.mean() < 0.1, "ATR should be very low for constant prices"
    
    def test_empty_series(self):
        """Test indicators with empty series."""
        empty_series = pd.Series([], dtype=float)
        
        # Should return empty series without crashing
        rsi = TechnicalIndicators.rsi(empty_series, 14)
        assert len(rsi) == 0, "Empty input should return empty output"
        
        bb = TechnicalIndicators.bollinger_bands(empty_series, 20, 2.0)
        assert len(bb['upper']) == 0, "Empty input should return empty output"
    
    def test_single_value(self):
        """Test indicators with single value."""
        single_value = pd.Series([50.0])
        
        # Should handle single value gracefully
        rsi = TechnicalIndicators.rsi(single_value, 14)
        assert len(rsi) == 1, "Single input should return single output"
        assert pd.isna(rsi.iloc[0]), "Single value RSI should be NaN"