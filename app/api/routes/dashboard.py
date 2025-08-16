from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from datetime import datetime
import structlog

from app.config.database import get_async_db
from app.data.collectors.market_data import MarketDataCollector
from app.data.collectors.asx_contracts import get_asx200_symbols, get_liquid_stocks

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/status")
async def get_system_status():
    """Get overall system status for dashboard"""
    try:
        collector = MarketDataCollector()
        stats = collector.get_collection_stats()
        
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "status": "running",
                "uptime": "TODO",  # TODO: Calculate actual uptime
                "market_open": stats["market_open"],
                "trading_day": stats["trading_day"]
            },
            "data_collection": {
                "active_subscriptions": stats["active_subscriptions"],
                "symbols_with_data": stats["symbols_with_data"],
                "requests_made": stats["requests_made"],
                "successful_responses": stats["successful_responses"],
                "errors": stats["errors"],
                "success_rate": (
                    stats["successful_responses"] / max(stats["requests_made"], 1) * 100
                )
            },
            "connection": stats["connection_status"]
        }
        
        return status
        
    except Exception as e:
        logger.error("Error getting system status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-data")
async def get_market_data_overview():
    """Get market data overview for dashboard"""
    try:
        collector = MarketDataCollector()
        
        # Get available symbols
        asx200_symbols = get_asx200_symbols()
        liquid_symbols = get_liquid_stocks(20)
        
        # Get latest data for liquid stocks
        latest_data = {}
        for symbol in liquid_symbols[:10]:  # Limit to first 10 for dashboard
            data_point = collector.get_latest_data(symbol)
            if data_point:
                latest_data[symbol] = {
                    "price": data_point.price,
                    "bid": data_point.bid,
                    "ask": data_point.ask,
                    "volume": data_point.volume,
                    "timestamp": data_point.timestamp.isoformat()
                }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_symbols": len(asx200_symbols),
            "liquid_symbols": len(liquid_symbols),
            "latest_data": latest_data,
            "data_points_available": len(latest_data)
        }
        
    except Exception as e:
        logger.error("Error getting market data overview", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
async def get_symbols_list():
    """Get list of available symbols"""
    try:
        return {
            "asx200": get_asx200_symbols(),
            "liquid": get_liquid_stocks(20),
            "total_count": len(get_asx200_symbols())
        }
    except Exception as e:
        logger.error("Error getting symbols list", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data-collection/start")
async def start_data_collection():
    """Start market data collection"""
    try:
        collector = MarketDataCollector()
        
        if await collector.start_collection():
            # Start with a small sample for testing
            req_ids = await collector.subscribe_to_asx200_sample(max_symbols=5)
            
            return {
                "status": "started",
                "message": "Market data collection started",
                "subscriptions": len(req_ids),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail="Failed to start market data collection"
            )
            
    except Exception as e:
        logger.error("Error starting data collection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data-collection/stop")
async def stop_data_collection():
    """Stop market data collection"""
    try:
        collector = MarketDataCollector()
        await collector.stop_collection()
        
        return {
            "status": "stopped",
            "message": "Market data collection stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error stopping data collection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_metrics():
    """Get system performance metrics"""
    try:
        # TODO: Implement actual performance metrics
        # This would include trading performance, risk metrics, etc.
        
        placeholder_metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "portfolio": {
                "total_value": 0,
                "daily_pnl": 0,
                "unrealized_pnl": 0,
                "realized_pnl": 0,
                "positions_count": 0
            },
            "risk": {
                "total_exposure": 0,
                "max_drawdown": 0,
                "var_95": 0,
                "correlation_risk": 0
            },
            "trading": {
                "trades_today": 0,
                "win_rate": 0,
                "avg_holding_period": 0,
                "sharpe_ratio": 0
            }
        }
        
        return placeholder_metrics
        
    except Exception as e:
        logger.error("Error getting performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))