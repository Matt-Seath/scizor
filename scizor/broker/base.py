"""
Broker integrations and adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class Order:
    """Represents a trading order."""
    
    def __init__(
        self,
        symbol: str,
        action: str,  # 'buy' or 'sell'
        quantity: float,
        order_type: str = 'market',  # 'market', 'limit', 'stop'
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ):
        self.symbol = symbol
        self.action = action
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        self.stop_price = stop_price
        self.order_id = None
        self.status = 'pending'
        self.timestamp = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'order_type': self.order_type,
            'price': self.price,
            'stop_price': self.stop_price,
            'order_id': self.order_id,
            'status': self.status,
            'timestamp': self.timestamp
        }


class BaseBroker(ABC):
    """Abstract base class for broker adapters."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the broker."""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Place an order and return order ID."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        pass
    
    async def place_buy_order(self, symbol: str, quantity: float, order_type: str = 'market', price: Optional[float] = None) -> str:
        """Convenience method to place a buy order."""
        order = Order(symbol, 'buy', quantity, order_type, price)
        return await self.place_order(order)
    
    async def place_sell_order(self, symbol: str, quantity: float, order_type: str = 'market', price: Optional[float] = None) -> str:
        """Convenience method to place a sell order."""
        order = Order(symbol, 'sell', quantity, order_type, price)
        return await self.place_order(order)


class MockBroker(BaseBroker):
    """Mock broker for testing and development."""
    
    def __init__(self):
        self.connected = False
        self.orders = {}
        self.positions = {}
        self.account_balance = 100000.0
        self._order_counter = 0
        
    async def connect(self) -> bool:
        """Connect to mock broker."""
        self.connected = True
        return True
    
    async def disconnect(self):
        """Disconnect from mock broker."""
        self.connected = False
    
    async def place_order(self, order: Order) -> str:
        """Place a mock order."""
        if not self.connected:
            raise RuntimeError("Not connected to broker")
            
        self._order_counter += 1
        order_id = f"MOCK_{self._order_counter}"
        order.order_id = order_id
        order.status = 'filled'  # Immediately fill for mock
        
        # Update positions
        if order.action == 'buy':
            current_qty = self.positions.get(order.symbol, 0)
            self.positions[order.symbol] = current_qty + order.quantity
        elif order.action == 'sell':
            current_qty = self.positions.get(order.symbol, 0)
            self.positions[order.symbol] = max(0, current_qty - order.quantity)
        
        self.orders[order_id] = order
        return order_id
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a mock order."""
        if order_id in self.orders:
            self.orders[order_id].status = 'cancelled'
            return True
        return False
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get mock order status."""
        if order_id in self.orders:
            return self.orders[order_id].to_dict()
        return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get mock positions."""
        positions = []
        for symbol, quantity in self.positions.items():
            if quantity > 0:
                positions.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'market_value': quantity * 100,  # Mock price
                    'unrealized_pnl': 0
                })
        return positions
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get mock account info."""
        return {
            'account_id': 'MOCK_ACCOUNT',
            'cash_balance': self.account_balance,
            'total_value': self.account_balance,
            'buying_power': self.account_balance,
            'positions_value': sum(qty * 100 for qty in self.positions.values())
        }
