from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import structlog

from app.config.database import get_async_db
from app.config.settings import settings
from app.data.collectors.market_data import MarketDataCollector

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version
    }


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_async_db)):
    """Detailed health check with database and external service status"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version,
        "checks": {}
    }
    
    overall_healthy = True
    
    # Database health check
    try:
        result = await db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # TODO: Add timing
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False
    
    # Market data collector health check
    try:
        collector = MarketDataCollector()
        stats = collector.get_collection_stats()
        
        # Check if connection is healthy
        connection_status = stats["connection_status"]
        if connection_status["connected"]:
            health_status["checks"]["market_data"] = {
                "status": "healthy",
                "connection": connection_status,
                "stats": {
                    "requests_made": stats["requests_made"],
                    "successful_responses": stats["successful_responses"],
                    "errors": stats["errors"],
                    "active_subscriptions": stats["active_subscriptions"]
                }
            }
        else:
            health_status["checks"]["market_data"] = {
                "status": "degraded",
                "connection": connection_status,
                "message": "IBKR connection not established"
            }
    except Exception as e:
        health_status["checks"]["market_data"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False
    
    # Market hours check
    try:
        from app.data.collectors.market_data import MarketHours
        market_hours = MarketHours()
        
        health_status["checks"]["market_hours"] = {
            "status": "healthy",
            "market_open": market_hours.is_market_open(),
            "trading_day": market_hours.is_trading_day(),
            "timezone": str(market_hours.timezone)
        }
    except Exception as e:
        health_status["checks"]["market_hours"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Update overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_async_db)):
    """Kubernetes readiness probe endpoint"""
    try:
        # Quick database check
        await db.execute(text("SELECT 1"))
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503, 
            detail={"status": "not ready", "error": str(e)}
        )


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }