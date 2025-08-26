import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from celery import current_task

from app.tasks.celery_app import celery_app
from app.data.collectors.market_data import MarketDataCollector
from app.data.collectors.historical_collector import HistoricalDataCollector
from app.data.services.watchlist_service import WatchlistService
from app.data.models.market import DailyPrice, IntradayPrice, ApiRequest
from app.utils.rate_limiter import IBKRRateLimiter
from app.config.database import AsyncSessionLocal
from app.config.settings import settings

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name='app.tasks.data_collection.collect_daily_data')
def collect_daily_data(self, symbols: Optional[List[str]] = None, exchange: str = "ASX"):
    """
    Celery task to collect daily market data
    Runs daily at market close time for specified exchange
    
    Args:
        symbols: Optional list of symbols to collect (None = all from database)
        exchange: Exchange to collect from (default: ASX)
    """
    task_id = self.request.id
    logger.info("Starting daily data collection", task_id=task_id, exchange=exchange)
    
    try:
        # Run the async data collection
        result = asyncio.run(_async_collect_daily_data(symbols, exchange, task_id))
        
        if result['success']:
            logger.info("Daily data collection completed successfully", 
                       collected=result['collected_count'],
                       errors=result['error_count'],
                       task_id=task_id)
            return {
                'status': 'success',
                'collected': result['collected_count'],
                'errors': result['error_count'],
                'duration_seconds': result['duration_seconds'],
                'symbols_processed': result['symbols_processed']
            }
        else:
            logger.error("Daily data collection failed", 
                        error=result['error'], task_id=task_id)
            return {
                'status': 'failed',
                'error': result['error']
            }
            
    except Exception as e:
        logger.error("Unexpected error in data collection task", 
                    error=str(e), task_id=task_id)
        raise self.retry(countdown=300, max_retries=3)  # Retry in 5 minutes


async def _async_collect_daily_data(symbols: Optional[List[str]], exchange: str, task_id: str) -> dict:
    """Async helper function for data collection"""
    start_time = datetime.now()
    collected_count = 0
    error_count = 0
    
    try:
        # Initialize market data collector
        collector = MarketDataCollector()
        
        # Start the collector (connects to IBKR)
        if not await collector.start_collection():
            return {
                'success': False,
                'error': 'Failed to connect to IBKR TWS'
            }
        
        # Use all symbols from database if none provided
        if symbols is None:
            watchlist_service = WatchlistService()
            symbol_info_list = await watchlist_service.get_all_symbols_for_daily_collection(exchange)
            symbols = [info.symbol for info in symbol_info_list]
        
        logger.info("Collecting data for symbols", count=len(symbols))
        
        # Collect daily data with rate limiting
        success = await collector.collect_daily_data(symbols)
        
        if success:
            collected_count = len(symbols)
        else:
            error_count = len(symbols)
        
        # Stop the collector
        await collector.stop_collection()
        
        # Log collection statistics to database
        await _log_collection_stats(task_id, collected_count, error_count)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'success': success,
            'collected_count': collected_count,
            'error_count': error_count,
            'duration_seconds': duration,
            'symbols_processed': len(symbols)
        }
        
    except Exception as e:
        logger.error("Error in async data collection", error=str(e))
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(bind=True, name='app.tasks.data_collection.collect_intraday_data')
def collect_intraday_data(self, timeframe: str = "5min", max_symbols: int = None):
    """
    Collect intraday data for symbols from active watchlists
    Runs during market hours only
    
    Args:
        timeframe: Bar timeframe ('5min', '15min', '1hour') 
        max_symbols: Limit number of symbols (None = no limit)
    """
    task_id = self.request.id
    logger.info("Starting intraday data collection", 
               timeframe=timeframe, max_symbols=max_symbols, task_id=task_id)
    
    try:
        result = asyncio.run(_async_collect_intraday_data(timeframe, max_symbols, task_id))
        
        return {
            'status': 'success' if result['success'] else 'failed',
            'timeframe': timeframe,
            **result
        }
        
    except Exception as e:
        logger.error("Intraday data collection failed", 
                    timeframe=timeframe, error=str(e), task_id=task_id)
        raise self.retry(countdown=300, max_retries=2)  # Retry in 5 minutes


