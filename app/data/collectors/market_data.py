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
from app.data.models.market import DailyPrice
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

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
    
    def _historical_data_callback(self, symbol: str, data_buffer: List[HistoricalBar]) -> Callable:
        """Create callback for historical data that stores in buffer for async processing"""
        def callback(bar):
            try:
                # Parse date - handle both "20240101" and "20240101  23:59:59" formats
                date_str = bar.date.strip()
                if len(date_str) == 8:  # Format: "20240101"
                    bar_date = datetime.strptime(date_str, "%Y%m%d")
                else:  # Format: "20240101  23:59:59"
                    bar_date = datetime.strptime(date_str.split()[0], "%Y%m%d")
                
                historical_bar = HistoricalBar(
                    symbol=symbol,
                    date=bar_date,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume) if bar.volume != -1 else 0,
                    adjusted_close=float(bar.close)  # Use close as adjusted_close for now
                )
                
                # Store in buffer for async processing
                data_buffer.append(historical_bar)
                
                logger.debug("Historical bar received", 
                           symbol=symbol, date=bar_date.strftime('%Y-%m-%d'), close=bar.close)
                
                self.collection_stats["successful_responses"] += 1
                
            except Exception as e:
                logger.error("Error processing historical data", 
                           symbol=symbol, error=str(e))
                self.collection_stats["errors"] += 1
        
        return callback
    
    async def _store_historical_bars(self, bars: List[HistoricalBar], db_session: AsyncSession) -> int:
        """Store historical bars in database with upsert logic"""
        stored_count = 0
        
        for bar in bars:
            try:
                # Create DailyPrice object
                daily_price = DailyPrice(
                    symbol=bar.symbol,
                    date=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    adj_close=bar.adjusted_close,
                    created_at=datetime.now()
                )
                
                # Use PostgreSQL UPSERT to handle duplicates
                stmt = insert(DailyPrice).values(
                    symbol=bar.symbol,
                    date=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    adj_close=bar.adjusted_close,
                    created_at=datetime.now()
                )
                
                # ON CONFLICT DO NOTHING - skip duplicates
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['symbol', 'date']
                )
                
                await db_session.execute(stmt)
                stored_count += 1
                
                logger.debug("Stored historical data", 
                           symbol=bar.symbol, 
                           date=bar.date.strftime('%Y-%m-%d'),
                           close=bar.close)
                
            except Exception as e:
                logger.error("Error storing historical bar", 
                           symbol=bar.symbol, 
                           date=bar.date.strftime('%Y-%m-%d') if bar.date else 'unknown',
                           error=str(e))
                self.collection_stats["errors"] += 1
                continue
        
        try:
            await db_session.commit()
            logger.info("Successfully stored historical data", 
                       bars_stored=stored_count, 
                       total_bars=len(bars))
        except Exception as e:
            await db_session.rollback()
            logger.error("Error committing historical data", error=str(e))
            raise
        
        return stored_count
    
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
        symbol_data_buffers = {}  # Store data buffers for each symbol
        pending_requests = {}     # Track pending request IDs
        
        # Phase 1: Submit all historical data requests
        for i, symbol in enumerate(symbols):
            try:
                contract = create_asx_stock_contract(symbol)
                
                # Create data buffer for this symbol
                data_buffer = []
                symbol_data_buffers[symbol] = data_buffer
                
                callback = self._historical_data_callback(symbol, data_buffer)
                
                req_id = self.ibkr_client.request_historical_data(
                    contract, "1 D", "1 day", callback
                )
                
                if req_id:
                    pending_requests[req_id] = symbol
                    successful_collections += 1
                    self.collection_stats["requests_made"] += 1
                    
                    logger.debug("Submitted historical data request", 
                               symbol=symbol, req_id=req_id)
                
                # Rate limiting: batch processing with delays
                if (i + 1) % 10 == 0:  # Every 10 requests
                    logger.info("Processing batch", completed=i+1, total=len(symbols))
                    await asyncio.sleep(2)  # 2 second pause between batches
                else:
                    await asyncio.sleep(0.1)  # 100ms between individual requests
                    
            except Exception as e:
                logger.error("Error submitting request for symbol", 
                           symbol=symbol, error=str(e))
                self.collection_stats["errors"] += 1
        
        # Phase 2: Wait for all data to be received (with timeout)
        logger.info("Waiting for historical data responses", pending_requests=len(pending_requests))
        
        wait_timeout = 60  # 60 seconds total timeout
        wait_start = time.time()
        
        while pending_requests and (time.time() - wait_start) < wait_timeout:
            # Check which requests have completed by looking at client's pending requests
            completed_requests = []
            for req_id, symbol in pending_requests.items():
                if req_id not in self.ibkr_client.pending_requests:
                    completed_requests.append(req_id)
                    logger.debug("Historical data request completed", 
                               symbol=symbol, req_id=req_id)
            
            # Remove completed requests
            for req_id in completed_requests:
                del pending_requests[req_id]
            
            if pending_requests:
                await asyncio.sleep(0.5)  # Check every 500ms
        
        if pending_requests:
            logger.warning("Some historical data requests timed out", 
                         remaining=len(pending_requests))
        
        # Phase 3: Store all collected data in database
        total_bars_stored = 0
        
        async with AsyncSessionLocal() as db_session:
            for symbol, data_buffer in symbol_data_buffers.items():
                if data_buffer:
                    try:
                        stored_count = await self._store_historical_bars(data_buffer, db_session)
                        total_bars_stored += stored_count
                        logger.info("Stored historical data", 
                                  symbol=symbol, bars=stored_count)
                    except Exception as e:
                        logger.error("Error storing data for symbol", 
                                   symbol=symbol, error=str(e))
                        self.collection_stats["errors"] += 1
                else:
                    logger.warning("No data received for symbol", symbol=symbol)
        
        logger.info("Daily data collection completed", 
                   successful_requests=successful_collections, 
                   total_symbols=len(symbols),
                   total_bars_stored=total_bars_stored)
        
        return successful_collections > 0 and total_bars_stored > 0
    
    async def get_existing_data_dates(self, symbol: str) -> set:
        """Get set of dates that already have data for this symbol"""
        async with AsyncSessionLocal() as db_session:
            from sqlalchemy import select
            
            result = await db_session.execute(
                select(DailyPrice.date).where(DailyPrice.symbol == symbol)
            )
            
            existing_dates = set()
            for row in result:
                date_str = row[0].strftime('%Y-%m-%d')
                existing_dates.add(date_str)
            
            return existing_dates
    
    def _generate_date_ranges(self, start_date: datetime, end_date: datetime, max_days_per_request: int = 365) -> List[tuple]:
        """Generate date ranges for IBKR requests, respecting maximum request size"""
        ranges = []
        current_start = start_date
        
        while current_start < end_date:
            days_remaining = (end_date - current_start).days
            chunk_days = min(max_days_per_request, days_remaining)
            current_end = current_start + timedelta(days=chunk_days)
            
            if current_end > end_date:
                current_end = end_date
            
            ranges.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)
        
        return ranges
    
    def _format_date_for_ibkr(self, date: datetime) -> str:
        """Format date for IBKR API with timezone"""
        # Use UTC to avoid timezone issues with IBKR API
        return date.strftime("%Y%m%d 23:59:59 UTC")
    
    def _is_trading_day(self, date: datetime) -> bool:
        """Check if a date is likely a trading day (exclude weekends)"""
        return date.weekday() < 5  # Monday=0 to Friday=4
    
    async def backfill_historical_data(self, symbol: str, start_date: datetime, 
                                     end_date: datetime, skip_existing: bool = True) -> dict:
        """
        Backfill historical data for a symbol over a date range
        
        Args:
            symbol: The symbol to collect data for
            start_date: Start date for data collection
            end_date: End date for data collection
            skip_existing: If True, skip dates that already have data
            
        Returns:
            Dict with collection statistics
        """
        logger.info("Starting historical data backfill", 
                   symbol=symbol, 
                   start_date=start_date.strftime('%Y-%m-%d'),
                   end_date=end_date.strftime('%Y-%m-%d'))
        
        # Initialize statistics
        backfill_stats = {
            "symbol": symbol,
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "total_days": (end_date - start_date).days + 1,
            "successful_requests": 0,
            "failed_requests": 0,
            "bars_collected": 0,
            "bars_stored": 0,
            "existing_dates_skipped": 0,
            "start_time": datetime.now(),
            "end_time": None
        }
        
        try:
            # Get existing data dates if we should skip them
            existing_dates = set()
            if skip_existing:
                existing_dates = await self.get_existing_data_dates(symbol)
                logger.info("Found existing data points to skip", 
                           symbol=symbol, existing_count=len(existing_dates))
            
            # Generate date ranges for chunked requests
            date_ranges = self._generate_date_ranges(start_date, end_date)
            logger.info("Generated date ranges for backfill", 
                       symbol=symbol, chunks=len(date_ranges))
            
            all_data_buffers = []
            
            # Process each date range chunk
            for i, (range_start, range_end) in enumerate(date_ranges):
                logger.info("Processing backfill chunk", 
                           symbol=symbol, 
                           chunk=f"{i+1}/{len(date_ranges)}",
                           range_start=range_start.strftime('%Y-%m-%d'),
                           range_end=range_end.strftime('%Y-%m-%d'))
                
                # Check if we need data for this range
                if skip_existing:
                    days_needed = self._count_trading_days_needed(range_start, range_end, existing_dates)
                    if days_needed == 0:
                        logger.info("Skipping chunk - all data already exists", 
                                   symbol=symbol, chunk=i+1)
                        continue
                    
                    logger.info("Need data for trading days", 
                               symbol=symbol, days_needed=days_needed)
                
                # Request historical data for this chunk
                chunk_buffer = await self._request_historical_data_chunk(
                    symbol, range_start, range_end
                )
                
                if chunk_buffer:
                    all_data_buffers.extend(chunk_buffer)
                    backfill_stats["successful_requests"] += 1
                    backfill_stats["bars_collected"] += len(chunk_buffer)
                    logger.info("Collected chunk data", 
                               symbol=symbol, bars=len(chunk_buffer))
                else:
                    backfill_stats["failed_requests"] += 1
                    logger.warning("Failed to collect chunk data", 
                                  symbol=symbol, chunk=i+1)
                
                # Rate limiting between chunks
                if i < len(date_ranges) - 1:
                    await asyncio.sleep(2)  # 2 second delay between chunks
            
            # Store all collected data
            if all_data_buffers:
                logger.info("Storing backfilled data", 
                           symbol=symbol, total_bars=len(all_data_buffers))
                
                async with AsyncSessionLocal() as db_session:
                    stored_count = await self._store_historical_bars(all_data_buffers, db_session)
                    backfill_stats["bars_stored"] = stored_count
                    
                    logger.info("Successfully stored backfilled data", 
                               symbol=symbol, bars_stored=stored_count)
            
            backfill_stats["end_time"] = datetime.now()
            duration = (backfill_stats["end_time"] - backfill_stats["start_time"]).total_seconds()
            backfill_stats["duration_seconds"] = duration
            
            logger.info("Historical data backfill completed", 
                       symbol=symbol, 
                       bars_stored=backfill_stats["bars_stored"],
                       duration_seconds=duration)
            
            return backfill_stats
            
        except Exception as e:
            logger.error("Error in historical data backfill", 
                        symbol=symbol, error=str(e))
            backfill_stats["error"] = str(e)
            backfill_stats["end_time"] = datetime.now()
            return backfill_stats
    
    def _count_trading_days_needed(self, start_date: datetime, end_date: datetime, existing_dates: set) -> int:
        """Count how many trading days we need to collect in a date range"""
        count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if self._is_trading_day(current_date):
                date_str = current_date.strftime('%Y-%m-%d')
                if date_str not in existing_dates:
                    count += 1
            current_date += timedelta(days=1)
        
        return count
    
    async def _request_historical_data_chunk(self, symbol: str, start_date: datetime, 
                                           end_date: datetime) -> List[HistoricalBar]:
        """Request historical data for a specific date range chunk"""
        try:
            # Create contract for the symbol
            contract = create_asx_stock_contract(symbol)
            
            # Calculate duration for IBKR request
            duration_days = (end_date - start_date).days + 1
            
            # Format duration for IBKR API
            if duration_days > 365:
                duration_years = round(duration_days / 365.25, 1)
                duration_str = f"{int(duration_years) if duration_years.is_integer() else duration_years} Y"
            else:
                duration_str = f"{duration_days} D"
            
            # Format end date with timezone
            end_date_str = self._format_date_for_ibkr(end_date)
            
            logger.debug("Requesting historical data chunk", 
                        symbol=symbol, 
                        duration=duration_str, 
                        end_date=end_date_str)
            
            # Create data buffer for this request
            data_buffer = []
            callback = self._historical_data_callback(symbol, data_buffer)
            
            # Submit request
            req_id = self.ibkr_client.request_historical_data(
                contract, duration_str, "1 day", callback
            )
            
            if not req_id:
                logger.error("Failed to submit historical data request", symbol=symbol)
                return []
            
            # Wait for data to be received (with timeout)
            wait_timeout = 30  # 30 seconds timeout per chunk
            wait_start = time.time()
            
            while (req_id in self.ibkr_client.pending_requests and 
                   (time.time() - wait_start) < wait_timeout):
                await asyncio.sleep(0.5)
            
            if req_id in self.ibkr_client.pending_requests:
                logger.warning("Historical data request timed out", 
                              symbol=symbol, req_id=req_id)
                return []
            
            logger.debug("Historical data chunk received", 
                        symbol=symbol, bars=len(data_buffer))
            
            return data_buffer
            
        except Exception as e:
            logger.error("Error requesting historical data chunk", 
                        symbol=symbol, error=str(e))
            return []
    
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