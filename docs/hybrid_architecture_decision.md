#  Data Collection Architecture Decision
**SCIZOR Implementation Strategy - Database-Driven Hybrid Architecture**

**Updated**: August 7, 2025  
**Decision**: Hybrid architecture with database-driven configuration  
**Context**:  day-trading implementation for 18-stock ASX portfolio

---

## 🎯 Architecture Decision: Hybrid Database-Driven Approach

### ** Analysis: Scripts vs Server Instance**

After analyzing this like a day-trading  would approach mission-critical infrastructure:

**Winner**: **Hybrid Architecture** - Combines reliability of dedicated servers with flexibility of scripts

#### **Decision Matrix**

| Requirement | Centralized Server | Cron Scripts | **Hybrid Solution** |
|-------------|-------------------|--------------|-------------------|
| **Rate Limiting Coordination** | ✅ Perfect | ❌ Risky overlaps | ✅ **Perfect coordination** |
| **Real-time Data Quality** | ✅ Excellent | ❌ Batch only | ✅ **Real-time monitoring** |
| **System Reliability** | ⚠️ Single point failure | ✅ Fault tolerant | ✅ **Best of both** |
| **Operational Simplicity** | ❌ Complex monitoring | ✅ Simple restart | ✅ **Proper separation** |
| **Database Configuration** | ✅ Dynamic reload | ✅ Query on start | ✅ **Dynamic + scheduled** |
| **IBKR Free-Tier Limits** | ✅ Perfect control | ⚠️ Manual coordination | ✅ **Bulletproof limits** |

---

## 🏗️ Hybrid Architecture Implementation

### **Component 1: FastAPI Collector Service**
**Purpose**: High-performance real-time data collection and API management  
**Technology**: FastAPI + asyncio for  trading performance

```python
# services/collector/main.py
from fastapi import FastAPI, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .services.realtime_collector import RealtimeCollector
from .services.watchlist_manager import DatabaseWatchlistManager
from .services.rate_limiter import CentralizedRateLimiter

app = FastAPI(
    title="SCIZOR  Data Collector",
    description="Institutional-grade market data collection",
    version="1.0.0"
)

#  background services
collector_service = RealtimeCollector()
watchlist_manager = DatabaseWatchlistManager()
rate_limiter = CentralizedRateLimiter()

@app.on_event("startup")
async def startup_event():
    """Initialize  data collection services."""
    await collector_service.start__collection()
    
@app.websocket("/ws/realtime")
async def websocket_realtime_data(websocket: WebSocket):
    """Real-time data streaming for trading interfaces."""
    await collector_service.stream_realtime_data(websocket)

@app.get("/api/watchlist")
async def get__watchlist():
    """Get current  watchlist configuration."""
    return await watchlist_manager.get_asx__config()
```

### **Component 2: Integrated Cron Scripts**
**Purpose**: Scheduled historical data collection and maintenance  
**Technology**: Enhanced Python scripts within collector service structure

```python
# services/collector/scripts/historical_collection.py
class HistoricalCollector:
    """Integrated historical data collection with FastAPI coordination."""
    
    def __init__(self):
        self.lock_file = "/tmp/scizor_historical.lock"
        self.api_client = CollectorAPIClient()  # Internal API communication
        self.rate_limiter = CentralizedRateLimiter()
        
    async def run_scheduled_collection(self):
        """ scheduled collection with API coordination."""
        if self.is_locked():
            return
            
        with self.acquire_lock():
            # Coordinate with main collector service via API
            watchlist = await self.api_client.get_active_watchlist()
            
            # Use centralized rate limiter
            for symbol in watchlist:
                await self.rate_limiter.acquire_historical_slot()
                await self.collect_symbol_history(symbol)
```

### **Component 3:  Service Coordination**
**Purpose**: Unified service management and monitoring  
**Technology**: FastAPI lifespan events + background task coordination

