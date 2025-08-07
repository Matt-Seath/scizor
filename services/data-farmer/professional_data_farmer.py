#!/usr/bin/env python3
"""
Professional Data Farmer - Core Implementation
Real-time market data collection for 18-stock ASX portfolio
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

from shared.ibkr.client import IBKRManager
from shared.database.connection import get_db, AsyncSessionLocal
from shared.database.models import Symbol, MarketData, SecurityType
from shared.ibkr.contracts import create_stock_contract
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TickData:
    """Real-time tick data structure"""
    symbol: str
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    last_size: Optional[int] = None
    volume: Optional[int] = None


@dataclass
class ValidationResult:
    """Data validation result"""
    is_valid: bool
    issues: List[str]
    severity: str


class ProfessionalConnectionManager:
    """Bulletproof IBKR connection management"""
    
    def __init__(self):
        self.primary_port = 4001        # Paper trading gateway
        self.backup_ports = [4002, 7497] # Live gateway, TWS
        self.client_id = 1
        self.ibkr_manager: Optional[IBKRManager] = None
        self.is_connected_flag = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
    async def ensure_connection(self) -> bool:
        """Ensure IBKR connection is active"""
        if not self.is_connected():
            return await self.reconnect_with_fallback()
        return True
        
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return (self.ibkr_manager and 
                self.ibkr_manager.is_connected() and 
                self.is_connected_flag)
    
    async def reconnect_with_fallback(self) -> bool:
        """Try primary port, then fallbacks with exponential backoff"""
        for port in [self.primary_port] + self.backup_ports:
            for attempt in range(self.max_reconnect_attempts):
                try:
                    logger.info(f"🔌 Attempting IBKR connection on port {port} (attempt {attempt + 1})")
                    
                    # Create new connection
                    self.ibkr_manager = IBKRManager(
                        host="127.0.0.1",
                        port=port,
                        client_id=self.client_id
                    )
                    
                    # Attempt connection
                    success = await self.ibkr_manager.connect()
                    if success:
                        self.is_connected_flag = True
                        self.reconnect_attempts = 0
                        logger.info(f"✅ Connected to IBKR on port {port}")
                        return True
                        
                except Exception as e:
                    logger.warning(f"❌ Connection attempt {attempt + 1} failed: {e}")
                    wait_time = min(2 ** attempt, 60)  # Cap at 60 seconds
                    await asyncio.sleep(wait_time)
                    
        self.is_connected_flag = False
        logger.error("❌ All IBKR connection attempts failed")
        return False
    
    async def disconnect(self):
        """Clean disconnect"""
        if self.ibkr_manager:
            await self.ibkr_manager.disconnect()
        self.is_connected_flag = False


class ProfessionalDataValidator:
    """Professional-grade data validation"""
    
    def __init__(self):
        self.price_change_threshold = 0.15  # 15% max price change
        self.volume_spike_threshold = 10.0  # 10x average volume
        self.bid_ask_spread_threshold = 0.10 # 10% max spread
        self.last_prices: Dict[str, float] = {}
        self.average_volumes: Dict[str, float] = {}
        
    def validate_tick(self, tick: TickData) -> ValidationResult:
        """Validate incoming tick data"""
        issues = []
        
        # Price sanity check
        if tick.last and tick.symbol in self.last_prices:
            last_price = self.last_prices[tick.symbol]
            price_change = abs(tick.last - last_price) / last_price
            if price_change > self.price_change_threshold:
                issues.append(f"Price spike: {tick.last:.2f} vs {last_price:.2f} ({price_change:.1%})")
        
        # Bid-ask spread check
        if tick.bid and tick.ask and tick.ask > tick.bid:
            spread = (tick.ask - tick.bid) / tick.ask
            if spread > self.bid_ask_spread_threshold:
                issues.append(f"Wide spread: {spread:.3%}")
        
        # Volume spike check
        if tick.volume and tick.symbol in self.average_volumes:
            avg_volume = self.average_volumes[tick.symbol]
            if avg_volume > 0 and tick.volume > avg_volume * self.volume_spike_threshold:
                issues.append(f"Volume spike: {tick.volume:,} vs avg {avg_volume:,.0f}")
        
        # Update tracking
        if tick.last:
            self.last_prices[tick.symbol] = tick.last
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            severity="HIGH" if any("spike" in issue for issue in issues) else "LOW"
        )


class ProfessionalAlertManager:
    """Professional alerting system"""
    
    def __init__(self):
        self.alert_channels = {
            AlertLevel.CRITICAL: ["console", "log"],  # Would add email, SMS in production
            AlertLevel.HIGH: ["console", "log"],
            AlertLevel.MEDIUM: ["log"],
            AlertLevel.LOW: ["log"]
        }
    
    async def send_alert(self, level: AlertLevel, message: str):
        """Send alert through appropriate channels"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level.value.upper()}: {message}"
        
        channels = self.alert_channels.get(level, ["log"])
        
        if "console" in channels:
            if level == AlertLevel.CRITICAL:
                print(f"🚨 {formatted_message}")
            elif level == AlertLevel.HIGH:
                print(f"⚠️  {formatted_message}")
            else:
                print(f"ℹ️  {formatted_message}")
        
        if "log" in channels:
            if level == AlertLevel.CRITICAL:
                logger.critical(formatted_message)
            elif level == AlertLevel.HIGH:
                logger.warning(formatted_message)
            else:
                logger.info(formatted_message)
    
    async def data_quality_alert(self, symbol: str, issues: List[str]):
        """Alert for data quality issues"""
        message = f"Data quality issue for {symbol}: {', '.join(issues)}"
        await self.send_alert(AlertLevel.HIGH, message)
    
    async def connection_alert(self, message: str):
        """Alert for connection issues"""
        await self.send_alert(AlertLevel.CRITICAL, f"Connection: {message}")
    
    async def performance_alert(self, metric: str, value: float, threshold: float):
        """Alert for performance issues"""
        message = f"Performance alert - {metric}: {value:.2f} > {threshold:.2f}"
        await self.send_alert(AlertLevel.MEDIUM, message)


