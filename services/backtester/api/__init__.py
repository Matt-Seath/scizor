"""API routers for Backtester service."""

from .strategies import router as strategies_router
from .backtests import router as backtests_router  
from .results import router as results_router
from .performance import router as performance_router

__all__ = [
    "strategies_router",
    "backtests_router", 
    "results_router",
    "performance_router"
]
