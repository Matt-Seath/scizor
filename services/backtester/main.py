"""
Backtester service main module.

This module provides the main entry point for the backtesting service,
allowing users to test trading strategies against historical data.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from ...shared.database.connection import DatabaseConnection
from ...shared.strategy.base import StrategyConfig
from ...shared.utils.config import load_config
from ...shared.utils.logging import setup_logging
from .engine import BacktestEngine
from .strategies import MovingAverageCrossoverStrategy, MeanReversionStrategy, BuyAndHoldStrategy


def main():
    """Main entry point for backtester service."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Backtester Service")
    
    # Load configuration
    config = load_config()
    
    # Initialize database connection
    db = DatabaseConnection(config)
    
    # Initialize backtesting engine
    engine = BacktestEngine(db)
    
    # Example: Test moving average crossover strategy
    logger.info("Running example backtest with Moving Average Crossover strategy")
    
    # Define strategy configuration
    strategy_config = StrategyConfig(
        name="MA Crossover 20/50",
        description="Moving average crossover with 20/50 periods",
        parameters={
            'short_window': 20,
            'long_window': 50,
            'position_size_pct': 0.1
        },
        max_position_size=Decimal('0.2'),
        max_positions=5,
        risk_per_trade=Decimal('0.02'),
        lookback_period=100,
        rebalance_frequency='daily'
    )
    
    # Create strategy instance
    strategy = MovingAverageCrossoverStrategy(strategy_config)
    
    # Define test parameters
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']  # Example symbols
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 1 year backtest
    initial_capital = Decimal('100000')
    
    try:
        # Run backtest
        result = engine.run_backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # Print results
        logger.info("Backtest Results:")
        logger.info(f"  Initial Capital: ${result.initial_capital:,.2f}")
        logger.info(f"  Final Value: ${result.final_value:,.2f}")
        logger.info(f"  Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2%})")
        logger.info(f"  Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2%})")
        logger.info(f"  Sharpe Ratio: {result.sharpe_ratio:.3f}" if result.sharpe_ratio else "  Sharpe Ratio: N/A")
        logger.info(f"  Total Trades: {result.total_trades}")
        logger.info(f"  Win Rate: {result.win_rate:.2%}")
        logger.info(f"  Profit Factor: {result.profit_factor:.3f}" if result.profit_factor else "  Profit Factor: N/A")
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise


if __name__ == "__main__":
    main()

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
