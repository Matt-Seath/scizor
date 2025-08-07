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
        self.connection_ready = False  # Full connection readiness flag
        
        # Data storage
        self.market_data: Dict[int, Dict] = {}
        self.historical_data: Dict[int, List[BarData]] = {}
        self.positions: List = []
        self.account_values: Dict = {}
        self.open_orders: List = []
        self.executions: List = []
        self.contract_details: Dict[int, List] = {}
        
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
        """Receive next valid order ID - indicates full connection readiness."""
        self.next_order_id = orderId
        self.connection_ready = True  # Add connection readiness flag
        logger.info(f"IBKR connection ready - Next valid order ID: {orderId}")
        
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
        
    def contractDetails(self, reqId: int, contractDetails):
        """Handle contract details response."""
        if reqId not in self.contract_details:
            self.contract_details[reqId] = []
        self.contract_details[reqId].append(contractDetails)
        logger.info(f"Received contract details for request {reqId}: {contractDetails.contract.symbol}")
        
    def contractDetailsEnd(self, reqId: int):
        """Contract details response completed."""
        logger.info(f"Contract details completed for request {reqId}")
        
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
        
    def is_connected(self) -> bool:
        """Check if client is connected and ready for requests."""
        return self.isConnected() and self.wrapper.connected and self.wrapper.connection_ready
        
    def disconnect_and_cleanup(self):
        """Disconnect and cleanup resources."""
        if self.isConnected():
            self.disconnect()
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
        self._last_request_time = 0.0  # Track request timing for pacing
        
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
                
            logger.info("Socket connection established, waiting for connection readiness...")
            
            # Wait for nextValidID to indicate full connection readiness
            start_time = time.time()
            while not self.wrapper.connection_ready and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
                
            if not self.wrapper.connection_ready:
                logger.warning("Connection established but nextValidID not received - proceeding anyway")
                # Don't fail here, some data requests might still work
                
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

    def request_contract_details(self, req_id: int, contract: Contract) -> bool:
        """Request contract details."""
        try:
            self.client.reqContractDetails(req_id, contract)
            logger.info(f"Requested contract details for {contract.symbol} (reqId: {req_id})")
            return True
        except Exception as e:
            logger.error(f"Error requesting contract details: {e}")
            return False

    async def get_contract_details(self, contract: Contract, timeout: float = 10.0) -> Optional[List]:
        """Get contract details with timeout and proper pacing."""
        if not self.is_connected():
            logger.error("Not connected to IBKR API")
            return None
            
        # Enforce request pacing (minimum 50ms between requests)
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < 0.05:  # 50ms minimum
            await asyncio.sleep(0.05 - time_since_last)
        
        # Generate unique req_id using timestamp to avoid conflicts
        req_id = int(time.time() * 1000) % 100000 + 1000  
        
        # Ensure this request ID isn't already in use
        if req_id in self.wrapper.contract_details:
            del self.wrapper.contract_details[req_id]
        
        logger.info(f"Requesting contract details for {contract.symbol} with reqId {req_id}")
        
        # Request contract details
        success = self.request_contract_details(req_id, contract)
        if not success:
            logger.error(f"Failed to send contract details request for {contract.symbol}")
            return None
            
        self._last_request_time = time.time()  # Update request time
            
        # Wait for response - don't check connection during wait as it may be temporarily unavailable
        start_time = time.time()
        while req_id not in self.wrapper.contract_details and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
            
        if req_id in self.wrapper.contract_details:
            details = self.wrapper.contract_details[req_id]
            logger.info(f"Successfully received {len(details)} contract details for {contract.symbol}")
            return details
        else:
            logger.warning(f"Timeout waiting for contract details for {contract.symbol} (reqId: {req_id})")
            return None

    async def get_historical_data(self, contract: Contract, end_date: str, duration: str = "1 D", 
                                 bar_size: str = "1 day", what_to_show: str = "TRADES", 
                                 use_rth: bool = True, format_date: int = 1, 
                                 timeout: float = 30.0) -> Optional[List]:
        """Get historical data for a contract.
        
        Args:
            contract: IBKR contract object
            end_date: End date for data (format: "YYYYMMDD HH:MM:SS")
            duration: Duration string (e.g., "1 D", "1 W", "1 M")
            bar_size: Bar size (e.g., "1 day", "1 hour", "1 min")
            what_to_show: Data type ("TRADES", "MIDPOINT", "BID", "ASK")
            use_rth: Use regular trading hours only
            format_date: Date format (1 for string, 2 for Unix timestamp)
            timeout: Timeout in seconds
            
        Returns:
            List of BarData objects or None if failed
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR API")
            return None
        
        # Enforce request pacing (minimum 50ms between requests)
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < 0.05:  # 50ms minimum
            await asyncio.sleep(0.05 - time_since_last)
        
        # Generate unique req_id
        req_id = int(time.time() * 1000) % 100000 + 2000  # Different range from contract details
        
        # Clear any existing data for this request
        if req_id in self.wrapper.historical_data:
            del self.wrapper.historical_data[req_id]
        
        logger.info(f"Requesting historical data for {contract.symbol} (reqId: {req_id})")
        
        try:
            # Request historical data
            self.client.reqHistoricalData(
                reqId=req_id,
                contract=contract,
                endDateTime=end_date,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=format_date,
                keepUpToDate=False,
                chartOptions=[]
            )
            
            self._last_request_time = time.time()
            
            # Wait for historical data end signal
            start_time = time.time()
            data_complete = False
            
            while not data_complete and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
                
                # Check for data completion through the data queue
                try:
                    while True:
                        data = self.wrapper.data_queue.get_nowait()
                        if (data.get("type") == "historical_data_end" and 
                            data.get("reqId") == req_id):
                            data_complete = True
                            break
                except:
                    pass  # Queue empty, continue waiting
            
            if data_complete and req_id in self.wrapper.historical_data:
                bars = self.wrapper.historical_data[req_id]
                logger.info(f"Successfully received {len(bars)} historical bars for {contract.symbol}")
                return bars
            else:
                logger.warning(f"Timeout or no data received for {contract.symbol} (reqId: {req_id})")
                return None
                
        except Exception as e:
            logger.error(f"Error requesting historical data for {contract.symbol}: {str(e)}")
            return None
