# Backtesting System

The backtesting system allows you to test trading strategies against historical market data to evaluate their performance before deploying them in live trading.

## Overview

The backtesting framework consists of several key components:

- **Strategy Framework**: Base classes and utilities for creating trading strategies
- **Backtesting Engine**: Core engine that simulates trading with historical data
- **Portfolio Management**: Tracks positions, trades, and performance metrics
- **Technical Indicators**: Library of common technical analysis indicators
- **Validation**: Ensures strategies are properly implemented and configured

## Quick Start

### 1. Create a Strategy

```python
from shared.strategy import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from shared.strategy.indicators import TechnicalIndicators

class MyStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.short_window = config.parameters.get('short_window', 20)
        self.long_window = config.parameters.get('long_window', 50)
    
    def initialize(self, symbols, start_date, end_date):
        super().initialize(symbols, start_date, end_date)
        # Strategy-specific initialization
    
    def generate_signals(self, data, timestamp, portfolio_state):
        signals = []
        for symbol in self.symbols:
            # Your trading logic here
            # Example: Moving average crossover
            df = data[symbol]
            short_ma = TechnicalIndicators.sma(df['close'], self.short_window)
            long_ma = TechnicalIndicators.sma(df['close'], self.long_window)
            
            if short_ma.iloc[-1] > long_ma.iloc[-1]:
                signal = StrategySignal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=df['close'].iloc[-1],
                    quantity=100,
                    timestamp=timestamp
                )
                signals.append(signal)
        
        return signals
    
    def update_state(self, data, timestamp, portfolio_state):
        super().update_state(data, timestamp, portfolio_state)
        # Update any internal state
```

### 2. Configure and Run Backtest

```python
from services.backtester.engine import BacktestEngine
from shared.database.connection import DatabaseConnection
from shared.strategy.base import StrategyConfig
from datetime import datetime, timedelta
from decimal import Decimal

# Initialize database and engine
db = DatabaseConnection(config)
engine = BacktestEngine(db)

# Configure strategy
config = StrategyConfig(
    name="My Strategy",
    description="Example strategy",
    parameters={'short_window': 20, 'long_window': 50},
    max_position_size=Decimal('0.1'),
    risk_per_trade=Decimal('0.02')
)

# Create strategy
strategy = MyStrategy(config)

# Run backtest
result = engine.run_backtest(
    strategy=strategy,
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_capital=Decimal('100000')
)

# View results
print(f"Total Return: {result.total_return_pct:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.3f}")
print(f"Max Drawdown: {result.max_drawdown_pct:.2%}")
```

## Strategy Development

### Base Strategy Class

All strategies must inherit from `BaseStrategy` and implement three key methods:

- `initialize()`: Set up strategy state and parameters
- `generate_signals()`: Generate trading signals based on market data
- `update_state()`: Update internal strategy state

### Strategy Configuration

Use `StrategyConfig` to define strategy parameters:

```python
config = StrategyConfig(
    name="Strategy Name",
    description="Strategy description",
    parameters={
        'param1': value1,
        'param2': value2
    },
    max_position_size=Decimal('0.2'),    # Max 20% in single position
    max_positions=5,                      # Max 5 concurrent positions
    risk_per_trade=Decimal('0.02'),      # Risk 2% per trade
    stop_loss_pct=Decimal('0.05'),       # 5% stop loss
    take_profit_pct=Decimal('0.10'),     # 10% take profit
    lookback_period=50,                   # Days of historical data needed
    rebalance_frequency='daily'           # Rebalancing frequency
)
```

### Signal Generation

Generate trading signals using the `StrategySignal` class:

```python
signal = StrategySignal(
    symbol="AAPL",
    signal_type=SignalType.BUY,           # BUY or SELL
    price=Decimal('150.00'),              # Current market price
    quantity=100,                         # Number of shares
    timestamp=datetime.now(),
    confidence=0.8,                       # Signal confidence (0-1)
    order_type=OrderType.MARKET,          # MARKET, LIMIT, STOP, etc.
    reason="Moving average crossover"     # Optional reason
)
```

## Technical Indicators

The framework includes a comprehensive library of technical indicators:

```python
from shared.strategy.indicators import TechnicalIndicators

# Moving averages
sma = TechnicalIndicators.sma(prices, period=20)
ema = TechnicalIndicators.ema(prices, period=20)

# Oscillators
rsi = TechnicalIndicators.rsi(prices, period=14)
stoch = TechnicalIndicators.stochastic(high, low, close, k_period=14)

# Volatility
bb_upper, bb_middle, bb_lower = TechnicalIndicators.bollinger_bands(prices)
atr = TechnicalIndicators.atr(high, low, close, period=14)

# Trend
macd, signal, histogram = TechnicalIndicators.macd(prices)
adx = TechnicalIndicators.adx(high, low, close, period=14)
```

## Portfolio Management

The portfolio management system tracks positions and performance:

