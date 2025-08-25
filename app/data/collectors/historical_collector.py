import asyncio
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
import structlog
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.data.collectors.ibkr_client import IBKRClient
from app.utils.ibkr_contracts import create_asx_stock_contract
from app.data.services.watchlist_service import WatchlistService
from app.data.models.market import DailyPrice, ApiRequest
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.utils.rate_limiter import IBKRRateLimiter, RequestType, rate_limited_request
from sqlalchemy.dialects.postgresql import insert

logger = structlog.get_logger(__name__)


@dataclass
class BackfillStats:
    """Statistics for backfill operations"""
    symbol: str
    start_date: date
    end_date: date
    bars_requested: int
    bars_received: int
    bars_stored: int
    gaps_found: int
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class BackfillProgress:
    """Progress tracking for backfill operations"""
    total_symbols: int
    completed_symbols: int
    current_symbol: str
    estimated_completion: Optional[datetime] = None


class HistoricalDataCollector:
    """
    Specialized collector for historical data backfill operations
    
    Handles:
    - Gap detection and filling
    - Bulk historical data collection
    - Progress tracking and resume capability
    - Rate limiting compliance
    - Data quality validation during backfill
    """
    
    def __init__(self, rate_limiter: IBKRRateLimiter = None):
        self.ibkr_client = IBKRClient()
        self.rate_limiter = rate_limiter
        self._rate_limiter_owned = False
        self.backfill_stats: List[BackfillStats] = []
        self.progress: Optional[BackfillProgress] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Initialize rate limiter if not provided
        if self.rate_limiter is None:
            self.rate_limiter = IBKRRateLimiter()
            await self.rate_limiter.__aenter__()
            self._rate_limiter_owned = True
        
        # Connect to TWS
        if not self.ibkr_client.connect_to_tws():
            raise ConnectionError("Failed to connect to IBKR TWS")
            
        logger.info("Historical data collector initialized")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.ibkr_client:
            self.ibkr_client.disconnect_from_tws()
            
        if self._rate_limiter_owned and self.rate_limiter:
            await self.rate_limiter.__aexit__(exc_type, exc_val, exc_tb)
            self.rate_limiter = None
            self._rate_limiter_owned = False
    
    async def detect_data_gaps(self, symbol: str, start_date: date, end_date: date) -> List[Tuple[date, date]]:
        """
        Detect gaps in historical data for a symbol
        
        Returns:
            List of (start_date, end_date) tuples representing gaps
        """
        gaps = []
        
        async with AsyncSessionLocal() as db_session:
            try:
                # Get all existing dates for this symbol in the range
                result = await db_session.execute(
                    select(DailyPrice.date)
                    .where(
                        and_(
                            DailyPrice.symbol == symbol,
                            DailyPrice.date >= start_date,
                            DailyPrice.date <= end_date
                        )
                    )
                    .order_by(DailyPrice.date)
                )
                
                existing_dates = {row[0] for row in result}
                
                # Generate expected trading dates (Monday-Friday, excluding holidays)
                expected_dates = self._generate_trading_dates(start_date, end_date)
                
                # Find gaps
                missing_dates = sorted(expected_dates - existing_dates)
                
                if missing_dates:
                    # Group consecutive missing dates into ranges
                    gaps = self._group_consecutive_dates(missing_dates)
                
                logger.info("Gap detection completed", 
                           symbol=symbol, gaps_found=len(gaps), missing_dates=len(missing_dates))
                
            except Exception as e:
                logger.error("Error detecting data gaps", symbol=symbol, error=str(e))
                
        return gaps
    
    def _generate_trading_dates(self, start_date: date, end_date: date) -> set:
        """Generate set of expected trading dates (weekdays only, no holiday logic yet)"""
        trading_dates = set()
        current_date = start_date
        
        while current_date <= end_date:
            # Only include weekdays (Monday=0, Friday=4)
            if current_date.weekday() < 5:
                trading_dates.add(current_date)
            current_date += timedelta(days=1)
            
        return trading_dates
    
    def _group_consecutive_dates(self, dates: List[date]) -> List[Tuple[date, date]]:
        """Group consecutive dates into ranges"""
        if not dates:
            return []
            
        groups = []
        start_date = dates[0]
        end_date = dates[0]
        
        for i in range(1, len(dates)):
            if dates[i] == end_date + timedelta(days=1):
                end_date = dates[i]
            else:
                groups.append((start_date, end_date))
                start_date = dates[i]
                end_date = dates[i]
        
        groups.append((start_date, end_date))
        return groups
    
    async def backfill_symbol(self, symbol: str, start_date: date, end_date: date, 
                             fill_gaps_only: bool = False) -> BackfillStats:
        """
        Backfill historical data for a single symbol
        
        Args:
            symbol: Stock symbol to backfill
            start_date: Start date for backfill
            end_date: End date for backfill  
            fill_gaps_only: If True, only fill detected gaps
            
        Returns:
            BackfillStats object with operation results
        """
        start_time = time.time()
        
        logger.info("Starting symbol backfill", 
                   symbol=symbol, start_date=start_date, end_date=end_date, 
                   fill_gaps_only=fill_gaps_only)
        
        try:
            # Detect gaps if only filling gaps
            if fill_gaps_only:
                gaps = await self.detect_data_gaps(symbol, start_date, end_date)
                if not gaps:
                    logger.info("No gaps found for symbol", symbol=symbol)
                    return BackfillStats(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        bars_requested=0,
                        bars_received=0,
                        bars_stored=0,
                        gaps_found=0,
                        duration_seconds=time.time() - start_time,
                        success=True
                    )
                
                # Process each gap separately to respect IBKR limits
                total_bars_stored = 0
                total_gaps = len(gaps)
                
                for gap_start, gap_end in gaps:
                    gap_stats = await self._backfill_date_range(symbol, gap_start, gap_end)
                    total_bars_stored += gap_stats.bars_stored
                    
                    if not gap_stats.success:
                        return BackfillStats(
                            symbol=symbol,
                            start_date=start_date,
                            end_date=end_date,
                            bars_requested=gap_stats.bars_requested,
                            bars_received=gap_stats.bars_received,
                            bars_stored=total_bars_stored,
                            gaps_found=total_gaps,
                            duration_seconds=time.time() - start_time,
                            success=False,
                            error_message=gap_stats.error_message
                        )
                
                return BackfillStats(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    bars_requested=sum((gap_end - gap_start).days + 1 for gap_start, gap_end in gaps),
                    bars_received=total_bars_stored,
                    bars_stored=total_bars_stored,
                    gaps_found=total_gaps,
                    duration_seconds=time.time() - start_time,
                    success=True
                )
            
            else:
                # Backfill entire date range
                return await self._backfill_date_range(symbol, start_date, end_date)
                
        except Exception as e:
            logger.error("Error in symbol backfill", symbol=symbol, error=str(e))
            return BackfillStats(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                bars_requested=0,
                bars_received=0,
                bars_stored=0,
                gaps_found=0,
                duration_seconds=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _backfill_date_range(self, symbol: str, start_date: date, end_date: date) -> BackfillStats:
        """Backfill a specific date range for a symbol"""
        start_time = time.time()
        
        # Calculate duration string for IBKR API
        total_days = (end_date - start_date).days + 1
        
        # IBKR duration string mapping (approximate)
        if total_days <= 30:
            duration_str = f"{total_days} D"
        elif total_days <= 365:
            weeks = total_days // 7
            duration_str = f"{weeks} W"
        else:
            years = total_days // 365
            duration_str = f"{years} Y"
        
        logger.debug("Backfilling date range", 
                    symbol=symbol, start_date=start_date, end_date=end_date, 
                    duration_str=duration_str)
        
        try:
            data_buffer = []
            
            async with rate_limited_request(
                self.rate_limiter,
                RequestType.HISTORICAL,
                symbol=symbol,
                identifier=f"{symbol}_{start_date}_{end_date}"
            ):
                contract = create_asx_stock_contract(symbol)
                callback = self._create_historical_callback(symbol, data_buffer)
                
                # Format end date for IBKR API (YYYYMMDD HH:MM:SS)
                end_datetime_str = end_date.strftime("%Y%m%d 23:59:59")
                
                req_id = self.ibkr_client.request_historical_data(
                    contract=contract,
                    end_datetime=end_datetime_str,
                    duration_str=duration_str,
                    bar_size_setting="1 day",
                    what_to_show="TRADES",
                    use_rth=1,  # Regular trading hours only
                    format_date=1,  # String format
                    keep_up_to_date=False,
                    chart_options=[],
                    callback=callback
                )
                
                if not req_id:
                    raise Exception("Failed to submit historical data request")
                
                # Wait for data with timeout
                timeout_seconds = 30
                start_wait = time.time()
                
                while len(data_buffer) == 0 and (time.time() - start_wait) < timeout_seconds:
                    await asyncio.sleep(0.5)
                
                # Wait a bit more for all data to arrive
                await asyncio.sleep(2)
            
            # Store data in database
            bars_stored = await self._store_backfill_data(data_buffer, symbol)
            
            return BackfillStats(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                bars_requested=total_days,
                bars_received=len(data_buffer),
                bars_stored=bars_stored,
                gaps_found=0,
                duration_seconds=time.time() - start_time,
                success=bars_stored > 0
            )
            
        except Exception as e:
            logger.error("Error backfilling date range", 
                        symbol=symbol, start_date=start_date, end_date=end_date, error=str(e))
            return BackfillStats(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                bars_requested=total_days,
                bars_received=0,
                bars_stored=0,
                gaps_found=0,
                duration_seconds=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def _create_historical_callback(self, symbol: str, data_buffer: List):
        """Create callback for historical data that validates and stores in buffer"""
        def callback(bar):
            try:
                # Parse date - handle both "20240101" and "20240101  23:59:59" formats
                date_str = bar.date.strip()
                if len(date_str) == 8:  # Format: "20240101"
                    bar_date = datetime.strptime(date_str, "%Y%m%d").date()
                else:  # Format: "20240101  23:59:59"
                    bar_date = datetime.strptime(date_str.split()[0], "%Y%m%d").date()
                
                # Validate bar data
                if not self._validate_historical_bar(bar, symbol):
                    return
                
                # Store in buffer
                bar_data = {
                    'symbol': symbol,
                    'date': bar_date,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume) if bar.volume != -1 else 0,
                    'adj_close': float(bar.close)  # Use close as adjusted for now
                }
                
                data_buffer.append(bar_data)
                
                logger.debug("Historical bar received and validated", 
                           symbol=symbol, date=bar_date, close=bar.close)
                
            except Exception as e:
                logger.error("Error processing backfill bar", 
                           symbol=symbol, bar_date=getattr(bar, 'date', 'unknown'), error=str(e))
        
        return callback
    
    def _validate_historical_bar(self, bar, symbol: str) -> bool:
        """Validate historical bar data for basic sanity checks"""
        try:
            # Check for valid OHLC relationships
            if bar.high < bar.low:
                logger.warning("Invalid OHLC: high < low", symbol=symbol, high=bar.high, low=bar.low)
                return False
            
            if bar.open < 0 or bar.close < 0:
                logger.warning("Invalid prices: negative values", symbol=symbol, open=bar.open, close=bar.close)
                return False
            
            if bar.volume < 0:
                logger.warning("Invalid volume: negative", symbol=symbol, volume=bar.volume)
                return False
            
            # Price range check for ASX stocks
            if bar.close > 10000 or bar.close < 0.001:
                logger.warning("Price outside expected range", symbol=symbol, close=bar.close)
                return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating historical bar", symbol=symbol, error=str(e))
            return False
    
    async def _store_backfill_data(self, data_buffer: List[Dict], symbol: str) -> int:
        """Store backfilled data in database with upsert logic"""
        if not data_buffer:
            return 0
            
        stored_count = 0
        
        async with AsyncSessionLocal() as db_session:
            try:
                for bar_data in data_buffer:
                    stmt = insert(DailyPrice).values(
                        symbol=bar_data['symbol'],
                        date=bar_data['date'],
                        open=bar_data['open'],
                        high=bar_data['high'],
                        low=bar_data['low'],
                        close=bar_data['close'],
                        volume=bar_data['volume'],
                        adj_close=bar_data['adj_close'],
                        created_at=datetime.now()
                    )
                    
                    # Use ON CONFLICT DO UPDATE to update existing records with newer data
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['symbol', 'date'],
                        set_={
                            'open': stmt.excluded.open,
                            'high': stmt.excluded.high,
                            'low': stmt.excluded.low,
                            'close': stmt.excluded.close,
                            'volume': stmt.excluded.volume,
                            'adj_close': stmt.excluded.adj_close,
                            'created_at': stmt.excluded.created_at
                        }
                    )
                    
                    await db_session.execute(stmt)
                    stored_count += 1
                
                await db_session.commit()
                logger.info("Backfill data stored", symbol=symbol, bars_stored=stored_count)
                
            except Exception as e:
                await db_session.rollback()
                logger.error("Error storing backfill data", symbol=symbol, error=str(e))
                raise
        
        return stored_count
    
    async def bulk_backfill(self, symbols: List[str], start_date: date, end_date: date,
                           fill_gaps_only: bool = False, max_concurrent: int = 1) -> List[BackfillStats]:
        """
        Perform bulk backfill for multiple symbols
        
        Args:
            symbols: List of symbols to backfill
            start_date: Start date for backfill
            end_date: End date for backfill
            fill_gaps_only: If True, only fill detected gaps
            max_concurrent: Maximum concurrent backfill operations (keep at 1 for rate limiting)
            
        Returns:
            List of BackfillStats for each symbol
        """
        logger.info("Starting bulk backfill", 
                   symbols_count=len(symbols), start_date=start_date, end_date=end_date)
        
        self.progress = BackfillProgress(
            total_symbols=len(symbols),
            completed_symbols=0,
            current_symbol=""
        )
        
        all_stats = []
        
        # Process symbols sequentially to respect rate limits
        for i, symbol in enumerate(symbols):
            self.progress.current_symbol = symbol
            self.progress.completed_symbols = i
            
            logger.info("Backfilling symbol", 
                       symbol=symbol, progress=f"{i+1}/{len(symbols)}")
            
            try:
                stats = await self.backfill_symbol(symbol, start_date, end_date, fill_gaps_only)
                all_stats.append(stats)
                
                if stats.success:
                    logger.info("Symbol backfill completed", 
                               symbol=symbol, bars_stored=stats.bars_stored, 
                               duration_seconds=stats.duration_seconds)
                else:
                    logger.error("Symbol backfill failed", 
                                symbol=symbol, error=stats.error_message)
                
                # Small delay between symbols to avoid overwhelming the system
                if i < len(symbols) - 1:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error("Unexpected error in bulk backfill", symbol=symbol, error=str(e))
                all_stats.append(BackfillStats(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    bars_requested=0,
                    bars_received=0,
                    bars_stored=0,
                    gaps_found=0,
                    duration_seconds=0,
                    success=False,
                    error_message=str(e)
                ))
        
        self.progress.completed_symbols = len(symbols)
        self.backfill_stats = all_stats
        
        # Summary statistics
        successful_backfills = sum(1 for stats in all_stats if stats.success)
        total_bars_stored = sum(stats.bars_stored for stats in all_stats)
        
        logger.info("Bulk backfill completed", 
                   successful_symbols=successful_backfills, 
                   total_symbols=len(symbols),
                   total_bars_stored=total_bars_stored)
        
        return all_stats
    
    async def get_backfill_progress(self) -> Optional[BackfillProgress]:
        """Get current backfill progress"""
        return self.progress
    
    def get_backfill_summary(self) -> Dict:
        """Get summary of completed backfill operations"""
        if not self.backfill_stats:
            return {"status": "no_backfills_completed"}
        
        successful = [s for s in self.backfill_stats if s.success]
        failed = [s for s in self.backfill_stats if not s.success]
        
        return {
            "total_symbols": len(self.backfill_stats),
            "successful_symbols": len(successful),
            "failed_symbols": len(failed),
            "total_bars_stored": sum(s.bars_stored for s in successful),
            "total_duration_seconds": sum(s.duration_seconds for s in self.backfill_stats),
            "average_duration_per_symbol": sum(s.duration_seconds for s in self.backfill_stats) / len(self.backfill_stats),
            "failed_symbol_details": [(s.symbol, s.error_message) for s in failed] if failed else None
        }