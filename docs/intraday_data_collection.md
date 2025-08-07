# Intraday Data Collection System

This system enables collection of high-frequency market data (5-minute and 1-minute bars) for specific symbols you want to track closely. It's designed for enhanced analysis and potentially higher-frequency trading strategies.

## Overview

The intraday data collection system extends the existing daily data collection with:

- **Watchlist Management**: Track specific symbols for enhanced data collection
- **Multiple Timeframes**: Support for 5-minute and 1-minute bars
- **Priority-Based Collection**: Collect most important symbols first
- **Gap Detection**: Automatically detect and fill data gaps
- **Market Hours Awareness**: Respects different market trading hours
- **Rate Limiting**: Follows IBKR API limits for historical data requests

## Architecture

### Database Schema

**Watchlist Table** (`watchlist`):
- Tracks symbols for enhanced data collection
- Supports multiple watchlists (e.g., "tech_stocks", "high_volatility")
- Priority-based collection order
- Configurable timeframes per symbol

**Market Data Table** (`market_data`):
- Stores OHLCV data for multiple timeframes
- Timeframe field supports: "1day", "5min", "1min"
- Optimized for time-series queries

### Key Components

1. **Watchlist Manager** (`scripts/manage_watchlist.py`)
   - Add/remove symbols from watchlists
   - Configure collection settings per symbol
   - List and manage multiple watchlists

2. **Intraday Collector** (`scripts/intraday_collection.py`)
   - Collects 5min/1min bars for watchlist symbols
   - Intelligent gap detection and backfilling
   - Rate-limited API requests

3. **Configuration** (`config/intraday_collection_config.py`)
   - Collection schedules and market hours
   - API rate limits and retry settings
   - Data quality validation rules

4. **Automation** (`scripts/intraday_cron.sh`)
   - Cron job for automated collection
   - Locking to prevent concurrent runs
   - Logging and error handling

## Quick Start

### 1. Setup Database

First, add the watchlist table to your database:

```bash
python scripts/migrate_watchlist_table.py
```

### 2. Create Default Watchlist

Create a default watchlist with popular symbols:

```bash
python scripts/manage_watchlist.py create-default
```

This creates a watchlist called "default_intraday" with:
- Major ASX stocks (CBA, BHP, CSL, etc.)
- Popular US tech stocks (AAPL, MSFT, GOOGL, etc.)
- Key ETFs (VAS, VGS, NDQ, etc.)

### 3. Test Collection

Run a test collection to ensure everything works:

```bash
python scripts/intraday_collection.py --timeframe 5min --test-mode
```

### 4. Start Regular Collection

For manual collection:
```bash
python scripts/intraday_collection.py --timeframe 5min --watchlist default_intraday
```

## Watchlist Management

### Add Symbols

Add specific symbols to your watchlist:

```bash
# Add high-priority symbol for 5min collection
python scripts/manage_watchlist.py add --symbol TSLA --name "high_frequency" --priority 1 --5min --notes "High volatility EV stock"

# Add medium-priority symbol for both 5min and 1min
python scripts/manage_watchlist.py add --symbol BHP --name "commodities" --priority 2 --5min --1min --notes "Mining exposure"
```

### Remove Symbols

```bash
python scripts/manage_watchlist.py remove --symbol TSLA --name "high_frequency"
```

### List Watchlists

```bash
# List specific watchlist
python scripts/manage_watchlist.py list --name "default_intraday"

# List all watchlists
python scripts/manage_watchlist.py list
```

### Update Symbol Settings

```bash
python scripts/manage_watchlist.py update --symbol AAPL --name "default_intraday" --priority 1 --1min true
```

## Collection Options

### Timeframes

**5-Minute Bars** (recommended for most use cases):
- Good balance of detail vs. API usage
- Suitable for short-term strategies
- Lower API request volume

```bash
python scripts/intraday_collection.py --timeframe 5min
```

**1-Minute Bars** (high-frequency strategies):
- Maximum intraday detail
- Higher API request volume
- Requires more storage space

```bash
python scripts/intraday_collection.py --timeframe 1min
```

### Collection Modes

**Normal Collection** (recent data):
```bash
python scripts/intraday_collection.py --timeframe 5min --backfill 1
```

**Backfill Collection** (historical data):
```bash
python scripts/intraday_collection.py --timeframe 5min --backfill 7
```

**Test Mode** (limited symbols):
```bash
python scripts/intraday_collection.py --timeframe 5min --test-mode
```

**Specific Watchlist**:
```bash
python scripts/intraday_collection.py --timeframe 5min --watchlist "tech_stocks"
```

## Automated Collection

### Setup Cron Jobs

Add to your crontab for automated collection:

```bash
# Edit crontab
crontab -e

# Add these lines for automated collection during market hours:

# 5-minute data collection every 15 minutes during ASX hours (10 AM - 4 PM)
*/15 10-16 * * 1-5 /Users/seath/github/scizor/scripts/intraday_cron.sh 5min

# Evening catchup collection at 5:30 PM
30 17 * * 1-5 /Users/seath/github/scizor/scripts/intraday_cron.sh 5min catchup

# Weekend catch-up on Sunday evening
0 19 * * 0 /Users/seath/github/scizor/scripts/intraday_cron.sh 5min catchup
```

### Manual Cron Execution

Test the cron script manually:

```bash
# Normal collection
./scripts/intraday_cron.sh 5min

# Catchup collection
./scripts/intraday_cron.sh 5min catchup

# Test mode
./scripts/intraday_cron.sh 5min test
```

## Configuration

### Key Settings (`config/intraday_collection_config.py`)

