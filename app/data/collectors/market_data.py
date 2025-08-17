import asyncio
import time
from datetime import datetime, timedelta, time as datetime_time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import pytz
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.collectors.ibkr_client import IBKRClient
from app.data.collectors.asx_contracts import (
    create_asx_stock_contract, 
    get_asx200_symbols, 
    get_liquid_stocks
)
from app.config.database import AsyncSessionLocal
from app.config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class MarketDataPoint:
    """Single market data point"""
    symbol: str
    timestamp: datetime
    price: float
    volume: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None


@dataclass
class HistoricalBar:
    """Historical OHLCV bar"""
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: Optional[float] = None


class ASXMarketHours:
    """ASX market hours and trading session validation"""
    
    def __init__(self):
        self.timezone = pytz.timezone('Australia/Sydney')
        self.market_open = datetime_time(10, 0)   # 10:00 AM
        self.market_close = datetime_time(16, 0)  # 4:00 PM
        self.pre_market_start = datetime_time(7, 0)   # 7:00 AM
        self.after_hours_end = datetime_time(19, 0)   # 7:00 PM
    
    def is_market_open(self, dt: datetime = None) -> bool:
        """Check if ASX market is currently open"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        # Check if weekend
        if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        # Check market hours
        current_time = dt.time()
        return self.market_open <= current_time <= self.market_close
    
    def is_trading_day(self, dt: datetime = None) -> bool:
        """Check if today is a trading day"""
        if dt is None:
            dt = datetime.now(self.timezone)
            
        # Weekend check
        if dt.weekday() >= 5:
            return False
            
        # TODO: Add ASX holiday calendar check
        return True
    
    def next_market_open(self) -> datetime:
        """Get next market open time"""
        now = datetime.now(self.timezone)
        next_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # If after market close today, next open is tomorrow
        if now.time() > self.market_close:
            next_open += timedelta(days=1)
            
        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
            
        return next_open
    
    def time_until_market_open(self) -> timedelta:
        """Get time until next market open"""
        return self.next_market_open() - datetime.now(self.timezone)


class MarketDataCollector:
    """
    Collects market data from IBKR TWS API for ASX200 stocks
    Handles rate limiting, data validation, and storage
    """
    
    def __init__(self):
        self.ibkr_client = IBKRClient()
        self.market_hours = ASXMarketHours()
        self.active_subscriptions: Dict[int, str] = {}
        self.data_storage: Dict[str, List[MarketDataPoint]] = {}
        self.collection_stats = {
            "requests_made": 0,
            "successful_responses": 0,
            "errors": 0,
            "rate_limited": 0
        }
        
    async def start_collection(self) -> bool:
        """Start the market data collection service"""
        try:
            # Connect to TWS
            if not self.ibkr_client.connect_to_tws():
                logger.error("Failed to connect to TWS")
                return False
            
            logger.info("Market data collector started")
            return True
            
        except Exception as e:
            logger.error("Failed to start market data collector", error=str(e))
            return False
    
    async def stop_collection(self) -> None:
        """Stop the market data collection service"""
        try:
            # Cancel all active subscriptions
            for req_id in list(self.active_subscriptions.keys()):
                self.ibkr_client.cancel_market_data(req_id)
            
            self.active_subscriptions.clear()
            self.ibkr_client.disconnect_from_tws()
            
            logger.info("Market data collector stopped")
            
        except Exception as e:
            logger.error("Error stopping market data collector", error=str(e))
    
    def _market_data_callback(self, symbol: str) -> Callable:
        """Create callback function for market data updates"""
        def callback(data_type: str, tick_type: int, value: float, attrib):
            try:
                now = datetime.now(self.market_hours.timezone)
                
                if symbol not in self.data_storage:
                    self.data_storage[symbol] = []
                
                # Create or update market data point
                data_point = MarketDataPoint(
                    symbol=symbol,
                    timestamp=now,
                    price=value if data_type == 'price' and tick_type in [1, 2, 4] else 0,
                    volume=int(value) if data_type == 'size' and tick_type == 8 else 0
                )
                
                # Handle different tick types
                if data_type == 'price':
                    if tick_type == 1:  # Bid
                        data_point.bid = value
                    elif tick_type == 2:  # Ask
                        data_point.ask = value
                    elif tick_type == 4:  # Last
                        data_point.price = value
                elif data_type == 'size':
                    if tick_type == 0:  # Bid size
                        data_point.bid_size = int(value)
                    elif tick_type == 3:  # Ask size
                        data_point.ask_size = int(value)
                
                self.data_storage[symbol].append(data_point)
                self.collection_stats["successful_responses"] += 1
                
                logger.debug("Market data received", 
                           symbol=symbol, tick_type=tick_type, value=value)
                
            except Exception as e:
                logger.error("Error processing market data", 
                           symbol=symbol, error=str(e))
                self.collection_stats["errors"] += 1
        
        return callback
    
    async def subscribe_to_symbol(self, symbol: str) -> Optional[int]:
        """Subscribe to real-time market data for a symbol"""
        try:
            contract = create_asx_stock_contract(symbol)
            callback = self._market_data_callback(symbol)
            
            req_id = self.ibkr_client.request_market_data(contract, callback)
            
            if req_id:
                self.active_subscriptions[req_id] = symbol
                self.collection_stats["requests_made"] += 1
                logger.info("Subscribed to market data", symbol=symbol, req_id=req_id)
                return req_id
            else:
                logger.error("Failed to subscribe to market data", symbol=symbol)
                return None
                
        except Exception as e:
            logger.error("Error subscribing to market data", 
                        symbol=symbol, error=str(e))
            return None
    
    async def subscribe_to_asx200_sample(self, max_symbols: int = 10) -> List[int]:
        """Subscribe to a sample of ASX200 stocks for testing"""
        symbols = get_liquid_stocks(max_symbols)
        request_ids = []
        
        for symbol in symbols:
            req_id = await self.subscribe_to_symbol(symbol)
            if req_id:
                request_ids.append(req_id)
            
            # Rate limiting delay
            await asyncio.sleep(0.1)  # 100ms between requests
        
        logger.info("Subscribed to ASX200 sample", 
                   symbols=len(request_ids), total=len(symbols))
        return request_ids
    
    def _historical_data_callback(self, symbol: str, db_session: AsyncSession) -> Callable:
        """Create callback for historical data"""
        def callback(bar):
            try:
                historical_bar = HistoricalBar(
                    symbol=symbol,
                    date=datetime.strptime(bar.date, "%Y%m%d"),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume)
                )
                
                # TODO: Store in database
                logger.debug("Historical bar received", 
                           symbol=symbol, date=bar.date, close=bar.close)
                
                self.collection_stats["successful_responses"] += 1
                
            except Exception as e:
                logger.error("Error processing historical data", 
                           symbol=symbol, error=str(e))
                self.collection_stats["errors"] += 1
        
        return callback
    
    async def collect_daily_data(self, symbols: List[str] = None) -> bool:
        """
        Collect daily historical data for ASX200 stocks
        Respects rate limits and market hours
        """
        if symbols is None:
            symbols = get_asx200_symbols()
        
        # Check if we should collect data (after market close)
        now = datetime.now(self.market_hours.timezone)
        if self.market_hours.is_market_open(now):
            logger.warning("Market is still open, waiting for close")
            return False
        
        # Wait additional time after market close for data availability
        minutes_after_close = settings.data_collection_delay_minutes
        close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        collection_time = close_time + timedelta(minutes=minutes_after_close)
        
        if now < collection_time:
            wait_time = collection_time - now
            logger.info("Waiting for data availability", 
                       wait_minutes=wait_time.total_seconds() / 60)
            await asyncio.sleep(wait_time.total_seconds())
        
        logger.info("Starting daily data collection", symbols=len(symbols))
        
        successful_collections = 0
        
        async with AsyncSessionLocal() as db_session:
            for i, symbol in enumerate(symbols):
                try:
                    contract = create_asx_stock_contract(symbol)
                    callback = self._historical_data_callback(symbol, db_session)
                    
                    req_id = self.ibkr_client.request_historical_data(
                        contract, "1 D", "1 day", callback
                    )
                    
                    if req_id:
                        successful_collections += 1
                        self.collection_stats["requests_made"] += 1
                    
                    # Rate limiting: batch processing with delays
                    if (i + 1) % 10 == 0:  # Every 10 requests
                        logger.info("Processing batch", completed=i+1, total=len(symbols))
                        await asyncio.sleep(2)  # 2 second pause between batches
                    else:
                        await asyncio.sleep(0.1)  # 100ms between individual requests
                        
                except Exception as e:
                    logger.error("Error collecting data for symbol", 
                               symbol=symbol, error=str(e))
                    self.collection_stats["errors"] += 1
        
        logger.info("Daily data collection completed", 
                   successful=successful_collections, total=len(symbols))
        
        return successful_collections > 0
    
    def get_latest_data(self, symbol: str) -> Optional[MarketDataPoint]:
        """Get latest market data point for a symbol"""
        if symbol in self.data_storage and self.data_storage[symbol]:
            return self.data_storage[symbol][-1]
        return None
    
    def get_collection_stats(self) -> Dict[str, any]:
        """Get collection statistics"""
        return {
            **self.collection_stats,
            "active_subscriptions": len(self.active_subscriptions),
            "symbols_with_data": len(self.data_storage),
            "connection_status": self.ibkr_client.get_connection_status(),
            "market_open": self.market_hours.is_market_open(),
            "trading_day": self.market_hours.is_trading_day()
        }