@celery_app.task(bind=True, name='app.tasks.data_collection.collect_high_priority_data') 
def collect_high_priority_data(self, timeframe: str = "5min"):
    """
    Collect intraday data for high-priority symbols only
    Faster collection for most important stocks
    """
    task_id = self.request.id
    logger.info("Starting high priority data collection", 
               timeframe=timeframe, task_id=task_id)
    
    try:
        result = asyncio.run(_async_collect_high_priority_data(timeframe, task_id))
        
        return {
            'status': 'success' if result['success'] else 'failed',
            'timeframe': timeframe,
            **result
        }
        
    except Exception as e:
        logger.error("High priority data collection failed", 
                    timeframe=timeframe, error=str(e), task_id=task_id)
        raise self.retry(countdown=180, max_retries=3)  # Retry in 3 minutes


@celery_app.task(bind=True, name='app.tasks.data_collection.validate_daily_data')
def validate_daily_data(self):
    """
    Validate the quality of collected daily data
    Runs 20 minutes after data collection to allow processing time
    """
    task_id = self.request.id
    logger.info("Starting daily data validation", task_id=task_id)
    
    try:
        result = asyncio.run(_async_validate_data(task_id))
        
        if result['issues_found'] > 0:
            logger.warning("Data quality issues detected", 
                          issues=result['issues_found'], 
                          details=result['issues'])
        else:
            logger.info("Data validation passed", 
                       symbols_validated=result['symbols_validated'])
        
        return result
        
    except Exception as e:
        logger.error("Data validation failed", error=str(e), task_id=task_id)
        return {
            'status': 'error',
            'error': str(e)
        }


async def _async_collect_intraday_data(timeframe: str, max_symbols: int, task_id: str) -> dict:
    """Enhanced async helper for intraday data collection using watchlists"""
    start_time = datetime.now()
    collected_count = 0
    error_count = 0
    
    # Initialize rate limiter and watchlist service
    async with IBKRRateLimiter() as rate_limiter:
        try:
            # Get symbols from watchlists that support this timeframe
            watchlist_service = WatchlistService()
            intraday_symbols = await watchlist_service.get_symbols_by_timeframe(timeframe)
            
            if not intraday_symbols:
                return {
                    'success': False,
                    'error': f'No symbols configured for {timeframe} timeframe'
                }
            
            # Limit symbols if requested
            if max_symbols and max_symbols < len(intraday_symbols):
                intraday_symbols = intraday_symbols[:max_symbols]
                logger.info("Limited symbols for collection", 
                           original=len(intraday_symbols), limited_to=max_symbols)
            
            # Initialize market data collector
            collector = MarketDataCollector(rate_limiter=rate_limiter)
            
            if not await collector.start_collection():
                return {
                    'success': False,
                    'error': 'Failed to connect to IBKR TWS'
                }
            
            # Extract just symbols for collection
            symbols = [s.symbol for s in intraday_symbols]
            
            logger.info("Collecting intraday data", 
                       timeframe=timeframe, symbols_count=len(symbols))
            
            # Collect intraday data
            success = await collector.collect_intraday_bars(symbols, timeframe)
            
            if success:
                collected_count = len(symbols)
            else:
                error_count = len(symbols)
            
            await collector.stop_collection()
            
            # Log collection statistics
            await _log_collection_stats(task_id, collected_count, error_count, 
                                       data_type=f"intraday_{timeframe}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': success,
                'collected_count': collected_count,
                'error_count': error_count,
                'duration_seconds': duration,
                'symbols_processed': len(symbols),
                'timeframe': timeframe
            }
            
        except Exception as e:
            logger.error("Error in intraday data collection", 
                        timeframe=timeframe, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }


