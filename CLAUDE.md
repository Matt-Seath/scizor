# Algorithmic Trading System - CLAUDE.md

## Project Overview

**Project Name**: ASX200 Swing Trading Algorithm  
**Purpose**: Automated algorithmic trading system for ASX200 stocks using swing trading strategies  
**Target User**: Professional day-trader with limited time for active management  
**Primary Goal**: Generate consistent returns with minimal maintenance through automated trading  

### Key Constraints & Requirements
- **Data Source**: IBKR TWS API (free tier) - must respect rate limits
- **Market Focus**: ASX200 exchange only
- **Trading Style**: Swing trading (2-10 day holding periods)
- **Maintenance**: Low-maintenance, highly automated
- **Risk Management**: Conservative approach with strict controls

## Technical Stack

### Core Technologies
- **Backend**: Python 3.11+
- **Web Framework**: FastAPI
- **Database**: PostgreSQL 15+
- **Task Queue**: Celery with Redis
- **Market Data**: IBKR TWS API
- **Deployment**: Docker + Docker Compose
- **Monitoring**: Prometheus + Grafana
- **Logging**: Python logging + ELK stack

### Why These Choices
- **Python**: Extensive financial libraries (pandas, numpy, TA-Lib)
- **FastAPI**: High performance, automatic API docs, async support
- **PostgreSQL**: ACID compliance critical for financial data
- **Celery**: Reliable task scheduling for market operations
- **Docker**: Consistent deployment across environments

## System Architecture

```
algotrading-system/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Environment configurations
│   │   └── database.py         # Database connection setup
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py         # Authentication & authorization
│   │   ├── middleware.py       # Custom middleware
│   │   └── exceptions.py       # Custom exception handlers
│   ├── data/
│   │   ├── __init__.py
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── ibkr_client.py  # IBKR TWS API client
│   │   │   ├── market_data.py  # Market data collection
│   │   │   └── fundamental.py  # Fundamental data collector
│   │   ├── processors/
│   │   │   ├── __init__.py
│   │   │   ├── technical.py    # Technical indicators
│   │   │   ├── signals.py      # Trading signal generation
│   │   │   └── validation.py   # Data quality validation
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── market.py       # Market data models
│   │       ├── signals.py      # Signal models
│   │       └── portfolio.py    # Portfolio models
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py             # Base strategy class
│   │   ├── momentum.py         # Momentum breakout strategy
│   │   ├── mean_reversion.py   # Mean reversion strategy
│   │   ├── earnings.py         # Earnings momentum strategy
│   │   └── portfolio.py        # Portfolio allocation logic
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── manager.py          # Risk management engine
│   │   ├── position_sizing.py  # Position sizing algorithms
│   │   ├── stops.py            # Stop loss management
│   │   └── limits.py           # Risk limit enforcement
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py    # Order execution logic
│   │   ├── slippage.py         # Slippage estimation
│   │   └── fills.py            # Fill processing
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py           # Backtesting engine
│   │   ├── metrics.py          # Performance metrics
│   │   └── reports.py          # Backtest reporting
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py    # Dashboard endpoints
│   │   │   ├── portfolio.py    # Portfolio endpoints
│   │   │   ├── strategies.py   # Strategy endpoints
│   │   │   ├── risk.py         # Risk monitoring endpoints
│   │   │   └── health.py       # Health check endpoints
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── data_collection.py  # Scheduled data collection
│   │   ├── signal_generation.py # Signal generation tasks
│   │   ├── trading.py          # Trading execution tasks
│   │   └── monitoring.py       # System monitoring tasks
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging.py          # Logging configuration
│   │   ├── metrics.py          # Performance metrics
│   │   ├── notifications.py    # Alert system
│   │   └── helpers.py          # Utility functions
│   └── db/
│       ├── __init__.py
│       ├── base.py             # Base database classes
│       ├── migrations/         # Database migrations
│       └── seeds/              # Initial data seeds
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest configuration
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fixtures/               # Test data fixtures
├── scripts/
│   ├── setup_db.py             # Database setup script
│   ├── seed_data.py            # Data seeding script
│   └── deploy.py               # Deployment script
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── nginx.conf
├── docs/
│   ├── api.md                  # API documentation
│   ├── strategies.md           # Strategy documentation
│   └── deployment.md           # Deployment guide
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## Database Schema Design

### Core Tables

```sql
-- Market data storage
CREATE TABLE daily_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,4) NOT NULL,
    high DECIMAL(12,4) NOT NULL,
    low DECIMAL(12,4) NOT NULL,
    close DECIMAL(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    adj_close DECIMAL(12,4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date),
    INDEX idx_symbol_date (symbol, date),
    INDEX idx_date (date)
);

