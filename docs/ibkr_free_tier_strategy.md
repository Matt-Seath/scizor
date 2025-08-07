# IBKR Free Tier Data Collection Strategy

**Created**: August 7, 2025  
**Status**: CORE STRATEGY DOCUMENT  
**Priority**: CRITICAL - Foundation for SCIZOR Development  

---

## 🎯 Executive Summary

This document defines the optimal data collection and trading strategy for SCIZOR operating within Interactive Brokers' free-tier limitations. The strategy focuses on maximizing signal quality through focused stock selection rather than broad market coverage.

**Key Decision**: Focus on 15-20 high-quality ASX stocks for maximum analysis depth and signal reliability.

---

## 🔒 Critical Free Tier Limitations

### **API Rate & Connection Limits**
```
Market Data Lines:        100 concurrent subscriptions (HARD LIMIT)
API Request Rate:         50 requests/second (100 lines ÷ 2)
Historical Data Pacing:   60 requests per 10 minutes maximum
Request Spacing:          15 seconds minimum between identical requests
Same Contract Limit:      6 requests per 2 seconds maximum
```

### **Advanced Data Restrictions**
```
Market Depth (Level 2):   3 concurrent subscriptions only
Tick-by-Tick Data:        5 subscriptions (5% of market data lines)
Real-time Bars:           Subject to historical pacing limits
Streaming Data Update:    250ms intervals (stocks), 100ms (options), 5ms (FX)
```

### **Market Data Subscription Requirements**
```
Account Minimum:          $500 USD equity requirement
API Access:               Market Data API Acknowledgement required
Real-time ASX Data:       Paid subscription required (NOT free)
Free Data Available:      Forex, Crypto, 15-20min delayed quotes only
TWS vs API:              Free data in TWS ≠ Free data via API
```

### **Connection & Session Limits**
```
Max API Clients:         32 per TWS/Gateway session
Client Connections:      Single connection recommended
Session Management:      Daily restart required (TWS/Gateway)
Authentication:          Manual login required (no headless mode)
```

---

## 📊 Optimal Stock Selection Strategy

### **Portfolio Structure (15-20 Stocks Total)**

#### **Tier 1: Core Holdings (5-8 stocks)**
**Purpose**: Stable, liquid, high-conviction positions
```
Large-Cap Leaders:
- CBA (Commonwealth Bank) - Banking sector representative
- BHP (BHP Group) - Mining/resources exposure
- CSL (CSL Limited) - Healthcare/biotech leader
- WBC (Westpac) - Banking diversification
- ANZ (ANZ Bank) - Banking sector completion

Sector Diversification:
- Choose 1-2 additional from: RIO, FMG, WES, WOW, TLS
```

#### **Tier 2: Growth/Momentum (5-8 stocks)**
**Purpose**: Medium-term swing trading opportunities
```
Technology/Growth:
- REA (REA Group) - PropTech leader
- WTC (WiseTech Global) - LogTech growth
- XRO (Xero Limited) - SaaS/FinTech
- PME (Pro Medicus) - HealthTech growth

Mid-Cap Opportunities:
- Select 2-4 based on current market conditions
- Focus on: High volume, clear trends, news sensitivity
```

#### **Tier 3: Speculative/Tactical (3-5 stocks)**
**Purpose**: Short-term opportunities and market timing
```
Selection Criteria:
- Small-cap breakout candidates
- Event-driven opportunities (M&A, earnings)
- Sector rotation plays
- Cyclical positioning stocks

Dynamic Allocation:
- Review weekly, adjust based on market conditions
- Maintain high liquidity for rapid position changes
```

---

## ⚡ Data Collection Framework

### **Real-Time Data Strategy**
```python
# Market Data Allocation (80/100 lines used)
CORE_STOCKS = 8        # Tier 1 - continuous monitoring
GROWTH_STOCKS = 7      # Tier 2 - active trading
SPECULATIVE = 5        # Tier 3 - opportunity tracking
BUFFER_LINES = 20      # Account data, historical requests, safety margin

# Data Types per Stock
- Level 1 market data (bid/ask/last/volume)
- 5-second real-time bars during market hours
- Generic tick types: Volume, VWAP, High/Low
```