async def _async_collect_high_priority_data(timeframe: str, task_id: str) -> dict:
    """Async helper for high-priority symbol collection"""
    start_time = datetime.now()
    collected_count = 0
    error_count = 0
    
    async with IBKRRateLimiter() as rate_limiter:
        try:
            # Get high-priority symbols (priority >= 8)
            watchlist_service = WatchlistService()
            high_priority_symbols = await watchlist_service.get_high_priority_symbols(
                min_priority=8, active_only=True
            )
            
            # Filter by timeframe
            filtered_symbols = [
                s for s in high_priority_symbols 
                if timeframe in s.timeframes
            ]
            
            if not filtered_symbols:
                return {
                    'success': False,
                    'error': f'No high-priority symbols support {timeframe} timeframe'
                }
            
            collector = MarketDataCollector(rate_limiter=rate_limiter)
            
            if not await collector.start_collection():
                return {
                    'success': False,
                    'error': 'Failed to connect to IBKR TWS'
                }
            
            symbols = [s.symbol for s in filtered_symbols]
            
            logger.info("Collecting high-priority intraday data", 
                       timeframe=timeframe, symbols_count=len(symbols),
                       min_priority=8)
            
            success = await collector.collect_intraday_bars(symbols, timeframe)
            
            if success:
                collected_count = len(symbols)
            else:
                error_count = len(symbols)
                
            await collector.stop_collection()
            
            await _log_collection_stats(task_id, collected_count, error_count,
                                       data_type=f"high_priority_{timeframe}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': success,
                'collected_count': collected_count,
                'error_count': error_count,
                'duration_seconds': duration,
                'symbols_processed': len(symbols),
                'timeframe': timeframe,
                'priority_filter': 8
            }
            
        except Exception as e:
            logger.error("Error in high-priority data collection", 
                        timeframe=timeframe, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }


async def _async_validate_data(task_id: str) -> dict:
    """Async data validation helper"""
    today = datetime.now().date()
    issues = []
    symbols_validated = 0
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Check if we have data for today
            result = await db_session.execute(
                select(func.count(DailyPrice.id))
                .where(DailyPrice.date == today)
            )
            daily_count = result.scalar()
            
            if daily_count == 0:
                issues.append("No daily price data found for today")
            elif daily_count < 100:  # Expect at least 100 stocks
                issues.append(f"Low daily data count: {daily_count} (expected >100)")
            
            symbols_validated = daily_count
            
            # Check for price anomalies (basic validation)
            result = await db_session.execute(
                select(DailyPrice)
                .where(DailyPrice.date == today)
                .where(
                    (DailyPrice.high < DailyPrice.low) |
                    (DailyPrice.open <= 0) |
                    (DailyPrice.close <= 0) |
                    (DailyPrice.volume < 0)
                )
            )
            
            anomalies = result.fetchall()
            if anomalies:
                issues.append(f"Found {len(anomalies)} price anomalies")
            
            # Check data freshness
            result = await db_session.execute(
                select(func.max(DailyPrice.created_at))
                .where(DailyPrice.date == today)
            )
            latest_created = result.scalar()
            
            if latest_created:
                age_hours = (datetime.now() - latest_created).total_seconds() / 3600
                if age_hours > 2:  # Data older than 2 hours
                    issues.append(f"Data appears stale: {age_hours:.1f} hours old")
            
            await db_session.commit()
            
        except Exception as e:
            logger.error("Database validation error", error=str(e))
            issues.append(f"Database validation error: {str(e)}")
    
    return {
        'status': 'completed',
        'symbols_validated': symbols_validated,
        'issues_found': len(issues),
        'issues': issues,
        'task_id': task_id
    }


async def _log_collection_stats(task_id: str, collected: int, errors: int, 
                               data_type: str = "daily"):
    """Log collection statistics to database"""
    async with AsyncSessionLocal() as db_session:
        try:
            api_request = ApiRequest(
                request_type=f'DATA_COLLECTION_{data_type.upper()}',
                req_id=hash(task_id) % 10000,  # Convert task_id to int
                timestamp=datetime.now(),
                status='SUCCESS' if errors == 0 else 'PARTIAL_SUCCESS',
                client_id=settings.ibkr_client_id,
                response_time_ms=0  # Will be updated with actual time
            )
            
            db_session.add(api_request)
            await db_session.commit()
            
            logger.debug("Collection stats logged", 
                        collected=collected, errors=errors, data_type=data_type)
                        
        except Exception as e:
            logger.error("Failed to log collection stats", error=str(e))


@celery_app.task(bind=True, name='app.tasks.data_collection.test_ibkr_connection')
def test_ibkr_connection(self):
    """Test IBKR connection as a Celery task"""
    task_id = self.request.id
    logger.info("Testing IBKR connection", task_id=task_id)
    
    try:
        result = asyncio.run(_async_test_connection())
        return result
        
    except Exception as e:
        logger.error("IBKR connection test failed", error=str(e), task_id=task_id)
        return {
            'status': 'failed',
            'error': str(e)
        }