-- Intraday data for higher frequency strategies
CREATE TABLE intraday_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    datetime TIMESTAMP NOT NULL,
    open DECIMAL(12,4) NOT NULL,
    high DECIMAL(12,4) NOT NULL,
    low DECIMAL(12,4) NOT NULL,
    close DECIMAL(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '4H', '1H', '15m'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, datetime, timeframe),
    INDEX idx_symbol_datetime (symbol, datetime),
    INDEX idx_datetime (datetime)
);

-- Trading signals
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    signal_type VARCHAR(10) NOT NULL, -- BUY, SELL, CLOSE
    price DECIMAL(12,4) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    metadata JSONB,
    generated_at TIMESTAMP NOT NULL,
    executed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, EXECUTED, CANCELLED, EXPIRED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_generated (symbol, generated_at),
    INDEX idx_status (status),
    INDEX idx_strategy (strategy)
);

-- Portfolio positions
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL, -- LONG, SHORT
    entry_price DECIMAL(12,4) NOT NULL,
    current_price DECIMAL(12,4),
    quantity INTEGER NOT NULL,
    stop_loss DECIMAL(12,4),
    take_profit DECIMAL(12,4),
    unrealized_pnl DECIMAL(12,4),
    realized_pnl DECIMAL(12,4) DEFAULT 0,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'OPEN', -- OPEN, CLOSED, PARTIAL
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_status (symbol, status),
    INDEX idx_strategy_status (strategy, status),
    INDEX idx_opened_at (opened_at)
);

-- Order tracking
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(id),
    signal_id INTEGER REFERENCES signals(id),
    symbol VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL, -- MARKET, LIMIT, STOP, STOP_LIMIT
    side VARCHAR(10) NOT NULL, -- BUY, SELL
    quantity INTEGER NOT NULL,
    price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    filled_quantity INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(12,4),
    commission DECIMAL(8,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, FILLED, PARTIAL, CANCELLED, REJECTED
    broker_order_id VARCHAR(50),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    metadata JSONB,
    INDEX idx_symbol_status (symbol, status),
    INDEX idx_broker_order_id (broker_order_id),
    INDEX idx_submitted_at (submitted_at)
);

-- Risk metrics tracking
CREATE TABLE risk_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_exposure DECIMAL(12,4) NOT NULL,
    portfolio_value DECIMAL(12,4) NOT NULL,
    daily_pnl DECIMAL(12,4) NOT NULL,
    drawdown DECIMAL(8,4) NOT NULL,
    var_95 DECIMAL(12,4), -- Value at Risk 95%
    sharpe_ratio DECIMAL(8,4),
    max_positions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date),
    INDEX idx_date (date)
);

-- System performance metrics
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(12,4) NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metric_timestamp (metric_name, timestamp)
);

-- API request tracking for rate limiting and monitoring
CREATE TABLE api_requests (
    id SERIAL PRIMARY KEY,
    request_type VARCHAR(50) NOT NULL, -- MARKET_DATA, HISTORICAL_DATA, ORDER_PLACEMENT
    req_id INTEGER,
    symbol VARCHAR(10),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL, -- SUCCESS, FAILED, TIMEOUT, RATE_LIMITED
    error_code INTEGER,
    error_message TEXT,
    response_time_ms INTEGER,
    client_id INTEGER,
    INDEX idx_request_type_timestamp (request_type, timestamp),
    INDEX idx_status_timestamp (status, timestamp),
    INDEX idx_symbol_timestamp (symbol, timestamp)
);

