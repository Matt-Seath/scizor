"""
Portfolio management classes for backtesting.

This module handles position tracking, cash management, and portfolio state
during strategy backtesting.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd


class PositionType(Enum):
    """Types of positions."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeType(Enum):
    """Types of trades."""
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"


@dataclass
class Trade:
    """Represents a completed trade."""
    symbol: str
    trade_type: TradeType
    quantity: int
    price: Decimal
    timestamp: datetime
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def value(self) -> Decimal:
        """Total trade value including commission and slippage."""
        base_value = abs(self.quantity) * self.price
        return base_value + self.commission + self.slippage
    
    @property
    def net_value(self) -> Decimal:
        """Net trade value (positive for sells, negative for buys)."""
        multiplier = 1 if self.trade_type in [TradeType.SELL, TradeType.COVER] else -1
        return multiplier * self.value


@dataclass
class Position:
    """Represents a position in a security."""
    symbol: str
    quantity: int
    avg_price: Decimal
    current_price: Decimal
    position_type: PositionType
    opened_date: datetime
    last_updated: datetime
    trades: List[Trade] = field(default_factory=list)
    
    @property
    def market_value(self) -> Decimal:
        """Current market value of position."""
        return abs(self.quantity) * self.current_price
    
    @property
    def cost_basis(self) -> Decimal:
        """Total cost basis of position."""
        return abs(self.quantity) * self.avg_price
    
    @property
    def unrealized_pnl(self) -> Decimal:
        """Unrealized profit/loss."""
        if self.position_type == PositionType.LONG:
            return (self.current_price - self.avg_price) * self.quantity
        else:  # SHORT
            return (self.avg_price - self.current_price) * abs(self.quantity)
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized profit/loss percentage."""
        if self.cost_basis == 0:
            return 0.0
        return float(self.unrealized_pnl / self.cost_basis * 100)
    
    @property
    def realized_pnl(self) -> Decimal:
        """Realized profit/loss from closed trades."""
        return sum(trade.net_value for trade in self.trades if trade.quantity < 0)
    
    def update_price(self, new_price: Decimal, timestamp: datetime) -> None:
        """Update current price and timestamp."""
        self.current_price = new_price
        self.last_updated = timestamp
    
    def add_trade(self, trade: Trade) -> None:
        """Add a trade to this position."""
        if trade.symbol != self.symbol:
            raise ValueError(f"Trade symbol {trade.symbol} doesn't match position symbol {self.symbol}")
        
        self.trades.append(trade)
        
        # Update position quantity and average price
        if trade.trade_type in [TradeType.BUY, TradeType.COVER]:
            # Adding to position
            total_cost = self.cost_basis + (trade.quantity * trade.price)
            total_quantity = self.quantity + trade.quantity
            
            if total_quantity != 0:
                self.avg_price = total_cost / total_quantity
            
            self.quantity = total_quantity
            
        elif trade.trade_type in [TradeType.SELL, TradeType.SHORT]:
            # Reducing position
            self.quantity -= trade.quantity
            
            # If position is closed, reset avg_price
            if self.quantity == 0:
                self.avg_price = Decimal("0")
    
    def can_trade(self, trade_quantity: int, trade_type: TradeType) -> bool:
        """Check if a trade is valid for this position."""
        if trade_type == TradeType.SELL and trade_quantity > self.quantity:
            return False  # Can't sell more than we own
        
        if trade_type == TradeType.COVER and trade_quantity > abs(self.quantity):
            return False  # Can't cover more than we're short
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': int(self.quantity),
            'avg_price': float(self.avg_price),
            'current_price': float(self.current_price),
            'position_type': self.position_type.value,
            'market_value': float(self.market_value),
            'cost_basis': float(self.cost_basis),
            'unrealized_pnl': float(self.unrealized_pnl),
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'realized_pnl': float(self.realized_pnl),
            'opened_date': self.opened_date.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'trade_count': len(self.trades)
        }


class Portfolio:
    """
    Manages portfolio state during backtesting.
    
    Tracks positions, cash, and provides portfolio-level metrics.
    """
    
    def __init__(self, initial_cash: Decimal = Decimal("100000")):
        """Initialize portfolio with starting cash."""
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.value_history: List[Dict[str, Any]] = []
        
        # Portfolio metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = Decimal("0")
        self.total_slippage = Decimal("0")
    
    @property
    def market_value(self) -> Decimal:
        """Total market value of all positions."""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_value(self) -> Decimal:
        """Total portfolio value (cash + positions)."""
        return self.cash + self.market_value
    
    @property
    def unrealized_pnl(self) -> Decimal:
        """Total unrealized profit/loss."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def realized_pnl(self) -> Decimal:
        """Total realized profit/loss."""
        return sum(trade.net_value for trade in self.trade_history)
    
    @property
    def total_pnl(self) -> Decimal:
        """Total profit/loss (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def total_return(self) -> float:
        """Total return percentage."""
        if self.initial_cash == 0:
            return 0.0
        return float((self.total_value - self.initial_cash) / self.initial_cash * 100)
    
    @property
    def leverage(self) -> float:
        """Current leverage ratio."""
        if self.total_value == 0:
            return 0.0
        return float(self.market_value / self.total_value)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if portfolio has a position in symbol."""
        return symbol in self.positions and self.positions[symbol].quantity != 0
    
    def execute_trade(self, trade: Trade) -> bool:
        """
        Execute a trade and update portfolio state.
        
        Args:
            trade: Trade to execute
            
        Returns:
            True if trade was executed successfully
        """
        # Calculate trade cost
        trade_cost = trade.value
        
        # Check if we have enough cash for buy trades
        if trade.trade_type in [TradeType.BUY, TradeType.COVER]:
            if self.cash < trade_cost:
                return False  # Insufficient funds
        
        # Get or create position
        if trade.symbol not in self.positions:
            if trade.trade_type in [TradeType.SELL, TradeType.COVER]:
                return False  # Can't sell what we don't own
            
            # Create new position
            position_type = PositionType.LONG if trade.trade_type == TradeType.BUY else PositionType.SHORT
            self.positions[trade.symbol] = Position(
                symbol=trade.symbol,
                quantity=0,
                avg_price=Decimal("0"),
                current_price=trade.price,
                position_type=position_type,
                opened_date=trade.timestamp,
                last_updated=trade.timestamp
            )
        
        position = self.positions[trade.symbol]
        
        # Validate trade
        if not position.can_trade(trade.quantity, trade.trade_type):
            return False
        
        # Execute trade
        old_quantity = position.quantity
        position.add_trade(trade)
        
        # Update cash
        if trade.trade_type in [TradeType.BUY, TradeType.COVER]:
            self.cash -= trade_cost
        else:  # SELL or SHORT
            self.cash += trade_cost
        
        # Update portfolio metrics
        self.total_trades += 1
        self.total_commission += trade.commission
        self.total_slippage += trade.slippage
        
        # Track trade performance
        if trade.trade_type in [TradeType.SELL, TradeType.COVER]:
            # This is a closing trade, calculate P&L
            pnl = trade.net_value
            if pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
        
        # Add to trade history
        self.trade_history.append(trade)
        
        # Remove position if quantity is zero
        if position.quantity == 0:
            del self.positions[trade.symbol]
        
        return True
    
    def update_prices(self, prices: Dict[str, Decimal], timestamp: datetime) -> None:
        """Update current prices for all positions."""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol], timestamp)
    
    def record_value(self, timestamp: datetime, prices: Dict[str, Decimal]) -> None:
        """Record portfolio value at a point in time."""
        self.update_prices(prices, timestamp)
        
        self.value_history.append({
            'timestamp': timestamp,
            'total_value': float(self.total_value),
            'cash': float(self.cash),
            'market_value': float(self.market_value),
            'unrealized_pnl': float(self.unrealized_pnl),
            'realized_pnl': float(self.realized_pnl),
            'total_return': self.total_return,
            'position_count': len(self.positions),
            'leverage': self.leverage
        })
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        return {
            'cash': float(self.cash),
            'market_value': float(self.market_value),
            'total_value': float(self.total_value),
            'initial_cash': float(self.initial_cash),
            'total_return': self.total_return,
            'unrealized_pnl': float(self.unrealized_pnl),
            'realized_pnl': float(self.realized_pnl),
            'total_pnl': float(self.total_pnl),
            'leverage': self.leverage,
            'position_count': len(self.positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0,
            'total_commission': float(self.total_commission),
            'total_slippage': float(self.total_slippage),
            'positions': {symbol: pos.to_dict() for symbol, pos in self.positions.items()}
        }
    
    def get_value_series(self) -> pd.DataFrame:
        """Get portfolio value time series as DataFrame."""
        if not self.value_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.value_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    
    def reset(self, initial_cash: Optional[Decimal] = None) -> None:
        """Reset portfolio to initial state."""
        if initial_cash is not None:
            self.initial_cash = initial_cash
        
        self.cash = self.initial_cash
        self.positions.clear()
        self.trade_history.clear()
        self.value_history.clear()
        
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = Decimal("0")
        self.total_slippage = Decimal("0")
    
    def __str__(self) -> str:
        return f"Portfolio(value=${self.total_value:,.2f}, cash=${self.cash:,.2f}, positions={len(self.positions)})"
    
    def __repr__(self) -> str:
        return f"Portfolio(total_value={self.total_value}, cash={self.cash}, positions={len(self.positions)})"