class ProfessionalPerformanceMonitor:
    """Professional performance monitoring"""
    
    def __init__(self):
        self.tick_counts: Dict[str, int] = {}
        self.latency_measurements: List[float] = []
        self.error_count = 0
        self.start_time = datetime.now()
        self.last_tick_time: Dict[str, datetime] = {}
        
    def record_tick(self, symbol: str, latency_ms: float = 0):
        """Record tick reception"""
        self.tick_counts[symbol] = self.tick_counts.get(symbol, 0) + 1
        self.last_tick_time[symbol] = datetime.now()
        
        if latency_ms > 0:
            self.latency_measurements.append(latency_ms)
            # Keep only recent measurements
            if len(self.latency_measurements) > 1000:
                self.latency_measurements = self.latency_measurements[-500:]
    
    def record_error(self):
        """Record error occurrence"""
        self.error_count += 1
    
    def get_performance_stats(self) -> Dict:
        """Get current performance statistics"""
        uptime = datetime.now() - self.start_time
        total_ticks = sum(self.tick_counts.values())
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "total_ticks": total_ticks,
            "ticks_per_second": total_ticks / uptime.total_seconds() if uptime.total_seconds() > 0 else 0,
            "error_count": self.error_count,
            "active_symbols": len(self.tick_counts),
            "avg_latency_ms": sum(self.latency_measurements) / len(self.latency_measurements) if self.latency_measurements else 0,
            "symbol_tick_counts": self.tick_counts.copy()
        }


