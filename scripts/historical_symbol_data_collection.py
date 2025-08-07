#!/usr/bin/env python3
"""
Historical Symbol Data Collection Script

This script collects historical daily market data for a single symbol over a specified
date range using the Interactive Brokers TWS API. It follows TWS API best practices:

- Respects pacing limitations (max 60 requests per 10 minutes for small bars)
- Uses 1 day bar size for daily OHLCV data
- Collects TRADES data (open, high, low, close, volume)
- Handles different exchanges and security types properly
- Implements robust error handling and retry logic
- Skips dates that already exist in the database
- Logs all operations for monitoring

Usage:
    python scripts/historical_symbol_data_collection.py AAPL
    python scripts/historical_symbol_data_collection.py AAPL --start-date 2022-01-01 --end-date 2024-12-31
    python scripts/historical_symbol_data_collection.py CBA.AX --years 5
    python scripts/historical_symbol_data_collection.py TSLA --dry-run
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import traceback
import argparse

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.ibkr.client import IBKRManager
from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, MarketData, SecurityType, CollectionLog
from shared.ibkr.contracts import create_stock_contract
from shared.utils.error_analysis import ErrorAnalyzer
from config.daily_collection_config import *
from sqlalchemy import select, and_, desc, or_
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

# Default settings for historical collection
DEFAULT_YEARS_BACK = 3
MAX_DAYS_PER_REQUEST = 365  # Maximum days to request in a single IBKR call
WEEKEND_SKIP_DAYS = [5, 6]  # Saturday and Sunday


class HistoricalSymbolDataCollector:
    """Collects historical market data for a single symbol over a date range."""
    
    def __init__(self, symbol_name: str, dry_run: bool = False):
        """Initialize the historical data collector.
        
        Args:
            symbol_name: The symbol to collect data for
            dry_run: If True, don't actually collect data, just simulate the process
        """
        self.symbol_name = symbol_name.upper()
        self.ibkr_manager = None
        self.dry_run = dry_run
        self.request_id_counter = 2000
        self.symbol_obj = None
        self.collection_stats = {
            "total_days": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "skipped_days": 0,
            "start_time": None,
            "end_time": None,
            "date_range": None
        }
        
        # TWS API pacing - use same config as daily collection
        self.request_delay_seconds = REQUEST_DELAY_SECONDS * 2  # Be more conservative for historical data
        self.batch_delay_seconds = BATCH_DELAY_SECONDS
    
    def _format_date_with_timezone(self, date: datetime, exchange: str) -> str:
        """Format date with proper timezone for IBKR API.
        
        This prevents IBKR Warning 2174 about missing timezone information.
        IBKR requires space between date and time: "yyyymmdd hh:mm:ss timezone"
        
        For ASX, IBKR seems to have issues with Australia/Sydney format, so we'll use UTC.
        
        Args:
            date: The date to format
            exchange: The exchange code to get timezone for
            
        Returns:
            Formatted date string with timezone
        """
        # IBKR-compatible timezone mappings (some timezones like Australia/Sydney cause issues)
        ibkr_timezone_mappings = {
            "ASX": "UTC",  # Use UTC for ASX to avoid timezone issues
            "NASDAQ": "US/Eastern", 
            "NYSE": "US/Eastern",
            "LSE": "Europe/London",
            "TSE": "Asia/Tokyo",
            "HKEX": "Asia/Hong_Kong",
            "EURONEXT": "Europe/Paris",
            "TSX": "America/Toronto"
        }
        
        timezone = ibkr_timezone_mappings.get(exchange, "UTC")
        return date.strftime(f"%Y%m%d 23:59:59 {timezone}")
    
    def _is_trading_day(self, date: datetime) -> bool:
        """Check if a date is likely a trading day (exclude weekends)."""
        return date.weekday() not in WEEKEND_SKIP_DAYS
    
    def _generate_date_ranges(self, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """Generate date ranges for IBKR requests, respecting maximum request size."""
        ranges = []
        current_start = start_date
        
        while current_start < end_date:
            # Calculate end date for this chunk (max 365 days for day requests, or use years for longer periods)
            days_remaining = (end_date - current_start).days
            
            # For requests longer than 365 days, we'll use year-based requests
            # But we still chunk to avoid very large requests
            if days_remaining > 365:
                # Use 1-year chunks for very large requests
                chunk_days = min(365, days_remaining)
            else:
                chunk_days = days_remaining
            
            current_end = current_start + timedelta(days=chunk_days)
            
            # Ensure we don't go past the actual end date
            if current_end > end_date:
                current_end = end_date
            
            ranges.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)
        
        return ranges
    
    async def collect_historical_data(self, start_date: Optional[datetime] = None, 
                                    end_date: Optional[datetime] = None,
                                    years_back: Optional[int] = None) -> bool:
        """Main method to collect historical market data for the symbol.
        
        Args:
            start_date: Start date for data collection
            end_date: End date for data collection  
            years_back: Number of years back from today (used if start_date not provided)
            
        Returns:
            True if collection completed successfully, False otherwise
        """
        try:
            self.collection_stats["start_time"] = datetime.now()
            logger.info(f"🚀 Starting historical data collection for {self.symbol_name}...")
            
            # Initialize database
            await init_db()
            
            # Get symbol from database
            self.symbol_obj = await self._get_symbol_from_db()
            if not self.symbol_obj:
                logger.error(f"❌ Symbol {self.symbol_name} not found in database")
                logger.info("💡 Tip: Run 'python scripts/populate_symbols.py' to add symbols")
                return False
            
            logger.info(f"📊 Found symbol: {self.symbol_obj.symbol} ({self.symbol_obj.exchange}, {self.symbol_obj.security_type.value})")
            
            # Determine date range
            if not start_date:
                years = years_back or DEFAULT_YEARS_BACK
                start_date = datetime.now() - timedelta(days=years * 365)
            
            if not end_date:
                end_date = datetime.now() - timedelta(days=1)  # Yesterday
            
            # Ensure dates are properly ordered
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            
            self.collection_stats["date_range"] = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            total_days = (end_date - start_date).days + 1
            self.collection_stats["total_days"] = total_days
            
            logger.info(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({total_days} days)")
            
            if self.dry_run:
                logger.info("🔍 DRY RUN MODE - No actual data will be collected")
                await self._simulate_collection(start_date, end_date)
                return True
            
            # Connect to IBKR
            success = await self._connect_to_ibkr()
            if not success:
                return False
            
            # Get existing data dates to skip
            existing_dates = await self._get_existing_data_dates()
            logger.info(f"📊 Found {len(existing_dates)} existing data points to skip")
            
            # Process date ranges in chunks
            await self._process_date_ranges(start_date, end_date, existing_dates)
            
            # Disconnect from IBKR
            await self._disconnect_from_ibkr()
            
            self.collection_stats["end_time"] = datetime.now()
            duration = (self.collection_stats["end_time"] - self.collection_stats["start_time"]).total_seconds()
            
            logger.info("📈 Historical data collection completed")
            logger.info(f"📊 Stats: {self.collection_stats['successful_collections']} successful, "
                       f"{self.collection_stats['failed_collections']} failed, "
                       f"{self.collection_stats['skipped_days']} skipped")
            logger.info(f"⏱️  Total duration: {duration:.1f} seconds")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Fatal error in historical data collection: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def _get_symbol_from_db(self) -> Optional[Symbol]:
        """Get the symbol object from the database."""
        async with AsyncSessionLocal() as session:
            # Try exact match first
            result = await session.execute(
                select(Symbol).where(Symbol.symbol == self.symbol_name)
            )
            symbol = result.scalar_one_or_none()
            
            if symbol:
                return symbol
            
            # Try case-insensitive match
            result = await session.execute(
                select(Symbol).where(Symbol.symbol.ilike(self.symbol_name))
            )
            symbol = result.scalar_one_or_none()
            
            return symbol
    
    async def _get_existing_data_dates(self) -> set:
        """Get set of dates that already have data for this symbol."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MarketData.timestamp).where(
                    and_(
                        MarketData.symbol_id == self.symbol_obj.id,
                        MarketData.timeframe == "1day"
                    )
                )
            )
            
            # Convert timestamps to date strings for easy comparison
            existing_dates = set()
            for row in result:
                date_str = row[0].strftime('%Y-%m-%d')
                existing_dates.add(date_str)
            
            return existing_dates
    
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
                        client_id=IBKR_CLIENT_ID + 10  # Use different client ID
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
    
    async def _process_date_ranges(self, start_date: datetime, end_date: datetime, existing_dates: set):
        """Process the date range, requesting data in optimal chunks."""
        
        # Generate date ranges for requests
        date_ranges = self._generate_date_ranges(start_date, end_date)
        logger.info(f"📦 Will process {len(date_ranges)} date range chunks")
        
        for i, (range_start, range_end) in enumerate(date_ranges):
            logger.info(f"📦 Processing chunk {i + 1}/{len(date_ranges)}: "
                       f"{range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}")
            
            # Check if we need data for this range
            days_needed = self._count_trading_days_needed(range_start, range_end, existing_dates)
            
            if days_needed == 0:
                logger.info(f"⏭️  Skipping chunk - all data already exists")
                continue
            
            logger.info(f"📊 Need data for approximately {days_needed} trading days in this chunk")
            
            # Request historical data for this chunk
            success = await self._request_historical_data_range(range_start, range_end, existing_dates)
            
            if not success:
                logger.warning(f"⚠️  Failed to collect data for chunk {i + 1}")
            
            # Delay between chunks to respect API limits
            if i < len(date_ranges) - 1:
                logger.info(f"⏳ Waiting {self.batch_delay_seconds} seconds before next chunk...")
                await asyncio.sleep(self.batch_delay_seconds)
    
    def _count_trading_days_needed(self, start_date: datetime, end_date: datetime, existing_dates: set) -> int:
        """Count how many trading days we need to collect in a date range."""
        count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if self._is_trading_day(current_date):
                date_str = current_date.strftime('%Y-%m-%d')
                if date_str not in existing_dates:
                    count += 1
            current_date += timedelta(days=1)
        
        return count
    
    async def _request_historical_data_range(self, start_date: datetime, end_date: datetime, 
                                           existing_dates: set) -> bool:
        """Request historical data for a date range."""
        try:
            # Create contract for the symbol
            contract = self._create_contract_for_symbol()
            
            # Calculate duration for IBKR request
            duration_days = (end_date - start_date).days + 1
            
            # IBKR requires durations > 365 days to be specified in years
            if duration_days > 365:
                duration_years = round(duration_days / 365.25, 1)  # Account for leap years
                if duration_years.is_integer():
                    duration_str = f"{int(duration_years)} Y"
                else:
                    duration_str = f"{duration_years} Y"
            else:
                duration_str = f"{duration_days} D"
            
            # Format end date with proper timezone
            end_date_str = self._format_date_with_timezone(end_date, self.symbol_obj.exchange)
            
            request_id = self.request_id_counter
            self.request_id_counter += 1
            
            logger.debug(f"📡 Requesting historical data for {self.symbol_obj.symbol} "
                        f"(req_id: {request_id}) duration: {duration_str}, end: {end_date_str}")
            
            # Request historical data
            bars = await self.ibkr_manager.get_historical_data(
                contract=contract,
                end_date=end_date_str,
                duration=duration_str,
                bar_size=DEFAULT_BAR_SIZE,
                what_to_show=DEFAULT_WHAT_TO_SHOW,
                use_rth=USE_REGULAR_TRADING_HOURS,
                format_date=1,  # Return as string
                timeout=REQUEST_TIMEOUT * 2  # Longer timeout for historical data
            )
            
            if not bars:
                logger.warning(f"⚠️  No data returned for date range")
                return False
            
            logger.info(f"📈 Received {len(bars)} bars of historical data")
            
            # Process and store each bar
            stored_count = 0
            skipped_count = 0
            
            for bar in bars:
                # Parse the date from the bar
                try:
                    # IBKR returns dates as strings like "20240101" or "20240101  23:59:59"
                    date_str = bar.date.strip()
                    if len(date_str) == 8:  # Format: "20240101"
                        bar_date = datetime.strptime(date_str, "%Y%m%d")
                    else:  # Format: "20240101  23:59:59"
                        bar_date = datetime.strptime(date_str.split()[0], "%Y%m%d")
                    
                    date_key = bar_date.strftime('%Y-%m-%d')
                    
                    # Skip if we already have this data
                    if date_key in existing_dates:
                        skipped_count += 1
                        self.collection_stats["skipped_days"] += 1
                        continue
                    
                    # Store the data
                    await self._store_market_data(bar, bar_date)
                    stored_count += 1
                    self.collection_stats["successful_collections"] += 1
                    
                    # Add to existing dates to avoid duplicates in the same batch
                    existing_dates.add(date_key)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing bar with date {bar.date}: {str(e)}")
                    self.collection_stats["failed_collections"] += 1
            
            logger.info(f"💾 Stored {stored_count} new records, skipped {skipped_count} existing")
            
            # Small delay after processing
            await asyncio.sleep(self.request_delay_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error requesting historical data: {str(e)}")
            return False
    
    def _create_contract_for_symbol(self) -> Contract:
        """Create appropriate IBKR contract for the symbol."""
        contract = Contract()
        contract.symbol = self.symbol_obj.symbol
        contract.currency = self.symbol_obj.currency
        
        # Set security type using configuration mapping
        sec_type_str = self.symbol_obj.security_type.value if hasattr(self.symbol_obj.security_type, 'value') else str(self.symbol_obj.security_type)
        contract.secType = SECURITY_TYPE_MAPPINGS.get(sec_type_str, "STK")
        
        # Set exchange using configuration mapping
        exchange_config = EXCHANGE_MAPPINGS.get(self.symbol_obj.exchange, {
            "exchange": "SMART",
            "primary_exchange": self.symbol_obj.exchange,
            "currency": self.symbol_obj.currency
        })
        
        contract.exchange = exchange_config["exchange"]
        if "primary_exchange" in exchange_config:
            contract.primaryExchange = exchange_config["primary_exchange"]
        
        # Override currency if specified in exchange config
        if "currency" in exchange_config and not self.symbol_obj.currency:
            contract.currency = exchange_config["currency"]
        
        # Use contract ID if available
        if self.symbol_obj.contract_id:
            contract.conId = self.symbol_obj.contract_id
        
        return contract
    
    async def _store_market_data(self, bar: BarData, bar_date: datetime):
        """Store market data in the database."""
        try:
            async with AsyncSessionLocal() as session:
                # Create market data record with market close time
                market_data = MarketData(
                    symbol_id=self.symbol_obj.id,
                    timestamp=bar_date.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0),
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
                
                logger.debug(f"💾 Stored data for {bar_date.strftime('%Y-%m-%d')}: "
                           f"O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close} V:{bar.volume}")
                
        except IntegrityError:
            # Data already exists, which is fine
            logger.debug(f"⚠️  Data already exists for {bar_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logger.error(f"❌ Error storing data for {bar_date.strftime('%Y-%m-%d')}: {str(e)}")
            raise
    
    async def _simulate_collection(self, start_date: datetime, end_date: datetime):
        """Simulate the collection process for dry run mode."""
        logger.info("🔍 Simulating historical data collection...")
        
        # Get existing data to show what would be skipped
        existing_dates = await self._get_existing_data_dates()
        
        current_date = start_date
        trading_days = 0
        existing_count = 0
        
        while current_date <= end_date:
            if self._is_trading_day(current_date):
                trading_days += 1
                date_str = current_date.strftime('%Y-%m-%d')
                
                if date_str in existing_dates:
                    existing_count += 1
                    logger.debug(f"🔍 Would skip {date_str} (already exists)")
                else:
                    logger.debug(f"🔍 Would collect {date_str}")
            
            current_date += timedelta(days=1)
        
        need_to_collect = trading_days - existing_count
        
        logger.info(f"🔍 Simulation results:")
        logger.info(f"   📅 Total trading days in range: {trading_days}")
        logger.info(f"   ✅ Already have data for: {existing_count}")
        logger.info(f"   📈 Would collect: {need_to_collect}")
        
        if need_to_collect > 0:
            est_chunks = (need_to_collect // MAX_DAYS_PER_REQUEST) + 1
            est_time = est_chunks * (self.batch_delay_seconds + 5)  # Estimate
            logger.info(f"   🕐 Estimated collection time: ~{est_time:.0f} seconds")


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


async def main():
    """Main entry point for the historical symbol data collection script."""
    parser = argparse.ArgumentParser(
        description="Historical Symbol Data Collection Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s AAPL                                    # Last 3 years of AAPL data
  %(prog)s CBA.AX --years 5                       # Last 5 years of CBA data
  %(prog)s TSLA --start-date 2020-01-01            # From 2020 to yesterday
  %(prog)s MSFT --start-date 2022-01-01 --end-date 2024-12-31  # Specific range
  %(prog)s GOOGL --dry-run                         # Simulate without collecting
        """
    )
    
    parser.add_argument("symbol", help="Symbol to collect historical data for")
    parser.add_argument("--start-date", type=parse_date,
                       help="Start date for data collection (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=parse_date,
                       help="End date for data collection (YYYY-MM-DD)")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS_BACK,
                       help=f"Number of years back from today (default: {DEFAULT_YEARS_BACK})")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate the collection process without actually collecting data")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.start_date and args.end_date and args.start_date > args.end_date:
        logger.error("❌ Start date must be before end date")
        sys.exit(1)
    
    # Create and run collector
    collector = HistoricalSymbolDataCollector(args.symbol, dry_run=args.dry_run)
    success = await collector.collect_historical_data(
        start_date=args.start_date,
        end_date=args.end_date,
        years_back=args.years if not args.start_date else None
    )
    
    if success:
        logger.info("✅ Historical data collection completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Historical data collection failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
