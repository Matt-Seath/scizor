import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
from app.config.settings import settings
from app.config.database import get_async_session
from app.data.models.market import ConnectionState, ApiRequest

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
        
        # Enhanced connection state
        self.is_connected = False
        self.next_valid_order_id = None
        self.connection_retry_count = 0
        self.max_retries = 5
        self.connection_started_at = None
        self.last_heartbeat = None
        self.last_error_code = None
        self.last_error_message = None
        self.error_count = 0
        self.reconnect_delay = 5  # Initial reconnect delay in seconds
        self.max_reconnect_delay = 300  # Max 5 minutes between attempts
        
        # Health monitoring
        self.health_check_interval = 30  # seconds
        self.last_data_received = None
        self.connection_timeout = 10  # seconds
        self.health_monitor_thread = None
        self.stop_health_monitor = False
        
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
        self.connection_started_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.error_count = 0
        
        # Start health monitoring
        self._start_health_monitoring()
        
        logger.info("Connection established", 
                   next_order_id=orderId,
                   client_id=self.client_id,
                   connection_time=self.connection_started_at)
        
        # Update database state asynchronously
        asyncio.create_task(self._update_connection_state("CONNECTED"))
    
    def connectAck(self):
        """Connection acknowledgment"""
        super().connectAck()
        logger.debug("Connection acknowledged")
    
    def connectionClosed(self):
        """Called when connection is lost"""
        super().connectionClosed()
        self.is_connected = False
        self.last_heartbeat = None
        
        # Stop health monitoring
        self._stop_health_monitoring()
        
        logger.warning("Connection closed", 
                      client_id=self.client_id,
                      uptime_seconds=self._get_connection_uptime())
        
        # Update database state asynchronously
        asyncio.create_task(self._update_connection_state("DISCONNECTED"))
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Enhanced error handling with recovery strategies"""
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        
        self.last_error_code = errorCode
        self.last_error_message = errorString
        self.error_count += 1
        
        # Log the API request error asynchronously
        asyncio.create_task(self._log_api_error(reqId, errorCode, errorString))
        
        # Rate limit violations (100, 162)
        if errorCode in [100, 162]:
            logger.warning("Rate limit exceeded", 
                          req_id=reqId, error_code=errorCode, 
                          error_string=errorString)
            self._handle_rate_limit_error()
        
        # Connection issues
        elif errorCode in [1100, 1101, 1102, 1300, 2103, 2104, 2105, 2106, 2107, 2108, 2110]:
            self._handle_connection_error(errorCode, errorString)
        
        # Market data subscription issues
        elif errorCode in [354, 10089, 10090, 10091, 10167, 10168]:
            logger.warning("Market data subscription issue", 
                          req_id=reqId, error_code=errorCode, 
                          error_string=errorString)
        
        # Contract/Symbol errors
        elif errorCode in [200, 201, 321, 322]:
            logger.error("Contract/symbol error", 
                        req_id=reqId, error_code=errorCode,
                        error_string=errorString)
        
        # System errors requiring reconnection
        elif errorCode in [502, 503, 504, 507]:
            logger.error("System error, may require reconnection", 
                        error_code=errorCode, error_string=errorString)
        
        # General errors
        else:
            logger.error("API error", 
                        req_id=reqId, error_code=errorCode, 
                        error_string=errorString)
    
    def _handle_rate_limit_error(self):
        """Handle rate limit violations"""
        # Increase delay between requests
        self.rate_limiter.tokens = 0  # Reset tokens to force waiting
        time.sleep(2)  # Pause briefly to let rate limit reset
    
    def _handle_connection_error(self, error_code: int, error_string: str):
        """Handle connection-related errors"""
        if error_code == 1100:  # Connectivity lost
            self.is_connected = False
            logger.error("Connection lost", error_code=error_code)
            asyncio.create_task(self._update_connection_state("DISCONNECTED"))
            
        elif error_code == 1101:  # Connection restored, data lost
            logger.warning("Connection restored but data lost", error_code=error_code)
            self.is_connected = True
            self.last_heartbeat = datetime.now()
            asyncio.create_task(self._update_connection_state("CONNECTED"))
            
        elif error_code == 1102:  # Connection restored, data maintained
            logger.info("Connection fully restored", error_code=error_code)
            self.is_connected = True
            self.last_heartbeat = datetime.now()
            asyncio.create_task(self._update_connection_state("CONNECTED"))
            
        elif error_code == 1300:  # TWS socket port reset
            logger.error("TWS socket port reset", error_string=error_string)
            self.is_connected = False
    
    async def _log_api_error(self, req_id: int, error_code: int, error_string: str):
        """Log API error to database for monitoring"""
        try:
            async with get_async_session() as db:
                # Determine request type based on req_id and callbacks
                request_type = "UNKNOWN"
                if req_id in self.market_data_callbacks:
                    request_type = "MARKET_DATA"
                elif req_id in self.historical_data_callbacks:
                    request_type = "HISTORICAL_DATA"
                elif req_id in self.contract_details_callbacks:
                    request_type = "CONTRACT_DETAILS"
                
                # Log the API error
                insert_stmt = insert(ApiRequest).values(
                    request_type=request_type,
                    req_id=req_id,
                    timestamp=datetime.now(),
                    status="FAILED",
                    error_code=error_code,
                    error_message=error_string[:500],  # Limit length
                    client_id=self.client_id
                )
                await db.execute(insert_stmt)
                await db.commit()
                
        except Exception as e:
            logger.error("Failed to log API error", error=str(e))
    
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Market data price tick with data reception tracking"""
        super().tickPrice(reqId, tickType, price, attrib)
        self.last_data_received = datetime.now()
        
        if reqId in self.market_data_callbacks:
            self.market_data_callbacks[reqId]('price', tickType, price, attrib)
    
    def tickSize(self, reqId: int, tickType: int, size: float):
        """Market data size tick with data reception tracking"""
        super().tickSize(reqId, tickType, size)
        self.last_data_received = datetime.now()
        
        if reqId in self.market_data_callbacks:
            self.market_data_callbacks[reqId]('size', tickType, size, None)
    
    def historicalData(self, reqId: int, bar):
        """Historical data bar with data reception tracking"""
        super().historicalData(reqId, bar)
        self.last_data_received = datetime.now()
        
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
        """Contract details response with data reception tracking"""
        super().contractDetails(reqId, contractDetails)
        self.last_data_received = datetime.now()
        
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
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status"""
        uptime = self._get_connection_uptime()
        
        return {
            "connected": self.is_connected,
            "healthy": self._connection_healthy(),
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "connection_started_at": self.connection_started_at.isoformat() if self.connection_started_at else None,
            "uptime_seconds": uptime,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "retry_count": self.connection_retry_count,
            "error_count": self.error_count,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "pending_requests": len(self.pending_requests),
            "active_subscriptions": len(self.market_data_callbacks),
            "rate_limiter_tokens": round(self.rate_limiter.tokens, 2),
            "historical_limiter_tokens": round(self.historical_limiter.tokens, 2),
            "last_data_received": self.last_data_received.isoformat() if self.last_data_received else None
        }
    
    def _get_connection_uptime(self) -> Optional[int]:
        """Get connection uptime in seconds"""
        if self.connection_started_at and self.is_connected:
            return int((datetime.now() - self.connection_started_at).total_seconds())
        return None
    
    def _connection_healthy(self) -> bool:
        """Check if current connection is healthy"""
        if not self.is_connected:
            return False
        
        # Check for recent heartbeat
        if self.last_heartbeat:
            time_since_heartbeat = datetime.now() - self.last_heartbeat
            if time_since_heartbeat > timedelta(minutes=5):
                logger.warning("No heartbeat received recently", 
                             last_heartbeat=self.last_heartbeat)
                return False
        
        return True
    
    async def _update_connection_state(self, status: str):
        """Update connection state in database"""
        try:
            async with get_async_session() as db:
                # Update or insert connection state
                stmt = select(ConnectionState).where(ConnectionState.client_id == self.client_id)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing record
                    update_stmt = (
                        update(ConnectionState)
                        .where(ConnectionState.client_id == self.client_id)
                        .values(
                            status=status,
                            last_heartbeat=datetime.now(),
                            error_count=self.error_count,
                            last_error_code=self.last_error_code,
                            last_error_message=self.last_error_message,
                            connection_started_at=self.connection_started_at,
                            last_data_received_at=self.last_data_received
                        )
                    )
                    await db.execute(update_stmt)
                else:
                    # Insert new record
                    insert_stmt = insert(ConnectionState).values(
                        client_id=self.client_id,
                        status=status,
                        last_heartbeat=datetime.now(),
                        error_count=self.error_count,
                        last_error_code=self.last_error_code,
                        last_error_message=self.last_error_message,
                        connection_started_at=self.connection_started_at,
                        last_data_received_at=self.last_data_received
                    )
                    await db.execute(insert_stmt)
                
                await db.commit()
                
        except Exception as e:
            logger.error("Failed to update connection state", error=str(e))
    
    async def _log_api_request(self, request_type: str, req_id: int, symbol: str = None, 
                              status: str = "SUCCESS", error_msg: str = None):
        """Log API request for monitoring purposes"""
        try:
            async with get_async_session() as db:
                insert_stmt = insert(ApiRequest).values(
                    request_type=request_type,
                    req_id=req_id,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    status=status,
                    error_message=error_msg[:500] if error_msg else None,
                    client_id=self.client_id
                )
                await db.execute(insert_stmt)
                await db.commit()
        except Exception as e:
            logger.error("Failed to log API request", error=str(e))
    
    def _start_health_monitoring(self):
        """Start background health monitoring thread"""
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            return
        
        self.stop_health_monitor = False
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            name=f"IBKRHealthMonitor-{self.client_id}",
            daemon=True
        )
        self.health_monitor_thread.start()
        logger.debug("Health monitoring started")
    
    def _stop_health_monitoring(self):
        """Stop background health monitoring"""
        self.stop_health_monitor = True
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=5)
        logger.debug("Health monitoring stopped")
    
    def _health_monitor_loop(self):
        """Background health monitoring loop"""
        while not self.stop_health_monitor:
            try:
                if self.is_connected:
                    # Update heartbeat
                    self.last_heartbeat = datetime.now()
                    
                    # Update connection state in database
                    asyncio.create_task(self._update_connection_state("CONNECTED"))
                    
                    # Check for data staleness
                    if self.last_data_received:
                        time_since_data = datetime.now() - self.last_data_received
                        if time_since_data > timedelta(minutes=10):
                            logger.warning("No data received recently", 
                                         minutes_since_data=time_since_data.total_seconds() / 60)
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error("Health monitor error", error=str(e))
                time.sleep(self.health_check_interval)
    
    def shutdown(self):
        """Clean shutdown of the client"""
        logger.info("Shutting down IBKR client", client_id=self.client_id)
        
        # Stop health monitoring
        self._stop_health_monitoring()
        
        # Cancel all pending subscriptions
        for req_id in list(self.market_data_callbacks.keys()):
            self.cancel_market_data(req_id)
        
        # Disconnect from TWS
        self.disconnect_from_tws()
        
        # Update final connection state
        asyncio.create_task(self._update_connection_state("DISCONNECTED"))
        
        logger.info("IBKR client shutdown completed")