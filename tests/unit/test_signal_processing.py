import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.data.processors.signals import SignalProcessor, SignalValidator
from app.strategies.base import StrategySignal
from app.strategies.momentum import MomentumBreakoutStrategy, MomentumBreakoutParameters
from app.strategies.mean_reversion import MeanReversionStrategy, MeanReversionParameters
from app.data.models.signals import Signal
from tests.conftest import assert_signal_is_valid


class TestSignalProcessor:
    """Test signal processing functionality."""
    
    def test_processor_initialization(self):
        """Test signal processor initialization."""
        processor = SignalProcessor()
        
        # Should have default strategies
        assert 'momentum' in processor.strategies
        assert 'mean_reversion' in processor.strategies
        
        # Should have analyzer and validator
        assert processor.analyzer is not None
        assert processor.validator is not None
    
    def test_add_remove_strategy(self):
        """Test adding and removing custom strategies."""
        processor = SignalProcessor()
        
        # Create custom strategy
        custom_params = MomentumBreakoutParameters(name="custom_momentum")
        custom_strategy = MomentumBreakoutStrategy(custom_params)
        
        # Add strategy
        processor.add_strategy("custom", custom_strategy)
        assert "custom" in processor.strategies
        
        # Remove strategy
        processor.remove_strategy("custom")
        assert "custom" not in processor.strategies
    
    def test_enable_disable_strategy(self):
        """Test enabling and disabling strategies."""
        processor = SignalProcessor()
        
        # Disable strategy
        processor.disable_strategy("momentum")
        assert not processor.strategies["momentum"].parameters.enabled
        
        # Enable strategy
        processor.enable_strategy("momentum")
        assert processor.strategies["momentum"].parameters.enabled
    
    @pytest.mark.asyncio
    async def test_generate_signals_no_data(self):
        """Test signal generation with no data."""
        processor = SignalProcessor()
        
        signals = await processor.generate_signals({}, datetime.now())
        
        assert len(signals) == 0
    
    @pytest.mark.asyncio
    async def test_generate_signals_with_data(self, multiple_stock_data):
        """Test signal generation with market data."""
        processor = SignalProcessor()
        
        current_date = datetime.now()
        signals = await processor.generate_signals(multiple_stock_data, current_date)
        
        # Should return list of signals (may be empty)
        assert isinstance(signals, list)
        
        # Validate any generated signals
        for signal in signals:
            assert_signal_is_valid(signal)
    
    def test_prepare_technical_data(self, multiple_stock_data):
        """Test technical data preparation."""
        processor = SignalProcessor()
        
        processed_data = processor._prepare_technical_data(multiple_stock_data)
        
        # Should have same symbols
        assert set(processed_data.keys()) == set(multiple_stock_data.keys())
        
        # Should have technical indicators added
        for symbol, df in processed_data.items():
            # Should contain original columns
            original_cols = multiple_stock_data[symbol].columns
            for col in original_cols:
                assert col in df.columns
            
            # Should contain some technical indicators
            assert 'rsi' in df.columns
            assert 'sma_20' in df.columns
    
    def test_resolve_signal_conflicts_no_conflicts(self, sample_signals):
        """Test signal conflict resolution with no conflicts."""
        processor = SignalProcessor()
        
        # Signals for different symbols - no conflicts
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now()),
            StrategySignal('CBA', 'BUY', 100.0, 0.7, 'mean_reversion', datetime.now())
        ]
        
        resolved = processor._resolve_signal_conflicts(signals)
        
        # Should return all signals since no conflicts
        assert len(resolved) == 2
    
    def test_resolve_signal_conflicts_exit_priority(self):
        """Test that exit signals take priority over entry signals."""
        processor = SignalProcessor()
        
        # Conflicting signals for same symbol
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now()),
            StrategySignal('BHP', 'SELL', 49.0, 0.6, 'mean_reversion', datetime.now())
        ]
        
        resolved = processor._resolve_signal_conflicts(signals)
        
        # Should return only the SELL signal
        assert len(resolved) == 1
        assert resolved[0].signal_type == 'SELL'
    
    def test_resolve_signal_conflicts_confidence_priority(self):
        """Test that higher confidence signals take priority."""
        processor = SignalProcessor()
        
        # Multiple BUY signals for same symbol
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.6, 'momentum', datetime.now()),
            StrategySignal('BHP', 'BUY', 50.5, 0.9, 'mean_reversion', datetime.now())
        ]
        
        resolved = processor._resolve_signal_conflicts(signals)
        
        # Should return the higher confidence signal
        assert len(resolved) == 1
        assert resolved[0].confidence == 0.9
        assert resolved[0].strategy_name == 'mean_reversion'
    
    def test_summarize_signals(self):
        """Test signal summarization."""
        processor = SignalProcessor()
        
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now()),
            StrategySignal('CBA', 'BUY', 100.0, 0.7, 'momentum', datetime.now()),
            StrategySignal('CSL', 'SELL', 200.0, 0.9, 'mean_reversion', datetime.now())
        ]
        
        summary = processor._summarize_signals(signals)
        
        assert summary['total_signals'] == 3
        assert summary['buy_signals'] == 2
        assert summary['sell_signals'] == 1
        assert summary['avg_confidence'] == (0.8 + 0.7 + 0.9) / 3
        assert summary['strategy_breakdown']['momentum'] == 2
        assert summary['strategy_breakdown']['mean_reversion'] == 1
        assert 'BHP' in summary['symbols']
        assert 'CBA' in summary['symbols']
        assert 'CSL' in summary['symbols']
    
    @pytest.mark.asyncio
    async def test_save_signals_to_db(self, db_session):
        """Test saving signals to database."""
        processor = SignalProcessor()
        
        strategy_signals = [
            StrategySignal(
                symbol='BHP',
                signal_type='BUY',
                price=50.0,
                confidence=0.8,
                strategy_name='momentum',
                generated_at=datetime.now(),
                metadata={'test': 'data'}
            )
        ]
        
        saved_signals = await processor.save_signals_to_db(strategy_signals, db_session)
        
        assert len(saved_signals) == 1
        assert saved_signals[0].symbol == 'BHP'
        assert saved_signals[0].signal_type == 'BUY'
        assert saved_signals[0].strategy == 'momentum'
        assert saved_signals[0].status == 'PENDING'
    
    def test_get_strategy_status(self):
        """Test getting strategy status."""
        processor = SignalProcessor()
        
        status = processor.get_strategy_status()
        
        assert 'momentum' in status
        assert 'mean_reversion' in status
        
        # Each strategy should have status information
        for strategy_name, strategy_status in status.items():
            assert 'name' in strategy_status
            assert 'enabled' in strategy_status
            assert 'active_positions' in strategy_status
            assert 'max_positions' in strategy_status
    
    def test_reset_all_strategies(self):
        """Test resetting all strategies."""
        processor = SignalProcessor()
        
        # Add some mock positions
        processor.strategies['momentum'].active_positions = {'BHP': datetime.now()}
        processor.strategies['mean_reversion'].active_positions = {'CBA': datetime.now()}
        
        processor.reset_all_strategies()
        
        # All strategies should have no positions
        for strategy in processor.strategies.values():
            assert len(strategy.active_positions) == 0


