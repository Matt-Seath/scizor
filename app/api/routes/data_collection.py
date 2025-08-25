from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import List, Optional
import structlog

from app.config.database import get_async_db
from app.data.models.market import DailyPrice, ApiRequest
from app.data.services.watchlist_service import WatchlistService
from app.tasks.data_collection import (
    collect_daily_asx_data, 
    collect_sample_data,
    test_ibkr_connection,
    backfill_historical_data,
    batch_backfill_historical_data,
    validate_symbol_data,
    validate_batch_data
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/trigger/daily")
async def trigger_daily_collection(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None
):
    """Manually trigger daily ASX200 data collection"""
    try:
        # Submit task to Celery
        task = collect_daily_asx_data.delay(symbols)
        
        logger.info("Daily collection task triggered", task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "message": "Daily data collection task has been queued",
            "symbols_count": len(symbols) if symbols else len(get_asx200_symbols())
        }
        
    except Exception as e:
        logger.error("Failed to trigger daily collection", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger collection: {str(e)}"
        )


@router.post("/trigger/sample")
async def trigger_sample_collection(
    background_tasks: BackgroundTasks,
    max_symbols: int = 10
):
    """Trigger sample data collection for testing"""
    try:
        if max_symbols > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 symbols allowed for sample collection"
            )
        
        task = collect_sample_data.delay(max_symbols)
        
        logger.info("Sample collection task triggered", 
                   task_id=task.id, max_symbols=max_symbols)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "message": f"Sample data collection for {max_symbols} symbols queued",
            "symbols": get_liquid_stocks(max_symbols)
        }
        
    except Exception as e:
        logger.error("Failed to trigger sample collection", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger sample collection: {str(e)}"
        )


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a data collection task"""
    try:
        from app.tasks.celery_app import celery_app
        
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'task_id': task_id,
                'state': task.state,
                'status': 'Task is waiting to be processed'
            }
        elif task.state == 'PROGRESS':
            response = {
                'task_id': task_id,
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'status': task.info.get('status', '')
            }
        elif task.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'state': task.state,
                'result': task.result
            }
        else:  # FAILURE
            response = {
                'task_id': task_id,
                'state': task.state,
                'error': str(task.info)
            }
        
        return response
        
    except Exception as e:
        logger.error("Failed to get task status", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/history")
async def get_collection_history(
    days: int = 7,
    db: AsyncSession = Depends(get_async_db)
):
    """Get data collection history for the past N days"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get daily data counts
        result = await db.execute(
            select(
                DailyPrice.date,
                func.count(DailyPrice.id).label('count')
            )
            .where(DailyPrice.created_at >= cutoff_date)
            .group_by(DailyPrice.date)
            .order_by(desc(DailyPrice.date))
        )
        
        daily_counts = [
            {
                "date": row.date.isoformat(),
                "symbols_collected": row.count
            }
            for row in result
        ]
        
        # Get API request statistics
        result = await db.execute(
            select(
                func.date(ApiRequest.timestamp).label('date'),
                ApiRequest.status,
                func.count(ApiRequest.id).label('count')
            )
            .where(ApiRequest.timestamp >= cutoff_date)
            .where(ApiRequest.request_type == 'DATA_COLLECTION')
            .group_by(func.date(ApiRequest.timestamp), ApiRequest.status)
            .order_by(desc(func.date(ApiRequest.timestamp)))
        )
        
        api_stats = {}
        for row in result:
            date_str = row.date.isoformat()
            if date_str not in api_stats:
                api_stats[date_str] = {}
            api_stats[date_str][row.status] = row.count
        
        return {
            "period_days": days,
            "daily_collection_counts": daily_counts,
            "api_request_stats": api_stats,
            "summary": {
                "total_data_points": sum(item["symbols_collected"] for item in daily_counts),
                "trading_days_covered": len(daily_counts),
                "avg_symbols_per_day": round(
                    sum(item["symbols_collected"] for item in daily_counts) / max(len(daily_counts), 1), 1
                )
            }
        }
        
    except Exception as e:
        logger.error("Failed to get collection history", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get collection history: {str(e)}"
        )


