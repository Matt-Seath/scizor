from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
import structlog

from app.data.models.market import DailyPrice
from app.data.models.signals import Signal
from app.data.models.portfolio import Position, Order
from app.utils.logging import get_trading_logger

logger = structlog.get_logger(__name__)
trading_logger = get_trading_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting"""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    commission_per_share: float = 0.002  # $0.002 per share (typical IBKR)
    slippage_bps: float = 5.0  # 5 basis points
    max_positions: int = 5
    position_sizing_method: str = "equal_weight"  # equal_weight, kelly, fixed_dollar
    risk_per_trade: float = 0.02  # 2% risk per trade
    enable_short_selling: bool = False


@dataclass
class BacktestPosition:
    """Position in backtest"""
    symbol: str
    entry_date: datetime
    entry_price: float
    quantity: int
    side: str  # LONG or SHORT
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = "unknown"
    unrealized_pnl: float = 0.0
    
    def update_pnl(self, current_price: float) -> float:
        """Update and return unrealized P&L"""
        if self.side == "LONG":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
        return self.unrealized_pnl


@dataclass
class BacktestTrade:
    """Completed trade in backtest"""
    symbol: str
    strategy: str
    side: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    commission: float
    pnl: float
    return_pct: float
    holding_days: int
    exit_reason: str  # SIGNAL, STOP_LOSS, TAKE_PROFIT, TIME_LIMIT


@dataclass
class BacktestMetrics:
    """Backtest performance metrics"""
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_holding_days: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0


class BacktestEngine:
    """
    Backtesting engine for trading strategies
    Simulates trading on historical ASX200 data
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.portfolio_value = config.initial_capital
        self.cash = config.initial_capital
        self.positions: Dict[str, BacktestPosition] = {}
        self.completed_trades: List[BacktestTrade] = []
        self.daily_portfolio_values: List[Tuple[datetime, float]] = []
        self.price_data: Dict[str, pd.DataFrame] = {}
        
        logger.info("Backtest engine initialized", 
                   start_date=config.start_date,
                   end_date=config.end_date,
                   initial_capital=config.initial_capital)
    
    def load_price_data(self, price_data: Dict[str, pd.DataFrame]) -> None:
        """Load historical price data for backtesting"""
        self.price_data = price_data
        
        # Validate data coverage
        for symbol, df in price_data.items():
            if df.empty:
                logger.warning("Empty price data", symbol=symbol)
                continue
            
            start_coverage = df.index.min()
            end_coverage = df.index.max()
            
            if start_coverage > self.config.start_date:
                logger.warning("Insufficient historical data", 
                             symbol=symbol, 
                             data_start=start_coverage,
                             backtest_start=self.config.start_date)
            
            logger.debug("Price data loaded", 
                        symbol=symbol,
                        rows=len(df),
                        start=start_coverage,
                        end=end_coverage)
        
        logger.info("Price data loaded for backtest", symbols=len(price_data))
    
    def get_price(self, symbol: str, date: datetime, price_type: str = "close") -> Optional[float]:
        """Get price for symbol on specific date"""
        if symbol not in self.price_data:
            return None
        
        df = self.price_data[symbol]
        date_str = date.strftime('%Y-%m-%d')
        
        if date_str not in df.index:
            return None
        
        return df.loc[date_str, price_type]
    
    def calculate_position_size(self, symbol: str, signal_price: float, 
                              stop_loss: Optional[float] = None) -> int:
        """Calculate position size based on configuration"""
        if self.config.position_sizing_method == "equal_weight":
            # Equal weight across max positions
            target_allocation = self.portfolio_value / self.config.max_positions
            return int(target_allocation / signal_price)
        
        elif self.config.position_sizing_method == "fixed_dollar":
            # Fixed dollar amount per position
            target_allocation = 20000  # $20k per position
            return int(target_allocation / signal_price)
        
        elif self.config.position_sizing_method == "kelly" and stop_loss:
            # Kelly criterion with risk management
            risk_amount = self.portfolio_value * self.config.risk_per_trade
            risk_per_share = abs(signal_price - stop_loss)
            if risk_per_share > 0:
                return int(risk_amount / risk_per_share)
        
        # Default fallback
        return int(10000 / signal_price)  # $10k position
    
    def calculate_commission(self, price: float, quantity: int) -> float:
        """Calculate commission cost"""
        return self.config.commission_per_share * quantity
    
    def calculate_slippage(self, price: float, side: str) -> float:
        """Calculate slippage cost"""
        slippage_amount = price * (self.config.slippage_bps / 10000)
        if side == "BUY":
            return price + slippage_amount
        else:  # SELL
            return price - slippage_amount
    
    def can_open_position(self, symbol: str) -> bool:
        """Check if we can open a new position"""
        if symbol in self.positions:
            return False  # Already have position in this symbol
        
        if len(self.positions) >= self.config.max_positions:
            return False  # At position limit
        
        return True
    
    def execute_signal(self, signal: Signal, current_date: datetime) -> bool:
        """Execute a trading signal"""
        symbol = signal.symbol
        
        if signal.signal_type == "BUY" and self.can_open_position(symbol):
            return self._open_position(signal, current_date)
        
        elif signal.signal_type == "SELL" and symbol in self.positions:
            return self._close_position(symbol, signal.price, current_date, "SIGNAL")
        
        elif signal.signal_type == "CLOSE" and symbol in self.positions:
            return self._close_position(symbol, signal.price, current_date, "SIGNAL")
        
        return False
    
    def _open_position(self, signal: Signal, current_date: datetime) -> bool:
        """Open a new position"""
        symbol = signal.symbol
        signal_price = signal.price
        
        # Check if we have price data for this symbol
        if symbol not in self.price_data:
            logger.warning("No price data available for symbol", symbol=symbol)
            return False
        
        # Calculate position size
        stop_loss = None
        if hasattr(signal, 'signal_metadata') and signal.signal_metadata:
            stop_loss = signal.signal_metadata.get('stop_loss')
        
        quantity = self.calculate_position_size(symbol, signal_price, stop_loss)
        
        if quantity <= 0:
            logger.warning("Invalid position size calculated", symbol=symbol, quantity=quantity)
            return False
        
        # Apply slippage
        execution_price = self.calculate_slippage(signal_price, "BUY")
        
        # Calculate costs
        position_value = execution_price * quantity
        commission = self.calculate_commission(execution_price, quantity)
        total_cost = position_value + commission
        
        # Check if we have enough cash
        if total_cost > self.cash:
            logger.warning("Insufficient cash for position", 
                         symbol=symbol, 
                         required=total_cost, 
                         available=self.cash)
            return False
        
        # Create position
        position = BacktestPosition(
            symbol=symbol,
            entry_date=current_date,
            entry_price=execution_price,
            quantity=quantity,
            side="LONG",
            stop_loss=stop_loss,
            strategy=signal.strategy
        )
        
        # Update portfolio
        self.positions[symbol] = position
        self.cash -= total_cost
        
        trading_logger.log_trade_signal(
            symbol=symbol,
            signal_type="BUY",
            price=execution_price,
            confidence=signal.confidence,
            strategy=signal.strategy
        )
        
        logger.info("Position opened", 
                   symbol=symbol,
                   quantity=quantity,
                   price=execution_price,
                   cost=total_cost)
        
        return True
    
    def _close_position(self, symbol: str, exit_price: float, 
                       current_date: datetime, exit_reason: str) -> bool:
        """Close an existing position"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        
        # Apply slippage
        execution_price = self.calculate_slippage(exit_price, "SELL")
        
        # Calculate proceeds and costs
        gross_proceeds = execution_price * position.quantity
        commission = self.calculate_commission(execution_price, position.quantity)
        net_proceeds = gross_proceeds - commission
        
        # Calculate P&L
        entry_cost = position.entry_price * position.quantity
        pnl = net_proceeds - entry_cost - self.calculate_commission(position.entry_price, position.quantity)
        return_pct = pnl / entry_cost * 100
        
        # Create completed trade record
        holding_days = (current_date - position.entry_date).days
        
        trade = BacktestTrade(
            symbol=symbol,
            strategy=position.strategy,
            side=position.side,
            entry_date=position.entry_date,
            exit_date=current_date,
            entry_price=position.entry_price,
            exit_price=execution_price,
            quantity=position.quantity,
            commission=commission + self.calculate_commission(position.entry_price, position.quantity),
            pnl=pnl,
            return_pct=return_pct,
            holding_days=holding_days,
            exit_reason=exit_reason
        )
        
        # Update portfolio
        self.cash += net_proceeds
        del self.positions[symbol]
        self.completed_trades.append(trade)
        
        trading_logger.log_trade_signal(
            symbol=symbol,
            signal_type="SELL",
            price=execution_price,
            confidence=1.0,
            strategy=position.strategy
        )
        
        logger.info("Position closed", 
                   symbol=symbol,
                   pnl=pnl,
                   return_pct=return_pct,
                   holding_days=holding_days,
                   reason=exit_reason)
        
        return True
    
    def update_positions(self, current_date: datetime) -> None:
        """Update all positions with current prices and check stops"""
        positions_to_close = []
        
        for symbol, position in self.positions.items():
            current_price = self.get_price(symbol, current_date)
            
            if current_price is None:
                continue
            
            # Update unrealized P&L
            position.update_pnl(current_price)
            
            # Check stop loss
            if position.stop_loss and current_price <= position.stop_loss:
                positions_to_close.append((symbol, current_price, "STOP_LOSS"))
                continue
            
            # Check take profit
            if position.take_profit and current_price >= position.take_profit:
                positions_to_close.append((symbol, current_price, "TAKE_PROFIT"))
                continue
            
            # Check time-based exit (max 14 days for swing trades)
            holding_days = (current_date - position.entry_date).days
            if holding_days >= 14:
                positions_to_close.append((symbol, current_price, "TIME_LIMIT"))
        
        # Close positions that hit stops or limits
        for symbol, price, reason in positions_to_close:
            self._close_position(symbol, price, current_date, reason)
    
    def calculate_portfolio_value(self, current_date: datetime) -> float:
        """Calculate total portfolio value"""
        total_value = self.cash
        
        for symbol, position in self.positions.items():
            current_price = self.get_price(symbol, current_date)
            if current_price:
                position_value = current_price * position.quantity
                total_value += position_value
        
        return total_value
    
    def run_backtest(self, signals: List[Signal]) -> BacktestMetrics:
        """Run the complete backtest"""
        logger.info("Starting backtest", 
                   signals=len(signals),
                   period=f"{self.config.start_date} to {self.config.end_date}")
        
        # Sort signals by date
        signals.sort(key=lambda x: x.generated_at)
        
        # Generate date range for backtesting
        current_date = self.config.start_date
        signal_index = 0
        
        while current_date <= self.config.end_date:
            # Process signals for current date
            while (signal_index < len(signals) and 
                   signals[signal_index].generated_at.date() == current_date.date()):
                
                signal = signals[signal_index]
                self.execute_signal(signal, current_date)
                signal_index += 1
            
            # Update positions and check stops
            self.update_positions(current_date)
            
            # Record daily portfolio value
            portfolio_value = self.calculate_portfolio_value(current_date)
            self.daily_portfolio_values.append((current_date, portfolio_value))
            
            # Move to next trading day (skip weekends)
            current_date += timedelta(days=1)
            while current_date.weekday() >= 5:  # Skip weekends
                current_date += timedelta(days=1)
        
        # Close any remaining positions at end date
        for symbol in list(self.positions.keys()):
            final_price = self.get_price(symbol, self.config.end_date)
            if final_price:
                self._close_position(symbol, final_price, self.config.end_date, "BACKTEST_END")
        
        # Calculate final metrics
        metrics = self._calculate_metrics()
        
        logger.info("Backtest completed", 
                   total_trades=metrics.total_trades,
                   total_return=f"{metrics.total_return:.2%}",
                   sharpe_ratio=f"{metrics.sharpe_ratio:.2f}",
                   max_drawdown=f"{metrics.max_drawdown:.2%}")
        
        return metrics
    
    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate backtest performance metrics"""
        if not self.completed_trades:
            return BacktestMetrics()
        
        # Basic metrics
        total_trades = len(self.completed_trades)
        winning_trades = len([t for t in self.completed_trades if t.pnl > 0])
        losing_trades = total_trades - winning_trades
        
        total_pnl = sum(t.pnl for t in self.completed_trades)
        gross_profits = sum(t.pnl for t in self.completed_trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in self.completed_trades if t.pnl < 0))
        
        # Portfolio metrics
        final_value = self.daily_portfolio_values[-1][1] if self.daily_portfolio_values else self.config.initial_capital
        total_return = (final_value - self.config.initial_capital) / self.config.initial_capital
        
        # Time-based metrics
        trading_days = len(self.daily_portfolio_values)
        annual_return = ((1 + total_return) ** (252 / trading_days)) - 1 if trading_days > 0 else 0
        
        # Calculate Sharpe ratio
        if len(self.daily_portfolio_values) > 1:
            daily_returns = []
            for i in range(1, len(self.daily_portfolio_values)):
                prev_value = self.daily_portfolio_values[i-1][1]
                curr_value = self.daily_portfolio_values[i][1]
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)
            
            if daily_returns:
                sharpe_ratio = (np.mean(daily_returns) * 252) / (np.std(daily_returns) * np.sqrt(252))
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0
        
        # Calculate maximum drawdown
        max_drawdown = 0.0
        peak_value = self.config.initial_capital
        
        for date, value in self.daily_portfolio_values:
            if value > peak_value:
                peak_value = value
            else:
                drawdown = (peak_value - value) / peak_value
                max_drawdown = max(max_drawdown, drawdown)
        
        # Trade statistics
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        avg_trade_return = total_pnl / total_trades if total_trades > 0 else 0
        avg_holding_days = sum(t.holding_days for t in self.completed_trades) / total_trades if total_trades > 0 else 0
        
        largest_win = max((t.pnl for t in self.completed_trades), default=0)
        largest_loss = min((t.pnl for t in self.completed_trades), default=0)
        
        return BacktestMetrics(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_holding_days=avg_holding_days,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            largest_win=largest_win,
            largest_loss=largest_loss
        )
    
    def get_trade_log(self) -> pd.DataFrame:
        """Get detailed trade log as DataFrame"""
        if not self.completed_trades:
            return pd.DataFrame()
        
        trade_data = []
        for trade in self.completed_trades:
            trade_data.append({
                'symbol': trade.symbol,
                'strategy': trade.strategy,
                'side': trade.side,
                'entry_date': trade.entry_date,
                'exit_date': trade.exit_date,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'commission': trade.commission,
                'pnl': trade.pnl,
                'return_pct': trade.return_pct,
                'holding_days': trade.holding_days,
                'exit_reason': trade.exit_reason
            })
        
        return pd.DataFrame(trade_data)
    
    def get_portfolio_curve(self) -> pd.DataFrame:
        """Get portfolio value curve as DataFrame"""
        if not self.daily_portfolio_values:
            return pd.DataFrame()
        
        dates, values = zip(*self.daily_portfolio_values)
        return pd.DataFrame({
            'date': dates,
            'portfolio_value': values
        }).set_index('date')