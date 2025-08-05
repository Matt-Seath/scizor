"""Algo Trader service main application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.database.connection import init_db
from .config import get_settings
from .api import trading, orders, positions, risk
from .services.trader import AlgoTrader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global trader instance
trader_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global trader_instance
    
    # Startup
    logger.info("Starting Algo Trader service...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize algo trader
        trader_instance = AlgoTrader()
        await trader_instance.initialize()
        logger.info("Algo trader initialized")
        
        logger.info("Algo Trader service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Algo Trader service: {str(e)}")
        raise
        
    yield
    
    # Shutdown
    logger.info("Shutting down Algo Trader service...")
    
    try:
        # Clean shutdown of trader
        if trader_instance:
            await trader_instance.shutdown()
            
        logger.info("Algo Trader service shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during Algo Trader service shutdown: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title="SCIZOR Algo Trader Service",
    description="Algorithmic trading execution service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Global exception on {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "algo-trader",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        # Check trader status
        trader_status = "ready"
        if trader_instance:
            status = await trader_instance.get_status()
            trader_status = status.get("status", "unknown")
            
        return {
            "status": "ready" if trader_status == "ready" else "not ready",
            "service": "algo-trader",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "database": "healthy",
                "trader": trader_status,
                "ibkr_connection": "connected" if trader_instance and trader_instance.is_connected() else "disconnected"
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not ready",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


# Dependency to get trader instance
def get_trader():
    """Get the global trader instance."""
    if not trader_instance:
        raise HTTPException(status_code=503, detail="Trader not initialized")
    return trader_instance


# Include API routers
app.include_router(
    trading.router,
    prefix=f"{settings.api_prefix}/trading",
    tags=["trading"]
)

app.include_router(
    orders.router,
    prefix=f"{settings.api_prefix}/orders",
    tags=["orders"]
)

app.include_router(
    positions.router,
    prefix=f"{settings.api_prefix}/positions",
    tags=["positions"]
)

app.include_router(
    risk.router,
    prefix=f"{settings.api_prefix}/risk",
    tags=["risk"]
)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