### **Historical Data Collection Schedule**
```python
# After-Hours Collection (7-9 PM AEST)
DAILY_ROUTINE = {
    "7:00 PM": "Start historical data collection",
    "7:30 PM": "Tier 1 stocks - 3 months daily bars",
    "8:00 PM": "Tier 2 stocks - 1 month daily bars", 
    "8:30 PM": "Tier 3 stocks - 2 weeks daily bars",
    "9:00 PM": "Data validation and analysis prep"
}

# Pacing Strategy
REQUEST_INTERVAL = 1.2  # 50 req/sec with safety margin
BATCH_SIZE = 10         # Within 10-minute windows
RETRY_DELAY = 16        # For identical requests
```

### **Data Storage Optimization**
```sql
-- Essential fields only (minimize storage)
CREATE TABLE optimized_market_data (
    symbol_id INTEGER,
    timestamp TIMESTAMPTZ,
    open DECIMAL(10,3),
    high DECIMAL(10,3), 
    low DECIMAL(10,3),
    close DECIMAL(10,3),
    volume BIGINT,
    vwap DECIMAL(10,3),
    -- Skip: bid_size, ask_size, trade_count (reduce storage)
    INDEX(symbol_id, timestamp)
);
```

---

## 🎯 Signal Generation Strategy

### **Technical Analysis Focus**
```python
# Primary Indicators (computationally efficient)
INDICATORS = {
    "trend": ["SMA_20", "SMA_50", "EMA_12", "EMA_26"],
    "momentum": ["RSI_14", "MACD", "Stochastic"],
    "volume": ["Volume_SMA_20", "Volume_Breakout", "VWAP"],
    "volatility": ["ATR_14", "Bollinger_Bands"]
}

# Signal Generation Rules
ENTRY_SIGNALS = {
    "bullish_crossover": "SMA_20 > SMA_50 AND Volume > 1.5 * Volume_SMA_20",
    "momentum_breakout": "RSI > 60 AND Close > High_20_day",
    "volume_spike": "Volume > 2.0 * Volume_SMA_20 AND MACD > Signal_Line"
}
```

### **Risk Management Integration**
```python
# Position Sizing (Kelly Criterion + Risk Parity)
MAX_POSITION_SIZE = 0.15    # 15% max per stock
MAX_SECTOR_EXPOSURE = 0.30  # 30% max per sector
VOLATILITY_SCALING = True   # Reduce size for high-vol stocks

# Stop-Loss Levels
ATR_STOP_MULTIPLIER = 2.0   # 2x ATR below entry
MAX_LOSS_PER_TRADE = 0.02   # 2% max loss per position
TRAILING_STOP = True        # Dynamic stop adjustment
```

---

## 📈 Performance Optimization

### **Market Hours Strategy**
```
Pre-Market (9:00-10:00 AM):
- Monitor overnight news and gaps
- Prepare watchlist for market open
- Review risk exposure

Market Hours (10:00 AM-4:00 PM):
- Real-time monitoring of positions
- Signal generation and execution
- Risk monitoring and adjustments

After Hours (4:00-7:00 PM):
- Performance analysis
- Position review and planning
- Historical data collection prep

Evening (7:00-9:00 PM):
- Historical data collection
- Strategy backtesting
- Next-day preparation
```

### **Weekend Analysis Routine**
```
Saturday Morning:
- Weekly performance review
- Strategy parameter optimization
- Market regime analysis

Saturday Afternoon:
- Stock screening for tier adjustments
- Sector rotation analysis
- Risk exposure rebalancing

Sunday:
- Strategy backtesting on new data
- Coming week preparation
- System maintenance and updates
```

---

## 🔄 Scaling & Upgrade Path

### **Free Tier Maximization Checklist**
- [ ] Implement delayed data fallback for screening
- [ ] Optimize request timing to avoid rate limits
- [ ] Use regulatory snapshots for broad market monitoring
- [ ] Leverage forex/crypto data for market sentiment
- [ ] Implement intelligent caching to reduce API calls

