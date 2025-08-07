# Professional Data Collection Architecture Decision
**SCIZOR Implementation Strategy - Database-Driven Hybrid Architecture**

**Updated**: August 7, 2025  
**Decision**: Hybrid architecture with database-driven configuration  
**Context**: Professional day-trading implementation for 18-stock ASX portfolio

---

## 🎯 Architecture Decision: Hybrid Database-Driven Approach

### **Professional Analysis: Scripts vs Server Instance**

After analyzing this like a day-trading professional would approach mission-critical infrastructure:

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

### **Component 1: Real-Time Data Collection Service**
**Purpose**: Persistent service for market hours data collection  
**Technology**: Python asyncio daemon with database-driven configuration

```python
# services/data-farmer/realtime_data_service.py
class ProfessionalRealtimeDataService:
    """Persistent real-time data collection service."""
    
    def __init__(self):
        self.watchlist_manager = DatabaseWatchlistManager()
        self.rate_limiter = CentralizedRateLimiter(max_requests_per_minute=5)
        self.connection_manager = ProfessionalConnectionManager()
        self.data_validator = RealTimeDataValidator()
        
    async def start_market_hours_collection(self):
        """Start persistent data collection during market hours."""
        while self.is_market_hours():
            try:
                # Load current watchlist from database (no restart needed)
                active_symbols = await self.watchlist_manager.get_active_symbols()
                
                # Manage real-time subscriptions with rate limiting
                await self.manage_subscriptions(active_symbols)
                
                # Process incoming data with validation
                await self.process_realtime_data()
                
                # Health monitoring and alerts
                await self.monitor_service_health()
                
                await asyncio.sleep(1)  # 1-second processing loop
                
            except Exception as e:
                await self.handle_service_error(e)
```

### **Component 2: Scheduled Historical Data Scripts**
**Purpose**: Non-overlapping historical data collection and gap filling  
**Technology**: Individual Python scripts with file-based locking

```python
# scripts/professional_historical_collection.py
class ProfessionalHistoricalCollector:
    """Scheduled historical data collection with bulletproof locking."""
    
    def __init__(self):
        self.lock_file = "/tmp/scizor_historical.lock" 
        self.watchlist_manager = DatabaseWatchlistManager()
        self.rate_limiter = HistoricalRateLimiter(max_requests_per_10min=50)
        
    async def collect_historical_data(self):
        """Collect historical data with professional locking."""
        if self.is_locked():
            logger.warning("Historical collection already running - exiting")
            return
            
        with self.acquire_lock():
            # Load watchlist priorities from database
            symbols = await self.watchlist_manager.get_symbols_by_priority()
            
            # Process with strict rate limiting
            for symbol in symbols:
                await self.rate_limiter.wait_if_needed()
                await self.collect_symbol_history(symbol)
```

### **Component 3: Database-Driven Watchlist Configuration**
**Purpose**: Dynamic symbol management without code changes  
**Technology**: PostgreSQL watchlist table with real-time configuration

```sql
-- Professional 18-stock ASX portfolio configuration
-- Can be updated without restarting services

-- Tier 1: Core 8 stocks (highest priority, 5min + 1min collection)
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)
SELECT s.id, 'asx_professional', 1, true, true, 'Tier 1: Core blue chip - maximum data'
FROM symbols s 
WHERE s.symbol IN ('CBA', 'BHP', 'CSL', 'WBC', 'ANZ', 'NAB', 'WOW', 'WES');

-- Tier 2: Growth 6 stocks (high priority, 5min collection)  
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)
SELECT s.id, 'asx_professional', 2, true, false, 'Tier 2: Growth/Resources - 5min data'
FROM symbols s 
WHERE s.symbol IN ('RIO', 'MQG', 'FMG', 'TLS', 'TCL', 'COL');

-- Tier 3: Technology 4 stocks (medium priority, 5min collection)
INSERT INTO watchlist (symbol_id, name, priority, collect_5min, collect_1min, notes)  
SELECT s.id, 'asx_professional', 3, true, false, 'Tier 3: Technology - opportunity tracking'
FROM symbols s 
WHERE s.symbol IN ('XRO', 'WTC', 'APT', 'ZIP');
```

