"""API routers for Algo Trader service."""

from .trading import router as trading_router
from .orders import router as orders_router  
from .positions import router as positions_router
from .risk import router as risk_router

__all__ = [
    "trading_router",
    "orders_router", 
    "positions_router",
    "risk_router"
]