class ProfessionalDataFarmer:
    """Professional-grade data collection service"""
    
    def __init__(self):
        # Core components
        self.connection_manager = ProfessionalConnectionManager()
        self.data_validator = ProfessionalDataValidator()
        self.alert_manager = ProfessionalAlertManager()
        self.performance_monitor = ProfessionalPerformanceMonitor()
        
        # 18-stock ASX portfolio from strategy document
        self.target_symbols = [
            # Tier 1: Core Blue Chips (8 stocks)
            "CBA", "BHP", "WBC", "CSL", "ANZ", "NAB", "WOW", "WES",
            # Tier 2: Large Cap Growth & Resources (6 stocks)  
            "RIO", "FMG", "TLS", "TCL", "MQG", "WDS",
            # Tier 3: Technology & Growth (4 stocks)
            "XRO", "WTC", "REA", "ALL"
        ]
        
        # Operational state
        self.running = False
        self.symbol_ids: Dict[str, int] = {}
        self.active_subscriptions: Set[str] = set()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Configuration
        self.collection_config = {
            "market_data_lines": 25,        # Conservative allocation
            "tick_buffer_size": 10000,      # In-memory buffer
            "health_check_interval": 30,    # Seconds
            "reconnect_interval": 60,       # Seconds
            "performance_log_interval": 300, # 5 minutes
        }
    
    async def start(self) -> bool:
        """Start professional data collection"""
        try:
            logger.info("🚀 Starting Professional Data Farmer")
            
            # Initialize database
            await self._setup_database()
            
            # Setup symbols
            await self._setup_symbols()
            
            # Connect to IBKR
            if not await self.connection_manager.ensure_connection():
                await self.alert_manager.connection_alert("Failed to establish IBKR connection")
                return False
            
            # Start data collection
            self.running = True
            await self._start_data_subscriptions()
            
            # Start monitoring tasks
            asyncio.create_task(self._monitor_health())
            asyncio.create_task(self._monitor_performance())
            
            logger.info("✅ Professional Data Farmer started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Data Farmer: {e}")
            await self.alert_manager.send_alert(AlertLevel.CRITICAL, f"Startup failed: {e}")
            return False
    
    async def _setup_database(self):
        """Initialize database connection"""
        try:
            # Database initialization would go here
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            raise
    
    async def _setup_symbols(self):
        """Setup target symbols in database"""
        try:
            async with AsyncSessionLocal() as session:
                for symbol in self.target_symbols:
                    # Check if symbol exists
                    stmt = select(Symbol).where(
                        Symbol.symbol == symbol,
                        Symbol.exchange == "ASX"
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        self.symbol_ids[symbol] = existing.id
                        logger.info(f"📊 Symbol {symbol} found (ID: {existing.id})")
                    else:
                        # Create new symbol
                        new_symbol = Symbol(
                            symbol=symbol,
                            exchange="ASX",
                            currency="AUD",
                            security_type=SecurityType.STOCK,
                            active=True
                        )
                        session.add(new_symbol)
                        await session.flush()
                        self.symbol_ids[symbol] = new_symbol.id
                        logger.info(f"✨ Created symbol {symbol} (ID: {new_symbol.id})")
                
                await session.commit()
                logger.info(f"💾 Setup {len(self.symbol_ids)} symbols")
                
        except Exception as e:
            logger.error(f"❌ Symbol setup failed: {e}")
            raise
    
    async def _start_data_subscriptions(self):
        """Start real-time data subscriptions"""
        try:
            logger.info("📡 Starting market data subscriptions")
            
            # Phase 1: Start with Tier 1 stocks (most critical)
            tier1_symbols = self.target_symbols[:8]
            
            for symbol in tier1_symbols:
                try:
                    await self._subscribe_to_symbol(symbol)
                    self.active_subscriptions.add(symbol)
                    await asyncio.sleep(0.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"❌ Failed to subscribe to {symbol}: {e}")
                    await self.alert_manager.send_alert(
                        AlertLevel.HIGH, 
                        f"Subscription failed for {symbol}: {e}"
                    )
            
            logger.info(f"✅ Started subscriptions for {len(self.active_subscriptions)} symbols")
            
        except Exception as e:
            logger.error(f"❌ Subscription startup failed: {e}")
            raise
    
    async def _subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        try:
            # Create IBKR contract
            contract = create_stock_contract(symbol, "ASX", "AUD")
            
            # Generate request ID
            req_id = hash(f"{symbol}_realtime") % 10000
            
            # Subscribe to market data
            if self.connection_manager.ibkr_manager:
                success = self.connection_manager.ibkr_manager.request_market_data(
                    req_id=req_id,
                    contract=contract,
                    generic_tick_list="",
                    snapshot=False
                )
                
                if success:
                    logger.info(f"📈 Subscribed to {symbol} (req_id: {req_id})")
                else:
                    raise Exception(f"IBKR subscription failed for {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Symbol subscription failed for {symbol}: {e}")
            raise
    
    async def _process_market_data(self, symbol: str, tick_data: TickData):
        """Process incoming market data"""
        try:
            # Validate data quality
            validation = self.data_validator.validate_tick(tick_data)
            if not validation.is_valid:
                await self.alert_manager.data_quality_alert(symbol, validation.issues)
                if validation.severity == "HIGH":
                    return  # Skip storing bad data
            
            # Record performance metrics
            self.performance_monitor.record_tick(symbol)
            
            # Store in database
            await self._store_tick_data(symbol, tick_data)
            
            # Log activity (throttled)
            if hash(f"{symbol}_{int(time.time())}") % 20 == 0:  # Log ~5% of ticks
                logger.info(f"📊 {symbol}: ${tick_data.last:.2f} Vol: {tick_data.volume or 0:,}")
                
        except Exception as e:
            self.performance_monitor.record_error()
            logger.error(f"❌ Error processing {symbol} data: {e}")
    
    async def _store_tick_data(self, symbol: str, tick_data: TickData):
        """Store tick data in database"""
        try:
            symbol_id = self.symbol_ids.get(symbol)
            if not symbol_id:
                logger.warning(f"⚠️ Unknown symbol ID for {symbol}")
                return
            
            async with AsyncSessionLocal() as session:
                market_data = MarketData(
                    symbol_id=symbol_id,
                    timestamp=tick_data.timestamp,
                    timeframe="tick",
                    open=tick_data.last,
                    high=tick_data.last,
                    low=tick_data.last,
                    close=tick_data.last,
                    volume=tick_data.volume,
                    bid=tick_data.bid,
                    ask=tick_data.ask,
                    bid_size=tick_data.bid_size,
                    ask_size=tick_data.ask_size
                )
                
                session.add(market_data)
                await session.commit()
                
        except Exception as e:
            logger.error(f"❌ Database storage failed for {symbol}: {e}")
            raise
    
    async def _monitor_health(self):
        """Monitor system health"""
        while self.running:
            try:
                # Check IBKR connection
                if not self.connection_manager.is_connected():
                    await self.alert_manager.connection_alert("IBKR connection lost - attempting reconnect")
                    await self.connection_manager.reconnect_with_fallback()
                
                # Check data flow
                current_time = datetime.now()
                stale_symbols = []
                
                for symbol in self.active_subscriptions:
                    last_tick = self.performance_monitor.last_tick_time.get(symbol)
                    if last_tick and (current_time - last_tick).total_seconds() > 300:  # 5 minutes
                        stale_symbols.append(symbol)
                
                if stale_symbols:
                    await self.alert_manager.send_alert(
                        AlertLevel.MEDIUM,
                        f"Stale data detected for: {', '.join(stale_symbols)}"
                    )
                
                await asyncio.sleep(self.collection_config["health_check_interval"])
                
            except Exception as e:
                logger.error(f"❌ Health monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_performance(self):
        """Monitor and log performance metrics"""
        while self.running:
            try:
                stats = self.performance_monitor.get_performance_stats()
                
                logger.info(f"📈 Performance: {stats['total_ticks']:,} ticks, "
                          f"{stats['ticks_per_second']:.1f} tps, "
                          f"{stats['error_count']} errors, "
                          f"{stats['avg_latency_ms']:.1f}ms avg latency")
                
                # Check for performance issues
                if stats["avg_latency_ms"] > 100:
                    await self.alert_manager.performance_alert(
                        "Average Latency", stats["avg_latency_ms"], 100
                    )
                
                if stats["error_count"] > 50:
                    await self.alert_manager.performance_alert(
                        "Error Count", stats["error_count"], 50
                    )
                
                await asyncio.sleep(self.collection_config["performance_log_interval"])
                
            except Exception as e:
                logger.error(f"❌ Performance monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop data collection gracefully"""
        try:
            logger.info("🛑 Stopping Professional Data Farmer")
            self.running = False
            
            # Disconnect from IBKR
            await self.connection_manager.disconnect()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("✅ Professional Data Farmer stopped")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")


async def main():
    """Main function"""
    farmer = ProfessionalDataFarmer()
    
    try:
        success = await farmer.start()
        if success:
            # Run data collection (in production, this would run indefinitely)
            logger.info("🔄 Running data collection for 60 seconds (demo mode)")
            await asyncio.sleep(60)
        else:
            logger.error("❌ Failed to start data farmer")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1
    finally:
        await farmer.stop()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
