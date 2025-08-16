import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.backtest.engine import (
    BacktestEngine, BacktestConfig, BacktestPosition, BacktestTrade, 
    BacktestMetrics
)
from app.data.models.signals import Signal


class TestBacktestConfig:
    """Test backtest configuration."""
    
    def test_default_config(self):
        """Test default backtest configuration."""
        config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
        
        assert config.initial_capital == 100000.0
        assert config.commission_per_share == 0.002
        assert config.slippage_bps == 5.0
        assert config.max_positions == 5
        assert config.position_sizing_method == "equal_weight"
        assert config.risk_per_trade == 0.02
    
    def test_custom_config(self):
        """Test custom backtest configuration."""
        config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=200000.0,
            commission_per_share=0.001,
            max_positions=10
        )
        
        assert config.initial_capital == 200000.0
        assert config.commission_per_share == 0.001
        assert config.max_positions == 10


class TestBacktestPosition:
    """Test backtest position management."""
    
    def test_position_creation(self):
        """Test position creation."""
        position = BacktestPosition(
            symbol="BHP",
            entry_date=datetime(2023, 6, 15),
            entry_price=45.50,
            quantity=100,
            side="LONG"
        )
        
        assert position.symbol == "BHP"
        assert position.entry_price == 45.50
        assert position.quantity == 100
        assert position.side == "LONG"
        assert position.unrealized_pnl == 0.0
    
    def test_pnl_calculation_long(self):
        """Test P&L calculation for long position."""
        position = BacktestPosition(
            symbol="BHP",
            entry_date=datetime(2023, 6, 15),
            entry_price=45.50,
            quantity=100,
            side="LONG"
        )
        
        # Test profit
        pnl = position.update_pnl(47.00)
        expected_pnl = (47.00 - 45.50) * 100
        assert pnl == expected_pnl
        assert position.unrealized_pnl == expected_pnl
        
        # Test loss
        pnl = position.update_pnl(44.00)
        expected_pnl = (44.00 - 45.50) * 100
        assert pnl == expected_pnl
        assert position.unrealized_pnl == expected_pnl
    
    def test_pnl_calculation_short(self):
        """Test P&L calculation for short position."""
        position = BacktestPosition(
            symbol="BHP",
            entry_date=datetime(2023, 6, 15),
            entry_price=45.50,
            quantity=100,
            side="SHORT"
        )
        
        # Test profit (price goes down)
        pnl = position.update_pnl(44.00)
        expected_pnl = (45.50 - 44.00) * 100
        assert pnl == expected_pnl
        assert position.unrealized_pnl == expected_pnl
        
        # Test loss (price goes up)
        pnl = position.update_pnl(47.00)
        expected_pnl = (45.50 - 47.00) * 100
        assert pnl == expected_pnl
        assert position.unrealized_pnl == expected_pnl