```python
# services/collector/services/service_coordinator.py
class ServiceCoordinator:
    """Coordinates all data collection components through FastAPI."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.realtime_service = RealtimeCollector()
        self.historical_scheduler = HistoricalCollectionScheduler()
        self.health_monitor = ServiceHealthMonitor()
        
    async def start__operation(self):
        """Start coordinated  data collection."""
        # Start real-time collection as FastAPI background task
        self.app.add_task(self.realtime_service.run_continuous_collection)
        
        # Schedule historical collection
        self.app.add_task(self.historical_scheduler.run_scheduled_tasks)
        
        # Start health monitoring
        self.app.add_task(self.health_monitor.monitor_all_services)
```

```sql
--  18-stock ASX portfolio configuration
-- Can be updated without restarting services

-- Tier 1: Core 8 stocks (highest priority, 5min + 1min collection)
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)
SELECT s.id, 'asx_', 1, true, true, 'Tier 1: Core blue chip - maximum data'
FROM symbols s 
WHERE s.symbol IN ('CBA', 'BHP', 'CSL', 'WBC', 'ANZ', 'NAB', 'WOW', 'WES');

-- Tier 2: Growth 6 stocks (high priority, 5min collection)  
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)
SELECT s.id, 'asx_', 2, true, false, 'Tier 2: Growth/Resources - 5min data'
FROM symbols s 
WHERE s.symbol IN ('RIO', 'MQG', 'FMG', 'TLS', 'TCL', 'COL');

-- Tier 3: Technology 4 stocks (medium priority, 5min collection)
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)  
SELECT s.id, 'asx_', 3, true, false, 'Tier 3: Technology - opportunity tracking'
FROM symbols s 
WHERE s.symbol IN ('XRO', 'WTC', 'APT', 'ZIP');
```

---

## 🔄 Implementation Strategy

### **Phase 1: FastAPI Collector Foundation (Week 1)**

#### **1.1  Collector Service Setup**
```bash
# Create  collector service structure
mkdir -p services/collector/{app,scripts,services,tests}
mkdir -p services/collector/app/{api,core,models}

# Initialize FastAPI application
touch services/collector/main.py
touch services/collector/app/{__init__.py,config.py}
touch services/collector/app/api/{__init__.py,watchlist.py,collection.py,monitoring.py}
```

#### **1.2  Service Architecture**  
```python
# services/collector/app/core/service_manager.py
class ServiceManager:
    """Manages all collector services through FastAPI."""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.watchlist_manager = DatabaseWatchlistManager()
        self.rate_limiter = CentralizedRateLimiter()
        
    async def start_all_services(self):
        """Start coordinated  services."""
        await self.connection_manager.establish__connection()
        await self.watchlist_manager.load_asx__config()
        await self.rate_limiter.initialize_coordination()
```

#### **1.3 Integrated Cron Scripts Enhancement**
```python
# services/collector/scripts/cron_coordinator.py
class CronScriptCoordinator:
    """Coordinates cron scripts with main collector service."""
    
    def __init__(self):
        self.api_client = InternalCollectorAPI()
        self.scripts = {
            'historical': HistoricalCollectionScript(),
            'daily': DailyCollectionScript(),
            'maintenance': DatabaseMaintenanceScript()
        }
    
    async def run_coordinated_script(self, script_name: str):
        """Run script with collector service coordination."""
        # Check if collector service allows script execution
        if await self.api_client.can_run_script(script_name):
            await self.scripts[script_name].execute()
```

### **Phase 2: Service Integration (Week 2)**

#### **2.1 Orchestrated Service Management**
```python
# docker-compose..yml
services:
  realtime-data-service:
    build: ./services/data-farmer
    command: python _realtime_service.py
    restart: always
    depends_on: [postgres, redis]
    environment:
      - WATCHLIST_NAME=asx_
      - COLLECTION_MODE=realtime
      
  historical-data-cron:
    build: ./scripts
    command: cron -f
    volumes:
      - ./scripts/crontab:/etc/cron.d/scizor-cron
```

