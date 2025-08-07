"""
Backtesting engine for trading strategies.

This module provides the core backtesting engine that simulates trading with historical data.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd

from ...shared.database.connection import DatabaseConnection
from ...shared.models.schemas import DailyPrice
from ...shared.strategy.base import BaseStrategy, StrategySignal, StrategyMetrics
from ...shared.strategy.portfolio import Portfolio, Position, Trade
from ...shared.strategy.validation import StrategyValidator, ValidationError


logger = logging.getLogger(__name__)


class BacktestResult:
    """
    Results from a backtest run.
    """
    
    def __init__(self):
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.initial_capital: Decimal = Decimal('0')
        self.final_value: Decimal = Decimal('0')
        self.total_return: Decimal = Decimal('0')
        self.total_return_pct: Decimal = Decimal('0')
        self.max_drawdown: Decimal = Decimal('0')
        self.max_drawdown_pct: Decimal = Decimal('0')
        self.sharpe_ratio: Optional[Decimal] = None
        self.volatility: Optional[Decimal] = None
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.win_rate: Decimal = Decimal('0')
        self.avg_win: Decimal = Decimal('0')
        self.avg_loss: Decimal = Decimal('0')
        self.profit_factor: Optional[Decimal] = None
        self.portfolio_values: List[Tuple[datetime, Decimal]] = []
        self.trades: List[Trade] = []
        self.daily_returns: List[Decimal] = []
        self.strategy_metrics: Optional[StrategyMetrics] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'initial_capital': float(self.initial_capital),
            'final_value': float(self.final_value),
            'total_return': float(self.total_return),
            'total_return_pct': float(self.total_return_pct),
            'max_drawdown': float(self.max_drawdown),
            'max_drawdown_pct': float(self.max_drawdown_pct),
            'sharpe_ratio': float(self.sharpe_ratio) if self.sharpe_ratio else None,
            'volatility': float(self.volatility) if self.volatility else None,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': float(self.win_rate),
            'avg_win': float(self.avg_win),
            'avg_loss': float(self.avg_loss),
            'profit_factor': float(self.profit_factor) if self.profit_factor else None,
            'portfolio_values': [(dt.isoformat(), float(val)) for dt, val in self.portfolio_values],
            'daily_returns': [float(ret) for ret in self.daily_returns],
            'trades': [trade.to_dict() for trade in self.trades]
        }


class MarketDataProvider:
    """
    Provides historical market data for backtesting.
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._data_cache: Dict[str, pd.DataFrame] = {}
        
    def get_data(self, symbols: List[str], start_date: datetime, end_date: datetime) -> Dict[str, pd.DataFrame]:
        """
        Get historical market data for symbols.
        
        Args:
            symbols: List of symbols to get data for
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            Dictionary mapping symbol -> DataFrame with OHLCV data
        """
        data = {}
        
        for symbol in symbols:
            cache_key = f"{symbol}_{start_date.date()}_{end_date.date()}"
            
            if cache_key in self._data_cache:
                data[symbol] = self._data_cache[cache_key]
                continue
            
            try:
                with self.db.get_session() as session:
                    prices = session.query(DailyPrice).filter(
                        DailyPrice.symbol == symbol,
                        DailyPrice.date >= start_date.date(),
                        DailyPrice.date <= end_date.date()
                    ).order_by(DailyPrice.date).all()
                    
                    if not prices:
                        logger.warning(f"No data found for symbol {symbol}")
                        continue
                    
                    df_data = {
                        'date': [p.date for p in prices],
                        'open': [float(p.open_price) for p in prices],
                        'high': [float(p.high_price) for p in prices],
                        'low': [float(p.low_price) for p in prices],
                        'close': [float(p.close_price) for p in prices],
                        'volume': [int(p.volume) for p in prices]
                    }
                    
                    df = pd.DataFrame(df_data)
                    df.set_index('date', inplace=True)
                    
                    self._data_cache[cache_key] = df
                    data[symbol] = df
                    
            except Exception as e:
                logger.error(f"Error getting data for {symbol}: {e}")
                continue
        
        return data
    
    def get_price_at_date(self, symbol: str, date: datetime) -> Optional[Decimal]:
        """
        Get closing price for a symbol at a specific date.
        
        Args:
            symbol: Symbol to get price for
            date: Date to get price for
            
        Returns:
            Price or None if not found
        """
        try:
            with self.db.get_session() as session:
                price = session.query(DailyPrice).filter(
                    DailyPrice.symbol == symbol,
                    DailyPrice.date == date.date()
                ).first()
                
                return price.close_price if price else None
                
        except Exception as e:
            logger.error(f"Error getting price for {symbol} on {date}: {e}")
            return None


