"""Data collection management API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.connection import get_db
from shared.database.models import Symbol
from shared.models.schemas import APIResponse
from ..services.collector import DataCollector

router = APIRouter()


@router.post("/start", response_model=APIResponse)
async def start_collection(
    background_tasks: BackgroundTasks,
    symbol_ids: Optional[List[int]] = Query(None, description="Symbol IDs to start collection for"),
    collection_type: str = Query("real_time", description="Collection type: real_time, historical, or both"),
    db: AsyncSession = Depends(get_db)
):
    """Start data collection for specified symbols."""
    try:
        # Get symbols to start collection for
        if symbol_ids:
            symbols = await db.query(Symbol).filter(
                Symbol.id.in_(symbol_ids),
                Symbol.active == True
            ).all()
        else:
            symbols = await db.query(Symbol).filter(Symbol.active == True).all()
            
        if not symbols:
            raise HTTPException(status_code=404, detail="No active symbols found")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Start collection based on type
        for symbol in symbols:
            if collection_type in ["real_time", "both"]:
                background_tasks.add_task(collector.start_real_time_data, symbol.id)
            if collection_type in ["historical", "both"]:
                background_tasks.add_task(collector.collect_historical_data, symbol.id)
                
        return APIResponse(
            success=True,
            message=f"Started {collection_type} data collection for {len(symbols)} symbols"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start collection: {str(e)}")


@router.post("/stop", response_model=APIResponse)
async def stop_collection(
    symbol_ids: Optional[List[int]] = Query(None, description="Symbol IDs to stop collection for"),
    db: AsyncSession = Depends(get_db)
):
    """Stop data collection for specified symbols."""
    try:
        # Get symbols to stop collection for
        if symbol_ids:
            symbols = await db.query(Symbol).filter(Symbol.id.in_(symbol_ids)).all()
        else:
            symbols = await db.query(Symbol).all()
            
        if not symbols:
            raise HTTPException(status_code=404, detail="No symbols found")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Stop collection for each symbol
        for symbol in symbols:
            await collector.stop_real_time_data(symbol.id)
                
        return APIResponse(
            success=True,
            message=f"Stopped data collection for {len(symbols)} symbols"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop collection: {str(e)}")


@router.get("/status", response_model=Dict[str, Any])
async def get_collection_status():
    """Get the current status of data collection."""
    try:
        collector = DataCollector()
        status = await collector.get_collection_status()
        
        return {
            "active_collections": status.get("active_collections", 0),
            "total_symbols": status.get("total_symbols", 0),
            "collection_rate": status.get("collection_rate", "0/min"),
            "last_update": status.get("last_update"),
            "errors": status.get("errors", []),
            "uptime": status.get("uptime", "0s"),
            "memory_usage": status.get("memory_usage", "0MB"),
            "connection_status": status.get("connection_status", "disconnected")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get collection status: {str(e)}")


@router.post("/symbols/{symbol_id}/start", response_model=APIResponse)
async def start_symbol_collection(
    symbol_id: int,
    background_tasks: BackgroundTasks,
    collection_type: str = Query("real_time", description="Collection type: real_time, historical, or both"),
    db: AsyncSession = Depends(get_db)
):
    """Start data collection for a specific symbol."""
    try:
        # Verify symbol exists and is active
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
        if not symbol.active:
            raise HTTPException(status_code=400, detail="Symbol is not active")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Start collection based on type
        if collection_type in ["real_time", "both"]:
            background_tasks.add_task(collector.start_real_time_data, symbol_id)
        if collection_type in ["historical", "both"]:
            background_tasks.add_task(collector.collect_historical_data, symbol_id)
            
        return APIResponse(
            success=True,
            message=f"Started {collection_type} collection for symbol {symbol.symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start symbol collection: {str(e)}")


@router.post("/symbols/{symbol_id}/stop", response_model=APIResponse)
async def stop_symbol_collection(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Stop data collection for a specific symbol."""
    try:
        # Verify symbol exists
        symbol = await db.get(Symbol, symbol_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Initialize data collector and stop collection
        collector = DataCollector()
        await collector.stop_real_time_data(symbol_id)
        
        return APIResponse(
            success=True,
            message=f"Stopped collection for symbol {symbol.symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop symbol collection: {str(e)}")


@router.post("/restart", response_model=APIResponse)
async def restart_collection(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Restart data collection for all active symbols."""
    try:
        # Get all active symbols
        symbols = await db.query(Symbol).filter(Symbol.active == True).all()
        
        if not symbols:
            raise HTTPException(status_code=404, detail="No active symbols found")
            
        # Initialize data collector
        collector = DataCollector()
        
        # Stop all current collections
        await collector.stop_all_collections()
        
        # Wait a moment for cleanup
        await asyncio.sleep(2)
        
        # Restart collections
        for symbol in symbols:
            background_tasks.add_task(collector.start_real_time_data, symbol.id)
            
        return APIResponse(
            success=True,
            message=f"Restarted data collection for {len(symbols)} symbols"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart collection: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def get_collection_health():
    """Get health check information for data collection."""
    try:
        collector = DataCollector()
        health_status = await collector.get_health_status()
        
        return {
            "status": health_status.get("status", "unknown"),
            "ibkr_connection": health_status.get("ibkr_connection", False),
            "database_connection": health_status.get("database_connection", False),
            "active_subscriptions": health_status.get("active_subscriptions", 0),
            "error_count": health_status.get("error_count", 0),
            "last_error": health_status.get("last_error"),
            "last_data_received": health_status.get("last_data_received"),
            "performance_metrics": {
                "messages_per_second": health_status.get("messages_per_second", 0),
                "avg_latency_ms": health_status.get("avg_latency_ms", 0),
                "queue_size": health_status.get("queue_size", 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get collection health: {str(e)}")


@router.post("/maintenance/cleanup", response_model=APIResponse)
async def cleanup_old_data(
    background_tasks: BackgroundTasks,
    days_old: int = Query(30, ge=1, description="Delete data older than this many days"),
    symbol_ids: Optional[List[int]] = Query(None, description="Symbol IDs to cleanup (all if not specified)"),
    db: AsyncSession = Depends(get_db)
):
    """Clean up old market data."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        # Initialize data collector for cleanup task
        collector = DataCollector()
        
        # Start cleanup in background
        background_tasks.add_task(
            collector.cleanup_old_data,
            cutoff_date,
            symbol_ids
        )
        
        return APIResponse(
            success=True,
            message=f"Started cleanup of data older than {days_old} days"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start cleanup: {str(e)}")


@router.post("/maintenance/optimize", response_model=APIResponse)
async def optimize_database(
    background_tasks: BackgroundTasks
):
    """Optimize database performance."""
    try:
        collector = DataCollector()
        
        # Start database optimization in background
        background_tasks.add_task(collector.optimize_database)
        
        return APIResponse(
            success=True,
            message="Started database optimization"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start optimization: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_collection_metrics(
    timeframe: str = Query("1h", description="Timeframe for metrics (1h, 24h, 7d, 30d)"),
    db: AsyncSession = Depends(get_db)
):
    """Get data collection metrics."""
    try:
        collector = DataCollector()
        metrics = await collector.get_collection_metrics(timeframe)
        
        return {
            "timeframe": timeframe,
            "total_data_points": metrics.get("total_data_points", 0),
            "data_points_per_hour": metrics.get("data_points_per_hour", 0),
            "symbols_collected": metrics.get("symbols_collected", 0),
            "collection_efficiency": metrics.get("collection_efficiency", "0%"),
            "error_rate": metrics.get("error_rate", "0%"),
            "avg_latency": metrics.get("avg_latency", "0ms"),
            "peak_collection_rate": metrics.get("peak_collection_rate", "0/min"),
            "storage_usage": metrics.get("storage_usage", "0MB")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get collection metrics: {str(e)}")
