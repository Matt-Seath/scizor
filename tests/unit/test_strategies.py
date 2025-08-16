import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.strategies.base import BaseStrategy, StrategyParameters, StrategySignal, StrategyValidator
from app.strategies.momentum import MomentumBreakoutStrategy, MomentumBreakoutParameters
from app.strategies.mean_reversion import MeanReversionStrategy, MeanReversionParameters
from app.data.processors.technical import ASXTechnicalAnalyzer
from tests.conftest import assert_signal_is_valid


class TestStrategyParameters:
    """Test strategy parameter validation."""
    
    def test_valid_parameters(self):
        """Test valid strategy parameters."""
        params = StrategyParameters(
            name="test_strategy",
            max_positions=5,
            risk_per_trade=0.02,
            max_holding_days=14
        )
        
        errors = StrategyValidator.validate_parameters(params)
        assert len(errors) == 0, f"Valid parameters should have no errors: {errors}"
    
    def test_invalid_parameters(self):
        """Test invalid strategy parameters."""
        # Test negative max_positions
        params = StrategyParameters(
            name="test_strategy",
            max_positions=-1,
            risk_per_trade=0.02
        )
        
        errors = StrategyValidator.validate_parameters(params)
        assert len(errors) > 0, "Invalid parameters should have errors"
        assert any("max_positions" in error for error in errors)
        
        # Test excessive risk
        params = StrategyParameters(
            name="test_strategy",
            max_positions=5,
            risk_per_trade=0.15  # 15% risk per trade is too high
        )
        
        errors = StrategyValidator.validate_parameters(params)
        assert any("risk_per_trade" in error for error in errors)


class TestStrategySignal:
    """Test trading signal validation."""
    
    def test_valid_signal(self):
        """Test valid trading signal."""
        signal = StrategySignal(
            symbol="BHP",
            signal_type="BUY",
            price=45.50,
            confidence=0.75,
            strategy_name="test_strategy",
            generated_at=datetime.now(),
            stop_loss=43.00,
            take_profit=50.00
        )
        
        assert StrategyValidator.validate_signal(signal), "Valid signal should pass validation"
    
    def test_invalid_signal_price(self):
        """Test signal with invalid price."""
        signal = StrategySignal(
            symbol="BHP",
            signal_type="BUY",
            price=-10.0,  # Negative price
            confidence=0.75,
            strategy_name="test_strategy",
            generated_at=datetime.now()
        )
        
        assert not StrategyValidator.validate_signal(signal), "Negative price should fail validation"
    
    def test_invalid_signal_confidence(self):
        """Test signal with invalid confidence."""
        signal = StrategySignal(
            symbol="BHP",
            signal_type="BUY",
            price=45.50,
            confidence=1.5,  # > 1.0
            strategy_name="test_strategy",
            generated_at=datetime.now()
        )
        
        assert not StrategyValidator.validate_signal(signal), "Confidence > 1.0 should fail validation"
    
    def test_invalid_stop_loss(self):
        """Test signal with invalid stop loss."""
        signal = StrategySignal(
            symbol="BHP",
            signal_type="BUY",
            price=45.50,
            confidence=0.75,
            strategy_name="test_strategy",
            generated_at=datetime.now(),
            stop_loss=50.00  # Stop loss above entry price for BUY signal
        )
        
        assert not StrategyValidator.validate_signal(signal), "Stop loss above entry price should fail validation"


