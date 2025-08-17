import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from celery import current_task

from app.tasks.celery_app import celery_app
from app.data.collectors.market_data import MarketDataCollector
from app.data.collectors.asx_contracts import get_asx200_symbols, get_liquid_stocks
from app.data.models.market import DailyPrice, ApiRequest
from app.config.database import AsyncSessionLocal
from app.config.settings import settings

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name='app.tasks.data_collection.collect_daily_asx_data')
def collect_daily_asx_data(self, symbols: Optional[List[str]] = None):
    """
    Celery task to collect daily ASX200 market data
    Runs daily at 4:10 PM ASX time (post-market close)
    """
    task_id = self.request.id
    logger.info("Starting daily ASX data collection", task_id=task_id)
    
    try:
        # Run the async data collection
        result = asyncio.run(_async_collect_daily_data(symbols, task_id))
        
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


async def _async_collect_daily_data(symbols: Optional[List[str]], task_id: str) -> dict:
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
        
        # Use default ASX200 symbols if none provided
        if symbols is None:
            symbols = get_asx200_symbols()
        
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


@celery_app.task(bind=True, name='app.tasks.data_collection.collect_sample_data')
def collect_sample_data(self, max_symbols: int = 10):
    """
    Collect sample data for testing/development
    Uses most liquid ASX stocks for faster testing
    """
    task_id = self.request.id
    logger.info("Starting sample data collection", 
               max_symbols=max_symbols, task_id=task_id)
    
    try:
        symbols = get_liquid_stocks(max_symbols)
        result = asyncio.run(_async_collect_daily_data(symbols, task_id))
        
        return {
            'status': 'success' if result['success'] else 'failed',
            'symbols': symbols,
            **result
        }
        
    except Exception as e:
        logger.error("Sample data collection failed", error=str(e), task_id=task_id)
        raise self.retry(countdown=60, max_retries=2)  # Retry in 1 minute


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
            elif daily_count < 100:  # Expect at least 100 ASX200 stocks
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


async def _log_collection_stats(task_id: str, collected: int, errors: int):
    """Log collection statistics to database"""
    async with AsyncSessionLocal() as db_session:
        try:
            api_request = ApiRequest(
                request_type='DATA_COLLECTION',
                req_id=hash(task_id) % 10000,  # Convert task_id to int
                timestamp=datetime.now(),
                status='SUCCESS' if errors == 0 else 'PARTIAL_SUCCESS',
                client_id=settings.ibkr_client_id,
                response_time_ms=0  # Will be updated with actual time
            )
            
            db_session.add(api_request)
            await db_session.commit()
            
            logger.debug("Collection stats logged", 
                        collected=collected, errors=errors)
                        
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