class TestSignalValidator:
    """Test signal validation functionality."""
    
    def test_validate_market_conditions_sufficient_liquidity(self, multiple_stock_data):
        """Test market condition validation with sufficient liquidity."""
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now())
        ]
        
        # Ensure sufficient volume
        for symbol, df in multiple_stock_data.items():
            df.loc[df.index[-1], 'volume'] = 1000000  # High volume
        
        validated = SignalValidator.validate_market_conditions(signals, multiple_stock_data)
        
        # Should pass validation
        assert len(validated) == 1
    
    def test_validate_market_conditions_insufficient_liquidity(self, multiple_stock_data):
        """Test market condition validation with insufficient liquidity."""
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now())
        ]
        
        # Set very low volume
        for symbol, df in multiple_stock_data.items():
            df.loc[df.index[-1], 'volume'] = 10  # Very low volume
        
        validated = SignalValidator.validate_market_conditions(signals, multiple_stock_data)
        
        # Should fail validation due to low liquidity
        assert len(validated) == 0
    
    def test_validate_market_conditions_extreme_gap(self, multiple_stock_data):
        """Test market condition validation with extreme price gap."""
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now())
        ]
        
        # Create extreme gap
        df = multiple_stock_data['BHP']
        if len(df) >= 2:
            df.loc[df.index[-1], 'open'] = df.iloc[-2]['close'] * 1.20  # 20% gap up
            df.loc[df.index[-1], 'close'] = 50.0
        
        validated = SignalValidator.validate_market_conditions(signals, multiple_stock_data)
        
        # Should fail validation due to extreme gap
        assert len(validated) == 0
    
    def test_validate_market_conditions_extreme_volume(self, multiple_stock_data):
        """Test market condition validation with extreme volume spike."""
        signals = [
            StrategySignal('BHP', 'BUY', 50.0, 0.8, 'momentum', datetime.now())
        ]
        
        # Set normal volume first, then extreme spike
        df = multiple_stock_data['BHP']
        normal_volume = 500000
        df.loc[df.index[:-1], 'volume'] = normal_volume
        
        # Calculate volume ratio manually and set extreme spike
        df.loc[df.index[-1], 'volume'] = normal_volume * 15  # 15x normal volume
        df.loc[df.index[-1], 'volume_ratio'] = 15.0
        
        validated = SignalValidator.validate_market_conditions(signals, multiple_stock_data)
        
        # Should fail validation due to extreme volume
        assert len(validated) == 0
    
    def test_validate_market_conditions_missing_symbol(self):
        """Test market condition validation with missing symbol data."""
        signals = [
            StrategySignal('MISSING', 'BUY', 50.0, 0.8, 'momentum', datetime.now())
        ]
        
        market_data = {'BHP': pd.DataFrame()}  # No data for 'MISSING' symbol
        
        validated = SignalValidator.validate_market_conditions(signals, market_data)
        
        # Should fail validation due to missing data
        assert len(validated) == 0


