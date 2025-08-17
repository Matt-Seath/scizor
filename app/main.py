from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.config.settings import settings
from app.config.database import init_db, close_db
from app.api.routes import health, dashboard, data_collection
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    setup_logging()
    logger = structlog.get_logger(__name__)
    
    logger.info("Starting ASX200 Trading System", version=settings.app_version)
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down ASX200 Trading System")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error("Error closing database", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Algorithmic Trading System for ASX200 stocks using IBKR TWS API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(data_collection.router, prefix="/api/data", tags=["data-collection"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ASX200 Trading System API",
        "version": settings.app_version,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )