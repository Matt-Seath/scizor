"""API routes for Data Farmer service."""

from fastapi import APIRouter

from .symbols import router as symbols_router
from .data import router as data_router
from .collection import router as collection_router

# Create main router
router = APIRouter()

# Include sub-routers
router.include_router(symbols_router, prefix="/symbols", tags=["symbols"])
router.include_router(data_router, prefix="/data", tags=["data"])
router.include_router(collection_router, prefix="/collect", tags=["collection"])
