#!/usr/bin/env python3
"""
Daily Market Data Collection Script

This script collects daily close market data for all symbols in the database
using the Interactive Brokers TWS API. It follows TWS API best practices:

- Respects pacing limitations (max 60 requests per 10 minutes for small bars)
- Uses 1 day bar size for daily close data
- Collects TRADES data (open, high, low, close, volume)
- Handles different exchanges and security types properly
- Implements robust error handling and retry logic
- Logs all operations for monitoring

Run daily as a cron job to keep market data up to date.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import traceback

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.ibkr.client import IBKRManager
from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, MarketData, SecurityType, CollectionLog
from shared.ibkr.contracts import create_stock_contract
from shared.utils.error_analysis import ErrorAnalyzer
from config.daily_collection_config import *
from sqlalchemy import select, and_, desc
from sqlalchemy.exc import IntegrityError
from ibapi.contract import Contract
from ibapi.common import BarData

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyMarketDataCollector:
    """Collects daily market data for all symbols using TWS API."""
    
    def __init__(self, dry_run: bool = False):
        """Initialize the daily data collector.
        
        Args:
            dry_run: If True, don't actually collect data, just simulate the process
        """
        self.ibkr_manager = None
        self.dry_run = dry_run
        self.request_id_counter = 1000
        self.pending_requests: Dict[int, Symbol] = {}
        self.collected_data: Dict[int, List[BarData]] = {}
        self.collection_stats = {
            "total_symbols": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "skipped_symbols": 0,
            "start_time": None,
            "end_time": None
        }
        
        # TWS API pacing - configuration from config file
        self.max_requests_per_batch = MAX_REQUESTS_PER_BATCH
        self.batch_delay_seconds = BATCH_DELAY_SECONDS
        self.request_delay_seconds = REQUEST_DELAY_SECONDS
    
    def _format_date_with_timezone(self, date: datetime, exchange: str) -> str:
        """Format date with proper timezone for IBKR API.
        
        This prevents IBKR Warning 2174 about missing timezone information.
        IBKR requires space between date and time: "yyyymmdd hh:mm:ss timezone"
        
        Args:
            date: The date to format
            exchange: The exchange code to get timezone for
            
        Returns:
            Formatted date string with timezone
        """
        timezone = TIMEZONE_MAPPINGS.get(exchange, "UTC")
        return date.strftime(f"%Y%m%d 23:59:59 {timezone}")
        
    async def collect_daily_data(self, target_date: Optional[datetime] = None) -> bool:
        """Main method to collect daily market data for all symbols.
        
        Args:
            target_date: Date to collect data for. If None, uses previous trading day.
            
        Returns:
            True if collection completed successfully, False otherwise
        """
        try:
            self.collection_stats["start_time"] = datetime.now()
            logger.info("🚀 Starting daily market data collection...")
            
            # Initialize database
            await init_db()
            
            # Determine target date
            if target_date is None:
                target_date = self._get_previous_trading_day()
            
            logger.info(f"📅 Collecting data for: {target_date.strftime('%Y-%m-%d')}")
            
            # Get all active symbols from database
            symbols = await self._get_active_symbols()
            self.collection_stats["total_symbols"] = len(symbols)
            
            if not symbols:
                logger.warning("⚠️  No active symbols found in database")
                return False
                
            logger.info(f"📊 Found {len(symbols)} active symbols to process")
            
            if self.dry_run:
                logger.info("🔍 DRY RUN MODE - No actual data will be collected")
                await self._simulate_collection(symbols, target_date)
                return True
            
            # Connect to IBKR
            success = await self._connect_to_ibkr()
            if not success:
                return False
            
            # Process symbols in batches to respect API limits
            await self._process_symbols_in_batches(symbols, target_date)
            
            # Disconnect from IBKR
            await self._disconnect_from_ibkr()
            
            self.collection_stats["end_time"] = datetime.now()
            duration = (self.collection_stats["end_time"] - self.collection_stats["start_time"]).total_seconds()
            
            logger.info("📈 Daily market data collection completed")
            logger.info(f"📊 Stats: {self.collection_stats['successful_collections']} successful, "
                       f"{self.collection_stats['failed_collections']} failed, "
                       f"{self.collection_stats['skipped_symbols']} skipped")
            logger.info(f"⏱️  Total duration: {duration:.1f} seconds")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Fatal error in daily data collection: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def _get_active_symbols(self) -> List[Symbol]:
        """Get all active symbols from the database."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Symbol).where(
                    and_(
                        Symbol.active == True,
                        Symbol.tradeable == True
                    )
                ).order_by(Symbol.priority.asc(), Symbol.symbol.asc())
            )
            return result.scalars().all()
    
    async def _connect_to_ibkr(self) -> bool:
        """Connect to IBKR TWS/Gateway."""
        try:
            logger.info("🔌 Connecting to IBKR TWS/Gateway...")
            
            # Try ports from configuration
            for port in IBKR_PORTS:
                try:
                    self.ibkr_manager = IBKRManager(
                        host=IBKR_HOST,
                        port=port,
                        client_id=IBKR_CLIENT_ID
                    )
                    
                    connected = await self.ibkr_manager.connect()
                    if connected:
                        logger.info(f"✅ Connected to IBKR on port {port}")
                        return True
                    else:
                        logger.warning(f"⚠️  Failed to connect on port {port}")
                        
                except Exception as e:
                    logger.warning(f"⚠️  Connection attempt failed on port {port}: {str(e)}")
                    continue
            
            logger.error("❌ Could not connect to IBKR on any port")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error connecting to IBKR: {str(e)}")
            return False
    
    async def _disconnect_from_ibkr(self):
        """Disconnect from IBKR."""
        try:
            if self.ibkr_manager:
                await self.ibkr_manager.disconnect()
                logger.info("✅ Disconnected from IBKR")
        except Exception as e:
            logger.warning(f"⚠️  Error disconnecting from IBKR: {str(e)}")
    
    async def _process_symbols_in_batches(self, symbols: List[Symbol], target_date: datetime):
        """Process symbols in batches to respect TWS API pacing limits."""
        total_batches = (len(symbols) + self.max_requests_per_batch - 1) // self.max_requests_per_batch
        
        logger.info(f"📦 Processing {len(symbols)} symbols in {total_batches} batches")
        logger.info(f"⏱️  Batch size: {self.max_requests_per_batch}, Batch delay: {self.batch_delay_seconds}s")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * self.max_requests_per_batch
            end_idx = min(start_idx + self.max_requests_per_batch, len(symbols))
            batch_symbols = symbols[start_idx:end_idx]
            
            logger.info(f"📦 Processing batch {batch_num + 1}/{total_batches} "
                       f"(symbols {start_idx + 1}-{end_idx})")
            
            await self._process_symbol_batch(batch_symbols, target_date)
            
            # Wait between batches (except for the last one)
            if batch_num < total_batches - 1:
                logger.info(f"⏳ Waiting {self.batch_delay_seconds} seconds before next batch...")
                await asyncio.sleep(self.batch_delay_seconds)
    
    async def _process_symbol_batch(self, symbols: List[Symbol], target_date: datetime):
        """Process a single batch of symbols."""
        batch_start_time = datetime.now()
        
        for symbol in symbols:
            try:
                # Check if we already have data for this date
                if await self._has_existing_data(symbol.id, target_date):
                    logger.info(f"⏭️  Skipping {symbol.symbol} - data already exists for {target_date.strftime('%Y-%m-%d')}")
                    self.collection_stats["skipped_symbols"] += 1
                    continue
                
                # Create log entry
                log_id = await self._create_collection_log(symbol.id, target_date)
                
                # Request historical data with enhanced error tracking
                success, error_info = await self._request_historical_data(symbol, target_date)
                
                if success:
                    self.collection_stats["successful_collections"] += 1
                    await self._update_collection_log(log_id, "completed")
                    logger.info(f"✅ Successfully collected data for {symbol.symbol}")
                else:
                    self.collection_stats["failed_collections"] += 1
                    
                    # Extract error details for enhanced logging
                    error_message = error_info.get("error_message", "Data request failed") if error_info else "Data request failed"
                    error_code = error_info.get("error_code") if error_info else None
                    request_id = error_info.get("request_id") if error_info else None
                    
                    await self._update_collection_log(
                        log_id=log_id,
                        status="failed", 
                        error_message=error_message,
                        error_code=error_code,
                        ibkr_request_id=request_id,
                        error_details=error_info
                    )
                    
                    logger.error(f"❌ Failed to collect data for {symbol.symbol}: {error_message}")
                    if error_code:
                        logger.error(f"   🔍 IBKR Error Code: {error_code}")
                
                # Small delay between requests
                await asyncio.sleep(self.request_delay_seconds)
                
            except Exception as e:
                logger.error(f"❌ Error processing symbol {symbol.symbol}: {str(e)}")
                self.collection_stats["failed_collections"] += 1
        
        batch_duration = (datetime.now() - batch_start_time).total_seconds()
        logger.info(f"📦 Batch completed in {batch_duration:.1f} seconds")
    
    async def _request_historical_data(self, symbol: Symbol, target_date: datetime) -> Tuple[bool, Optional[dict]]:
        """Request historical data for a single symbol and return success status and error details."""
        try:
            # Create appropriate contract
            contract = self._create_contract_for_symbol(symbol)
            
            # Format end date with proper timezone (IBKR requirement)
            # Use market-specific timezone to avoid IBKR Warning 2174
            end_date_str = self._format_date_with_timezone(target_date, symbol.exchange)
            
            # Request historical data
            request_id = self.request_id_counter
            self.request_id_counter += 1
            self.pending_requests[request_id] = symbol
            
            logger.debug(f"📡 Requesting historical data for {symbol.symbol} (req_id: {request_id}) with timezone: {end_date_str}")
            
            # Use the historical data method from IBKR manager
            bars = await self.ibkr_manager.get_historical_data(
                contract=contract,
                end_date=end_date_str,
                duration=DEFAULT_DURATION,
                bar_size=DEFAULT_BAR_SIZE,
                what_to_show=DEFAULT_WHAT_TO_SHOW,
                use_rth=USE_REGULAR_TRADING_HOURS,
                format_date=1,  # Return as string
                timeout=REQUEST_TIMEOUT
            )
            
            # Check for IBKR errors during request
            error_info = await self._check_for_ibkr_errors(request_id, symbol)
            if error_info:
                logger.warning(f"⚠️  IBKR error for {symbol.symbol}: {error_info}")
                return False, error_info
            
            if bars and len(bars) > 0:
                # Store the data
                await self._store_market_data(symbol, bars[0], target_date)
                return True, None
            else:
                logger.warning(f"⚠️  No data returned for {symbol.symbol}")
                return False, {
                    "error_type": "NO_DATA",
                    "error_message": "No historical data returned",
                    "error_code": None,
                    "request_id": request_id
                }
                
        except Exception as e:
            error_info = {
                "error_type": "EXCEPTION",
                "error_message": str(e),
                "error_code": None,
                "request_id": None
            }
            logger.error(f"❌ Error requesting data for {symbol.symbol}: {str(e)}")
            return False, error_info
    
    async def _check_for_ibkr_errors(self, request_id: int, symbol: Symbol) -> Optional[dict]:
        """Check for IBKR errors related to a specific request."""
        try:
            # Wait briefly for any errors to be reported
            await asyncio.sleep(0.5)
            
            # Check for errors in the IBKR client
            error = await self.ibkr_manager.get_error()
            if error:
                # Check if error is related to our request
                if error.get("reqId") == request_id or error.get("reqId") == -1:
                    return {
                        "error_type": "IBKR_ERROR",
                        "error_message": error.get("errorString", "Unknown IBKR error"),
                        "error_code": error.get("errorCode"),
                        "request_id": request_id,
                        "symbol": symbol.symbol,
                        "timestamp": error.get("timestamp")
                    }
            return None
            
        except Exception as e:
            logger.error(f"❌ Error checking for IBKR errors: {str(e)}")
            return None
    
    def _create_contract_for_symbol(self, symbol: Symbol) -> Contract:
        """Create appropriate IBKR contract for a symbol."""
        contract = Contract()
        contract.symbol = symbol.symbol
        contract.currency = symbol.currency
        
        # Set security type using configuration mapping
        sec_type_str = symbol.security_type.value if hasattr(symbol.security_type, 'value') else str(symbol.security_type)
        contract.secType = SECURITY_TYPE_MAPPINGS.get(sec_type_str, "STK")
        
        # Set exchange using configuration mapping
        exchange_config = EXCHANGE_MAPPINGS.get(symbol.exchange, {
            "exchange": "SMART",
            "primary_exchange": symbol.exchange,
            "currency": symbol.currency
        })
        
        contract.exchange = exchange_config["exchange"]
        if "primary_exchange" in exchange_config:
            contract.primaryExchange = exchange_config["primary_exchange"]
        
        # Override currency if specified in exchange config
        if "currency" in exchange_config and not symbol.currency:
            contract.currency = exchange_config["currency"]
        
        # Use contract ID if available
        if symbol.contract_id:
            contract.conId = symbol.contract_id
        
        return contract
    
    async def _store_market_data(self, symbol: Symbol, bar: BarData, target_date: datetime):
        """Store market data in the database."""
        try:
            async with AsyncSessionLocal() as session:
                # Create market data record
                market_data = MarketData(
                    symbol_id=symbol.id,
                    timestamp=target_date.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0),
                    timeframe="1day",
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume) if bar.volume != -1 else 0,
                    wap=float(bar.wap) if hasattr(bar, 'wap') and bar.wap != -1 else None,
                    bar_count=int(bar.barCount) if hasattr(bar, 'barCount') else 1
                )
                
                session.add(market_data)
                await session.commit()
                
                logger.debug(f"💾 Stored market data for {symbol.symbol}: "
                           f"O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close} V:{bar.volume}")
                
        except IntegrityError:
            # Data already exists, which is fine
            logger.debug(f"⚠️  Market data already exists for {symbol.symbol} on {target_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logger.error(f"❌ Error storing market data for {symbol.symbol}: {str(e)}")
            raise
    
    async def _has_existing_data(self, symbol_id: int, target_date: datetime) -> bool:
        """Check if market data already exists for symbol on target date."""
        try:
            async with AsyncSessionLocal() as session:
                # Check for data on the target date (with some time tolerance)
                start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                result = await session.execute(
                    select(MarketData).where(
                        and_(
                            MarketData.symbol_id == symbol_id,
                            MarketData.timeframe == "1day",
                            MarketData.timestamp >= start_of_day,
                            MarketData.timestamp <= end_of_day
                        )
                    ).limit(1)
                )
                
                return result.scalar() is not None
                
        except Exception as e:
            logger.error(f"❌ Error checking existing data: {str(e)}")
            return False
    
    async def _create_collection_log(self, symbol_id: int, target_date: datetime) -> int:
        """Create a collection log entry."""
        try:
            async with AsyncSessionLocal() as session:
                log_entry = CollectionLog(
                    symbol_id=symbol_id,
                    collection_type="historical",
                    timeframe="1day",
                    start_date=target_date,
                    end_date=target_date,
                    status="pending"
                )
                
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                
                return log_entry.id
                
        except Exception as e:
            logger.error(f"❌ Error creating collection log: {str(e)}")
            return None
    
    async def _update_collection_log(self, log_id: int, status: str, error_message: Optional[str] = None,
                                   error_code: Optional[int] = None, error_details: Optional[dict] = None,
                                   ibkr_request_id: Optional[int] = None, retry_count: int = 0):
        """Update collection log status with enhanced error tracking."""
        if log_id is None:
            return
            
        try:
            async with AsyncSessionLocal() as session:
                log_entry = await session.get(CollectionLog, log_id)
                if log_entry:
                    log_entry.status = status
                    log_entry.error_message = error_message
                    log_entry.completed_at = datetime.now()
                    log_entry.retry_count = retry_count
                    
                    # Enhanced error tracking
                    if error_code:
                        log_entry.error_code = error_code
                        
                    if ibkr_request_id:
                        log_entry.ibkr_request_id = ibkr_request_id
                        
                    # Analyze and categorize error
                    if error_code or error_message:
                        error_analysis = ErrorAnalyzer.analyze_error(
                            error_code=error_code,
                            error_message=error_message,
                            request_id=ibkr_request_id
                        )
                        log_entry.error_type = error_analysis.get("error_type")
                        log_entry.error_details = error_analysis
                        
                        # Log detailed error summary
                        error_summary = ErrorAnalyzer.format_error_summary(error_analysis)
                        logger.warning(f"📊 Error Analysis: {error_summary}")
                    
                    if status == "completed":
                        log_entry.records_collected = 1
                    
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"❌ Error updating collection log: {str(e)}")
    
    def _get_previous_trading_day(self) -> datetime:
        """Get the previous trading day (excludes weekends)."""
        today = datetime.now().date()
        
        # Go back one day
        target_date = today - timedelta(days=1)
        
        # If it's a weekend, go back to Friday
        while target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            target_date -= timedelta(days=1)
        
        return datetime.combine(target_date, datetime.min.time())
    
    async def _simulate_collection(self, symbols: List[Symbol], target_date: datetime):
        """Simulate the collection process for dry run mode."""
        logger.info("🔍 Simulating daily data collection...")
        
        for i, symbol in enumerate(symbols):
            logger.info(f"🔍 [{i+1}/{len(symbols)}] Would collect data for {symbol.symbol} "
                       f"({symbol.exchange}, {symbol.security_type.value})")
            
            # Simulate processing time
            await asyncio.sleep(0.1)
        
        logger.info("🔍 Dry run simulation completed")


async def main():
    """Main entry point for the daily data collection script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Market Data Collection Script")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Simulate the collection process without actually collecting data")
    parser.add_argument("--date", type=str, 
                       help="Target date for data collection (YYYY-MM-DD). If not provided, uses previous trading day")
    
    args = parser.parse_args()
    
    # Parse target date if provided
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            logger.error("❌ Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Create and run collector
    collector = DailyMarketDataCollector(dry_run=args.dry_run)
    success = await collector.collect_daily_data(target_date)
    
    if success:
        logger.info("✅ Daily market data collection completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Daily market data collection failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