### **Paid Tier Upgrade Triggers**
```
Capital Threshold:     $50,000+ trading capital
Performance Metric:    6+ months consistent profitability
Strategy Complexity:   Need for Level 2 data or >20 stocks
Automation Level:      Fully automated execution system
Latency Requirements:  Sub-second execution needs
```

### **Next Tier Benefits Analysis**
```
Real-time ASX Data:    Full market coverage without delays
Level 2 Market Depth:  Order book analysis and hidden liquidity
Expanded Universe:     50+ stocks for diversification
Tick-by-Tick Data:     Scalping and microstructure strategies
Reduced Latency:       High-frequency trading capabilities
```

---

## ⚠️ Critical Implementation Notes

### **Connection Management**
```python
# Single Connection Strategy
class IBKRConnection:
    def __init__(self):
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 30
        self.heartbeat_interval = 60
        
    def maintain_connection(self):
        # Implement robust reconnection logic
        # Monitor connection health
        # Handle TWS daily restart
```

### **Error Handling & Fallbacks**
```python
# Rate Limit Management
class RateLimiter:
    def __init__(self):
        self.request_times = deque(maxlen=100)
        self.max_requests_per_second = 45  # Safety margin
        
    def can_make_request(self):
        # Implement sliding window rate limiting
        # Fallback to delayed data on rate limit
        
# Market Data Validation
def validate_market_data(data):
    # Check for stale timestamps
    # Validate price ranges
    # Detect data gaps
    # Alert on anomalies
```

### **Backup Strategies**
```
Primary Data Source:   IBKR TWS API
Fallback 1:           IBKR delayed data (15-20min)
Fallback 2:           ASX.com.au scraping (delayed)
Fallback 3:           Yahoo Finance API (backup)
Emergency Mode:       Manual monitoring via TWS
```

---

## 📋 Monitoring & Alerts

### **System Health Metrics**
```python
HEALTH_INDICATORS = {
    "api_connection": "Connected for >23 hours/day",
    "data_completeness": ">99% of expected data points",
    "request_success_rate": ">98% successful API calls",
    "latency": "<2 seconds average response time",
    "error_rate": "<1% of total requests"
}
```

### **Trading Performance KPIs**
```python
PERFORMANCE_METRICS = {
    "signal_accuracy": "Win rate >55%",
    "risk_adjusted_return": "Sharpe ratio >1.5",
    "max_drawdown": "<15% from peak",
    "data_driven_decisions": ">95% algorithm-based entries",
    "execution_efficiency": "<0.1% slippage average"
}
```

---

## 🎯 Success Criteria

### **Phase 1: Foundation (Month 1)**
- [ ] 15-stock watchlist operational within rate limits
- [ ] Real-time data collection stable >99% uptime
- [ ] Historical data backfilled for 6+ months
- [ ] Basic signal generation producing tradeable alerts
- [ ] Risk management preventing dangerous positions

### **Phase 2: Optimization (Month 2-3)**
- [ ] Signal quality >55% accuracy
- [ ] Portfolio performance tracking vs benchmarks
- [ ] Automated position sizing and risk controls
- [ ] Strategy parameter optimization based on performance
- [ ] Preparation for live trading implementation

### **Phase 3: Live Trading Ready (Month 4+)**
- [ ] Consistent paper trading profitability
- [ ] All risk controls tested and validated
- [ ] Emergency procedures implemented and tested
- [ ] Performance monitoring automated
- [ ] Ready for capital deployment

---

## 📝 Future Considerations

### **Advanced Features (Post Free-Tier)**
- Multi-asset class support (options, futures)
- Machine learning signal enhancement
- Alternative data integration (news, sentiment)
- High-frequency trading capabilities
- Institutional-grade risk management

### **Technology Scaling**
- Cloud deployment for reduced latency
- Real-time streaming data architecture
- Advanced backtesting with walk-forward analysis
- Portfolio optimization algorithms
- Automated strategy development pipeline

---

**Document Status**: ✅ APPROVED - Core Strategy Foundation  
**Next Review**: Monthly or upon major market structure changes  
**Implementation Priority**: IMMEDIATE - Required for Phase 3A development
