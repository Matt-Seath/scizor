import time
import threading
from typing import Dict, List, Optional, Callable
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import structlog
from app.config.settings import settings

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter for IBKR API requests"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self) -> bool:
        """Acquire a token for making a request"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.max_requests, 
                self.tokens + (elapsed * self.max_requests / self.time_window)
            )
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
    
    def wait_for_token(self) -> None:
        """Wait until a token is available"""
        while not self.acquire():
            time.sleep(0.1)


class IBKRClient(EWrapper, EClient):
    """
    Interactive Brokers TWS API Client
    Handles connection, rate limiting, and basic API operations
    """
    
    def __init__(self):
        EClient.__init__(self, self)
        
        # Connection settings
        self.host = settings.ibkr_host
        self.port = settings.ibkr_port if not settings.testing else settings.ibkr_paper_port
        self.client_id = settings.ibkr_client_id
        
        # Rate limiters (using 80% of max to be safe)
        self.rate_limiter = RateLimiter(40, 1)  # 40 req/sec (80% of 50)
        self.historical_limiter = RateLimiter(48, 600)  # 48 req/10min (80% of 60)
        
        # Connection state
        self.is_connected = False
        self.next_valid_order_id = None
        self.connection_retry_count = 0
        self.max_retries = 3
        
        # Data storage
        self.market_data_callbacks: Dict[int, Callable] = {}
        self.historical_data_callbacks: Dict[int, Callable] = {}
        self.contract_details_callbacks: Dict[int, Callable] = {}
        
        # Request tracking
        self.request_counter = 1000
        self.pending_requests = set()
        
        logger.info("IBKR Client initialized", 
                   host=self.host, port=self.port, client_id=self.client_id)
    
    def get_next_request_id(self) -> int:
        """Get next unique request ID"""
        self.request_counter += 1
        return self.request_counter
    
    def connect_to_tws(self) -> bool:
        """Connect to TWS/Gateway with retry logic"""
        try:
            logger.info("Attempting to connect to TWS", 
                       host=self.host, port=self.port)
            
            self.connect(self.host, self.port, self.client_id)
            
            # Wait for connection confirmation
            timeout = 10  # seconds
            start_time = time.time()
            
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.is_connected:
                logger.info("Successfully connected to TWS")
                self.connection_retry_count = 0
                return True
            else:
                logger.error("Connection timeout")
                return False
                
        except Exception as e:
            logger.error("Connection failed", error=str(e))
            return False
    
    def disconnect_from_tws(self) -> None:
        """Safely disconnect from TWS"""
        try:
            if self.is_connected:
                self.disconnect()
                self.is_connected = False
                logger.info("Disconnected from TWS")
        except Exception as e:
            logger.error("Error during disconnect", error=str(e))
    
    def ensure_connection(self) -> bool:
        """Ensure we have an active connection, reconnect if needed"""
        if self.is_connected:
            return True
        
        if self.connection_retry_count >= self.max_retries:
            logger.error("Max connection retries exceeded")
            return False
        
        self.connection_retry_count += 1
        logger.info("Attempting to reconnect", retry=self.connection_retry_count)
        
        return self.connect_to_tws()
    
    # EWrapper callback implementations
    def nextValidId(self, orderId: int):
        """Called when connection is established"""
        super().nextValidId(orderId)
        self.next_valid_order_id = orderId
        self.is_connected = True
        logger.info("Connection established", next_order_id=orderId)
    
    def connectAck(self):
        """Connection acknowledgment"""
        super().connectAck()
        logger.debug("Connection acknowledged")
    
    def connectionClosed(self):
        """Called when connection is lost"""
        super().connectionClosed()
        self.is_connected = False
        logger.warning("Connection closed")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle API errors"""
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        
        # Rate limit violations
        if errorCode == 100:
            logger.warning("Rate limit exceeded", 
                          req_id=reqId, error_string=errorString)
            time.sleep(1)  # Pause briefly
        
        # Connection issues
        elif errorCode in [1100, 1101, 1102]:
            if errorCode == 1100:
                self.is_connected = False
                logger.error("Connection lost", error_code=errorCode)
            elif errorCode == 1101:
                logger.warning("Connection restored, data lost", error_code=errorCode)
                self.is_connected = True
            elif errorCode == 1102:
                logger.info("Connection restored, data maintained", error_code=errorCode)
                self.is_connected = True
        
        # Market data issues
        elif errorCode in [354, 10089]:
            logger.warning("Market data subscription issue", 
                          error_code=errorCode, error_string=errorString)
        
        # General errors
        else:
            logger.error("API error", 
                        req_id=reqId, error_code=errorCode, 
                        error_string=errorString)
    
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Market data price tick"""
        super().tickPrice(reqId, tickType, price, attrib)
        if reqId in self.market_data_callbacks:
            self.market_data_callbacks[reqId]('price', tickType, price, attrib)
    
    def tickSize(self, reqId: int, tickType: int, size: float):
        """Market data size tick"""
        super().tickSize(reqId, tickType, size)
        if reqId in self.market_data_callbacks:
            self.market_data_callbacks[reqId]('size', tickType, size, None)
    
    def historicalData(self, reqId: int, bar):
        """Historical data bar"""
        super().historicalData(reqId, bar)
        if reqId in self.historical_data_callbacks:
            self.historical_data_callbacks[reqId](bar)
    
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data request completed"""
        super().historicalDataEnd(reqId, start, end)
        if reqId in self.historical_data_callbacks:
            # Clean up callback
            del self.historical_data_callbacks[reqId]
        self.pending_requests.discard(reqId)
    
    def contractDetails(self, reqId: int, contractDetails):
        """Contract details response"""
        super().contractDetails(reqId, contractDetails)
        if reqId in self.contract_details_callbacks:
            self.contract_details_callbacks[reqId](contractDetails)
    
    def contractDetailsEnd(self, reqId: int):
        """Contract details request completed"""
        super().contractDetailsEnd(reqId)
        if reqId in self.contract_details_callbacks:
            del self.contract_details_callbacks[reqId]
        self.pending_requests.discard(reqId)
    
    # API request methods with rate limiting
    def request_market_data(self, contract: Contract, callback: Callable) -> Optional[int]:
        """Request real-time market data with rate limiting"""
        if not self.ensure_connection():
            return None
        
        if not self.rate_limiter.acquire():
            logger.warning("Rate limit reached, waiting for token")
            self.rate_limiter.wait_for_token()
        
        req_id = self.get_next_request_id()
        self.market_data_callbacks[req_id] = callback
        
        try:
            # Set market data type based on configuration
            if settings.enable_live_data:
                self.reqMarketDataType(1)  # Live data
            else:
                self.reqMarketDataType(3)  # Delayed data
            
            self.reqMktData(req_id, contract, "", False, False, [])
            self.pending_requests.add(req_id)
            
            logger.debug("Market data requested", req_id=req_id, symbol=contract.symbol)
            return req_id
            
        except Exception as e:
            logger.error("Failed to request market data", error=str(e))
            if req_id in self.market_data_callbacks:
                del self.market_data_callbacks[req_id]
            return None
    
    def request_historical_data(self, contract: Contract, duration: str, 
                              bar_size: str, callback: Callable) -> Optional[int]:
        """Request historical data with rate limiting"""
        if not self.ensure_connection():
            return None
        
        if not self.historical_limiter.acquire():
            logger.warning("Historical data rate limit reached, waiting")
            self.historical_limiter.wait_for_token()
        
        req_id = self.get_next_request_id()
        self.historical_data_callbacks[req_id] = callback
        
        try:
            self.reqHistoricalData(
                req_id, contract, "", duration, bar_size, 
                "TRADES", 1, 1, False, []
            )
            self.pending_requests.add(req_id)
            
            logger.debug("Historical data requested", 
                        req_id=req_id, symbol=contract.symbol, 
                        duration=duration, bar_size=bar_size)
            return req_id
            
        except Exception as e:
            logger.error("Failed to request historical data", error=str(e))
            if req_id in self.historical_data_callbacks:
                del self.historical_data_callbacks[req_id]
            return None
    
    def request_contract_details(self, contract: Contract, callback: Callable) -> Optional[int]:
        """Request contract details"""
        if not self.ensure_connection():
            return None
        
        if not self.rate_limiter.acquire():
            self.rate_limiter.wait_for_token()
        
        req_id = self.get_next_request_id()
        self.contract_details_callbacks[req_id] = callback
        
        try:
            self.reqContractDetails(req_id, contract)
            self.pending_requests.add(req_id)
            
            logger.debug("Contract details requested", 
                        req_id=req_id, symbol=contract.symbol)
            return req_id
            
        except Exception as e:
            logger.error("Failed to request contract details", error=str(e))
            if req_id in self.contract_details_callbacks:
                del self.contract_details_callbacks[req_id]
            return None
    
    def cancel_market_data(self, req_id: int) -> None:
        """Cancel market data subscription"""
        try:
            self.cancelMktData(req_id)
            if req_id in self.market_data_callbacks:
                del self.market_data_callbacks[req_id]
            self.pending_requests.discard(req_id)
            logger.debug("Market data cancelled", req_id=req_id)
        except Exception as e:
            logger.error("Failed to cancel market data", req_id=req_id, error=str(e))
    
    def get_connection_status(self) -> Dict[str, any]:
        """Get current connection status"""
        return {
            "connected": self.is_connected,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "retry_count": self.connection_retry_count,
            "pending_requests": len(self.pending_requests),
            "rate_limiter_tokens": self.rate_limiter.tokens,
            "historical_limiter_tokens": self.historical_limiter.tokens
        }