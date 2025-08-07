#!/usr/bin/env python3
"""
Intraday Market Data Collection Script

This script collects intraday market data (5-minute, 1-minute bars) for symbols
in the watchlist using the Interactive Brokers TWS API.

Features:
- Collects 5min and 1min bars for watchlist symbols
- Respects TWS API rate limits for historical data
- Intelligent gap detection and backfilling
- Priority-based collection order
- Comprehensive error handling and logging
- Market hours awareness

Usage:
    python intraday_collection.py --timeframe 5min --watchlist default_intraday
    python intraday_collection.py --timeframe 1min --backfill --days 5
    python intraday_collection.py --all-watchlists
"""

import asyncio
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, time as time_obj
from typing import Dict, List, Optional, Tuple
import traceback

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.ibkr.client import IBKRManager
from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, MarketData, Watchlist, CollectionLog
from shared.ibkr.contracts import create_stock_contract
from config.intraday_collection_config import *
from sqlalchemy import select, and_, desc, func
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


class IntradayDataCollector:
    """Manages intraday data collection for watchlist symbols."""
    
    def __init__(self, timeframe: str = "5min"):
        self.timeframe = timeframe
        self.timeframe_config = TIMEFRAMES.get(timeframe, TIMEFRAMES["5min"])
        self.ibkr_manager = None
        self.session = None
        self.collection_stats = {
            "symbols_processed": 0,
            "bars_collected": 0,
            "errors": 0,
            "api_requests": 0,
            "start_time": datetime.now()
        }
    
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
        return date.strftime(f"%Y%m%d %H:%M:%S {timezone}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await init_db()
        self.session = AsyncSessionLocal()
        self.ibkr_manager = IBKRManager(
            host=IBKR_HOST,
            port=IBKR_PORT,
            client_id=IBKR_CLIENT_ID
        )
        await self.ibkr_manager.connect(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.ibkr_manager:
            await self.ibkr_manager.disconnect()
        if self.session:
            await self.session.close()
    
    async def get_watchlist_symbols(self, watchlist_name: Optional[str] = None) -> List[Tuple[Symbol, Watchlist]]:
        """Get symbols from watchlist ordered by priority."""
        try:
            query = select(Symbol, Watchlist).join(Watchlist).where(
                Watchlist.active == True
            )
            
            # Filter by watchlist name if specified
            if watchlist_name:
                query = query.where(Watchlist.name == watchlist_name)
            
            # Filter by timeframe collection settings
            if self.timeframe == "5min":
                query = query.where(Watchlist.collect_5min == True)
            elif self.timeframe == "1min":
                query = query.where(Watchlist.collect_1min == True)
            
            # Order by priority (1 = highest priority)
            query = query.order_by(Watchlist.priority, Symbol.symbol)
            
            result = await self.session.execute(query)
            symbols = result.all()
            
            logger.info(f"Found {len(symbols)} symbols for {self.timeframe} collection"
                       f"{f' in watchlist {watchlist_name}' if watchlist_name else ''}")
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting watchlist symbols: {e}")
            return []
    
    async def get_latest_data_timestamp(self, symbol_id: int) -> Optional[datetime]:
        """Get the latest data timestamp for a symbol and timeframe."""
        try:
            result = await self.session.execute(
                select(MarketData.timestamp).where(
                    and_(
                        MarketData.symbol_id == symbol_id,
                        MarketData.timeframe == self.timeframe
                    )
                ).order_by(desc(MarketData.timestamp)).limit(1)
            )
            latest = result.scalar_one_or_none()
            return latest
            
        except Exception as e:
            logger.error(f"Error getting latest timestamp for symbol {symbol_id}: {e}")
            return None
    
    async def detect_data_gaps(self, symbol_id: int, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """Detect gaps in data coverage."""
        try:
            # Get all timestamps for the symbol in the date range
            result = await self.session.execute(
                select(MarketData.timestamp).where(
                    and_(
                        MarketData.symbol_id == symbol_id,
                        MarketData.timeframe == self.timeframe,
                        MarketData.timestamp >= start_date,
                        MarketData.timestamp <= end_date
                    )
                ).order_by(MarketData.timestamp)
            )
            
            timestamps = [row[0] for row in result.all()]
            
            if not timestamps:
                # No data at all - entire range is a gap
                return [(start_date, end_date)]
            
            gaps = []
            expected_interval = timedelta(minutes=5 if self.timeframe == "5min" else 1)
            
            # Check for gap at the beginning
            if timestamps[0] > start_date + expected_interval:
                gaps.append((start_date, timestamps[0] - expected_interval))
            
            # Check for gaps between timestamps
            for i in range(len(timestamps) - 1):
                current = timestamps[i]
                next_timestamp = timestamps[i + 1]
                expected_next = current + expected_interval
                
                # Skip weekends and adjust for market hours
                while expected_next < next_timestamp:
                    # Check if this is a significant gap (more than double the interval)
                    if next_timestamp - expected_next > expected_interval * 2:
                        gap_start = current + expected_interval
                        gap_end = next_timestamp - expected_interval
                        if gap_end > gap_start:
                            gaps.append((gap_start, gap_end))
                        break
                    expected_next += expected_interval
            
            # Check for gap at the end
            if timestamps[-1] < end_date - expected_interval:
                gaps.append((timestamps[-1] + expected_interval, end_date))
            
            return gaps
            
        except Exception as e:
            logger.error(f"Error detecting data gaps for symbol {symbol_id}: {e}")
            return []
    
    async def collect_bars_for_symbol(self, symbol: Symbol, start_time: datetime, 
                                    end_time: datetime) -> Tuple[int, bool]:
        """Collect bars for a specific symbol and time range."""
        try:
            # Create IBKR contract
            contract = create_stock_contract(
                symbol=symbol.local_symbol,
                exchange=symbol.exchange,
                currency=symbol.currency
            )
            
            if not contract:
                logger.error(f"Failed to create contract for {symbol.symbol}")
                return 0, False
            
            # Calculate duration string
            duration_days = (end_time - start_time).days + 1
            duration = f"{duration_days} D"
            
            # Override with config duration if it's smaller
            if duration_days > 2 and self.timeframe == "5min":
                duration = self.timeframe_config["duration"]
            elif duration_days > 1 and self.timeframe == "1min":
                duration = self.timeframe_config["duration"]
            
            logger.info(f"Requesting {self.timeframe} bars for {symbol.symbol} "
                       f"from {start_time.date()} to {end_time.date()} (duration: {duration})")
            
            # Request historical data with timezone-aware formatting
            bars = await self.ibkr_manager.get_historical_data(
                contract=contract,
                end_date=self._format_date_with_timezone(end_time, symbol.exchange),
                duration=duration,
                bar_size=self.timeframe_config["bar_size"],
                what_to_show=self.timeframe_config["what_to_show"],
                use_rth=self.timeframe_config["use_rth"]
            )
            
            self.collection_stats["api_requests"] += 1
            
            if not bars:
                logger.warning(f"No bars returned for {symbol.symbol}")
                return 0, True
            
            # Process and store bars
            bars_stored = await self.store_bars(symbol.id, bars)
            self.collection_stats["bars_collected"] += bars_stored
            
            logger.info(f"✅ Collected {bars_stored} {self.timeframe} bars for {symbol.symbol}")
            return bars_stored, True
            
        except Exception as e:
            logger.error(f"❌ Error collecting bars for {symbol.symbol}: {e}")
            logger.error(traceback.format_exc())
            self.collection_stats["errors"] += 1
            return 0, False
    
    async def store_bars(self, symbol_id: int, bars: List[BarData]) -> int:
        """Store bars in the database."""
        try:
            bars_to_insert = []
            
            for bar in bars:
                # Convert IBKR timestamp to datetime
                bar_time = datetime.strptime(bar.date, "%Y%m%d %H:%M:%S")
                
                # Quality checks
                if not self.validate_bar_data(bar):
                    logger.warning(f"Invalid bar data for {symbol_id} at {bar_time}: {bar}")
                    continue
                
                # Check if bar already exists
                existing_result = await self.session.execute(
                    select(MarketData).where(
                        and_(
                            MarketData.symbol_id == symbol_id,
                            MarketData.timeframe == self.timeframe,
                            MarketData.timestamp == bar_time
                        )
                    )
                )
                
                if existing_result.scalar_one_or_none():
                    continue  # Skip duplicate
                
                market_data = MarketData(
                    symbol_id=symbol_id,
                    timestamp=bar_time,
                    timeframe=self.timeframe,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    wap=bar.wap if hasattr(bar, 'wap') else None,
                    bar_count=bar.count if hasattr(bar, 'count') else 0
                )
                
                bars_to_insert.append(market_data)
            
            # Batch insert
            if bars_to_insert:
                self.session.add_all(bars_to_insert)
                await self.session.commit()
                return len(bars_to_insert)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error storing bars for symbol {symbol_id}: {e}")
            await self.session.rollback()
            return 0
    
    def validate_bar_data(self, bar: BarData) -> bool:
        """Validate bar data quality."""
        try:
            # Check for required fields
            if not all([bar.open, bar.high, bar.low, bar.close]):
                return False
            
            # Check OHLC relationships
            if bar.high < bar.open or bar.high < bar.close:
                logger.warning(f"Invalid OHLC: high ({bar.high}) < open ({bar.open}) or close ({bar.close})")
                return False
            
            if bar.low > bar.open or bar.low > bar.close:
                logger.warning(f"Invalid OHLC: low ({bar.low}) > open ({bar.open}) or close ({bar.close})")
                return False
            
            # Check for reasonable values
            if bar.volume < 0:
                return False
            
            # Check for extreme price changes (more than 50% in one bar)
            if abs(bar.close - bar.open) / bar.open > 0.5:
                logger.warning(f"Extreme price change: {bar.open} -> {bar.close}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating bar data: {e}")
            return False
    
    async def log_collection_job(self, symbol_id: int, status: str, 
                               start_date: datetime, end_date: datetime,
                               records_collected: int = 0, error_message: str = None):
        """Log collection job status."""
        try:
            collection_log = CollectionLog(
                symbol_id=symbol_id,
                collection_type="historical",
                timeframe=self.timeframe,
                start_date=start_date,
                end_date=end_date,
                status=status,
                error_message=error_message,
                records_collected=records_collected,
                completed_at=datetime.now() if status in ["completed", "failed"] else None
            )
            
            self.session.add(collection_log)
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging collection job: {e}")
    
    async def collect_for_watchlist(self, watchlist_name: Optional[str] = None,
                                  backfill_days: int = 7, max_symbols: Optional[int] = None) -> Dict:
        """Collect intraday data for watchlist symbols."""
        logger.info(f"🚀 Starting {self.timeframe} data collection"
                   f"{f' for watchlist: {watchlist_name}' if watchlist_name else ''}")
        
        # Get symbols from watchlist
        symbol_pairs = await self.get_watchlist_symbols(watchlist_name)
        
        if max_symbols:
            symbol_pairs = symbol_pairs[:max_symbols]
        
        if not symbol_pairs:
            logger.warning("No symbols found for collection")
            return self.collection_stats
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=backfill_days)
        
        logger.info(f"Collecting data from {start_time.date()} to {end_time.date()}")
        logger.info(f"Processing {len(symbol_pairs)} symbols with {self.timeframe} timeframe")
        
        # Process symbols with rate limiting
        for i, (symbol, watchlist_entry) in enumerate(symbol_pairs):
            try:
                logger.info(f"[{i+1}/{len(symbol_pairs)}] Processing {symbol.symbol} "
                           f"(Priority: {watchlist_entry.priority})")
                
                # Check for existing data and gaps
                latest_timestamp = await self.get_latest_data_timestamp(symbol.id)
                
                if latest_timestamp:
                    # Only collect data newer than what we have
                    collection_start = latest_timestamp + timedelta(minutes=5 if self.timeframe == "5min" else 1)
                    logger.info(f"Latest data for {symbol.symbol}: {latest_timestamp}, "
                               f"collecting from {collection_start}")
                else:
                    collection_start = start_time
                    logger.info(f"No existing data for {symbol.symbol}, collecting from {collection_start}")
                
                if collection_start >= end_time:
                    logger.info(f"✅ {symbol.symbol} data is up to date")
                    continue
                
                # Collect bars
                bars_collected, success = await self.collect_bars_for_symbol(
                    symbol, collection_start, end_time
                )
                
                # Log the collection job
                await self.log_collection_job(
                    symbol_id=symbol.id,
                    status="completed" if success else "failed",
                    start_date=collection_start,
                    end_date=end_time,
                    records_collected=bars_collected,
                    error_message=None if success else "Collection failed"
                )
                
                self.collection_stats["symbols_processed"] += 1
                
                # Rate limiting - respect IBKR API limits
                if i < len(symbol_pairs) - 1:  # Don't wait after the last symbol
                    pacing_delay = self.timeframe_config["pacing_delay"]
                    logger.info(f"⏱️  Waiting {pacing_delay}s for API pacing...")
                    await asyncio.sleep(pacing_delay)
                
            except Exception as e:
                logger.error(f"❌ Error processing {symbol.symbol}: {e}")
                self.collection_stats["errors"] += 1
                continue
        
        # Print summary
        elapsed_time = datetime.now() - self.collection_stats["start_time"]
        logger.info("🎉 Collection completed!")
        logger.info(f"📊 Summary:")
        logger.info(f"   • Symbols processed: {self.collection_stats['symbols_processed']}")
        logger.info(f"   • Bars collected: {self.collection_stats['bars_collected']}")
        logger.info(f"   • API requests: {self.collection_stats['api_requests']}")
        logger.info(f"   • Errors: {self.collection_stats['errors']}")
        logger.info(f"   • Elapsed time: {elapsed_time}")
        
        return self.collection_stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Collect intraday market data")
    parser.add_argument("--timeframe", choices=["5min", "1min"], default="5min",
                       help="Timeframe for data collection")
    parser.add_argument("--watchlist", help="Specific watchlist name to collect")
    parser.add_argument("--all-watchlists", action="store_true",
                       help="Collect for all active watchlists")
    parser.add_argument("--backfill", type=int, default=7,
                       help="Days to backfill (default: 7)")
    parser.add_argument("--max-symbols", type=int,
                       help="Maximum number of symbols to process")
    parser.add_argument("--test-mode", action="store_true",
                       help="Test mode - process only first 3 symbols")
    
    args = parser.parse_args()
    
    try:
        # Test mode
        if args.test_mode:
            args.max_symbols = 3
            args.backfill = 2
            logger.info("🧪 Running in test mode")
        
        async with IntradayDataCollector(args.timeframe) as collector:
            if args.all_watchlists:
                # Collect for all watchlists
                stats = await collector.collect_for_watchlist(
                    watchlist_name=None,
                    backfill_days=args.backfill,
                    max_symbols=args.max_symbols
                )
            else:
                # Collect for specific watchlist or default
                stats = await collector.collect_for_watchlist(
                    watchlist_name=args.watchlist,
                    backfill_days=args.backfill,
                    max_symbols=args.max_symbols
                )
        
        return stats
        
    except KeyboardInterrupt:
        logger.info("🛑 Collection interrupted by user")
        return None
    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    asyncio.run(main())