class BacktestEngine:
    """
    Main backtesting engine that simulates trading strategies.
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.data_provider = MarketDataProvider(db_connection)
        
    def run_backtest(self, 
                    strategy: BaseStrategy,
                    symbols: List[str],
                    start_date: datetime,
                    end_date: datetime,
                    initial_capital: Decimal = Decimal('100000'),
                    commission_pct: Decimal = Decimal('0.001'),
                    slippage_pct: Decimal = Decimal('0.001')) -> BacktestResult:
        """
        Run a backtest for a strategy.
        
        Args:
            strategy: Strategy to test
            symbols: List of symbols to trade
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Initial capital amount
            commission_pct: Commission percentage per trade
            slippage_pct: Slippage percentage per trade
            
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting backtest for {strategy.config.name}")
        
        # Validate strategy
        validation_result = StrategyValidator.run_comprehensive_validation(
            type(strategy), strategy.config
        )
        
        if not validation_result['is_valid']:
            issues = (validation_result['class_issues'] + 
                     validation_result['config_issues'] + 
                     validation_result['instance_issues'])
            raise ValidationError(f"Strategy validation failed: {issues}")
        
        # Get historical data
        logger.info("Loading historical data...")
        historical_data = self.data_provider.get_data(symbols, start_date, end_date)
        
        if not historical_data:
            raise ValueError("No historical data available for specified symbols and date range")
        
        # Validate data format
        data_issues = StrategyValidator.validate_data_format(historical_data)
        if data_issues:
            raise ValidationError(f"Invalid data format: {data_issues}")
        
        # Initialize strategy
        strategy.initialize(symbols, start_date, end_date)
        
        # Initialize portfolio
        portfolio = Portfolio(initial_capital)
        
        # Initialize result
        result = BacktestResult()
        result.start_date = start_date
        result.end_date = end_date
        result.initial_capital = initial_capital
        
        # Get all trading dates
        all_dates = set()
        for df in historical_data.values():
            all_dates.update(df.index)
        
        trading_dates = sorted(list(all_dates))
        trading_dates = [date for date in trading_dates if start_date.date() <= date <= end_date.date()]
        
        logger.info(f"Backtesting over {len(trading_dates)} trading days")
        
        # Track portfolio values for performance calculation
        portfolio_values = []
        daily_returns = []
        previous_value = initial_capital
        
        # Main backtesting loop
        for i, current_date in enumerate(trading_dates):
            current_datetime = datetime.combine(current_date, datetime.min.time())
            
            # Get current data up to this date
            current_data = {}
            for symbol, df in historical_data.items():
                # Filter data up to current date
                mask = df.index <= current_date
                if mask.any():
                    current_data[symbol] = df[mask]
            
            if not current_data:
                continue
            
            # Update portfolio values with current prices
            self._update_portfolio_values(portfolio, current_data, current_date)
            
            # Get portfolio state
            portfolio_state = {
                'cash': portfolio.cash,
                'positions': {pos.symbol: {'quantity': pos.quantity, 'avg_price': pos.avg_price}
                            for pos in portfolio.positions.values()},
                'total_value': portfolio.get_total_value()
            }
            
            # Update strategy state
            strategy.update_state(current_data, current_datetime, portfolio_state)
            
            # Generate signals
            signals = strategy.generate_signals(current_data, current_datetime, portfolio_state)
            
            # Execute signals
            for signal in signals:
                if signal.symbol not in current_data:
                    logger.warning(f"No data for symbol {signal.symbol} on {current_date}")
                    continue
                
                self._execute_signal(portfolio, signal, current_data[signal.symbol].iloc[-1], 
                                   commission_pct, slippage_pct, current_datetime)
            
            # Record portfolio value
            total_value = portfolio.get_total_value()
            portfolio_values.append((current_datetime, total_value))
            
            # Calculate daily return
            if i > 0:
                daily_return = (total_value - previous_value) / previous_value
                daily_returns.append(daily_return)
            
            previous_value = total_value
            
            # Log progress
            if i % 50 == 0 or i == len(trading_dates) - 1:
                logger.info(f"Processed {i+1}/{len(trading_dates)} days, Portfolio value: ${total_value:,.2f}")
        
        # Calculate final results
        result.final_value = portfolio.get_total_value()
        result.total_return = result.final_value - result.initial_capital
        result.total_return_pct = result.total_return / result.initial_capital
        result.portfolio_values = portfolio_values
        result.trades = portfolio.trade_history
        result.daily_returns = daily_returns
        
        # Calculate performance metrics
        self._calculate_performance_metrics(result)
        
        # Get strategy metrics
        result.strategy_metrics = strategy.get_metrics()
        
        logger.info(f"Backtest completed. Final value: ${result.final_value:,.2f}, "
                   f"Return: {result.total_return_pct:.2%}")
        
        return result
    
    def _update_portfolio_values(self, portfolio: Portfolio, current_data: Dict[str, pd.DataFrame], 
                               current_date: datetime.date):
        """Update portfolio position values with current market prices."""
        for position in portfolio.positions.values():
            if position.symbol in current_data:
                df = current_data[position.symbol]
                if not df.empty and current_date in df.index:
                    current_price = Decimal(str(df.loc[current_date, 'close']))
                    position.current_price = current_price
    
    def _execute_signal(self, portfolio: Portfolio, signal: StrategySignal, 
                       current_bar: pd.Series, commission_pct: Decimal, 
                       slippage_pct: Decimal, timestamp: datetime):
        """Execute a trading signal."""
        try:
            # Calculate execution price with slippage
            base_price = Decimal(str(current_bar['close']))
            
            if signal.signal_type.value == 'BUY':
                # Buy orders get worse fill (higher price)
                execution_price = base_price * (Decimal('1') + slippage_pct)
            else:
                # Sell orders get worse fill (lower price)
                execution_price = base_price * (Decimal('1') - slippage_pct)
            
            # Determine quantity if not specified
            quantity = signal.quantity
            if quantity is None:
                # Use portfolio's position sizing logic
                available_cash = portfolio.cash
                max_position_value = available_cash * Decimal('0.1')  # 10% of cash
                quantity = int(max_position_value / execution_price)
            
            if quantity <= 0:
                return
            
            # Calculate commission
            trade_value = execution_price * quantity
            commission = trade_value * commission_pct
            
            # Execute trade
            if signal.signal_type.value == 'BUY':
                total_cost = trade_value + commission
                if portfolio.cash >= total_cost:
                    portfolio.add_position(signal.symbol, quantity, execution_price, timestamp)
                    portfolio.cash -= total_cost
                    
                    logger.debug(f"BUY {quantity} {signal.symbol} @ ${execution_price:.2f}")
            
            elif signal.signal_type.value == 'SELL':
                if signal.symbol in portfolio.positions:
                    position = portfolio.positions[signal.symbol]
                    sell_quantity = min(quantity, position.quantity)
                    
                    if sell_quantity > 0:
                        proceeds = execution_price * sell_quantity - commission
                        portfolio.remove_position(signal.symbol, sell_quantity, execution_price, timestamp)
                        portfolio.cash += proceeds
                        
                        logger.debug(f"SELL {sell_quantity} {signal.symbol} @ ${execution_price:.2f}")
                        
        except Exception as e:
            logger.error(f"Error executing signal for {signal.symbol}: {e}")
    
    def _calculate_performance_metrics(self, result: BacktestResult):
        """Calculate performance metrics for the backtest result."""
        if not result.portfolio_values or not result.daily_returns:
            return
        
        # Basic metrics
        result.total_trades = len(result.trades)
        
        # Trade analysis
        profitable_trades = [t for t in result.trades if t.pnl > 0]
        losing_trades = [t for t in result.trades if t.pnl < 0]
        
        result.winning_trades = len(profitable_trades)
        result.losing_trades = len(losing_trades)
        
        if result.total_trades > 0:
            result.win_rate = Decimal(result.winning_trades) / Decimal(result.total_trades)
        
        if profitable_trades:
            result.avg_win = sum(t.pnl for t in profitable_trades) / len(profitable_trades)
        
        if losing_trades:
            result.avg_loss = sum(abs(t.pnl) for t in losing_trades) / len(losing_trades)
        
        # Profit factor
        total_wins = sum(t.pnl for t in profitable_trades)
        total_losses = sum(abs(t.pnl) for t in losing_trades)
        
        if total_losses > 0:
            result.profit_factor = total_wins / total_losses
        
        # Drawdown calculation
        values = [val for _, val in result.portfolio_values]
        peak = values[0]
        max_drawdown = Decimal('0')
        
        for value in values:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        result.max_drawdown = max_drawdown
        if peak > 0:
            result.max_drawdown_pct = max_drawdown / peak
        
        # Volatility and Sharpe ratio
        if len(result.daily_returns) > 1:
            returns_df = pd.Series([float(r) for r in result.daily_returns])
            result.volatility = Decimal(str(returns_df.std() * (252 ** 0.5)))  # Annualized
            
            mean_return = returns_df.mean()
            if result.volatility > 0:
                # Assuming risk-free rate of 2%
                risk_free_rate = 0.02 / 252  # Daily risk-free rate
                result.sharpe_ratio = Decimal(str((mean_return - risk_free_rate) / returns_df.std() * (252 ** 0.5)))
    
    def optimize_parameters(self, strategy_class, base_config, symbols: List[str],
                          start_date: datetime, end_date: datetime,
                          parameter_ranges: Dict[str, List]) -> List[Dict[str, Any]]:
        """
        Run parameter optimization for a strategy.
        
        Args:
            strategy_class: Strategy class to optimize
            base_config: Base configuration to start from
            symbols: Symbols to test on
            start_date: Start date for optimization
            end_date: End date for optimization
            parameter_ranges: Dictionary of parameter name -> list of values to test
            
        Returns:
            List of optimization results sorted by performance
        """
        logger.info(f"Starting parameter optimization for {strategy_class.__name__}")
        
        results = []
        
        # Generate all parameter combinations
        import itertools
        
        param_names = list(parameter_ranges.keys())
        param_values = list(parameter_ranges.values())
        
        combinations = list(itertools.product(*param_values))
        total_combinations = len(combinations)
        
        logger.info(f"Testing {total_combinations} parameter combinations")
        
        for i, combination in enumerate(combinations):
            try:
                # Create config with current parameters
                config_dict = base_config.model_dump()
                
                for param_name, value in zip(param_names, combination):
                    if hasattr(base_config, param_name):
                        config_dict[param_name] = value
                
                config = base_config.__class__(**config_dict)
                
                # Create strategy instance
                strategy = strategy_class(config)
                
                # Run backtest
                result = self.run_backtest(strategy, symbols, start_date, end_date)
                
                # Store result with parameters
                optimization_result = {
                    'parameters': dict(zip(param_names, combination)),
                    'total_return_pct': float(result.total_return_pct),
                    'sharpe_ratio': float(result.sharpe_ratio) if result.sharpe_ratio else 0,
                    'max_drawdown_pct': float(result.max_drawdown_pct),
                    'win_rate': float(result.win_rate),
                    'total_trades': result.total_trades,
                    'profit_factor': float(result.profit_factor) if result.profit_factor else 0,
                    'final_value': float(result.final_value)
                }
                
                results.append(optimization_result)
                
                if i % 10 == 0:
                    logger.info(f"Completed {i+1}/{total_combinations} optimizations")
                
            except Exception as e:
                logger.error(f"Error in optimization iteration {i}: {e}")
                continue
        
        # Sort by Sharpe ratio (or total return if Sharpe not available)
        results.sort(key=lambda x: x['sharpe_ratio'] if x['sharpe_ratio'] > 0 else x['total_return_pct'], 
                    reverse=True)
        
        logger.info(f"Optimization completed. Best Sharpe ratio: {results[0]['sharpe_ratio']:.3f}")
        
        return results