class TestBacktestEngine:
    """Test backtesting engine."""
    
    def test_engine_initialization(self, backtest_config):
        """Test engine initialization."""
        engine = BacktestEngine(backtest_config)
        
        assert engine.config == backtest_config
        assert engine.portfolio_value == backtest_config.initial_capital
        assert engine.cash == backtest_config.initial_capital
        assert len(engine.positions) == 0
        assert len(engine.completed_trades) == 0
    
    def test_load_price_data(self, backtest_config, multiple_stock_data):
        """Test loading price data."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data(multiple_stock_data)
        
        assert len(engine.price_data) == len(multiple_stock_data)
        
        for symbol in multiple_stock_data.keys():
            assert symbol in engine.price_data
    
    def test_get_price(self, backtest_config, sample_price_data):
        """Test getting price for specific date."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'TEST': sample_price_data})
        
        # Test valid date
        test_date = sample_price_data.index[10]
        price = engine.get_price('TEST', test_date)
        expected_price = sample_price_data.loc[test_date, 'close']
        assert price == expected_price
        
        # Test invalid symbol
        price = engine.get_price('INVALID', test_date)
        assert price is None
        
        # Test invalid date
        invalid_date = datetime(2025, 1, 1)
        price = engine.get_price('TEST', invalid_date)
        assert price is None
    
    def test_position_sizing_equal_weight(self, backtest_config):
        """Test equal weight position sizing."""
        engine = BacktestEngine(backtest_config)
        
        signal_price = 50.0
        quantity = engine.calculate_position_size('TEST', signal_price)
        
        # Should be portfolio_value / max_positions / price
        expected_quantity = int(engine.portfolio_value / engine.config.max_positions / signal_price)
        assert quantity == expected_quantity
    
    def test_position_sizing_kelly(self, backtest_config):
        """Test Kelly criterion position sizing."""
        config = backtest_config
        config.position_sizing_method = "kelly"
        engine = BacktestEngine(config)
        
        signal_price = 50.0
        stop_loss = 47.5  # 5% stop
        quantity = engine.calculate_position_size('TEST', signal_price, stop_loss)
        
        # Should calculate based on risk amount
        risk_amount = engine.portfolio_value * engine.config.risk_per_trade
        risk_per_share = abs(signal_price - stop_loss)
        expected_quantity = int(risk_amount / risk_per_share)
        assert quantity == expected_quantity
    
    def test_commission_calculation(self, backtest_config):
        """Test commission calculation."""
        engine = BacktestEngine(backtest_config)
        
        price = 50.0
        quantity = 100
        commission = engine.calculate_commission(price, quantity)
        
        expected_commission = backtest_config.commission_per_share * quantity
        assert commission == expected_commission
    
    def test_slippage_calculation(self, backtest_config):
        """Test slippage calculation."""
        engine = BacktestEngine(backtest_config)
        
        price = 50.0
        slippage_bps = backtest_config.slippage_bps
        
        # Test buy slippage (higher price)
        buy_price = engine.calculate_slippage(price, "BUY")
        expected_buy_price = price * (1 + slippage_bps / 10000)
        assert buy_price == expected_buy_price
        
        # Test sell slippage (lower price)
        sell_price = engine.calculate_slippage(price, "SELL")
        expected_sell_price = price * (1 - slippage_bps / 10000)
        assert sell_price == expected_sell_price
    
    def test_can_open_position(self, backtest_config):
        """Test position opening validation."""
        engine = BacktestEngine(backtest_config)
        
        # Should be able to open position initially
        assert engine.can_open_position('BHP') == True
        
        # Add position
        engine.positions['BHP'] = BacktestPosition(
            symbol='BHP',
            entry_date=datetime.now(),
            entry_price=50.0,
            quantity=100,
            side='LONG'
        )
        
        # Should not be able to open another position in same symbol
        assert engine.can_open_position('BHP') == False
        
        # Should still be able to open position in different symbol
        assert engine.can_open_position('CBA') == True
        
        # Fill up to max positions
        for i, symbol in enumerate(['CBA', 'CSL', 'ANZ', 'WBC'], 1):
            engine.positions[symbol] = BacktestPosition(
                symbol=symbol,
                entry_date=datetime.now(),
                entry_price=50.0,
                quantity=100,
                side='LONG'
            )
        
        # Should not be able to open more positions
        assert engine.can_open_position('NAB') == False
    
    def test_signal_execution_buy(self, backtest_config, sample_price_data):
        """Test buy signal execution."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Create buy signal
        signal = Signal(
            symbol='BHP',
            strategy='test',
            signal_type='BUY',
            price=50.0,
            confidence=0.8,
            generated_at=datetime(2023, 6, 15)
        )
        
        current_date = datetime(2023, 6, 15)
        success = engine.execute_signal(signal, current_date)
        
        assert success == True
        assert 'BHP' in engine.positions
        assert engine.cash < backtest_config.initial_capital
    
    def test_signal_execution_insufficient_cash(self, backtest_config, sample_price_data):
        """Test signal execution with insufficient cash."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        engine.cash = 100  # Very low cash
        
        signal = Signal(
            symbol='BHP',
            strategy='test',
            signal_type='BUY',
            price=50.0,
            confidence=0.8,
            generated_at=datetime(2023, 6, 15)
        )
        
        current_date = datetime(2023, 6, 15)
        success = engine.execute_signal(signal, current_date)
        
        assert success == False
        assert 'BHP' not in engine.positions
    
    def test_position_close(self, backtest_config, sample_price_data):
        """Test position closing."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Add position manually
        entry_price = 50.0
        quantity = 100
        engine.positions['BHP'] = BacktestPosition(
            symbol='BHP',
            entry_date=datetime(2023, 6, 15),
            entry_price=entry_price,
            quantity=quantity,
            side='LONG'
        )
        
        # Reduce cash to simulate position opening
        position_cost = entry_price * quantity + engine.calculate_commission(entry_price, quantity)
        engine.cash -= position_cost
        initial_cash = engine.cash
        
        # Close position at profit
        exit_price = 55.0
        current_date = datetime(2023, 6, 20)
        success = engine._close_position('BHP', exit_price, current_date, 'SIGNAL')
        
        assert success == True
        assert 'BHP' not in engine.positions
        assert len(engine.completed_trades) == 1
        assert engine.cash > initial_cash  # Should have made profit
        
        # Check trade record
        trade = engine.completed_trades[0]
        assert trade.symbol == 'BHP'
        assert trade.entry_price == entry_price
        assert trade.pnl > 0  # Should be profitable
    
    def test_update_positions(self, backtest_config, sample_price_data):
        """Test position updates with price changes."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Add position with stop loss
        entry_date = sample_price_data.index[10]
        entry_price = sample_price_data.loc[entry_date, 'close']
        stop_loss = entry_price * 0.80  # 20% stop loss (much lower to avoid random triggering)
        
        position = BacktestPosition(
            symbol='BHP',
            entry_date=entry_date,
            entry_price=entry_price,
            quantity=100,
            side='LONG',
            stop_loss=stop_loss
        )
        engine.positions['BHP'] = position
        
        # Update positions with current price above stop loss
        current_date = sample_price_data.index[15]
        engine.update_positions(current_date)
        
        # Position should still be open
        assert 'BHP' in engine.positions
        
        # Test with price that would trigger stop loss
        # Manually set a low price in the data
        test_date = sample_price_data.index[20]
        low_price = stop_loss - 1.0  # Below stop loss
        sample_price_data.loc[test_date, 'close'] = low_price
        
        engine.update_positions(test_date)
        
        # Position should be closed due to stop loss
        assert 'BHP' not in engine.positions
        assert len(engine.completed_trades) == 1
        assert engine.completed_trades[0].exit_reason == 'STOP_LOSS'
    
    def test_calculate_portfolio_value(self, backtest_config, sample_price_data):
        """Test portfolio value calculation."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Initial portfolio value should equal cash
        test_date = sample_price_data.index[10]
        portfolio_value = engine.calculate_portfolio_value(test_date)
        assert portfolio_value == engine.cash
        
        # Add position
        entry_price = sample_price_data.loc[test_date, 'close']
        quantity = 100
        position = BacktestPosition(
            symbol='BHP',
            entry_date=test_date,
            entry_price=entry_price,
            quantity=quantity,
            side='LONG'
        )
        engine.positions['BHP'] = position
        
        # Reduce cash to simulate position cost
        position_cost = entry_price * quantity
        engine.cash -= position_cost
        
        # Portfolio value should now include position value
        current_date = sample_price_data.index[15]
        current_price = sample_price_data.loc[current_date, 'close']
        portfolio_value = engine.calculate_portfolio_value(current_date)
        
        expected_value = engine.cash + (current_price * quantity)
        assert abs(portfolio_value - expected_value) < 0.01
    
    def test_run_backtest_simple(self, backtest_config, sample_price_data):
        """Test running a simple backtest."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Create simple signals
        signals = []
        
        # Buy signal
        buy_signal = Signal(
            symbol='BHP',
            strategy='test',
            signal_type='BUY',
            price=sample_price_data.iloc[10]['close'],
            confidence=0.8,
            generated_at=sample_price_data.index[10]
        )
        signals.append(buy_signal)
        
        # Sell signal
        sell_signal = Signal(
            symbol='BHP',
            strategy='test',
            signal_type='SELL',
            price=sample_price_data.iloc[20]['close'],
            confidence=0.8,
            generated_at=sample_price_data.index[20]
        )
        signals.append(sell_signal)
        
        # Run backtest
        metrics = engine.run_backtest(signals)
        
        # Should have completed at least one trade
        assert len(engine.completed_trades) >= 1
        assert len(engine.daily_portfolio_values) > 0
        
        # Metrics should be calculated
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_trades >= 1


