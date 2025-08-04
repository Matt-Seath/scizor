"""
Portfolio management and position tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Position:
    """Represents a portfolio position."""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float = 0.0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    @property
    def value(self) -> float:
        """Current market value of the position."""
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        """Total cost basis of the position."""
        return self.quantity * self.avg_price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        return self.value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'value': self.value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'last_updated': self.last_updated
        }


@dataclass
class RiskSettings:
    """Risk management settings."""
    max_position_size: float = 0.1  # 10% of portfolio
    stop_loss: float = 0.02  # 2%
    take_profit: float = 0.06  # 6%
    max_drawdown: float = 0.15  # 15%


class PortfolioManager:
    """Manages portfolio positions and risk."""
    
    def __init__(self, initial_capital: float, risk_settings: RiskSettings = None):
        self.initial_capital = initial_capital
        self.cash_balance = initial_capital
        self.positions: Dict[str, Position] = {}
        self.risk_settings = risk_settings or RiskSettings()
        
        # Performance tracking
        self._performance_history = []
        self._peak_value = initial_capital
        self._current_drawdown = 0.0
        
    def add_position(self, symbol: str, quantity: float, price: float = None) -> bool:
        """
        Add to or create a position.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares to add
            price: Price per share (if None, uses current market price)
            
        Returns:
            True if position was added successfully
        """
        if price is None:
            # In a real implementation, get current market price
            price = 100.0  # Mock price
            
        cost = quantity * price
        
        # Check if we have enough cash
        if cost > self.cash_balance:
            return False
            
        # Check position size limits
        total_value = self.get_total_value()
        if symbol in self.positions:
            existing_value = self.positions[symbol].value
        else:
            existing_value = 0
            
        new_position_value = existing_value + cost
        if new_position_value > total_value * self.risk_settings.max_position_size:
            return False
        
        # Update or create position
        if symbol in self.positions:
            position = self.positions[symbol]
            # Calculate new average price
            total_quantity = position.quantity + quantity
            total_cost = position.cost_basis + cost
            new_avg_price = total_cost / total_quantity
            
            position.quantity = total_quantity
            position.avg_price = new_avg_price
            position.last_updated = datetime.now()
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=price
            )
        
        # Update cash balance
        self.cash_balance -= cost
        
        return True
    
    def reduce_position(self, symbol: str, quantity: float, price: float = None) -> bool:
        """
        Reduce or close a position.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares to sell
            price: Price per share (if None, uses current market price)
            
        Returns:
            True if position was reduced successfully
        """
        if symbol not in self.positions:
            return False
            
        position = self.positions[symbol]
        if quantity > position.quantity:
            return False
            
        if price is None:
            price = 100.0  # Mock price
            
        # Calculate proceeds
        proceeds = quantity * price
        
        # Update position
        if quantity == position.quantity:
            # Close position completely
            del self.positions[symbol]
        else:
            # Reduce position
            position.quantity -= quantity
            position.last_updated = datetime.now()
        
        # Update cash balance
        self.cash_balance += proceeds
        
        return True
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def get_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        return self.positions.copy()
    
    def get_total_value(self) -> float:
        """Get total portfolio value."""
        positions_value = sum(pos.value for pos in self.positions.values())
        return self.cash_balance + positions_value
    
    def get_positions_value(self) -> float:
        """Get total value of all positions."""
        return sum(pos.value for pos in self.positions.values())
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price
                self.positions[symbol].last_updated = datetime.now()
    
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown."""
        current_value = self.get_total_value()
        
        # Update peak value
        if current_value > self._peak_value:
            self._peak_value = current_value
        
        # Calculate drawdown
        if self._peak_value > 0:
            self._current_drawdown = (self._peak_value - current_value) / self._peak_value
        else:
            self._current_drawdown = 0.0
            
        return self._current_drawdown
    
    def check_risk_limits(self) -> List[str]:
        """
        Check if any risk limits are breached.
        
        Returns:
            List of risk violations
        """
        violations = []
        
        # Check drawdown
        current_drawdown = self.calculate_drawdown()
        if current_drawdown > self.risk_settings.max_drawdown:
            violations.append(f"Drawdown {current_drawdown:.2%} exceeds limit {self.risk_settings.max_drawdown:.2%}")
        
        # Check position sizes
        total_value = self.get_total_value()
        for symbol, position in self.positions.items():
            position_pct = position.value / total_value if total_value > 0 else 0
            if position_pct > self.risk_settings.max_position_size:
                violations.append(f"Position {symbol} {position_pct:.2%} exceeds limit {self.risk_settings.max_position_size:.2%}")
        
        return violations
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get portfolio performance summary."""
        total_value = self.get_total_value()
        total_return = (total_value - self.initial_capital) / self.initial_capital
        
        return {
            'initial_capital': self.initial_capital,
            'current_value': total_value,
            'cash_balance': self.cash_balance,
            'positions_value': self.get_positions_value(),
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'current_drawdown': self._current_drawdown,
            'peak_value': self._peak_value,
            'number_of_positions': len(self.positions)
        }
