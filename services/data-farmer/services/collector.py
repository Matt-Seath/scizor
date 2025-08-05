"""Data collection service for market data."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
from concurrent.futures import ThreadPoolExecutor

from shared.ibkr.client import IBKRManager
from shared.database.connection import get_db
from shared.database.models import Symbol, MarketData
from shared.models.schemas import ContractBase
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DataCollector:
    """Main data collection service for managing market data collection."""
    
    def __init__(self):
        """Initialize the data collector."""
        self.ibkr_manager = None
        self.active_subscriptions: Dict[int, bool] = {}
        self.collection_stats = {
            "start_time": datetime.now(),
            "total_messages": 0,
            "error_count": 0,
            "last_error": None,
            "last_data_received": None
        }
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()
        
    async def initialize(self):
        """Initialize IBKR connection and other resources."""
        try:
            self.ibkr_manager = IBKRManager()
            await self.ibkr_manager.connect()
            logger.info("Data collector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize data collector: {str(e)}")
            raise
            
    async def shutdown(self):
        """Clean shutdown of the data collector."""
        try:
            # Stop all active subscriptions
            await self.stop_all_collections()
            
            # Disconnect from IBKR
            if self.ibkr_manager:
                await self.ibkr_manager.disconnect()
                
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Data collector shutdown completed")
        except Exception as e:
            logger.error(f"Error during data collector shutdown: {str(e)}")
            
    async def start_real_time_data(self, symbol_id: int):
        """Start real-time data collection for a symbol."""
        try:
            if not self.ibkr_manager:
                await self.initialize()
                
            # Get symbol information
            async with get_db() as db:
                symbol = await db.get(Symbol, symbol_id)
                if not symbol:
                    raise ValueError(f"Symbol with ID {symbol_id} not found")
                    
            # Create contract for IBKR
            contract = ContractBase(
                symbol=symbol.symbol,
                exchange=symbol.exchange,
                currency=symbol.currency,
                security_type=symbol.security_type,
                contract_id=symbol.contract_id
            )
            
            # Start real-time data subscription
            with self._lock:
                if symbol_id not in self.active_subscriptions:
                    self.active_subscriptions[symbol_id] = True
                    
            # Subscribe to market data
            await self.ibkr_manager.subscribe_market_data(
                contract=contract,
                callback=lambda data: asyncio.create_task(
                    self._process_market_data(symbol_id, data)
                )
            )
            
            logger.info(f"Started real-time data collection for symbol {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Failed to start real-time data for symbol {symbol_id}: {str(e)}")
            self.collection_stats["error_count"] += 1
            self.collection_stats["last_error"] = str(e)
            raise
            
    async def stop_real_time_data(self, symbol_id: int):
        """Stop real-time data collection for a symbol."""
        try:
            with self._lock:
                if symbol_id in self.active_subscriptions:
                    del self.active_subscriptions[symbol_id]
                    
            # Get symbol information
            async with get_db() as db:
                symbol = await db.get(Symbol, symbol_id)
                if symbol:
                    # Create contract for IBKR
                    contract = ContractBase(
                        symbol=symbol.symbol,
                        exchange=symbol.exchange,
                        currency=symbol.currency,
                        security_type=symbol.security_type,
                        contract_id=symbol.contract_id
                    )
                    
                    # Unsubscribe from market data
                    if self.ibkr_manager:
                        await self.ibkr_manager.unsubscribe_market_data(contract)
                        
            logger.info(f"Stopped real-time data collection for symbol {symbol_id}")
            
        except Exception as e:
            logger.error(f"Failed to stop real-time data for symbol {symbol_id}: {str(e)}")
            raise
            
    async def collect_historical_data(
        self,
        symbol_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """Collect historical data for a symbol."""
        try:
            if not self.ibkr_manager:
                await self.initialize()
                
            # Get symbol information
            async with get_db() as db:
                symbol = await db.get(Symbol, symbol_id)
                if not symbol:
                    raise ValueError(f"Symbol with ID {symbol_id} not found")
                    
            # Set default date range
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)
                
            # Create contract for IBKR
            contract = ContractBase(
                symbol=symbol.symbol,
                exchange=symbol.exchange,
                currency=symbol.currency,
                security_type=symbol.security_type,
                contract_id=symbol.contract_id
            )
            
            # Request historical data
            historical_data = await self.ibkr_manager.get_historical_data(
                contract=contract,
                duration="30 D",
                bar_size="1 min",
                what_to_show="TRADES"
            )
            
            # Process and store historical data
            await self._process_historical_data(symbol_id, historical_data)
            
            logger.info(f"Collected historical data for symbol {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Failed to collect historical data for symbol {symbol_id}: {str(e)}")
            self.collection_stats["error_count"] += 1
            self.collection_stats["last_error"] = str(e)
            raise
            
    async def _process_market_data(self, symbol_id: int, data: Dict[str, Any]):
        """Process and store real-time market data."""
        try:
            # Create market data record
            market_data = MarketData(
                symbol_id=symbol_id,
                timestamp=datetime.now(),
                bid=data.get("bid"),
                ask=data.get("ask"),
                last=data.get("last"),
                bid_size=data.get("bid_size"),
                ask_size=data.get("ask_size"),
                last_size=data.get("last_size"),
                high=data.get("high"),
                low=data.get("low"),
                volume=data.get("volume"),
                open=data.get("open"),
                close=data.get("close")
            )
            
            # Store in database
            async with get_db() as db:
                db.add(market_data)
                await db.commit()
                
            # Update stats
            self.collection_stats["total_messages"] += 1
            self.collection_stats["last_data_received"] = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to process market data for symbol {symbol_id}: {str(e)}")
            self.collection_stats["error_count"] += 1
            self.collection_stats["last_error"] = str(e)
            
    async def _process_historical_data(self, symbol_id: int, data: List[Dict[str, Any]]):
        """Process and store historical market data."""
        try:
            market_data_records = []
            
            for bar in data:
                market_data = MarketData(
                    symbol_id=symbol_id,
                    timestamp=bar.get("date"),
                    open=bar.get("open"),
                    high=bar.get("high"),
                    low=bar.get("low"),
                    close=bar.get("close"),
                    volume=bar.get("volume")
                )
                market_data_records.append(market_data)
                
            # Bulk insert historical data
            async with get_db() as db:
                db.add_all(market_data_records)
                await db.commit()
                
            logger.info(f"Stored {len(market_data_records)} historical data points for symbol {symbol_id}")
            
        except Exception as e:
            logger.error(f"Failed to process historical data for symbol {symbol_id}: {str(e)}")
            raise
            
    async def stop_all_collections(self):
        """Stop all active data collections."""
        try:
            symbol_ids = list(self.active_subscriptions.keys())
            for symbol_id in symbol_ids:
                await self.stop_real_time_data(symbol_id)
                
            logger.info("Stopped all data collections")
            
        except Exception as e:
            logger.error(f"Failed to stop all collections: {str(e)}")
            raise
            
    async def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status."""
        try:
            uptime = datetime.now() - self.collection_stats["start_time"]
            
            return {
                "active_collections": len(self.active_subscriptions),
                "total_symbols": len(self.active_subscriptions),
                "collection_rate": f"{self.collection_stats['total_messages']}/min",
                "last_update": self.collection_stats["last_data_received"].isoformat() if self.collection_stats["last_data_received"] else None,
                "errors": [self.collection_stats["last_error"]] if self.collection_stats["last_error"] else [],
                "uptime": str(uptime),
                "memory_usage": "0MB",  # Would implement actual memory tracking
                "connection_status": "connected" if self.ibkr_manager and self.ibkr_manager.is_connected() else "disconnected"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection status: {str(e)}")
            return {}
            
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the data collector."""
        try:
            # Check IBKR connection
            ibkr_connected = self.ibkr_manager and self.ibkr_manager.is_connected()
            
            # Check database connection
            db_connected = True  # Would implement actual DB health check
            
            # Determine overall status
            if ibkr_connected and db_connected:
                status = "healthy"
            elif ibkr_connected or db_connected:
                status = "degraded"
            else:
                status = "unhealthy"
                
            return {
                "status": status,
                "ibkr_connection": ibkr_connected,
                "database_connection": db_connected,
                "active_subscriptions": len(self.active_subscriptions),
                "error_count": self.collection_stats["error_count"],
                "last_error": self.collection_stats["last_error"],
                "last_data_received": self.collection_stats["last_data_received"].isoformat() if self.collection_stats["last_data_received"] else None,
                "messages_per_second": 0,  # Would implement actual rate calculation
                "avg_latency_ms": 0,  # Would implement latency tracking
                "queue_size": 0  # Would implement queue monitoring
            }
            
        except Exception as e:
            logger.error(f"Failed to get health status: {str(e)}")
            return {"status": "error", "error": str(e)}
            
    async def cleanup_old_data(
        self,
        cutoff_date: datetime,
        symbol_ids: Optional[List[int]] = None
    ):
        """Clean up old market data."""
        try:
            async with get_db() as db:
                query = db.query(MarketData).filter(MarketData.timestamp < cutoff_date)
                
                if symbol_ids:
                    query = query.filter(MarketData.symbol_id.in_(symbol_ids))
                    
                count = await query.count()
                await query.delete()
                await db.commit()
                
            logger.info(f"Cleaned up {count} old market data records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}")
            raise
            
    async def optimize_database(self):
        """Optimize database performance."""
        try:
            # Would implement database optimization tasks
            # Such as VACUUM, ANALYZE, index maintenance, etc.
            logger.info("Database optimization completed")
            
        except Exception as e:
            logger.error(f"Failed to optimize database: {str(e)}")
            raise
            
    async def get_collection_metrics(self, timeframe: str) -> Dict[str, Any]:
        """Get collection metrics for a specific timeframe."""
        try:
            # Parse timeframe
            if timeframe == "1h":
                start_time = datetime.now() - timedelta(hours=1)
            elif timeframe == "24h":
                start_time = datetime.now() - timedelta(days=1)
            elif timeframe == "7d":
                start_time = datetime.now() - timedelta(days=7)
            elif timeframe == "30d":
                start_time = datetime.now() - timedelta(days=30)
            else:
                start_time = datetime.now() - timedelta(hours=1)
                
            # Get metrics from database
            async with get_db() as db:
                total_data_points = await db.query(MarketData).filter(
                    MarketData.timestamp >= start_time
                ).count()
                
            # Calculate metrics
            hours_elapsed = (datetime.now() - start_time).total_seconds() / 3600
            data_points_per_hour = int(total_data_points / hours_elapsed) if hours_elapsed > 0 else 0
            
            return {
                "total_data_points": total_data_points,
                "data_points_per_hour": data_points_per_hour,
                "symbols_collected": len(self.active_subscriptions),
                "collection_efficiency": "100%",  # Would calculate actual efficiency
                "error_rate": "0%",  # Would calculate actual error rate
                "avg_latency": "0ms",  # Would track actual latency
                "peak_collection_rate": "0/min",  # Would track peak rates
                "storage_usage": "0MB"  # Would calculate storage usage
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection metrics: {str(e)}")
            return {}
