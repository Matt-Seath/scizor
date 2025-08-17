from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import List, Optional
import structlog

from app.config.database import get_async_db
from app.data.models.market import DailyPrice, ApiRequest
from app.data.collectors.asx_contracts import get_asx200_symbols, get_liquid_stocks
from app.tasks.data_collection import (
    collect_daily_asx_data, 
    collect_sample_data,
    test_ibkr_connection
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