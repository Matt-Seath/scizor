"""Market data API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, and_

from shared.database.connection import get_db
from shared.database.models import Symbol, MarketData
from shared.models.schemas import APIResponse, MarketDataResponse
from ..services.collector import DataCollector

router = APIRouter()


@router.get("/symbols/{symbol_id}/latest", response_model=MarketDataResponse)
async def get_latest_data(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get the latest market data for a symbol."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Get latest market data
        latest_data = await db.query(MarketData).filter(
            MarketData.symbol_id == symbol_id
        ).order_by(desc(MarketData.timestamp)).first()
        
        if not latest_data:
            raise HTTPException(status_code=404, detail="No market data found for symbol")
            
        return MarketDataResponse(
            symbol_id=latest_data.symbol_id,
            timestamp=latest_data.timestamp,
            open_price=latest_data.open,
            high_price=latest_data.high,
            low_price=latest_data.low,
            close_price=latest_data.close,
            volume=latest_data.volume,
            bid_price=latest_data.bid,
            ask_price=latest_data.ask,
            bid_size=latest_data.bid_size,
            ask_size=latest_data.ask_size,
            last_price=latest_data.last,
            last_size=latest_data.last_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve market data: {str(e)}")


@router.get("/symbols/{symbol_id}/historical", response_model=List[MarketDataResponse])
async def get_historical_data(
    symbol_id: int,
    start_date: Optional[datetime] = Query(None, description="Start date for historical data"),
    end_date: Optional[datetime] = Query(None, description="End date for historical data"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical market data for a symbol."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Query historical data
        query = db.query(MarketData).filter(
            and_(
                MarketData.symbol_id == symbol_id,
                MarketData.timestamp >= start_date,
                MarketData.timestamp <= end_date
            )
        ).order_by(desc(MarketData.timestamp)).limit(limit)
        
        data_records = await query.all()
        
        return [
            MarketDataResponse(
                symbol_id=record.symbol_id,
                timestamp=record.timestamp,
                open_price=record.open,
                high_price=record.high,
                low_price=record.low,
                close_price=record.close,
                volume=record.volume,
                bid_price=record.bid,
                ask_price=record.ask,
                bid_size=record.bid_size,
                ask_size=record.ask_size,
                last_price=record.last,
                last_size=record.last_size
            )
            for record in data_records
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve historical data: {str(e)}")


@router.get("/symbols/{symbol_id}/ohlcv", response_model=List[Dict[str, Any]])
async def get_ohlcv_data(
    symbol_id: int,
    start_date: Optional[datetime] = Query(None, description="Start date for OHLCV data"),
    end_date: Optional[datetime] = Query(None, description="End date for OHLCV data"),
    interval: str = Query("1min", description="Data interval (1min, 5min, 15min, 1h, 1d)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get OHLCV (Open, High, Low, Close, Volume) data for a symbol."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Query OHLCV data
        query = db.query(MarketData).filter(
            and_(
                MarketData.symbol_id == symbol_id,
                MarketData.timestamp >= start_date,
                MarketData.timestamp <= end_date
            )
        ).order_by(MarketData.timestamp).limit(limit)
        
        data_records = await query.all()
        
        return [
            {
                "timestamp": record.timestamp.isoformat(),
                "open": float(record.open) if record.open else None,
                "high": float(record.high) if record.high else None,
                "low": float(record.low) if record.low else None,
                "close": float(record.close) if record.close else None,
                "volume": int(record.volume) if record.volume else None,
            }
            for record in data_records
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve OHLCV data: {str(e)}")


@router.post("/symbols/{symbol_id}/subscribe", response_model=APIResponse)
async def subscribe_to_data(
    symbol_id: int,
    background_tasks: BackgroundTasks,
    data_type: str = Query("real_time", description="Type of data subscription (real_time, historical)"),
    db: AsyncSession = Depends(get_db)
):
    """Subscribe to real-time data for a symbol."""
    try:
        # Verify symbol exists and is active
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
        if not symbol.active:
            raise HTTPException(status_code=400, detail="Symbol is not active")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Start data subscription in background
        if data_type == "real_time":
            background_tasks.add_task(collector.start_real_time_data, symbol_id)
        elif data_type == "historical":
            background_tasks.add_task(collector.collect_historical_data, symbol_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid data type")
            
        return APIResponse(
            success=True,
            message=f"Started {data_type} data subscription for symbol {symbol.symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to subscribe to data: {str(e)}")


@router.post("/symbols/{symbol_id}/unsubscribe", response_model=APIResponse)
async def unsubscribe_from_data(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from real-time data for a symbol."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Initialize data collector and stop subscription
        collector = DataCollector()
        await collector.stop_real_time_data(symbol_id)
        
        return APIResponse(
            success=True,
            message=f"Stopped data subscription for symbol {symbol.symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe from data: {str(e)}")


@router.get("/status", response_model=Dict[str, Any])
async def get_data_status(
    db: AsyncSession = Depends(get_db)
):
    """Get data collection status."""
    try:
        # Get count of active symbols
        active_symbols_count = await db.query(Symbol).filter(Symbol.active == True).count()
        
        # Get latest data timestamp
        latest_data = await db.query(MarketData).order_by(desc(MarketData.timestamp)).first()
        latest_timestamp = latest_data.timestamp if latest_data else None
        
        # Get total data points count
        total_data_points = await db.query(MarketData).count()
        
        return {
            "active_symbols": active_symbols_count,
            "latest_data_timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
            "total_data_points": total_data_points,
            "collector_status": "active",  # This would be dynamic in real implementation
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data status: {str(e)}")


@router.post("/collect/historical", response_model=APIResponse)
async def trigger_historical_collection(
    background_tasks: BackgroundTasks,
    symbol_ids: Optional[List[int]] = Query(None, description="Symbol IDs to collect (all active if not specified)"),
    start_date: Optional[datetime] = Query(None, description="Start date for historical collection"),
    end_date: Optional[datetime] = Query(None, description="End date for historical collection"),
    db: AsyncSession = Depends(get_db)
):
    """Trigger historical data collection for symbols."""
    try:
        # Get symbols to collect data for
        if symbol_ids:
            symbols = await db.query(Symbol).filter(Symbol.id.in_(symbol_ids)).all()
        else:
            symbols = await db.query(Symbol).filter(Symbol.active == True).all()
            
        if not symbols:
            raise HTTPException(status_code=404, detail="No symbols found for collection")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Start historical collection for each symbol
        for symbol in symbols:
            background_tasks.add_task(
                collector.collect_historical_data,
                symbol.id,
                start_date,
                end_date
            )
            
        return APIResponse(
            success=True,
            message=f"Started historical data collection for {len(symbols)} symbols"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger historical collection: {str(e)}")


@router.delete("/symbols/{symbol_id}/data", response_model=APIResponse)
async def delete_symbol_data(
    symbol_id: int,
    start_date: Optional[datetime] = Query(None, description="Start date for data deletion"),
    end_date: Optional[datetime] = Query(None, description="End date for data deletion"),
    db: AsyncSession = Depends(get_db)
):
    """Delete market data for a symbol within a date range."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Build delete query
        query = db.query(MarketData).filter(MarketData.symbol_id == symbol_id)
        
        if start_date:
            query = query.filter(MarketData.timestamp >= start_date)
        if end_date:
            query = query.filter(MarketData.timestamp <= end_date)
            
        # Count records to be deleted
        count = await query.count()
        
        # Delete the data
        await query.delete()
        await db.commit()
        
        return APIResponse(
            success=True,
            message=f"Deleted {count} market data records for symbol {symbol.symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete symbol data: {str(e)}")
