"""IBKR API client implementation for Scizor trading system."""

import asyncio
import logging
import threading
import time
from datetime import datetime
from queue import Empty, Queue
from typing import Dict, List, Optional

from ibapi.client import EClient
from ibapi.common import BarData, TickAttrib, TickerId
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper

logger = logging.getLogger(__name__)


class IBKRWrapper(EWrapper):
    """IBKR API wrapper to handle incoming data."""
    
    def __init__(self):
        super().__init__()
        self.data_queue = Queue()
        self.error_queue = Queue()
        self.next_order_id: Optional[int] = None
        self.connected = False
        
        # Data storage
        self.market_data: Dict[int, Dict] = {}
        self.historical_data: Dict[int, List[BarData]] = {}
        self.positions: List = []
        self.account_values: Dict = {}
        self.open_orders: List = []
        self.executions: List = []
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle error messages."""
        error_msg = f"Error {errorCode}: {errorString}"
        if reqId != -1:
            error_msg = f"Request {reqId} - {error_msg}"
            
        logger.error(error_msg)
        self.error_queue.put({
            "reqId": reqId,
            "errorCode": errorCode,
            "errorString": errorString,
            "timestamp": datetime.now()
        })
        
    def connectAck(self):
        """Acknowledge successful connection."""
        logger.info("IBKR API connection established")
        self.connected = True
        
    def nextValidId(self, orderId: int):
        """Receive next valid order ID."""
        self.next_order_id = orderId
        logger.info(f"Next valid order ID: {orderId}")
        
    def managedAccounts(self, accountsList: str):
        """Receive managed accounts."""
        accounts = accountsList.split(",")
        logger.info(f"Managed accounts: {accounts}")
        self.data_queue.put({
            "type": "managed_accounts",
            "data": accounts,
            "timestamp": datetime.now()
        })
        
    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib: TickAttrib):
        """Handle real-time price updates."""
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
            
        self.market_data[reqId][tickType] = {
            "price": price,
            "timestamp": datetime.now(),
            "attrib": attrib
        }
        
        self.data_queue.put({
            "type": "tick_price",
            "reqId": reqId,
            "tickType": tickType,
            "price": price,
            "attrib": attrib,
            "timestamp": datetime.now()
        })
        
    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        """Handle real-time size updates."""
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
            
        self.market_data[reqId][f"{tickType}_size"] = {
            "size": size,
            "timestamp": datetime.now()
        }
        
        self.data_queue.put({
            "type": "tick_size",
            "reqId": reqId,
            "tickType": tickType,
            "size": size,
            "timestamp": datetime.now()
        })
        
    def historicalData(self, reqId: int, bar: BarData):
        """Handle historical data bars."""
        if reqId not in self.historical_data:
            self.historical_data[reqId] = []
            
        self.historical_data[reqId].append(bar)
        
        self.data_queue.put({
            "type": "historical_data",
            "reqId": reqId,
            "bar": bar,
            "timestamp": datetime.now()
        })
        
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data request completed."""
        logger.info(f"Historical data request {reqId} completed: {start} to {end}")
        self.data_queue.put({
            "type": "historical_data_end",
            "reqId": reqId,
            "start": start,
            "end": end,
            "timestamp": datetime.now()
        })
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Handle position updates."""
        position_data = {
            "account": account,
            "contract": contract,
            "position": position,
            "avgCost": avgCost,
            "timestamp": datetime.now()
        }
        
        self.positions.append(position_data)
        self.data_queue.put({
            "type": "position",
            "data": position_data,
            "timestamp": datetime.now()
        })
        
    def positionEnd(self):
        """Position updates completed."""
        logger.info("Position updates completed")
        self.data_queue.put({
            "type": "position_end",
            "timestamp": datetime.now()
        })
        
    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """Handle account value updates."""
        self.account_values[key] = {
            "value": val,
            "currency": currency,
            "account": accountName,
            "timestamp": datetime.now()
        }
        
        self.data_queue.put({
            "type": "account_value",
            "key": key,
            "value": val,
            "currency": currency,
            "account": accountName,
            "timestamp": datetime.now()
        })
        
    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState):
        """Handle open order updates."""
        order_data = {
            "orderId": orderId,
            "contract": contract,
            "order": order,
            "orderState": orderState,
            "timestamp": datetime.now()
        }
        
        self.open_orders.append(order_data)
        self.data_queue.put({
            "type": "open_order",
            "data": order_data,
            "timestamp": datetime.now()
        })
        
    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float,
                   avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                   clientId: int, whyHeld: str, mktCapPrice: float):
        """Handle order status updates."""
        status_data = {
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "permId": permId,
            "parentId": parentId,
            "lastFillPrice": lastFillPrice,
            "clientId": clientId,
            "whyHeld": whyHeld,
            "mktCapPrice": mktCapPrice,
            "timestamp": datetime.now()
        }
        
        self.data_queue.put({
            "type": "order_status",
            "data": status_data,
            "timestamp": datetime.now()
        })
        
    def execDetails(self, reqId: int, contract: Contract, execution):
        """Handle execution details."""
        exec_data = {
            "reqId": reqId,
            "contract": contract,
            "execution": execution,
            "timestamp": datetime.now()
        }
        
        self.executions.append(exec_data)
        self.data_queue.put({
            "type": "execution",
            "data": exec_data,
            "timestamp": datetime.now()
        })


class IBKRClient(EClient):
    """IBKR API client implementation."""
    
    def __init__(self, wrapper: IBKRWrapper):
        super().__init__(wrapper)
        self.wrapper = wrapper
        self._is_connected = False
        
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected and self.wrapper.connected
        
    def disconnect_and_cleanup(self):
        """Disconnect and cleanup resources."""
        if self._is_connected:
            self.disconnect()
            self._is_connected = False
            logger.info("IBKR client disconnected")


class IBKRManager:
    """High-level IBKR API manager."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        
        self.wrapper = IBKRWrapper()
        self.client = IBKRClient(self.wrapper)
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        
    async def connect(self, timeout: int = 30) -> bool:
        """Connect to IBKR API."""
        try:
            logger.info(f"Connecting to IBKR at {self.host}:{self.port} with client ID {self.client_id}")
            
            # Connect to IBKR (note: this might return None instead of True)
            connect_result = self.client.connect(self.host, self.port, self.client_id)
            logger.info(f"client.connect() returned: {connect_result}")
            
            # Start reader thread regardless of return value
            self._start_reader_thread()
            
            # Wait for connection acknowledgment
            start_time = time.time()
            while not self.wrapper.connected and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
                
            if not self.wrapper.connected:
                logger.error("Connection timeout - no acknowledgment received")
                await self.disconnect()
                return False
                
            # For read-only data collection, we don't need to wait for nextValidId
            # Just return success once we have connection acknowledgment
            logger.info("Successfully connected to IBKR API")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to IBKR: {e}")
            return False
            
    def _start_reader_thread(self):
        """Start the reader thread for processing incoming messages."""
        if self._reader_thread is None or not self._reader_thread.is_alive():
            self._running = True
            self._reader_thread = threading.Thread(target=self._run_reader, daemon=True)
            self._reader_thread.start()
            
    def _run_reader(self):
        """Run the message reader loop."""
        while self._running and self.client.isConnected():
            try:
                self.client.run()
            except Exception as e:
                logger.error(f"Error in reader thread: {e}")
                break
                
    async def disconnect(self):
        """Disconnect from IBKR API."""
        try:
            self._running = False
            
            if self.client.isConnected():
                self.client.disconnect_and_cleanup()
                
            # Wait for reader thread to finish
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=5)
                
            logger.info("Disconnected from IBKR API")
            
        except Exception as e:
            logger.error(f"Error disconnecting from IBKR: {e}")
            
    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self.client.is_connected()
        
    async def get_data(self, timeout: float = 1.0) -> Optional[Dict]:
        """Get data from the queue with timeout."""
        try:
            # Convert async timeout to blocking timeout
            return self.wrapper.data_queue.get(timeout=timeout)
        except Empty:
            return None
            
    async def get_error(self, timeout: float = 1.0) -> Optional[Dict]:
        """Get error from the queue with timeout."""
        try:
            return self.wrapper.error_queue.get(timeout=timeout)
        except Empty:
            return None
            
    def request_market_data(self, req_id: int, contract: Contract, 
                          generic_tick_list: str = "", snapshot: bool = False) -> bool:
        """Request real-time market data."""
        try:
            self.client.reqMktData(req_id, contract, generic_tick_list, snapshot, False, [])
            logger.info(f"Requested market data for {contract.symbol} (reqId: {req_id})")
            return True
        except Exception as e:
            logger.error(f"Error requesting market data: {e}")
            return False
            
    def cancel_market_data(self, req_id: int) -> bool:
        """Cancel market data subscription."""
        try:
            self.client.cancelMktData(req_id)
            logger.info(f"Cancelled market data subscription (reqId: {req_id})")
            return True
        except Exception as e:
            logger.error(f"Error cancelling market data: {e}")
            return False
            
    def request_historical_data(self, req_id: int, contract: Contract, 
                               end_date: str, duration: str, bar_size: str,
                               what_to_show: str = "TRADES", use_rth: bool = True) -> bool:
        """Request historical data."""
        try:
            self.client.reqHistoricalData(
                req_id, contract, end_date, duration, bar_size, 
                what_to_show, int(use_rth), 1, False, []
            )
            logger.info(f"Requested historical data for {contract.symbol} (reqId: {req_id})")
            return True
        except Exception as e:
            logger.error(f"Error requesting historical data: {e}")
            return False
            
    def place_order(self, order_id: int, contract: Contract, order: Order) -> bool:
        """Place an order."""
        try:
            self.client.placeOrder(order_id, contract, order)
            logger.info(f"Placed order {order_id} for {contract.symbol}")
            return True
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return False
            
    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order."""
        try:
            self.client.cancelOrder(order_id, "")
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
            
    def request_positions(self) -> bool:
        """Request current positions."""
        try:
            self.client.reqPositions()
            logger.info("Requested positions")
            return True
        except Exception as e:
            logger.error(f"Error requesting positions: {e}")
            return False
            
    def request_account_updates(self, account: str) -> bool:
        """Request account updates."""
        try:
            self.client.reqAccountUpdates(True, account)
            logger.info(f"Requested account updates for {account}")
            return True
        except Exception as e:
            logger.error(f"Error requesting account updates: {e}")
            return False
            
    def get_next_order_id(self) -> Optional[int]:
        """Get the next valid order ID."""
        if self.wrapper.next_order_id is not None:
            order_id = self.wrapper.next_order_id
            self.wrapper.next_order_id += 1
            return order_id
        return None