async def _async_test_connection() -> dict:
    """Async connection test helper"""
    try:
        collector = MarketDataCollector()
        
        # Test connection
        connected = await collector.start_collection()
        
        if connected:
            # Get connection status
            status = collector.ibkr_client.get_connection_status()
            await collector.stop_collection()
            
            return {
                'status': 'success',
                'connected': True,
                'connection_details': status
            }
        else:
            return {
                'status': 'failed',
                'connected': False,
                'error': 'Failed to connect to IBKR TWS'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'connected': False,
            'error': str(e)
        }


@celery_app.task(bind=True, name='app.tasks.data_collection.backfill_historical_data')
def backfill_historical_data(self, symbol: str, start_date: str, end_date: str, skip_existing: bool = True):
    """
    Celery task to backfill historical data for a specific symbol
    
    Args:
        symbol: Stock symbol to backfill
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        skip_existing: Whether to skip dates that already have data
    """
    task_id = self.request.id
    logger.info("Starting historical data backfill", 
               symbol=symbol, start_date=start_date, end_date=end_date, task_id=task_id)
    
    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Run the async backfill
        result = asyncio.run(_async_backfill_symbol(symbol, start_dt, end_dt, skip_existing, task_id))
        
        if result['success']:
            logger.info("Historical data backfill completed successfully", 
                       symbol=symbol, bars_stored=result['bars_stored'], task_id=task_id)
            return {
                'status': 'success',
                'symbol': symbol,
                **result
            }
        else:
            logger.error("Historical data backfill failed", 
                        symbol=symbol, error=result.get('error'), task_id=task_id)
            return {
                'status': 'failed',
                'symbol': symbol,
                'error': result.get('error', 'Unknown error')
            }
            
    except ValueError as e:
        error_msg = f"Invalid date format: {str(e)}"
        logger.error("Backfill task failed", error=error_msg, task_id=task_id)
        return {
            'status': 'failed',
            'error': error_msg
        }
    except Exception as e:
        logger.error("Unexpected error in backfill task", 
                    error=str(e), task_id=task_id)
        raise self.retry(countdown=300, max_retries=2)  # Retry in 5 minutes


async def _async_backfill_symbol(symbol: str, start_date: datetime, end_date: datetime, 
                                skip_existing: bool, task_id: str) -> dict:
    """Async helper function for symbol backfill"""
    try:
        # Initialize market data collector
        collector = MarketDataCollector()
        
        # Start the collector (connects to IBKR)
        if not await collector.start_collection():
            return {
                'success': False,
                'error': 'Failed to connect to IBKR TWS'
            }
        
        logger.info("Starting backfill for symbol", symbol=symbol, 
                   start_date=start_date.strftime('%Y-%m-%d'), 
                   end_date=end_date.strftime('%Y-%m-%d'))
        
        # Update task progress
        if hasattr(current_task, 'update_state'):
            current_task.update_state(
                state='PROGRESS',
                meta={'current': 0, 'total': 100, 'status': f'Starting backfill for {symbol}'}
            )
        
        # Perform backfill
        backfill_stats = await collector.backfill_historical_data(
            symbol, start_date, end_date, skip_existing
        )
        
        # Update task progress
        if hasattr(current_task, 'update_state'):
            current_task.update_state(
                state='PROGRESS', 
                meta={'current': 100, 'total': 100, 'status': f'Completed backfill for {symbol}'}
            )
        
        # Stop the collector
        await collector.stop_collection()
        
        # Log backfill statistics to database
        await _log_backfill_stats(task_id, symbol, backfill_stats)
        
        return {
            'success': backfill_stats.get('bars_stored', 0) > 0 or backfill_stats.get('error') is None,
            **backfill_stats
        }
        
    except Exception as e:
        logger.error("Error in async backfill", symbol=symbol, error=str(e))
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(bind=True, name='app.tasks.data_collection.batch_backfill_historical_data')
def batch_backfill_historical_data(self, symbols: List[str], start_date: str, end_date: str, skip_existing: bool = True):
    """
    Celery task to backfill historical data for multiple symbols
    
    Args:
        symbols: List of stock symbols to backfill
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        skip_existing: Whether to skip dates that already have data
    """
    task_id = self.request.id
    logger.info("Starting batch historical data backfill", 
               symbols_count=len(symbols), start_date=start_date, end_date=end_date, task_id=task_id)
    
    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Run the async batch backfill
        result = asyncio.run(_async_batch_backfill(symbols, start_dt, end_dt, skip_existing, task_id))
        
        logger.info("Batch historical data backfill completed", 
                   successful=result['successful_symbols'], 
                   failed=result['failed_symbols'], 
                   task_id=task_id)
        
        return {
            'status': 'completed',
            'symbols_requested': len(symbols),
            **result
        }
        
    except ValueError as e:
        error_msg = f"Invalid date format: {str(e)}"
        logger.error("Batch backfill task failed", error=error_msg, task_id=task_id)
        return {
            'status': 'failed',
            'error': error_msg
        }
    except Exception as e:
        logger.error("Unexpected error in batch backfill task", 
                    error=str(e), task_id=task_id)
        raise self.retry(countdown=600, max_retries=2)  # Retry in 10 minutes