class TestSignalProcessorIntegration:
    """Test signal processor integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_disabled_strategy_no_signals(self, multiple_stock_data):
        """Test that disabled strategies don't generate signals."""
        processor = SignalProcessor()
        
        # Disable all strategies
        processor.disable_strategy('momentum')
        processor.disable_strategy('mean_reversion')
        
        signals = await processor.generate_signals(multiple_stock_data, datetime.now())
        
        # Should generate no signals
        assert len(signals) == 0
    
    @pytest.mark.asyncio
    async def test_single_strategy_enabled(self, multiple_stock_data):
        """Test with only one strategy enabled."""
        processor = SignalProcessor()
        
        # Disable mean reversion, keep momentum
        processor.disable_strategy('mean_reversion')
        
        signals = await processor.generate_signals(multiple_stock_data, datetime.now())
        
        # All signals should be from momentum strategy
        for signal in signals:
            assert signal.strategy_name == 'momentum_breakout'
    
    def test_strategy_position_limits_respected(self, multiple_stock_data):
        """Test that strategy position limits are respected."""
        processor = SignalProcessor()
        
        # Set very low position limits
        momentum_strategy = processor.strategies['momentum']
        momentum_strategy.parameters.max_positions = 1
        
        # Simulate having a position
        momentum_strategy.active_positions = {'BHP': datetime.now()}
        momentum_strategy.position_count = 1
        
        # Try to generate signals
        current_date = datetime.now()
        entry_signals = momentum_strategy.generate_entry_signals(multiple_stock_data, current_date)
        
        # Should not generate entry signals when at position limit
        assert len(entry_signals) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_in_signal_generation(self, multiple_stock_data):
        """Test error handling during signal generation."""
        processor = SignalProcessor()
        
        # Mock strategy to raise exception
        with patch.object(processor.strategies['momentum'], 'get_all_signals', 
                         side_effect=Exception("Test error")):
            
            signals = await processor.generate_signals(multiple_stock_data, datetime.now())
            
            # Should handle error gracefully and continue with other strategies
            # May still get signals from mean_reversion strategy
            assert isinstance(signals, list)
    
    def test_signal_conflict_resolution_complex(self):
        """Test complex signal conflict resolution scenarios."""
        processor = SignalProcessor()
        
        # Multiple signals for same symbol with different types and confidences
        current_time = datetime.now()
        signals = [
            # BUY signals with different confidences
            StrategySignal('BHP', 'BUY', 50.0, 0.7, 'momentum', current_time),
            StrategySignal('BHP', 'BUY', 50.5, 0.8, 'mean_reversion', current_time),
            # SELL signal (should take priority)
            StrategySignal('BHP', 'SELL', 49.0, 0.6, 'exit_strategy', current_time),
            # Signals for different symbol (no conflict)
            StrategySignal('CBA', 'BUY', 100.0, 0.9, 'momentum', current_time),
        ]
        
        resolved = processor._resolve_signal_conflicts(signals)
        
        # Should have 2 signals: SELL for BHP (priority) and BUY for CBA
        assert len(resolved) == 2
        
        # Find signals by symbol
        bhp_signal = next(s for s in resolved if s.symbol == 'BHP')
        cba_signal = next(s for s in resolved if s.symbol == 'CBA')
        
        assert bhp_signal.signal_type == 'SELL'  # Exit signal won
        assert cba_signal.signal_type == 'BUY'
        assert cba_signal.confidence == 0.9


