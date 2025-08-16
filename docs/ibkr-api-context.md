# IBKR TWS API - Implementation Context

## Overview

The Interactive Brokers Trader Workstation (TWS) API is a TCP Socket Protocol API that connects to either the Trader Workstation or IB Gateway. This document provides essential context for implementing algorithmic trading systems using the TWS API, specifically focused on ASX200 trading requirements.

## Critical Technical Requirements

### Python Version & Installation
- **Minimum Python Version**: 3.11.0
- **Installation**: Must use official IB API download (not pip/PyPI)
- **Setup**: `python setup.py install` from source directory
- **Location**: Download from https://interactivebrokers.github.io/

### TWS/Gateway Requirements
- **TWS Version**: Latest stable release required
- **Connection**: TWS or IB Gateway must be running and authenticated
- **API Settings**: Must enable "ActiveX and Socket Clients" in Global Configuration
- **Socket Port**: Default 7497 (live), 7496 (paper trading)

## Connection Architecture

### Socket Connection
```python
# Basic connection pattern
app.connect("127.0.0.1", 7497, clientId=1)  # Live account
app.connect("127.0.0.1", 7496, clientId=1)  # Paper trading
```

### Client ID Management
- **Client ID 0**: Special - can access TWS manual orders and all API orders
- **Multiple Clients**: Up to 32 concurrent connections per TWS session
- **Master Client ID**: Can be set in Global Configuration to receive all order data

### Connection Lifecycle
1. **Socket Connection**: `eConnect()` establishes TCP connection
2. **Handshake**: Version negotiation between API and TWS
3. **Authentication**: Automatic via TWS session
4. **Ready State**: `nextValidId()` callback indicates connection ready

## Critical Rate Limitations

### Request Pacing
- **Maximum Rate**: 50 requests per second (100 market data lines ÷ 2)
- **Historical Data**: Max 60 requests per 10-minute period
- **Same Contract**: Max 6 requests within 2 seconds for same contract/exchange/tick type
- **Identical Requests**: 15-second minimum interval between identical historical requests

### Violation Consequences
- **First Violation**: Error code 100 warning
- **Multiple Violations**: API disconnection after 3 violations
- **Recovery**: Automatic pacing if "reject messages" setting disabled

### ASX200 Specific Considerations
```python
# Rate limiting for 200 stocks daily collection
# Spread requests across time to avoid violations
import time

for symbol in asx200_symbols:
    request_market_data(symbol)
    time.sleep(0.1)  # 100ms delay = max 10 req/sec (well under 50/sec limit)
```

## Market Data Implementation

### Top of Book (Level 1) Data
```python
# Request market data
self.reqMktData(reqId, contract, "", False, False, [])

# Handle callbacks
def tickPrice(self, reqId, tickType, price, attrib):
    # Price updates (bid, ask, last)
    pass

def tickSize(self, reqId, tickType, size):
    # Size updates (bid size, ask size, volume)
    pass
```

### Historical Data
```python
# Request historical bars
self.reqHistoricalData(
    reqId=4102, 
    contract=contract, 
    endDateTime="",  # Current time
    durationStr="1 M",  # 1 month
    barSizeSetting="1 day", 
    whatToShow="TRADES", 
    useRTH=1,  # Regular trading hours only
    formatDate=1,  # String format
    keepUpToDate=False,  # One-time request
    chartOptions=[]
)
```

### Market Data Types
- **Live (1)**: Real-time data (requires subscription)
- **Frozen (2)**: Last available data when market closed
- **Delayed (3)**: 15-20 minutes delayed (free)
- **Delayed Frozen (4)**: Delayed + frozen combination

```python
# Switch to delayed data for development/testing
self.reqMarketDataType(3)  # Delayed data
```

## Order Management

### Order Placement
```python
# Basic order structure
order = Order()
order.action = "BUY"  # or "SELL"
order.orderType = "LMT"  # MKT, LMT, STP, etc.
order.totalQuantity = 100
order.lmtPrice = 50.25
order.tif = "DAY"  # Time in force

# Place order
self.placeOrder(orderId, contract, order)
```

### Order Status Monitoring
```python
def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
    # Status values: PendingSubmit, Submitted, Filled, Cancelled, etc.
    pass

def execDetails(self, reqId, contract, execution):
    # Execution details for filled orders
    pass
```

### Risk Management Integration
```python
# Position sizing with risk limits
order.totalQuantity = calculate_position_size(
    account_value=portfolio_value,
    risk_per_trade=0.02,  # 2% risk
    entry_price=entry_price,
    stop_loss=stop_loss_price
)
```

## ASX200 Specific Implementation

### Contract Definition
```python
# ASX stock contract
contract = Contract()
contract.symbol = "BHP"
contract.secType = "STK"
contract.currency = "AUD"
contract.exchange = "ASX"
contract.primaryExchange = "ASX"
```

### Market Hours & Timezone
- **Market Hours**: 10:00 AM - 4:00 PM AEST
- **Data Collection**: After 4:10 PM AEST (market close + 10 minutes)
- **Timezone Handling**: Use AEST for all ASX operations

```python
# Market hours check
import datetime
import pytz

aest = pytz.timezone('Australia/Sydney')
now = datetime.datetime.now(aest)
market_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

is_market_hours = market_open <= now <= market_close
```