async def _async_batch_backfill(symbols: List[str], start_date: datetime, end_date: datetime, 
                               skip_existing: bool, task_id: str) -> dict:
    """Async helper function for batch backfill"""
    successful_symbols = []
    failed_symbols = []
    total_bars_stored = 0
    
    try:
        # Initialize market data collector once for all symbols
        collector = MarketDataCollector()
        
        # Start the collector (connects to IBKR)
        if not await collector.start_collection():
            return {
                'successful_symbols': 0,
                'failed_symbols': len(symbols),
                'total_bars_stored': 0,
                'error': 'Failed to connect to IBKR TWS'
            }
        
        # Process each symbol
        for i, symbol in enumerate(symbols):
            try:
                # Update task progress
                if hasattr(current_task, 'update_state'):
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i + 1, 
                            'total': len(symbols), 
                            'status': f'Processing {symbol} ({i+1}/{len(symbols)})'
                        }
                    )
                
                logger.info("Processing symbol in batch", symbol=symbol, progress=f"{i+1}/{len(symbols)}")
                
                # Perform backfill for this symbol
                backfill_stats = await collector.backfill_historical_data(
                    symbol, start_date, end_date, skip_existing
                )
                
                if backfill_stats.get('bars_stored', 0) > 0 or backfill_stats.get('error') is None:
                    successful_symbols.append(symbol)
                    total_bars_stored += backfill_stats.get('bars_stored', 0)
                    logger.info("Symbol backfill successful", symbol=symbol, bars=backfill_stats.get('bars_stored', 0))
                else:
                    failed_symbols.append({
                        'symbol': symbol,
                        'error': backfill_stats.get('error', 'Unknown error')
                    })
                    logger.warning("Symbol backfill failed", symbol=symbol, error=backfill_stats.get('error'))
                
                # Rate limiting between symbols
                if i < len(symbols) - 1:
                    await asyncio.sleep(5)  # 5 second delay between symbols
                    
            except Exception as e:
                failed_symbols.append({
                    'symbol': symbol,
                    'error': str(e)
                })
                logger.error("Error processing symbol in batch", symbol=symbol, error=str(e))
        
        # Stop the collector
        await collector.stop_collection()
        
        return {
            'successful_symbols': len(successful_symbols),
            'failed_symbols': len(failed_symbols),
            'total_bars_stored': total_bars_stored,
            'successful_symbol_list': successful_symbols,
            'failed_symbol_details': failed_symbols
        }
        
    except Exception as e:
        logger.error("Error in async batch backfill", error=str(e))
        return {
            'successful_symbols': len(successful_symbols),
            'failed_symbols': len(symbols) - len(successful_symbols),
            'total_bars_stored': total_bars_stored,
            'error': str(e)
        }


async def _log_backfill_stats(task_id: str, symbol: str, backfill_stats: dict):
    """Log backfill statistics to database"""
    async with AsyncSessionLocal() as db_session:
        try:
            api_request = ApiRequest(
                request_type='HISTORICAL_BACKFILL',
                req_id=hash(task_id) % 10000,  # Convert task_id to int
                symbol=symbol,
                timestamp=datetime.now(),
                status='SUCCESS' if backfill_stats.get('bars_stored', 0) > 0 else 'FAILED',
                client_id=settings.ibkr_client_id,
                response_time_ms=int(backfill_stats.get('duration_seconds', 0) * 1000)
            )
            
            db_session.add(api_request)
            await db_session.commit()
            
            logger.debug("Backfill stats logged", 
                        symbol=symbol, bars_stored=backfill_stats.get('bars_stored', 0))
                        
        except Exception as e:
            logger.error("Failed to log backfill stats", symbol=symbol, error=str(e))


