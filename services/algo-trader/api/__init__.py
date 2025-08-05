"""API routes for the Algo Trader service."""

from fastapi import APIRouter
from .trading import router as trading_router
from .orders import router as orders_router
from .positions import router as positions_router
from .risk import router as risk_router

router = APIRouter()
router.include_router(trading_router, prefix="/trading", tags=["trading"])
router.include_router(orders_router, prefix="/orders", tags=["orders"])
router.include_router(positions_router, prefix="/positions", tags=["positions"])
router.include_router(risk_router, prefix="/risk", tags=["risk"])