-- Connection state management
CREATE TABLE connection_state (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL, -- CONNECTED, DISCONNECTED, RECONNECTING, ERROR
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error_code INTEGER,
    last_error_message TEXT,
    connection_started_at TIMESTAMP,
    last_data_received_at TIMESTAMP,
    UNIQUE(client_id),
    INDEX idx_status (status),
    INDEX idx_last_heartbeat (last_heartbeat)
);

-- Rate limiting tracking and enforcement
CREATE TABLE rate_limits (
    id SERIAL PRIMARY KEY,
    request_type VARCHAR(50) NOT NULL, -- GENERAL, HISTORICAL, MARKET_DATA
    client_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    limit_exceeded BOOLEAN DEFAULT FALSE,
    reset_at TIMESTAMP,
    INDEX idx_client_type_window (client_id, request_type, window_start),
    INDEX idx_window_end (window_end)
);

-- IBKR contract details cache
CREATE TABLE contract_details (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    con_id BIGINT NOT NULL,
    sec_type VARCHAR(10) NOT NULL, -- STK, OPT, FUT, etc.
    currency VARCHAR(10) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    primary_exchange VARCHAR(20),
    local_symbol VARCHAR(20),
    trading_class VARCHAR(20),
    min_tick DECIMAL(10,8),
    market_rule_ids TEXT, -- JSON array of market rule IDs
    contract_month VARCHAR(10),
    last_trading_day DATE,
    time_zone_id VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(con_id),
    INDEX idx_symbol_exchange (symbol, exchange),
    INDEX idx_updated_at (updated_at)
);

-- Market data subscriptions tracking
CREATE TABLE market_data_subscriptions (
    id SERIAL PRIMARY KEY,
    req_id INTEGER NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    con_id BIGINT,
    subscription_type VARCHAR(20) NOT NULL, -- LIVE, DELAYED, SNAPSHOT
    generic_tick_list VARCHAR(100),
    status VARCHAR(20) NOT NULL, -- ACTIVE, CANCELLED, ERROR
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP,
    last_update_at TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    UNIQUE(req_id),
    INDEX idx_symbol_status (symbol, status),
    INDEX idx_subscribed_at (subscribed_at)
);
```

## IBKR TWS API Integration

### Rate Limiting Strategy
- **API Limits**: 50 requests per second maximum (calculated as max market data lines ÷ 2)
- **Historical Data**: Maximum 60 requests per 10-minute period
- **Identical Requests**: 15-second minimum interval between identical requests
- **Implementation**: Use token bucket algorithm with redis-based rate limiting
- **Safety Margin**: Use 40 req/sec (80% of limit) to avoid violations
- **Batch Operations**: Group requests efficiently to minimize API calls
- **Retry Logic**: Exponential backoff with jitter for failed requests
- **Violation Recovery**: System pauses on rate limit errors (code 100)

### Market Data Subscription Requirements

**CRITICAL**: IBKR does not have a "free tier" for live market data. The system must account for subscription costs and data access levels.

#### Data Access Levels:
- **Live Data**: Real-time market data (requires paid subscription per exchange)
  - ASX Real-time: ~$45 AUD/month for professional use
  - Required for production algorithmic trading
  - Essential for accurate signal generation

- **Delayed Data**: 15-20 minute delayed data (free)
  - Available via `reqMarketDataType(3)` 
  - Suitable for backtesting and development
  - NOT suitable for live trading strategies

- **Snapshot Data**: Regulatory snapshots ($0.01 USD per request)
  - Alternative to streaming subscriptions
  - Cost-effective for infrequent price checks
  - Subject to pacing limits (1 request/second)

#### Development Strategy:
```python
# Development mode (delayed data)
self.reqMarketDataType(3)  # Delayed market data

# Production mode (live data - requires subscription)
self.reqMarketDataType(1)  # Live market data

# Fallback mode (snapshots)
self.reqMktData(reqId, contract, "", False, True, [])  # regulatorySnapshot=True
```

#### Subscription Planning:
- **Phase 1 (Development)**: Use delayed data for strategy development and backtesting
- **Phase 2 (Paper Trading)**: Test with delayed data to validate strategy logic
- **Phase 3 (Live Trading)**: Upgrade to live ASX data subscription for production
- **Cost Consideration**: Live ASX data subscription is essential operational expense

### Data Collection Schedule
```python
# ASX market hours and data collection timing
MARKET_OPEN_TIME = "10:00"   # AEST/AEDT
MARKET_CLOSE_TIME = "16:00"  # AEST/AEDT (4:00 PM, not 4:10 PM)
DATA_COLLECTION_START = "16:10"  # 10 minutes after market close
DATA_COLLECTION_DELAY = 10   # minutes after close to ensure data availability