@celery_app.task(bind=True, name='app.tasks.data_collection.validate_symbol_data')
def validate_symbol_data(self, symbol: str, days_lookback: int = 30):
    """
    Celery task to validate data quality for a specific symbol
    
    Args:
        symbol: Stock symbol to validate
        days_lookback: Number of days to look back for validation
    """
    task_id = self.request.id
    logger.info("Starting data validation", symbol=symbol, days_lookback=days_lookback, task_id=task_id)
    
    try:
        # Run the async validation
        result = asyncio.run(_async_validate_symbol(symbol, days_lookback, task_id))
        
        if result['success']:
            logger.info("Data validation completed successfully", 
                       symbol=symbol, quality_score=result['quality_score'], 
                       issues_found=result['issues_found'], task_id=task_id)
            return {
                'status': 'success',
                'symbol': symbol,
                **result
            }
        else:
            logger.error("Data validation failed", 
                        symbol=symbol, error=result.get('error'), task_id=task_id)
            return {
                'status': 'failed',
                'symbol': symbol,
                'error': result.get('error', 'Unknown error')
            }
            
    except Exception as e:
        logger.error("Unexpected error in validation task", 
                    error=str(e), task_id=task_id)
        return {
            'status': 'failed',
            'error': str(e)
        }


async def _async_validate_symbol(symbol: str, days_lookback: int, task_id: str) -> dict:
    """Async helper function for symbol validation"""
    try:
        from app.data.processors.validation import DataValidator
        
        validator = DataValidator()
        
        # Update task progress
        if hasattr(current_task, 'update_state'):
            current_task.update_state(
                state='PROGRESS',
                meta={'current': 25, 'total': 100, 'status': f'Starting validation for {symbol}'}
            )
        
        async with AsyncSessionLocal() as db_session:
            # Perform validation
            validation_report = await validator.validate_symbol_data(symbol, db_session, days_lookback)
            
            # Update task progress
            if hasattr(current_task, 'update_state'):
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': 75, 'total': 100, 'status': f'Analyzing results for {symbol}'}
                )
            
            # Log validation statistics
            await _log_validation_stats(task_id, symbol, validation_report)
            
            # Update task progress
            if hasattr(current_task, 'update_state'):
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': 100, 'total': 100, 'status': f'Validation completed for {symbol}'}
                )
            
            return {
                'success': True,
                'quality_score': validation_report.quality_score,
                'data_completeness': validation_report.data_completeness,
                'issues_found': len(validation_report.issues),
                'anomaly_count': validation_report.anomaly_count,
                'gap_count': validation_report.gap_count,
                'critical_issues': len([i for i in validation_report.issues if i.severity.value == 'critical']),
                'summary': validation_report.summary,
                'validation_report': {
                    'total_records': validation_report.total_records,
                    'validation_date': validation_report.validation_date.isoformat(),
                    'issues_by_severity': {
                        'critical': len([i for i in validation_report.issues if i.severity.value == 'critical']),
                        'error': len([i for i in validation_report.issues if i.severity.value == 'error']),
                        'warning': len([i for i in validation_report.issues if i.severity.value == 'warning']),
                        'info': len([i for i in validation_report.issues if i.severity.value == 'info'])
                    }
                }
            }
        
    except Exception as e:
        logger.error("Error in async validation", symbol=symbol, error=str(e))
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(bind=True, name='app.tasks.data_collection.validate_batch_data')
def validate_batch_data(self, symbols: List[str] = None, days_lookback: int = 30):
    """
    Celery task to validate data quality for multiple symbols
    
    Args:
        symbols: List of symbols to validate (None for all available)
        days_lookback: Number of days to look back for validation
    """
    task_id = self.request.id
    symbols_count = len(symbols) if symbols else "all available"
    logger.info("Starting batch data validation", 
               symbols_count=symbols_count, days_lookback=days_lookback, task_id=task_id)
    
    try:
        # Run the async batch validation
        result = asyncio.run(_async_validate_batch(symbols, days_lookback, task_id))
        
        logger.info("Batch data validation completed", 
                   validated_symbols=result['validated_symbols'], 
                   avg_quality_score=result.get('avg_quality_score', 0), 
                   task_id=task_id)
        
        return {
            'status': 'completed',
            'symbols_requested': len(symbols) if symbols else result.get('total_symbols', 0),
            **result
        }
        
    except Exception as e:
        logger.error("Unexpected error in batch validation task", 
                    error=str(e), task_id=task_id)
        return {
            'status': 'failed',
            'error': str(e)
        }