@router.get("/latest/{symbol}")
async def get_latest_price(
    symbol: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get latest price data for a specific symbol"""
    try:
        symbol = symbol.upper()
        
        result = await db.execute(
            select(DailyPrice)
            .where(DailyPrice.symbol == symbol)
            .order_by(desc(DailyPrice.date))
            .limit(1)
        )
        
        latest_price = result.scalar_one_or_none()
        
        if not latest_price:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for symbol {symbol}"
            )
        
        return {
            "symbol": latest_price.symbol,
            "date": latest_price.date.isoformat(),
            "open": float(latest_price.open),
            "high": float(latest_price.high),
            "low": float(latest_price.low),
            "close": float(latest_price.close),
            "volume": latest_price.volume,
            "adj_close": float(latest_price.adj_close) if latest_price.adj_close else None,
            "created_at": latest_price.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get latest price", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest price: {str(e)}"
        )


@router.get("/symbols")
async def get_available_symbols():
    """Get list of available ASX200 symbols"""
    try:
        return {
            "asx200_symbols": get_asx200_symbols(),
            "liquid_stocks_20": get_liquid_stocks(20),
            "total_symbols": len(get_asx200_symbols())
        }
        
    except Exception as e:
        logger.error("Failed to get symbols", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get symbols: {str(e)}"
        )


@router.post("/test/connection")
async def test_connection():
    """Test IBKR connection"""
    try:
        task = test_ibkr_connection.delay()
        
        logger.info("IBKR connection test triggered", task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "message": "IBKR connection test has been queued"
        }
        
    except Exception as e:
        logger.error("Failed to trigger connection test", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger connection test: {str(e)}"
        )


@router.post("/backfill/{symbol}")
async def trigger_symbol_backfill(
    symbol: str,
    start_date: str,
    end_date: str,
    skip_existing: bool = True
):
    """
    Trigger historical data backfill for a specific symbol
    
    Args:
        symbol: Stock symbol (e.g., 'BHP', 'CBA')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format  
        skip_existing: Whether to skip dates that already have data (default: True)
    """
    try:
        # Validate symbol format
        symbol = symbol.upper().strip()
        if not symbol or len(symbol) > 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid symbol format"
            )
        
        # Validate date formats
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD format"
            )
        
        # Check date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before end date"
            )
        
        if end_dt > datetime.now():
            raise HTTPException(
                status_code=400,
                detail="End date cannot be in the future"
            )
        
        # Limit backfill range to prevent excessive API usage
        max_days = 365 * 5  # 5 years maximum
        if (end_dt - start_dt).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large. Maximum {max_days} days allowed"
            )
        
        # Submit backfill task
        task = backfill_historical_data.delay(symbol, start_date, end_date, skip_existing)
        
        logger.info("Symbol backfill task triggered", 
                   symbol=symbol, start_date=start_date, end_date=end_date, task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "skip_existing": skip_existing,
            "message": f"Historical data backfill for {symbol} has been queued",
            "estimated_days": (end_dt - start_dt).days + 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger symbol backfill", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger backfill: {str(e)}"
        )


@router.post("/backfill/batch")
async def trigger_batch_backfill(
    symbols: List[str],
    start_date: str,
    end_date: str,
    skip_existing: bool = True
):
    """
    Trigger historical data backfill for multiple symbols
    
    Args:
        symbols: List of stock symbols (e.g., ['BHP', 'CBA', 'ANZ'])
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        skip_existing: Whether to skip dates that already have data (default: True)
    """
    try:
        # Validate symbols
        if not symbols or len(symbols) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one symbol must be provided"
            )
        
        if len(symbols) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 symbols allowed per batch request"
            )
        
        # Clean and validate symbols
        clean_symbols = []
        for symbol in symbols:
            symbol = symbol.upper().strip()
            if not symbol or len(symbol) > 10:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid symbol format: {symbol}"
                )
            clean_symbols.append(symbol)
        
        # Validate date formats
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD format"
            )
        
        # Check date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before end date"
            )
        
        if end_dt > datetime.now():
            raise HTTPException(
                status_code=400,
                detail="End date cannot be in the future"
            )
        
        # Limit backfill range
        max_days = 365 * 2  # 2 years maximum for batch
        if (end_dt - start_dt).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large for batch. Maximum {max_days} days allowed"
            )
        
        # Submit batch backfill task
        task = batch_backfill_historical_data.delay(clean_symbols, start_date, end_date, skip_existing)
        
        logger.info("Batch backfill task triggered", 
                   symbols_count=len(clean_symbols), start_date=start_date, end_date=end_date, task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "symbols": clean_symbols,
            "symbols_count": len(clean_symbols),
            "start_date": start_date,
            "end_date": end_date,
            "skip_existing": skip_existing,
            "message": f"Batch backfill for {len(clean_symbols)} symbols has been queued",
            "estimated_days_per_symbol": (end_dt - start_dt).days + 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger batch backfill", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger batch backfill: {str(e)}"
        )


@router.get("/history/{symbol}")
async def get_symbol_history(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get historical price data for a specific symbol
    
    Args:
        symbol: Stock symbol (e.g., 'BHP', 'CBA')
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (max 1000)
    """
    try:
        symbol = symbol.upper().strip()
        
        # Validate limit
        if limit <= 0 or limit > 1000:
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 1000"
            )
        
        # Build query
        query = select(DailyPrice).where(DailyPrice.symbol == symbol)
        
        # Add date filters if provided
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.where(DailyPrice.date >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.where(DailyPrice.date <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Order by date descending and apply limit
        query = query.order_by(desc(DailyPrice.date)).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        historical_data = result.scalars().all()
        
        if not historical_data:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for symbol {symbol}"
            )
        
        # Format response
        data_points = []
        for price_data in historical_data:
            data_points.append({
                "date": price_data.date.isoformat(),
                "open": float(price_data.open),
                "high": float(price_data.high),
                "low": float(price_data.low),
                "close": float(price_data.close),
                "volume": price_data.volume,
                "adj_close": float(price_data.adj_close) if price_data.adj_close else None,
                "created_at": price_data.created_at.isoformat()
            })
        
        # Get summary statistics
        first_date = historical_data[-1].date if historical_data else None
        last_date = historical_data[0].date if historical_data else None
        
        return {
            "symbol": symbol,
            "data_points": data_points,
            "summary": {
                "total_records": len(data_points),
                "date_range": {
                    "start": first_date.isoformat() if first_date else None,
                    "end": last_date.isoformat() if last_date else None
                },
                "latest_price": {
                    "date": last_date.isoformat() if last_date else None,
                    "close": float(historical_data[0].close) if historical_data else None
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get symbol history", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get symbol history: {str(e)}"
        )


@router.get("/coverage/{symbol}")
async def get_symbol_data_coverage(
    symbol: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get data coverage statistics for a specific symbol
    
    Args:
        symbol: Stock symbol (e.g., 'BHP', 'CBA')
    """
    try:
        symbol = symbol.upper().strip()
        
        # Get data coverage statistics
        result = await db.execute(
            select(
                func.min(DailyPrice.date).label('first_date'),
                func.max(DailyPrice.date).label('last_date'),
                func.count(DailyPrice.id).label('total_records')
            ).where(DailyPrice.symbol == symbol)
        )
        
        coverage_stats = result.first()
        
        if not coverage_stats or coverage_stats.total_records == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {symbol}"
            )
        
        # Calculate expected trading days (rough estimate excluding weekends)
        first_date = coverage_stats.first_date
        last_date = coverage_stats.last_date
        total_days = (last_date - first_date).days + 1
        estimated_trading_days = total_days * 5 / 7  # Rough estimate excluding weekends
        coverage_percentage = (coverage_stats.total_records / estimated_trading_days) * 100 if estimated_trading_days > 0 else 0
        
        # Get recent data quality
        recent_cutoff = datetime.now().date() - timedelta(days=30)
        result = await db.execute(
            select(func.count(DailyPrice.id))
            .where(DailyPrice.symbol == symbol)
            .where(DailyPrice.date >= recent_cutoff)
        )
        recent_records = result.scalar()
        
        # Estimate expected recent records (30 days * 5/7 for weekdays)
        expected_recent = 30 * 5 / 7
        recent_coverage = (recent_records / expected_recent) * 100 if expected_recent > 0 else 0
        
        return {
            "symbol": symbol,
            "coverage": {
                "first_date": first_date.isoformat(),
                "last_date": last_date.isoformat(),
                "total_records": coverage_stats.total_records,
                "estimated_coverage_percentage": round(coverage_percentage, 1),
                "data_span_days": total_days
            },
            "recent_quality": {
                "recent_30_days_records": recent_records,
                "estimated_recent_coverage_percentage": round(recent_coverage, 1)
            },
            "gaps_analysis": {
                "note": "Use GET /api/data/gaps/{symbol} for detailed gap analysis"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get symbol coverage", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get symbol coverage: {str(e)}"
        )


@router.post("/validate/{symbol}")
async def trigger_symbol_validation(
    symbol: str,
    days_lookback: int = 30
):
    """
    Trigger data quality validation for a specific symbol
    
    Args:
        symbol: Stock symbol (e.g., 'BHP', 'CBA')
        days_lookback: Number of days to look back for validation (default: 30, max: 365)
    """
    try:
        # Validate symbol format
        symbol = symbol.upper().strip()
        if not symbol or len(symbol) > 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid symbol format"
            )
        
        # Validate days_lookback parameter
        if days_lookback <= 0 or days_lookback > 365:
            raise HTTPException(
                status_code=400,
                detail="days_lookback must be between 1 and 365"
            )
        
        # Submit validation task
        task = validate_symbol_data.delay(symbol, days_lookback)
        
        logger.info("Symbol validation task triggered", 
                   symbol=symbol, days_lookback=days_lookback, task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "symbol": symbol,
            "days_lookback": days_lookback,
            "message": f"Data validation for {symbol} has been queued",
            "validation_scope": f"Last {days_lookback} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger symbol validation", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger validation: {str(e)}"
        )


@router.post("/validate/batch")
async def trigger_batch_validation(
    symbols: Optional[List[str]] = None,
    days_lookback: int = 30
):
    """
    Trigger data quality validation for multiple symbols
    
    Args:
        symbols: List of symbols to validate (None for all available symbols)
        days_lookback: Number of days to look back for validation (default: 30, max: 90)
    """
    try:
        # Validate days_lookback parameter (more restrictive for batch)
        if days_lookback <= 0 or days_lookback > 90:
            raise HTTPException(
                status_code=400,
                detail="days_lookback must be between 1 and 90 for batch validation"
            )
        
        # Validate symbols if provided
        if symbols is not None:
            if len(symbols) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="At least one symbol must be provided"
                )
            
            if len(symbols) > 100:
                raise HTTPException(
                    status_code=400,
                    detail="Maximum 100 symbols allowed per batch validation"
                )
            
            # Clean and validate symbols
            clean_symbols = []
            for symbol in symbols:
                symbol = symbol.upper().strip()
                if not symbol or len(symbol) > 10:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid symbol format: {symbol}"
                    )
                clean_symbols.append(symbol)
            symbols = clean_symbols
        
        # Submit batch validation task
        task = validate_batch_data.delay(symbols, days_lookback)
        
        logger.info("Batch validation task triggered", 
                   symbols_count=len(symbols) if symbols else "all available",
                   days_lookback=days_lookback, task_id=task.id)
        
        return {
            "status": "triggered",
            "task_id": task.id,
            "symbols": symbols,
            "symbols_count": len(symbols) if symbols else "all_available",
            "days_lookback": days_lookback,
            "message": f"Batch validation for {len(symbols) if symbols else 'all available'} symbols has been queued",
            "validation_scope": f"Last {days_lookback} days per symbol"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger batch validation", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger batch validation: {str(e)}"
        )


@router.get("/validate/report/{symbol}")
async def get_validation_report(
    symbol: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the latest validation report for a symbol (synchronous)
    
    Args:
        symbol: Stock symbol (e.g., 'BHP', 'CBA')
    """
    try:
        from app.data.processors.validation import ASXDataValidator
        
        symbol = symbol.upper().strip()
        
        validator = ASXDataValidator()
        validation_report = await validator.validate_symbol_data(symbol, db, days_lookback=30)
        
        # Convert ValidationIssue objects to dictionaries for JSON serialization
        issues_dict = []
        for issue in validation_report.issues:
            issues_dict.append({
                "symbol": issue.symbol,
                "date": issue.date.isoformat() if issue.date else None,
                "severity": issue.severity.value,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "current_value": issue.current_value,
                "expected_value": issue.expected_value,
                "metadata": issue.metadata
            })
        
        return {
            "symbol": validation_report.symbol,
            "total_records": validation_report.total_records,
            "validation_date": validation_report.validation_date.isoformat(),
            "quality_score": validation_report.quality_score,
            "data_completeness": validation_report.data_completeness,
            "anomaly_count": validation_report.anomaly_count,
            "gap_count": validation_report.gap_count,
            "summary": validation_report.summary,
            "issues": issues_dict,
            "issues_by_severity": {
                "critical": len([i for i in validation_report.issues if i.severity.value == 'critical']),
                "error": len([i for i in validation_report.issues if i.severity.value == 'error']),
                "warning": len([i for i in validation_report.issues if i.severity.value == 'warning']),
                "info": len([i for i in validation_report.issues if i.severity.value == 'info'])
            },
            "data_quality_assessment": {
                "overall_rating": (
                    "excellent" if validation_report.quality_score >= 90 else
                    "good" if validation_report.quality_score >= 70 else
                    "fair" if validation_report.quality_score >= 50 else
                    "poor"
                ),
                "completeness_rating": (
                    "complete" if validation_report.data_completeness >= 95 else
                    "mostly_complete" if validation_report.data_completeness >= 80 else
                    "incomplete"
                ),
                "critical_issues_found": len([i for i in validation_report.issues if i.severity.value == 'critical']) > 0
            }
        }
        
    except Exception as e:
        logger.error("Failed to generate validation report", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate validation report: {str(e)}"
        )


@router.get("/validate/summary")
async def get_validation_summary(
    symbols: Optional[List[str]] = None,
    days_lookback: int = 7,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get validation summary for multiple symbols (synchronous)
    
    Args:
        symbols: List of symbols to validate (None for top 20 liquid stocks)
        days_lookback: Number of days to look back (max 30 for sync operation)
    """
    try:
        # Limit scope for synchronous operation
        if days_lookback > 30:
            raise HTTPException(
                status_code=400,
                detail="Maximum 30 days lookback allowed for synchronous validation"
            )
        
        # Use liquid stocks if no symbols provided
        if symbols is None:
            from app.data.collectors.asx_contracts import get_liquid_stocks
            symbols = get_liquid_stocks(20)  # Top 20 liquid stocks
        else:
            if len(symbols) > 20:
                raise HTTPException(
                    status_code=400,
                    detail="Maximum 20 symbols allowed for synchronous validation"
                )
            symbols = [s.upper().strip() for s in symbols]
        
        from app.data.processors.validation import BatchDataValidator
        
        batch_validator = BatchDataValidator()
        validation_reports = await batch_validator.validate_asx200_batch(db, symbols, days_lookback)
        batch_summary = batch_validator.generate_batch_summary(validation_reports)
        
        # Create simplified symbol summaries
        symbol_summaries = {}
        for symbol, report in validation_reports.items():
            symbol_summaries[symbol] = {
                "quality_score": report.quality_score,
                "data_completeness": report.data_completeness,
                "total_issues": len(report.issues),
                "critical_issues": len([i for i in report.issues if i.severity.value == 'critical']),
                "data_integrity": report.summary.get('data_integrity', 'unknown'),
                "latest_price": report.summary.get('price_stats', {}).get('latest_price'),
                "total_records": report.total_records
            }
        
        return {
            "validation_summary": {
                "symbols_validated": len(validation_reports),
                "days_lookback": days_lookback,
                "validation_timestamp": datetime.now().isoformat(),
                "avg_quality_score": batch_summary['batch_summary']['avg_quality_score'],
                "avg_data_completeness": batch_summary['batch_summary']['avg_data_completeness'],
                "quality_distribution": batch_summary['batch_summary']['quality_distribution'],
                "symbols_with_critical_issues": batch_summary['batch_summary']['symbols_with_critical_issues']
            },
            "symbol_details": symbol_summaries,
            "recommendations": {
                "symbols_needing_attention": [
                    symbol for symbol, summary in symbol_summaries.items()
                    if summary['critical_issues'] > 0 or summary['quality_score'] < 70
                ],
                "high_quality_symbols": [
                    symbol for symbol, summary in symbol_summaries.items()
                    if summary['quality_score'] >= 90 and summary['critical_issues'] == 0
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate validation summary", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate validation summary: {str(e)}"
        )