---

## 🔄 Implementation Strategy

### **Phase 1: Database-Driven Foundation (Week 1)**

#### **1.1 Populate 18-Stock ASX Strategy**
```bash
# Create professional watchlist configuration
python scripts/populate_asx_professional_watchlist.py

# Verify configuration
python scripts/manage_watchlist.py list --name asx_professional
```

#### **1.2 Enhanced Connection Management**  
```python
class ProfessionalConnectionManager:
    """Bulletproof IBKR connection management."""
    
    def __init__(self):
        self.max_retries = 5
        self.backoff_multiplier = 2
        self.health_check_interval = 30
        self.connection_timeout = 60
        
    async def maintain_connection(self):
        """Continuous connection health monitoring."""
        while True:
            if not self.is_connected():
                await self.reconnect_with_backoff()
            await asyncio.sleep(self.health_check_interval)
```

#### **1.3 Professional Data Validation**
```python
class ProfessionalDataValidator:
    """Real-time data quality assurance."""
    
    def validate_tick_data(self, tick: TickData) -> bool:
        """Professional-grade tick validation."""
        # Price sanity checks
        if not self.is_price_reasonable(tick.price):
            return False
            
        # Market hours validation
        if not self.is_market_hours(tick.timestamp):
            return False
            
        # Volume spike detection
        if self.is_volume_anomaly(tick.volume):
            self.flag_for_review(tick)
            
        return True
```

### **Phase 2: Service Integration (Week 2)**

#### **2.1 Orchestrated Service Management**
```python
# docker-compose.professional.yml
services:
  realtime-data-service:
    build: ./services/data-farmer
    command: python professional_realtime_service.py
    restart: always
    depends_on: [postgres, redis]
    environment:
      - WATCHLIST_NAME=asx_professional
      - COLLECTION_MODE=realtime
      
  historical-data-cron:
    build: ./scripts
    command: cron -f
    volumes:
      - ./scripts/crontab:/etc/cron.d/scizor-cron
```

#### **2.2 Professional Service Monitoring**
```python
class ServiceHealthMonitor:
    """Professional system health monitoring."""
    
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

## 📊 Professional KPIs & Monitoring

### **Real-Time Dashboard Metrics**
```python
PROFESSIONAL_KPIS = {
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

### **Professional Alert System**
```python
class ProfessionalAlertManager:
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

### **Professional Deployment Strategy**
```yaml
# docker-compose.professional.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_DB: scizor_professional
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
      dockerfile: services/data-farmer/Dockerfile.professional
    restart: always
    depends_on: [postgres, redis]
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - WATCHLIST_NAME=asx_professional
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
python scripts/professional_health_check.py

# 2. Add new symbol to watchlist
python scripts/manage_watchlist.py add --symbol "NEW" --name asx_professional --priority 2

# 3. Monitor real-time performance
python scripts/monitor_professional_performance.py --dashboard

# 4. Emergency service restart
docker-compose -f docker-compose.professional.yml restart realtime-data-service
```

---

## ✅ Implementation Checklist

### **Week 1: Foundation**
- [ ] Create `populate_asx_professional_watchlist.py` script
- [ ] Implement `ProfessionalConnectionManager` class
- [ ] Build `ProfessionalDataValidator` with market hours logic
- [ ] Create `DatabaseWatchlistManager` for dynamic configuration
- [ ] Set up professional logging and error handling

### **Week 2: Service Integration** 
- [ ] Implement `ProfessionalRealtimeDataService` daemon
- [ ] Create professional cron scripts with file locking
- [ ] Build `ServiceHealthMonitor` with comprehensive KPIs
- [ ] Implement `ProfessionalAlertManager` with Slack/email integration
- [ ] Set up monitoring dashboard with real-time metrics

### **Week 3: Production Readiness**
- [ ] Professional Docker deployment configuration
- [ ] Comprehensive testing with 18-stock portfolio
- [ ] Performance optimization and tuning
- [ ] Documentation and operational procedures
- [ ] Production deployment and monitoring setup

This hybrid architecture provides the reliability and control of a professional trading operation while maintaining the flexibility to adapt to changing market conditions and strategy requirements.