class TestSignalProcessorPerformance:
    """Test signal processor performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_signal_generation_with_many_symbols(self):
        """Test signal generation performance with many symbols."""
        processor = SignalProcessor()
        
        # Create data for many symbols
        many_symbols_data = {}
        base_data = pd.DataFrame({
            'open': [50.0] * 50,
            'high': [51.0] * 50,
            'low': [49.0] * 50,
            'close': [50.5] * 50,
            'volume': [500000] * 50
        }, index=pd.date_range(start='2023-01-01', periods=50))
        
        # Create 50 symbols
        for i in range(50):
            symbol = f'TEST{i:02d}'
            # Slightly modify data for each symbol
            symbol_data = base_data.copy()
            symbol_data['close'] = symbol_data['close'] * (0.9 + i * 0.001)
            many_symbols_data[symbol] = symbol_data
        
        # Time signal generation
        import time
        start_time = time.time()
        
        signals = await processor.generate_signals(many_symbols_data, datetime.now())
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (< 5 seconds as per requirements)
        assert processing_time < 5.0, f"Signal generation took too long: {processing_time:.2f}s"
        
        # Should return valid signals
        assert isinstance(signals, list)
        for signal in signals:
            assert_signal_is_valid(signal)
    
    def test_technical_indicator_caching(self, multiple_stock_data):
        """Test that technical indicators are calculated efficiently."""
        processor = SignalProcessor()
        
        # Process data multiple times
        import time
        
        # First time (cold)
        start_time = time.time()
        processed_data_1 = processor._prepare_technical_data(multiple_stock_data)
        first_time = time.time() - start_time
        
        # Second time (should be similar since we're not caching between calls)
        start_time = time.time()
        processed_data_2 = processor._prepare_technical_data(multiple_stock_data)
        second_time = time.time() - start_time
        
        # Both should complete reasonably quickly
        assert first_time < 2.0, f"First indicator calculation too slow: {first_time:.2f}s"
        assert second_time < 2.0, f"Second indicator calculation too slow: {second_time:.2f}s"
        
        # Results should be identical
        for symbol in multiple_stock_data.keys():
            pd.testing.assert_frame_equal(
                processed_data_1[symbol], 
                processed_data_2[symbol], 
                check_dtype=False
            )