### Currency Considerations
- **Base Currency**: AUD for ASX stocks
- **Currency Conversion**: Automatic by IB
- **Portfolio Reporting**: Can be in account base currency

## Account & Portfolio Data

### Account Updates
```python
# Subscribe to account updates
self.reqAccountUpdates(True, "DU123456")  # Your account number

def updateAccountValue(self, key, val, currency, accountName):
    # Account values (cash, buying power, etc.)
    pass

def updatePortfolio(self, contract, position, marketPrice, marketValue, averageCost, unrealizedPNL, realizedPNL, accountName):
    # Position updates
    pass
```

### Position Monitoring
```python
# Request all positions
self.reqPositions()

def position(self, account, contract, position, avgCost):
    # Current positions across all accounts
    pass
```

## Error Handling & Recovery

### Critical Error Codes
- **100**: Rate limit exceeded
- **502**: Connection failed (TWS not running/API disabled)
- **1100**: TWS connectivity lost
- **1101**: TWS reconnected, data lost (need to re-subscribe)
- **1102**: TWS reconnected, data maintained
- **2104/2106**: Market data farm connection OK (normal)
- **10089**: Market data subscription required

### Connection Recovery
```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    if errorCode == 1100:
        # Connection lost - stop trading
        self.trading_enabled = False
    elif errorCode == 1101:
        # Reconnected but data lost - resubscribe
        self.resubscribe_market_data()
    elif errorCode == 1102:
        # Reconnected with data intact
        self.trading_enabled = True

def connectionClosed(self):
    # Handle connection loss
    self.trading_enabled = False
    # Implement reconnection logic
```

## Data Collection Best Practices

### Efficient ASX200 Data Collection
```python
# Collect data for all ASX200 stocks efficiently
def collect_daily_data(self):
    symbols = get_asx200_symbols()  # 200 symbols
    
    for i, symbol in enumerate(symbols):
        reqId = 1000 + i
        contract = create_asx_contract(symbol)
        
        # Request daily bar
        self.reqHistoricalData(
            reqId, contract, "", "1 D", "1 day", "TRADES", 1, 1, False, []
        )
        
        # Pace requests to avoid violations
        if i % 10 == 9:  # Every 10 requests
            time.sleep(1)  # 1 second pause
```

### Database Integration
```python
def historicalData(self, reqId, bar):
    # Store bar data in database
    symbol = self.req_id_to_symbol[reqId]
    
    bar_data = {
        'symbol': symbol,
        'date': bar.date,
        'open': bar.open,
        'high': bar.high,
        'low': bar.low,
        'close': bar.close,
        'volume': bar.volume
    }
    
    self.store_bar_data(bar_data)
```

## Configuration Requirements

### TWS Global Configuration
```
API Settings:
✓ Enable ActiveX and Socket Clients
✓ Read-Only API: DISABLED
✓ Create API message log file (for debugging)
✓ Socket port: 7497 (live) / 7496 (paper)
✓ Trusted IPs: Add your server IP if remote

Precautions (for automated trading):
✓ Bypass Order Precautions for API orders
✓ Bypass Bond warning for API orders
✓ (Enable other bypass options as needed)

Time Settings:
✓ Never lock Trader Workstation
✓ Auto restart (recommended)
```

### Memory Allocation
- **Recommended**: 4000 MB for API usage
- **Minimum**: 2000 MB
- **Location**: Global Configuration > General > Memory Allocation

## Production Considerations

### Paper Trading Setup
- **Account Type**: Paper trading account required for testing
- **Connection**: Use port 7496 for paper trading
- **Limitations**: Paper trading has some inherent limitations vs live

### Security
- **API Keys**: Not used (authentication via TWS login)
- **Network**: Use localhost (127.0.0.1) when possible
- **Trusted IPs**: Configure for remote connections
- **Encryption**: API logs are encrypted locally

### Monitoring & Logging
- **API Logs**: Enable in Global Configuration
- **Log Location**: Check with Ctrl+Alt+U in TWS
- **Log Rotation**: Automatic 7-day rotation
- **Error Tracking**: Implement comprehensive error logging

## Common Issues & Solutions

### Connection Issues
1. **"Couldn't connect to TWS" (502)**:
   - Ensure TWS is running and logged in
   - Check API is enabled in Global Configuration
   - Verify correct port number

2. **"Already Connected" (501)**:
   - Another client using same Client ID
   - Use unique Client ID for each connection

3. **Rate Limit Violations (100)**:
   - Implement request pacing
   - Use time delays between requests
   - Monitor and respect limits

### Data Issues
1. **"Market data not subscribed" (10089)**:
   - Need live data subscription for real-time data
   - Use delayed data for testing (reqMarketDataType(3))

2. **Historical data limitations**:
   - 6-month limit for bars < 30 seconds
   - 2-year limit for expired futures
   - No data for expired options

### Order Issues
1. **Order rejection (201/202)**:
   - Check order size limits
   - Verify price is reasonable vs market
   - Ensure sufficient buying power

2. **Order precautions**:
   - Configure precaution settings in TWS
   - Use bypass options for automated trading

This context provides the essential implementation details needed for building a robust ASX200 algorithmic trading system using the IBKR TWS API.