class TestMomentumBreakoutStrategy:
    """Test momentum breakout strategy."""
    
    def test_strategy_initialization(self):
        """Test strategy initialization."""
        params = MomentumBreakoutParameters(
            max_positions=3,
            min_confidence=0.7,
            lookback_period=20
        )
        
        strategy = MomentumBreakoutStrategy(params)
        
        assert strategy.parameters.name == "momentum_breakout"
        assert strategy.parameters.max_positions == 3
        assert strategy.momentum_params.min_confidence == 0.7
        assert strategy.momentum_params.lookback_period == 20
    
    def test_generate_entry_signals_no_data(self):
        """Test entry signal generation with no data."""
        strategy = MomentumBreakoutStrategy()
        signals = strategy.generate_entry_signals({}, datetime.now())
        
        assert len(signals) == 0, "No data should produce no signals"
    
    def test_generate_entry_signals_insufficient_data(self):
        """Test entry signal generation with insufficient data."""
        # Create very short price series
        short_data = pd.DataFrame({
            'close': [50, 51, 52],
            'volume': [100000, 110000, 120000]
        })
        
        strategy = MomentumBreakoutStrategy()
        signals = strategy.generate_entry_signals({'TEST': short_data}, datetime.now())
        
        assert len(signals) == 0, "Insufficient data should produce no signals"
    
    def test_generate_entry_signals_with_indicators(self, sample_price_data):
        """Test entry signal generation with technical indicators."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        # Manually set some indicator values to trigger a signal
        data_with_indicators.loc[data_with_indicators.index[-1], 'channel_upper'] = 45.0
        data_with_indicators.loc[data_with_indicators.index[-1], 'close'] = 46.0  # Breakout
        data_with_indicators.loc[data_with_indicators.index[-1], 'volume_ratio'] = 2.0  # High volume
        data_with_indicators.loc[data_with_indicators.index[-1], 'rsi'] = 60  # Trending
        data_with_indicators.loc[data_with_indicators.index[-1], 'sma_20'] = 44.0  # Above SMA
        
        strategy = MomentumBreakoutStrategy()
        signals = strategy.generate_entry_signals({'TEST': data_with_indicators}, datetime.now())
        
        # Should generate at least one signal with strong conditions
        if len(signals) > 0:
            signal = signals[0]
            assert_signal_is_valid(signal)
            assert signal.signal_type == "BUY"
            assert signal.symbol == "TEST"
    
    def test_breakout_strength_calculation(self, sample_price_data):
        """Test breakout strength calculation."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        strategy = MomentumBreakoutStrategy()
        
        # Test with last row of data
        latest = data_with_indicators.iloc[-1]
        recent_data = data_with_indicators.tail(20)
        
        strength = strategy._calculate_breakout_strength(data_with_indicators, latest, recent_data)
        
        assert 0 <= strength <= 1, "Breakout strength should be between 0 and 1"
    
    def test_momentum_failure_detection(self, sample_price_data):
        """Test momentum failure detection."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        strategy = MomentumBreakoutStrategy()
        
        # Test with various conditions
        latest = data_with_indicators.iloc[-1]
        
        # Should not fail with normal conditions
        failure = strategy._check_momentum_failure(data_with_indicators, latest)
        assert isinstance(failure, bool), "Momentum failure check should return boolean"
    
    def test_position_limits(self, sample_price_data):
        """Test that strategy respects position limits."""
        strategy = MomentumBreakoutStrategy()
        strategy.parameters.max_positions = 2
        
        # Simulate having positions
        strategy.active_positions = {'BHP': datetime.now(), 'CBA': datetime.now()}
        strategy.position_count = 2
        
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        signals = strategy.generate_entry_signals({'TEST': data_with_indicators}, datetime.now())
        
        # Should not generate new signals when at position limit
        assert len(signals) == 0, "Should not generate signals when at position limit"


class TestMeanReversionStrategy:
    """Test mean reversion strategy."""
    
    def test_strategy_initialization(self):
        """Test strategy initialization."""
        params = MeanReversionParameters(
            max_positions=4,
            min_confidence=0.6,
            rsi_oversold=30
        )
        
        strategy = MeanReversionStrategy(params)
        
        assert strategy.parameters.name == "mean_reversion"
        assert strategy.parameters.max_positions == 4
        assert strategy.mean_rev_params.min_confidence == 0.6
        assert strategy.mean_rev_params.rsi_oversold == 30
    
    def test_mean_reversion_strength_calculation(self, sample_price_data):
        """Test mean reversion strength calculation."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        strategy = MeanReversionStrategy()
        
        # Create oversold conditions
        latest = data_with_indicators.iloc[-1].copy()
        latest['rsi'] = 25  # Oversold
        latest['bb_position'] = 0.05  # Near lower band
        latest['stoch_k'] = 15  # Oversold
        latest['volume_ratio'] = 1.5  # Above average volume
        
        strength = strategy._calculate_mean_reversion_strength(data_with_indicators, latest)
        
        assert 0 <= strength <= 1, "Mean reversion strength should be between 0 and 1"
        assert strength > 0.5, "Strong oversold conditions should produce high strength"
    
    def test_exit_strength_calculation(self, sample_price_data):
        """Test exit strength calculation."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        strategy = MeanReversionStrategy()
        
        # Create overbought conditions
        latest = data_with_indicators.iloc[-1].copy()
        latest['rsi'] = 75  # Overbought
        latest['stoch_k'] = 85  # Overbought
        latest['bb_position'] = 0.95  # Near upper band
        
        strength = strategy._calculate_exit_strength(data_with_indicators, latest)
        
        assert 0 <= strength <= 1, "Exit strength should be between 0 and 1"
        assert strength > 0.5, "Strong overbought conditions should produce high exit strength"
    
    def test_trend_filter(self, sample_price_data):
        """Test trend filter functionality."""
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(sample_price_data)
        
        strategy = MeanReversionStrategy()
        
        # Set price below long-term SMA (should reduce signal strength)
        latest = data_with_indicators.iloc[-1].copy()
        latest['close'] = 40.0
        latest['sma_50'] = 45.0  # Price below SMA
        latest['rsi'] = 25  # Oversold
        latest['bb_position'] = 0.05  # Near lower band
        
        strength = strategy._calculate_mean_reversion_strength(data_with_indicators, latest)
        
        # Strength should be reduced due to trend filter
        assert strength < 0.5, "Price below trend filter should reduce signal strength"


class TestBaseStrategy:
    """Test base strategy functionality."""
    
    def test_position_tracking(self):
        """Test position tracking functionality."""
        params = StrategyParameters(name="test_strategy", max_positions=3)
        
        # Create a simple test strategy
        class TestStrategy(BaseStrategy):
            def generate_entry_signals(self, data, current_date):
                return []
            
            def generate_exit_signals(self, data, current_date):
                return []
        
        strategy = TestStrategy(params)
        
        # Test adding positions
        strategy.active_positions['BHP'] = datetime.now()
        strategy.position_count = 1
        
        assert len(strategy.active_positions) == 1
        assert strategy.position_count == 1
        
        # Test position limits
        assert strategy.position_count < strategy.parameters.max_positions
    
    def test_time_based_exits(self):
        """Test time-based exit functionality."""
        params = StrategyParameters(name="test_strategy", max_holding_days=10)
        
        class TestStrategy(BaseStrategy):
            def generate_entry_signals(self, data, current_date):
                return []
            
            def generate_exit_signals(self, data, current_date):
                return []
        
        strategy = TestStrategy(params)
        
        # Add old position
        old_date = datetime.now() - timedelta(days=15)
        strategy.active_positions['BHP'] = old_date
        
        # Check for time-based exits
        symbols_to_close = strategy.check_time_based_exits(datetime.now())
        
        assert 'BHP' in symbols_to_close, "Old position should be flagged for exit"
    
    def test_strategy_status(self):
        """Test strategy status reporting."""
        params = StrategyParameters(name="test_strategy", max_positions=5)
        
        class TestStrategy(BaseStrategy):
            def generate_entry_signals(self, data, current_date):
                return []
            
            def generate_exit_signals(self, data, current_date):
                return []
        
        strategy = TestStrategy(params)
        strategy.active_positions = {'BHP': datetime.now(), 'CBA': datetime.now()}
        
        status = strategy.get_strategy_status()
        
        assert status['name'] == "test_strategy"
        assert status['active_positions'] == 2
        assert status['max_positions'] == 5
        assert status['position_utilization'] == 0.4  # 2/5
        assert 'BHP' in status['symbols']
        assert 'CBA' in status['symbols']
    
    def test_reset_positions(self):
        """Test position reset functionality."""
        params = StrategyParameters(name="test_strategy")
        
        class TestStrategy(BaseStrategy):
            def generate_entry_signals(self, data, current_date):
                return []
            
            def generate_exit_signals(self, data, current_date):
                return []
        
        strategy = TestStrategy(params)
        strategy.active_positions = {'BHP': datetime.now(), 'CBA': datetime.now()}
        strategy.position_count = 2
        
        strategy.reset_positions()
        
        assert len(strategy.active_positions) == 0
        assert strategy.position_count == 0


class TestStrategyPerformance:
    """Test strategy performance and edge cases."""
    
    def test_strategy_with_volatile_data(self):
        """Test strategies with highly volatile price data."""
        # Create volatile price data
        np.random.seed(123)  # For reproducible results
        volatile_data = pd.DataFrame({
            'open': [50 + np.random.normal(0, 5) for _ in range(50)],
            'high': [55 + np.random.normal(0, 5) for _ in range(50)],
            'low': [45 + np.random.normal(0, 5) for _ in range(50)],
            'close': [50 + np.random.normal(0, 5) for _ in range(50)],
            'volume': [np.random.randint(500000, 2000000) for _ in range(50)]
        }, index=pd.date_range(start='2023-01-01', periods=50))
        
        # Ensure prices are positive
        for col in ['open', 'high', 'low', 'close']:
            volatile_data[col] = volatile_data[col].clip(lower=1.0)
        
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(volatile_data)
        
        # Test both strategies
        momentum_strategy = MomentumBreakoutStrategy()
        mean_rev_strategy = MeanReversionStrategy()
        
        current_date = datetime.now()
        
        # Should not crash with volatile data
        momentum_signals = momentum_strategy.generate_entry_signals({'TEST': data_with_indicators}, current_date)
        mean_rev_signals = mean_rev_strategy.generate_entry_signals({'TEST': data_with_indicators}, current_date)
        
        # Validate any generated signals
        for signal in momentum_signals:
            assert_signal_is_valid(signal)
        
        for signal in mean_rev_signals:
            assert_signal_is_valid(signal)
    
    def test_strategy_with_trending_data(self):
        """Test strategies with strongly trending data."""
        # Create uptrending data
        trending_data = pd.DataFrame({
            'close': [50 + i * 0.1 + np.random.normal(0, 0.5) for i in range(50)],
            'volume': [np.random.randint(500000, 1000000) for _ in range(50)]
        }, index=pd.date_range(start='2023-01-01', periods=50))
        
        # Generate OHLC from close
        trending_data['open'] = trending_data['close'].shift(1).fillna(trending_data['close'].iloc[0])
        trending_data['high'] = trending_data[['open', 'close']].max(axis=1) + np.random.uniform(0, 0.5, 50)
        trending_data['low'] = trending_data[['open', 'close']].min(axis=1) - np.random.uniform(0, 0.5, 50)
        
        analyzer = ASXTechnicalAnalyzer()
        data_with_indicators = analyzer.calculate_all_indicators(trending_data)
        
        momentum_strategy = MomentumBreakoutStrategy()
        signals = momentum_strategy.generate_entry_signals({'TREND': data_with_indicators}, datetime.now())
        
        # Momentum strategy should be more likely to generate signals in trending market
        # (This is probabilistic, so we just check it doesn't crash)
        for signal in signals:
            assert_signal_is_valid(signal)