**Rate Limiting**:
```python
TIMEFRAMES = {
    "5min": {
        "max_requests_per_batch": 30,
        "pacing_delay": 20  # seconds between requests
    },
    "1min": {
        "max_requests_per_batch": 20,
        "pacing_delay": 30  # seconds between requests
    }
}
```

**Market Hours**:
```python
ASX_MARKET_OPEN = time(10, 0)   # 10:00 AM
ASX_MARKET_CLOSE = time(16, 0)  # 4:00 PM
NASDAQ_MARKET_OPEN = time(23, 30)  # 11:30 PM (AEST)
NASDAQ_MARKET_CLOSE = time(6, 0)   # 6:00 AM (AEST)
```

**Data Quality**:
```python
QUALITY_CHECKS = {
    "min_volume_threshold": 1000,
    "max_price_change_pct": 0.20,
    "validate_ohlc_relationships": True
}
```

## Priority System

Symbols are collected in priority order to ensure most important data is collected first:

- **Priority 1**: Critical symbols (major indexes, key stocks)
- **Priority 2**: High importance (large caps, major ETFs)
- **Priority 3**: Medium importance (mid caps, sector ETFs)
- **Priority 4**: Low importance (small caps, specialized ETFs)
- **Priority 5**: Maintenance (rarely traded, experimental)

## Data Usage and Storage

### Storage Requirements

Approximate storage per symbol:

**5-Minute Bars**:
- ~70 bars per trading day
- ~18,000 bars per year
- ~1.5 MB per symbol per year

**1-Minute Bars**:
- ~390 bars per trading day  
- ~100,000 bars per year
- ~8 MB per symbol per year

### API Usage

IBKR Historical Data Limits:
- ~60 requests per 10 minutes for small bars
- Each request gets up to 2 days of 5min data
- Each request gets up to 1 day of 1min data

**Example for 20 symbols**:
- 5min data: ~10 requests (within limits)
- 1min data: ~20 requests (near limits)

## Monitoring and Logging

### Log Files

- **Collection Logs**: `logs/intraday_collection.log`
- **Cron Logs**: `logs/intraday_cron.log`
- **Application Logs**: `logs/intraday_collection.log`

### Monitor Collection Status

Check recent collection activity:
```bash
# View recent logs
tail -f logs/intraday_collection.log

# Check for errors
grep ERROR logs/intraday_collection.log

# Check collection statistics
grep "Collection completed" logs/intraday_collection.log
```

### Database Queries

Check collected data:
```sql
-- Count of 5min bars by symbol
SELECT s.symbol, COUNT(*) as bar_count, MAX(m.timestamp) as latest_data
FROM market_data m
JOIN symbols s ON m.symbol_id = s.id
WHERE m.timeframe = '5min'
GROUP BY s.symbol
ORDER BY bar_count DESC;

-- Check for data gaps
SELECT symbol_id, timestamp, 
       LAG(timestamp) OVER (PARTITION BY symbol_id ORDER BY timestamp) as prev_timestamp,
       timestamp - LAG(timestamp) OVER (PARTITION BY symbol_id ORDER BY timestamp) as gap
FROM market_data 
WHERE timeframe = '5min'
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY symbol_id, timestamp;
```

## Troubleshooting

### Common Issues

**1. No Data Collected**
- Check IBKR TWS connection (should be on port 4002)
- Verify symbols exist in database
- Check watchlist configuration
- Review API limits and pacing

**2. Collection Failures**
- Check log files for specific errors
- Verify market hours and trading status
- Check disk space and database connectivity
- Ensure no duplicate collection processes

**3. Data Gaps**
- Run backfill collection: `--backfill 7`
- Check for weekend/holiday gaps (normal)
- Verify market hours configuration
- Review API request failures

**4. Performance Issues**
- Reduce number of symbols in watchlist
- Increase pacing delays
- Check database performance
- Monitor memory usage

### Debug Mode

Run with verbose logging:
```bash
# Set debug logging level
export LOG_LEVEL=DEBUG

# Run collection with debug output
python scripts/intraday_collection.py --timeframe 5min --test-mode
```

### Emergency Stop

Create stop file to halt collection:
```bash
touch /tmp/stop_intraday_collection
```

## Integration with Backtesting

The collected intraday data can be used with the backtesting system for higher-frequency strategy testing:

```python
# Example: Use 5min data in backtesting
from services.backtester.engine import BacktestEngine

# Configure for 5min timeframe
engine = BacktestEngine(db_connection)
result = engine.run_backtest(
    strategy=my_strategy,
    symbols=['AAPL', 'MSFT'],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    timeframe='5min'  # Use intraday data
)
```

## Best Practices

### Symbol Selection

1. **Start Small**: Begin with 10-20 symbols
2. **High Liquidity**: Focus on actively traded symbols
3. **Diversification**: Include different sectors and asset classes
4. **Priority Order**: Set priorities based on importance

### Collection Strategy

1. **Conservative API Usage**: Start with 5min bars only
2. **Regular Monitoring**: Check logs and data quality
3. **Gradual Expansion**: Add more symbols/timeframes gradually
4. **Backup Strategy**: Keep daily collection as fallback

### Data Management

1. **Regular Cleanup**: Archive old intraday data
2. **Monitor Storage**: Track database size growth
3. **Data Validation**: Regularly check data quality
4. **Backup Important Data**: Backup critical watchlists

## Next Steps

Once you have intraday data collection running:

1. **Develop Strategies**: Create trading strategies using 5min data
2. **Real-time Monitoring**: Build dashboards for live monitoring
3. **Advanced Analytics**: Implement technical indicators on intraday data
4. **Live Trading**: Integrate with live trading system for real-time signals

The intraday data collection system provides the foundation for sophisticated short-term trading strategies and real-time market analysis!