async def _async_validate_batch(symbols: List[str], days_lookback: int, task_id: str) -> dict:
    """Async helper function for batch validation"""
    try:
        from app.data.processors.validation import BatchDataValidator
        
        batch_validator = BatchDataValidator()
        
        async with AsyncSessionLocal() as db_session:
            # Update task progress
            if hasattr(current_task, 'update_state'):
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': 10, 'total': 100, 'status': 'Starting batch validation'}
                )
            
            # Perform batch validation
            validation_reports = await batch_validator.validate_batch(
                db_session, symbols, days_lookback
            )
            
            # Update task progress
            if hasattr(current_task, 'update_state'):
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': 80, 'total': 100, 'status': 'Generating batch summary'}
                )
            
            # Generate batch summary
            batch_summary = batch_validator.generate_batch_summary(validation_reports)
            
            # Log batch validation statistics
            await _log_batch_validation_stats(task_id, validation_reports)
            
            # Update task progress
            if hasattr(current_task, 'update_state'):
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': 100, 'total': 100, 'status': 'Batch validation completed'}
                )
            
            # Calculate summary statistics
            total_symbols = len(validation_reports)
            avg_quality_score = sum(r.quality_score for r in validation_reports.values()) / total_symbols if total_symbols > 0 else 0
            total_issues = sum(len(r.issues) for r in validation_reports.values())
            symbols_with_critical = len([r for r in validation_reports.values() 
                                       if any(i.severity.value == 'critical' for i in r.issues)])
            
            return {
                'validated_symbols': total_symbols,
                'avg_quality_score': round(avg_quality_score, 1),
                'total_issues_found': total_issues,
                'symbols_with_critical_issues': symbols_with_critical,
                'batch_summary': batch_summary,
                'symbol_reports': {
                    symbol: {
                        'quality_score': report.quality_score,
                        'data_completeness': report.data_completeness,
                        'issues_count': len(report.issues),
                        'critical_issues': len([i for i in report.issues if i.severity.value == 'critical']),
                        'summary_status': report.summary.get('data_integrity', 'unknown')
                    }
                    for symbol, report in validation_reports.items()
                }
            }
        
    except Exception as e:
        logger.error("Error in async batch validation", error=str(e))
        return {
            'validated_symbols': 0,
            'error': str(e)
        }


async def _log_validation_stats(task_id: str, symbol: str, validation_report):
    """Log validation statistics to database"""
    async with AsyncSessionLocal() as db_session:
        try:
            api_request = ApiRequest(
                request_type='DATA_VALIDATION',
                req_id=hash(task_id) % 10000,
                symbol=symbol,
                timestamp=datetime.now(),
                status='SUCCESS' if validation_report.quality_score >= 70 else 'WARNING',
                client_id=settings.ibkr_client_id,
                response_time_ms=0
            )
            
            db_session.add(api_request)
            await db_session.commit()
            
            logger.debug("Validation stats logged", 
                        symbol=symbol, quality_score=validation_report.quality_score)
                        
        except Exception as e:
            logger.error("Failed to log validation stats", symbol=symbol, error=str(e))


async def _log_batch_validation_stats(task_id: str, validation_reports: dict):
    """Log batch validation statistics to database"""
    async with AsyncSessionLocal() as db_session:
        try:
            total_symbols = len(validation_reports)
            avg_quality = sum(r.quality_score for r in validation_reports.values()) / total_symbols if total_symbols > 0 else 0
            
            api_request = ApiRequest(
                request_type='BATCH_VALIDATION',
                req_id=hash(task_id) % 10000,
                timestamp=datetime.now(),
                status='SUCCESS' if avg_quality >= 70 else 'WARNING',
                client_id=settings.ibkr_client_id,
                response_time_ms=0
            )
            
            db_session.add(api_request)
            await db_session.commit()
            
            logger.debug("Batch validation stats logged", 
                        symbols_count=total_symbols, avg_quality_score=avg_quality)
                        
        except Exception as e:
            logger.error("Failed to log batch validation stats", error=str(e))