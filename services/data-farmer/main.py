"""Data Farmer main application."""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.database.connection import init_db, close_db
from shared.utils.config import get_config
from shared.utils.logging import setup_logging

from .api import router
from .services.collector import DataCollector


# Global variables
config = get_config("data-farmer")
logger = setup_logging("data-farmer", config.log_level, config.log_file)
data_collector: DataCollector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global data_collector
    
    # Startup
    logger.info("Starting Data Farmer service...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize data collector
        data_collector = DataCollector(config)
        await data_collector.start()
        logger.info("Data collector started")
        
        # Store references in app state
        app.state.data_collector = data_collector
        app.state.config = config
        
        logger.info("Data Farmer service started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Data Farmer service: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Data Farmer service...")
        
        if data_collector:
            await data_collector.stop()
            logger.info("Data collector stopped")
            
        await close_db()
        logger.info("Database connections closed")
        
        logger.info("Data Farmer service shut down")


# Create FastAPI app
app = FastAPI(
    title="Scizor Data Farmer",
    description="Market data collection and storage service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router, prefix="/api", tags=["data-farmer"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Scizor Data Farmer",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "service": "data-farmer",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "uptime": 0,  # TODO: Calculate uptime
        "connections": {}
    }
    
    # Check data collector status
    if hasattr(app.state, 'data_collector') and app.state.data_collector:
        health_status["connections"]["ibkr"] = app.state.data_collector.is_connected()
    else:
        health_status["connections"]["ibkr"] = False
        health_status["status"] = "degraded"
    
    return health_status


def main():
    """Main entry point."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )


if __name__ == "__main__":
    main()