#### **2.2  Service Monitoring**
```python
class ServiceHealthMonitor:
    """ system health monitoring."""
    
    async def monitor_all_services(self):
        """Continuous health monitoring with alerts."""
        while True:
            # Check real-time service health
            if not await self.check_realtime_service():
                await self.alert_critical("Realtime service down")
                
            # Check data freshness
            data_age = await self.get_latest_data_age()
            if data_age > timedelta(minutes=10):
                await self.alert_warning(f"Data stale: {data_age}")
                
            # Check rate limiting compliance
            current_rate = await self.get_current_request_rate()
            if current_rate > self.max_allowed_rate:
                await self.alert_critical("Rate limit exceeded")
                
            await asyncio.sleep(60)  # Check every minute
```

---

## 📊  KPIs & Monitoring

### **Real-Time Dashboard Metrics**
```python
_KPIS = {
    "data_latency": {
        "target": "< 100ms",
        "alert_threshold": "500ms",
        "critical_threshold": "2000ms"
    },
    "data_completeness": {
        "target": "> 99.5%",
        "alert_threshold": "< 98%", 
        "critical_threshold": "< 95%"
    },
    "connection_uptime": {
        "target": "> 99.9%",
        "alert_threshold": "< 99%",
        "critical_threshold": "< 95%"
    },
    "rate_limit_utilization": {
        "target": "< 80%",
        "alert_threshold": "> 90%",
        "critical_threshold": "> 95%"
    }
}
```

### ** Alert System**
```python
class AlertManager:
    """Institutional-grade alerting system."""
    
    async def send_critical_alert(self, message: str):
        """Critical alerts - immediate attention required."""
        await self.send_email_alert(message, priority="CRITICAL")
        await self.send_slack_alert(message, channel="#trading-alerts")
        await self.log_alert_to_database(message, level="CRITICAL")
        
    async def send_performance_alert(self, metric: str, value: float, threshold: float):
        """Performance degradation alerts."""
        message = f"Performance Alert: {metric} = {value} (threshold: {threshold})"
        await self.send_slack_alert(message, channel="#trading-performance")
```

---

## 🎯 Deployment & Operations

### ** Deployment Strategy**
```yaml
# docker-compose..yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_DB: scizor_
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7-alpine
    restart: always
    
  realtime-data-service:
    build: 
      context: .
      dockerfile: services/data-farmer/Dockerfile.
    restart: always
    depends_on: [postgres, redis]
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - WATCHLIST_NAME=asx_
    volumes:
      - ./logs:/app/logs
      
  monitoring-dashboard:
    build: ./monitoring
    ports:
      - "3000:3000"
    depends_on: [postgres, redis]
```

### **Operational Procedures**
```bash
# Daily operational commands

# 1. Check system health
python scripts/_health_check.py

# 2. Add new symbol to watchlist
python scripts/manage_watchlist.py add --symbol "NEW" --name asx_ --priority 2

# 3. Monitor real-time performance
python scripts/monitor__performance.py --dashboard

# 4. Emergency service restart
docker-compose -f docker-compose..yml restart realtime-data-service
```

---

## ✅ Implementation Checklist

### **Week 1: FastAPI Collector Foundation**
- [ ] Create `services/collector/` FastAPI application structure
- [ ] Implement  async API endpoints for data collection control
- [ ] Build WebSocket endpoints for real-time data streaming  
- [ ] Create  health monitoring and metrics API endpoints
- [ ] Integrate existing database models and IBKR client with FastAPI dependencies

### **Week 2: Service Integration & Cron Scripts** 
- [ ] Implement FastAPI background tasks for persistent real-time data collection
- [ ] Enhance and integrate cron scripts within `services/collector/scripts/`
- [ ] Build comprehensive KPI monitoring via `/api/metrics` endpoints
- [ ] Create  alerting system with API integration
- [ ] Set up coordinated rate limiting through FastAPI middleware

### **Week 3: Production Deployment**
- [ ]  Docker deployment with FastAPI service configuration
- [ ] Comprehensive API testing with 18-stock portfolio endpoints
- [ ] FastAPI performance optimization and async middleware tuning
- [ ] Production monitoring dashboards and operational API procedures
- [ ] Full integration testing of collector service with existing SCIZOR components

This hybrid architecture provides the reliability and control of a  trading operation while maintaining the flexibility to adapt to changing market conditions and strategy requirements.