```python
from shared.strategy.portfolio import Portfolio

portfolio = Portfolio(initial_capital=100000)

# Add position
portfolio.add_position('AAPL', quantity=100, price=150.00, timestamp=datetime.now())

# Remove position
portfolio.remove_position('AAPL', quantity=50, price=155.00, timestamp=datetime.now())

# Get portfolio metrics
total_value = portfolio.get_total_value()
total_pnl = portfolio.get_total_pnl()
```

## Example Strategies

The system includes several example strategies:

### Moving Average Crossover

```python
from services.backtester.strategies import MovingAverageCrossoverStrategy

config = StrategyConfig(
    name="MA Crossover",
    parameters={
        'short_window': 20,
        'long_window': 50,
        'position_size_pct': 0.1
    }
)

strategy = MovingAverageCrossoverStrategy(config)
```

### Mean Reversion (RSI)

```python
from services.backtester.strategies import MeanReversionStrategy

config = StrategyConfig(
    name="RSI Mean Reversion",
    parameters={
        'rsi_period': 14,
        'oversold_threshold': 30,
        'overbought_threshold': 70,
        'position_size_pct': 0.05
    }
)

strategy = MeanReversionStrategy(config)
```

### Buy and Hold

```python
from services.backtester.strategies import BuyAndHoldStrategy

config = StrategyConfig(
    name="Buy and Hold",
    parameters={
        'allocation_per_symbol': 0.9
    }
)

strategy = BuyAndHoldStrategy(config)
```

## Parameter Optimization

The backtesting engine supports parameter optimization:

```python
# Define parameter ranges to test
parameter_ranges = {
    'short_window': [10, 15, 20, 25],
    'long_window': [40, 50, 60, 70],
    'position_size_pct': [0.05, 0.1, 0.15, 0.2]
}

# Run optimization
results = engine.optimize_parameters(
    strategy_class=MovingAverageCrossoverStrategy,
    base_config=config,
    symbols=['AAPL', 'MSFT'],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    parameter_ranges=parameter_ranges
)

# Best parameters
best_params = results[0]['parameters']
best_sharpe = results[0]['sharpe_ratio']
```

## Validation and Testing

The framework includes comprehensive validation:

```python
from shared.strategy.validation import StrategyValidator

# Validate strategy class
issues = StrategyValidator.validate_strategy_class(MyStrategy)

# Validate configuration
issues = StrategyValidator.validate_strategy_config(config)

# Comprehensive validation
result = StrategyValidator.run_comprehensive_validation(
    strategy_class=MyStrategy,
    config=config,
    test_data=test_data
)

if result['is_valid']:
    print("Strategy passed all validations!")
else:
    print(f"Validation issues: {result['total_issues']}")
```

## Performance Metrics

Backtest results include comprehensive performance metrics:

- **Returns**: Total return, percentage return, daily returns
- **Risk**: Maximum drawdown, volatility, Sharpe ratio
- **Trading**: Total trades, win rate, profit factor
- **Portfolio**: Portfolio value history, position tracking

## Best Practices

### Strategy Development

1. **Start Simple**: Begin with basic strategies and add complexity gradually
2. **Validate Logic**: Use the validation framework to ensure correctness
3. **Test Thoroughly**: Run backtests on different time periods and symbols
4. **Consider Costs**: Include realistic commission and slippage estimates
5. **Avoid Overfitting**: Don't optimize too aggressively on historical data

### Risk Management

1. **Position Sizing**: Limit individual position sizes to manage risk
2. **Stop Losses**: Implement stop losses to limit downside
3. **Diversification**: Trade multiple uncorrelated assets
4. **Maximum Positions**: Limit total number of concurrent positions
5. **Risk Budget**: Define maximum risk per trade and total portfolio

### Performance Analysis

1. **Multiple Metrics**: Don't rely on a single performance metric
2. **Risk-Adjusted Returns**: Focus on Sharpe ratio and risk-adjusted metrics
3. **Drawdown Analysis**: Understand maximum drawdown characteristics
4. **Trade Analysis**: Review individual trade performance
5. **Benchmark Comparison**: Compare against buy-and-hold and market indices

## Troubleshooting

### Common Issues

1. **Insufficient Data**: Ensure enough historical data for indicator calculations
2. **Look-Ahead Bias**: Don't use future data in signal generation
3. **Survivorship Bias**: Consider delisted stocks in analysis
4. **Execution Assumptions**: Use realistic execution prices and timing
5. **Transaction Costs**: Include commissions, slippage, and market impact

### Performance Issues

1. **Data Caching**: Historical data is cached for performance
2. **Vectorized Calculations**: Use pandas vectorized operations
3. **Memory Management**: Process large datasets in chunks if needed
4. **Database Optimization**: Ensure database queries are optimized

## API Reference

For detailed API documentation, see the module docstrings:

- `shared.strategy.base`: Core strategy framework
- `shared.strategy.indicators`: Technical indicators
- `shared.strategy.portfolio`: Portfolio management
- `shared.strategy.validation`: Strategy validation
- `services.backtester.engine`: Backtesting engine
- `services.backtester.strategies`: Example strategies

## Contributing

When adding new strategies or features:

1. Follow the existing code patterns and style
2. Add comprehensive docstrings and type hints
3. Include validation and error handling
4. Add tests for new functionality
5. Update documentation as needed
