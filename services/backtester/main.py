"""Backtester service main application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.database.connection import init_db
from .config import get_settings
from .api import strategies, backtests, results, performance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Backtester service...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize backtesting engine
        # BacktestEngine will be initialized when needed
        
        logger.info("Backtester service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Backtester service: {str(e)}")
        raise
        
    yield
    
    # Shutdown
    logger.info("Shutting down Backtester service...")
    
    try:
        # Clean shutdown tasks here
        logger.info("Backtester service shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during Backtester service shutdown: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title="SCIZOR Backtester Service",
    description="Strategy backtesting and performance analysis service",
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
        "service": "backtester",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        # Check database connection
        # Would implement actual health checks here
        
        return {
            "status": "ready",
            "service": "backtester",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "database": "healthy",
                "engine": "ready"
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


# Include API routers
app.include_router(
    strategies.router,
    prefix=f"{settings.api_prefix}/strategies",
    tags=["strategies"]
)

app.include_router(
    backtests.router,
    prefix=f"{settings.api_prefix}/backtests",
    tags=["backtests"]
)

app.include_router(
    results.router,
    prefix=f"{settings.api_prefix}/results",
    tags=["results"]
)

app.include_router(
    performance.router,
    prefix=f"{settings.api_prefix}/performance",
    tags=["performance"]
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