class TestBacktestMetrics:
    """Test backtest metrics calculation."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = BacktestMetrics()
        
        assert metrics.total_return == 0.0
        assert metrics.annual_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.win_rate == 0.0
        assert metrics.total_trades == 0
    
    def test_metrics_calculation_empty_trades(self, backtest_config):
        """Test metrics calculation with no trades."""
        engine = BacktestEngine(backtest_config)
        metrics = engine._calculate_metrics()
        
        # All metrics should be zero or default values
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 0.0


class TestBacktestTrade:
    """Test completed trade representation."""
    
    def test_trade_creation(self):
        """Test trade creation."""
        trade = BacktestTrade(
            symbol='BHP',
            strategy='momentum',
            side='LONG',
            entry_date=datetime(2023, 6, 15),
            exit_date=datetime(2023, 6, 20),
            entry_price=50.0,
            exit_price=55.0,
            quantity=100,
            commission=0.4,
            pnl=450.0,  # (55-50)*100 - 0.4 = 500 - 0.4
            return_pct=9.0,  # Approximately 9% return
            holding_days=5,
            exit_reason='SIGNAL'
        )
        
        assert trade.symbol == 'BHP'
        assert trade.pnl == 450.0
        assert trade.return_pct == 9.0
        assert trade.holding_days == 5
        assert trade.exit_reason == 'SIGNAL'


class TestBacktestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_price_data(self, backtest_config):
        """Test backtest with empty price data."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({})
        
        signals = []
        metrics = engine.run_backtest(signals)
        
        # Should complete without error
        assert metrics.total_trades == 0
        assert len(engine.completed_trades) == 0
    
    def test_invalid_signal_symbol(self, backtest_config, sample_price_data):
        """Test signal for symbol not in price data."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Signal for symbol not in data
        signal = Signal(
            symbol='INVALID',
            strategy='test',
            signal_type='BUY',
            price=50.0,
            confidence=0.8,
            generated_at=datetime(2023, 6, 15)
        )
        
        success = engine.execute_signal(signal, datetime(2023, 6, 15))
        assert success == False
    
    def test_sell_signal_without_position(self, backtest_config, sample_price_data):
        """Test sell signal when no position exists."""
        engine = BacktestEngine(backtest_config)
        engine.load_price_data({'BHP': sample_price_data})
        
        # Sell signal without position
        signal = Signal(
            symbol='BHP',
            strategy='test',
            signal_type='SELL',
            price=50.0,
            confidence=0.8,
            generated_at=datetime(2023, 6, 15)
        )
        
        success = engine.execute_signal(signal, datetime(2023, 6, 15))
        assert success == False
    
    def test_extreme_slippage(self):
        """Test with extreme slippage settings."""
        config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            slippage_bps=1000  # 10% slippage (extreme)
        )
        
        engine = BacktestEngine(config)
        
        price = 50.0
        buy_price = engine.calculate_slippage(price, "BUY")
        sell_price = engine.calculate_slippage(price, "SELL")
        
        # Should still calculate correctly even with extreme values
        assert buy_price > price
        assert sell_price < price
        assert abs(buy_price - price) == abs(sell_price - price)