# Rate-limited collection strategy (40 req/sec safety margin)
# Total daily requests: ~270 requests over 10 minutes
COLLECTION_STRATEGY = {
    "daily_bars_asx200": {
        "requests": 200,  # All ASX200 stocks daily OHLCV
        "batch_size": 20,  # Process in batches
        "delay_between_batches": 15  # seconds (respects rate limits)
    },
    "intraday_bars_liquid": {
        "requests": 50,   # Top 50 liquid stocks 4-hour bars
        "batch_size": 10,
        "delay_between_batches": 10
    },
    "fundamental_updates": {
        "requests": 20,   # Weekly fundamental data
        "batch_size": 5,
        "delay_between_batches": 30
    }
}

# Timezone handling for ASX
import pytz
ASX_TIMEZONE = pytz.timezone('Australia/Sydney')  # Handles AEST/AEDT automatically
```

### Connection Management
```python
# app/data/collectors/ibkr_client.py
class IBKRClient:
    def __init__(self):
        self.connection_retry_limit = 3
        self.request_timeout = 30
        self.rate_limiter = RateLimiter(40, 1)   # 40 req/sec (safety margin)
        self.historical_limiter = RateLimiter(6, 60)  # 6 req/min for historical
        
    def ensure_connection(self):
        # Implement connection health checks
        # Auto-reconnect on failures
        # Log all connection events
```

### ASX Contract Specifications

**CRITICAL**: ASX contracts require specific parameters for proper market data and order routing.

#### ASX Stock Contract Template
```python
# app/data/collectors/asx_contracts.py
from ibapi.contract import Contract

def create_asx_stock_contract(symbol: str) -> Contract:
    """Create properly formatted ASX stock contract"""
    contract = Contract()
    contract.symbol = symbol.upper()      # e.g., "BHP", "CBA", "ANZ"
    contract.secType = "STK"              # Stock
    contract.currency = "AUD"             # Australian Dollars
    contract.exchange = "ASX"             # Australian Securities Exchange
    contract.primaryExchange = "ASX"      # Required for ASX stocks
    return contract

# Example ASX200 contracts
ASX200_MAJOR_STOCKS = {
    "BHP": create_asx_stock_contract("BHP"),     # BHP Group
    "CBA": create_asx_stock_contract("CBA"),     # Commonwealth Bank
    "CSL": create_asx_stock_contract("CSL"),     # CSL Limited
    "ANZ": create_asx_stock_contract("ANZ"),     # ANZ Banking Group
    "WBC": create_asx_stock_contract("WBC"),     # Westpac Banking
    "NAB": create_asx_stock_contract("NAB"),     # National Australia Bank
    "WES": create_asx_stock_contract("WES"),     # Wesfarmers
    "MQG": create_asx_stock_contract("MQG"),     # Macquarie Group
    "TLS": create_asx_stock_contract("TLS"),     # Telstra Corporation
    "WOW": create_asx_stock_contract("WOW"),     # Woolworths Group
}
```

#### Market Hours & Trading Session Validation
```python
# app/utils/market_hours.py
import pytz
from datetime import datetime, time, timedelta

