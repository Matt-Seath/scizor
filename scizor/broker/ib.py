"""
Interactive Brokers adapter using ib_insync.
"""

import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger

from scizor.broker.base import BaseBroker, Order


class InteractiveBrokersAdapter(BaseBroker):
    """Interactive Brokers adapter using ib_insync."""
    
    def __init__(
        self, 
        host: str = "127.0.0.1", 
        port: int = 7497, 
        client_id: int = 1,
        timeout: int = 30
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.ib = None
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to Interactive Brokers TWS/Gateway."""
        try:
            from ib_insync import IB
            
            self.ib = IB()
            
            # Connect to IB
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout
            )
            
            self.connected = True
            logger.info(f"Connected to IB at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to IB: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Interactive Brokers."""
        if self.ib and self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB")
    
    async def place_order(self, order: Order) -> str:
        """Place an order through IB."""
        if not self.connected or not self.ib:
            raise RuntimeError("Not connected to IB")
            
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder
            
            # Create contract
            contract = Stock(order.symbol, 'SMART', 'USD')
            
            # Create IB order
            if order.order_type == 'market':
                ib_order = MarketOrder(order.action.upper(), order.quantity)
            elif order.order_type == 'limit':
                if order.price is None:
                    raise ValueError("Limit order requires price")
                ib_order = LimitOrder(order.action.upper(), order.quantity, order.price)
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")
            
            # Place order
            trade = self.ib.placeOrder(contract, ib_order)
            
            # Wait for order to be submitted
            await asyncio.sleep(0.1)
            
            order.order_id = str(trade.order.orderId)
            order.status = trade.orderStatus.status
            
            logger.info(f"Placed {order.action} order for {order.quantity} {order.symbol}, ID: {order.order_id}")
            
            return order.order_id
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.connected or not self.ib:
            return False
            
        try:
            # Find the trade by order ID
            for trade in self.ib.trades():
                if str(trade.order.orderId) == order_id:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Cancelled order {order_id}")
                    return True
            
            logger.warning(f"Order {order_id} not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status."""
        if not self.connected or not self.ib:
            return {}
            
        try:
            # Find the trade by order ID
            for trade in self.ib.trades():
                if str(trade.order.orderId) == order_id:
                    return {
                        'order_id': order_id,
                        'status': trade.orderStatus.status,
                        'filled': trade.orderStatus.filled,
                        'remaining': trade.orderStatus.remaining,
                        'avg_fill_price': trade.orderStatus.avgFillPrice
                    }
            
            return {'order_id': order_id, 'status': 'not_found'}
            
        except Exception as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self.connected or not self.ib:
            return []
            
        try:
            positions = []
            for position in self.ib.positions():
                if position.position != 0:  # Only include non-zero positions
                    positions.append({
                        'symbol': position.contract.symbol,
                        'quantity': position.position,
                        'market_price': position.marketPrice,
                        'market_value': position.marketValue,
                        'avg_cost': position.avgCost,
                        'unrealized_pnl': position.unrealizedPNL
                    })
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        if not self.connected or not self.ib:
            return {}
            
        try:
            account_values = self.ib.accountValues()
            
            # Extract key account metrics
            account_info = {
                'account_id': self.ib.client.getAccount()
            }
            
            # Parse account values
            for value in account_values:
                if value.tag == 'TotalCashValue' and value.currency == 'USD':
                    account_info['cash_balance'] = float(value.value)
                elif value.tag == 'NetLiquidation' and value.currency == 'USD':
                    account_info['total_value'] = float(value.value)
                elif value.tag == 'BuyingPower' and value.currency == 'USD':
                    account_info['buying_power'] = float(value.value)
                elif value.tag == 'GrossPositionValue' and value.currency == 'USD':
                    account_info['positions_value'] = float(value.value)
            
            return account_info
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {}
    
    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time market data for a symbol."""
        if not self.connected or not self.ib:
            return None
            
        try:
            from ib_insync import Stock
            
            contract = Stock(symbol, 'SMART', 'USD')
            ticker = self.ib.reqMktData(contract)
            
            # Wait for data
            self.ib.sleep(1)
            
            return {
                'symbol': symbol,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'close': ticker.close,
                'volume': ticker.volume
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