class ASXMarketHours:
    def __init__(self):
        self.timezone = pytz.timezone('Australia/Sydney')
        self.market_open = time(10, 0)   # 10:00 AM
        self.market_close = time(16, 0)  # 4:00 PM
        self.pre_market_start = time(7, 0)   # 7:00 AM (pre-market)
        self.after_hours_end = time(19, 0)   # 7:00 PM (after-hours)
    
    def is_market_open(self, dt: datetime = None) -> bool:
        """Check if ASX market is currently open"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        # Check if weekend
        if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        # Check market hours
        current_time = dt.time()
        return self.market_open <= current_time <= self.market_close
    
    def is_trading_day(self, dt: datetime = None) -> bool:
        """Check if today is a trading day (excludes weekends and holidays)"""
        if dt is None:
            dt = datetime.now(self.timezone)
            
        # Weekend check
        if dt.weekday() >= 5:
            return False
            
        # TODO: Add ASX holiday calendar check
        return True
    
    def next_market_open(self) -> datetime:
        """Get next market open time"""
        now = datetime.now(self.timezone)
        next_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # If after market close today, next open is tomorrow
        if now.time() > self.market_close:
            next_open += timedelta(days=1)
            
        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
            
        return next_open
```

#### Error Handling for ASX-Specific Issues
```python
# app/data/collectors/asx_error_handler.py
class ASXErrorHandler:
    """Handle ASX-specific API errors and contract issues"""
    
    ASX_SPECIFIC_ERRORS = {
        200: "Contract not found - check symbol exists on ASX",
        201: "Order rejected - check ASX trading rules",
        354: "Market data not subscribed - need ASX data feed",
        10089: "Delayed market data available for ASX"
    }
    
    def handle_contract_error(self, symbol: str, error_code: int) -> str:
        """Handle ASX contract-related errors"""
        if error_code == 200:
            return f"ASX symbol '{symbol}' not found. Verify it's listed on ASX200."
        elif error_code == 354:
            return f"Need ASX market data subscription for '{symbol}'. Using delayed data."
        
        return self.ASX_SPECIFIC_ERRORS.get(error_code, f"Unknown ASX error for {symbol}")
```

#### ASX200 Symbol Management
```python
# app/data/asx200_symbols.py
def get_asx200_symbols() -> List[str]:
    """
    Get current ASX200 constituent symbols.
    NOTE: ASX200 composition changes quarterly. 
    This list should be updated from official ASX source.
    """
    # Top 50 most liquid ASX200 stocks for intraday data
    TOP_50_LIQUID = [
        "BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG", "TLS", "WOW",
        "NCM", "RIO", "TCL", "GMG", "STO", "COL", "ALL", "REA", "XRO", "CPU",
        "IAG", "QBE", "ASX", "JHX", "COH", "SHL", "APT", "CAR", "LLC", "TPM",
        "WTC", "RMD", "PME", "AMP", "ORG", "AGL", "CTD", "SGP", "ALD", "CWN",
        "BOQ", "HVN", "ING", "DXS", "SKI", "NAN", "FPH", "IPL", "TWE", "ALU"
    ]
    
    # Full ASX200 list (truncated for brevity - full list needed in production)
    # Updated quarterly from: https://www.asx.com.au/products/indices/s-p-asx-200.htm
    return ASX200_SYMBOLS  # Full 200 symbol list

# Market cap tiers for strategy allocation
ASX200_TIERS = {
    "large_cap": ["BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG"],
    "mid_cap": ["TLS", "WOW", "NCM", "RIO", "TCL", "GMG", "STO", "COL"],
    "small_cap": []  # Remaining ASX200 stocks
}
```

## Trading Strategies Implementation

### 1. Momentum Breakout Strategy
```python
# app/strategies/momentum.py
class MomentumBreakoutStrategy(BaseStrategy):
    def __init__(self):
        self.lookback_period = 20
        self.volume_multiplier = 1.5
        self.min_liquidity = 500000  # AUD daily volume
        
    def generate_signals(self, data):
        # 20-day high breakout with volume confirmation
        # RSI > 50 for trend confirmation
        # Price > 20-day SMA
```

### 2. Mean Reversion Strategy
```python
# app/strategies/mean_reversion.py
class MeanReversionStrategy(BaseStrategy):
    def __init__(self):
        self.rsi_oversold = 30
        self.bollinger_period = 20
        self.bollinger_std = 2
        
    def generate_signals(self, data):
        # RSI oversold + bounce off lower Bollinger Band
        # Volume above average
        # No recent earnings events
```

### 3. Earnings Momentum Strategy
```python
# app/strategies/earnings.py
class EarningsMomentumStrategy(BaseStrategy):
    def __init__(self):
        self.post_earnings_window = 5  # days
        self.min_earnings_surprise = 0.05  # 5%
        
    def generate_signals(self, data):
        # Post-earnings drift detection
        # Analyst upgrade/downgrade reactions
        # Revenue/EPS surprise reactions
```

## Risk Management Requirements

### Position Sizing
```python
# app/risk/position_sizing.py
class PositionSizer:
    def calculate_size(self, signal, portfolio_value, volatility):
        # Kelly Criterion with 0.25 fraction limit
        # Maximum 5% risk per trade
        # Maximum 20% total portfolio allocation
        # Account for correlation with existing positions
```

### Stop Loss Management
```python
# app/risk/stops.py
class StopLossManager:
    def calculate_stop(self, entry_price, atr, strategy_type):
        # ATR-based dynamic stops (2-3x ATR)
        # Time-based stops (max 14 days for swing trades)
        # Profit protection stops (trailing stops after 1.5R profit)
```

### Risk Limits
- Maximum 5 concurrent positions
- Maximum 2% portfolio risk per trade
- Maximum 20% total capital deployment
- Daily loss limit: 3% of portfolio
- Monthly drawdown limit: 10% of portfolio

## Security Requirements

### API Security
- Store IBKR credentials in environment variables
- Use OAuth2 with JWT tokens for dashboard access
- Implement rate limiting on all endpoints
- Log all trading activities with immutable audit trail

### Data Protection
- Encrypt sensitive data at rest
- Use SSL/TLS for all external communications
- Implement proper input validation and sanitization
- Regular security audits and dependency updates

## Development Phases

### Phase 1: Foundation (Weeks 1-2)
**Deliverables:**
- [ ] Project structure and configuration
- [ ] Database setup with migrations
- [ ] IBKR TWS API connection and authentication
- [ ] Basic data collection for ASX200 daily prices
- [ ] FastAPI setup with health endpoints
- [ ] Docker containerization
- [ ] Basic logging and monitoring

**Success Criteria:**
- Successfully collect daily price data for all ASX200 stocks
- Database properly stores and retrieves market data
- API endpoints respond correctly
- System runs without errors for 7 consecutive days

### Phase 2: Strategy Development (Weeks 3-4)
**Deliverables:**
- [ ] Backtesting engine implementation
- [ ] Momentum breakout strategy with full backtests
- [ ] Mean reversion strategy with validation
- [ ] Technical indicator calculations (RSI, Bollinger Bands, ATR)
- [ ] Signal generation and validation system
- [ ] Performance metrics calculation

**Success Criteria:**
- All strategies show positive Sharpe ratio (>1.0) in backtests
- Signal generation latency <5 seconds
- Backtest results match manual calculations
- Strategy parameters are optimized for ASX200 data

### Phase 3: Risk & Execution (Weeks 5-6)
**Deliverables:**
- [ ] Position sizing algorithms
- [ ] Stop loss and take profit management
- [ ] Order execution system with IBKR integration
- [ ] Risk monitoring and alerting
- [ ] Paper trading mode for validation
- [ ] Portfolio management dashboard

**Success Criteria:**
- Risk limits are properly enforced
- Orders execute within target slippage limits
- Paper trading matches backtest expectations
- All risk metrics update in real-time

### Phase 4: Production & Monitoring (Weeks 7-8)
**Deliverables:**
- [ ] Production deployment with monitoring
- [ ] Automated daily operations
- [ ] Performance reporting and alerting
- [ ] System health monitoring
- [ ] Backup and disaster recovery procedures
- [ ] Documentation and user guides

**Success Criteria:**
- System operates autonomously for 14 days
- All monitoring alerts are functional
- Performance metrics meet targets
- System recovers automatically from failures

## Testing Strategy

### Unit Tests (80%+ coverage required)
```python
# tests/unit/test_strategies.py
def test_momentum_strategy_signal_generation():
    # Test with known market data
    # Verify signal accuracy and timing
    
def test_position_sizing_calculations():
    # Test Kelly criterion implementation
    # Verify risk limits are respected
```

### Integration Tests
```python
# tests/integration/test_ibkr_integration.py
def test_data_collection_flow():
    # Test full data collection pipeline
    # Verify data quality and storage
    
def test_order_execution_flow():
    # Test order placement and fills
    # Verify risk controls activation
```

### Performance Tests
- API response time <500ms for dashboard
- Signal generation <5 seconds
- Order execution <10 seconds
- Database queries <100ms

## Deployment & DevOps

### Docker Configuration
```dockerfile
# docker/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration
```python
# app/config/settings.py
class Settings:
    # Database
    DATABASE_URL: str
    
    # IBKR Configuration
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    IBKR_CLIENT_ID: int = 1
    
    # Trading Configuration
    MAX_POSITIONS: int = 5
    MAX_RISK_PER_TRADE: float = 0.02
    DAILY_LOSS_LIMIT: float = 0.03
    
    # Monitoring
    LOG_LEVEL: str = "INFO"
    ENABLE_METRICS: bool = True
```

### Monitoring & Alerting
- **System Health**: CPU, memory, disk usage
- **Trading Performance**: Daily P&L, drawdown, Sharpe ratio
- **Risk Metrics**: Position exposure, correlation
- **Data Quality**: Missing data, price anomalies
- **API Status**: IBKR connection, rate limiting

### Alert Configuration
```python
# Critical alerts (immediate notification):
- Trading system down
- Risk limit breach
- Data collection failure
- Order execution errors

# Warning alerts (daily summary):
- Performance below targets
- High correlation between positions
- Unusual market conditions detected
```

## Performance Targets

### Financial Performance
- **Target Annual Return**: 15-25%
- **Maximum Drawdown**: <15%
- **Sharpe Ratio**: >1.2
- **Win Rate**: 45-55%
- **Average Holding Period**: 5-7 days
- **Maximum Risk per Trade**: 2%

### System Performance
- **Uptime**: >99.5%
- **Data Collection Success**: >99%
- **Order Execution Success**: >98%
- **Signal Generation Latency**: <5 seconds
- **Dashboard Response Time**: <500ms

## Compliance & Legal Considerations

### Regulatory Requirements
- Ensure compliance with ASX trading rules
- Implement proper record keeping for all trades
- Maintain audit trail for all system decisions
- Regular compliance monitoring and reporting

### Risk Disclosures
- Past performance does not guarantee future results
- All trading involves risk of loss
- Automated systems can fail or produce unexpected results
- Regular monitoring and oversight required

## Maintenance Schedule

### Daily Tasks (Automated)
- [ ] Market data collection and validation
- [ ] Signal generation and trade execution
- [ ] Risk metric calculation and monitoring
- [ ] System health checks and alerts
- [ ] Performance reporting

### Weekly Tasks (Semi-automated)
- [ ] Strategy performance review
- [ ] Risk exposure analysis
- [ ] System log review
- [ ] Database maintenance and cleanup
- [ ] Backup verification

### Monthly Tasks (Manual)
- [ ] Strategy optimization and rebalancing
- [ ] Performance attribution analysis
- [ ] Risk model validation
- [ ] System security audit
- [ ] Compliance reporting

## Development Guidelines

### Code Quality Standards
- **Type Hints**: All functions must have type annotations
- **Documentation**: Docstrings for all classes and functions
- **Testing**: Minimum 80% test coverage
- **Linting**: Use black, isort, flake8
- **Security**: Use bandit for security scanning

### Git Workflow
- **Branch Strategy**: GitFlow with feature branches
- **Commit Messages**: Conventional commit format
- **Code Reviews**: Required for all production changes
- **CI/CD**: Automated testing and deployment

### Error Handling
```python
# Implement comprehensive error handling
class TradingSystemError(Exception):
    """Base exception for trading system"""
    
class DataCollectionError(TradingSystemError):
    """Error in data collection process"""
    
class OrderExecutionError(TradingSystemError):
    """Error in order execution"""
```

## Logging Configuration
```python
# app/utils/logging.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
        },
        "file": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "logging.FileHandler",
            "filename": "logs/trading_system.log",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False
        }
    }
}
```

## Final Notes

This system prioritizes:
1. **Reliability over complexity** - Simple, proven strategies
2. **Risk management over returns** - Capital preservation first
3. **Automation over manual intervention** - Minimal daily oversight
4. **Compliance over optimization** - Meet all regulatory requirements

The agent building this system should focus on creating a robust, well-tested foundation before adding advanced features. Each component should be thoroughly tested before moving to the next phase.

Remember: This is a financial system handling real money. Every decision should be conservative, well-documented, and thoroughly tested.