# Stock Data Collection System

A standalone application for collecting, storing, and managing stock market data for the Scizor algorithmic trading framework.

## Features

- **Multi-Source Data Collection**: Yahoo Finance integration with extensible provider system
- **Robust Database Storage**: SQLite by default, with PostgreSQL and MySQL support
- **Automated Scheduling**: Built-in scheduler for regular data updates
- **Comprehensive CLI**: Easy-to-use command-line interface
- **Real-time Updates**: Continuous data collection during market hours
- **Data Integrity**: Automatic deduplication and error handling
- **Performance Monitoring**: Detailed logging and operation tracking

## Quick Start

### 1. Installation

```bash
# Clone and setup
git clone <repository>
cd scizor
./setup.sh
```

### 2. Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Initialize database with sample symbols
python -m scizor.database init

# Add specific symbols
python -m scizor.database add AAPL GOOGL MSFT TSLA NVDA

# Backfill historical data (1 year)
python -m scizor.database backfill AAPL GOOGL MSFT --days 365

# Show database summary
python -m scizor.database summary

# Run real-time updates
python -m scizor.database realtime --interval 15
```

### 3. Automated Scheduling

```bash
# Start the automated scheduler (runs in background)
python -m scizor.database.scheduler

# Or install as system service (Linux/macOS)
sudo systemctl start scizor-scheduler  # Linux
launchctl load ~/Library/LaunchAgents/com.scizor.scheduler.plist  # macOS
```

## Command Reference

### Database Initialization
```bash
# Initialize database with tables
python -m scizor.database init

# Initialize without sample data
python -m scizor.database init --no-samples
```

### Symbol Management
```bash
# Add symbols to track
python -m scizor.database add AAPL GOOGL MSFT TSLA

# Add with custom database
python -m scizor.database add AAPL --database-url postgresql://user:pass@localhost/scizor
```

### Data Updates
```bash
# Update specific symbols
python -m scizor.database update AAPL GOOGL

# Update with date range
python -m scizor.database update AAPL --start-date 2024-01-01 --end-date 2024-12-31

# Update all symbols
python -m scizor.database update-all

# Update all with custom batch size
python -m scizor.database update-all --batch-size 5
```

### Backfilling Data
```bash
# Backfill 1 year of data
python -m scizor.database backfill AAPL GOOGL --days 365

# Backfill 2 years
python -m scizor.database backfill AAPL --days 730
```

### Monitoring
```bash
# Show database summary
python -m scizor.database summary

# Real-time updates every 15 minutes
python -m scizor.database realtime --interval 15

# Real-time updates every 5 minutes
python -m scizor.database realtime --interval 5
```

## Configuration

### Database Configuration

**SQLite (Default)**
```bash
# Uses local file
python -m scizor.database init
# Creates: scizor_data.db
```

**PostgreSQL**
```bash
# Set database URL
export DATABASE_URL="postgresql://username:password@localhost:5432/scizor"
python -m scizor.database init --database-url $DATABASE_URL
```

**MySQL**
```bash
# Set database URL
export DATABASE_URL="mysql+pymysql://username:password@localhost:3306/scizor"
python -m scizor.database init --database-url $DATABASE_URL
```

### Environment Variables

Create a `.env` file:
```bash
# Database
DATABASE_URL=sqlite:///scizor_data.db

# Yahoo Finance (optional rate limiting)
YF_REQUEST_DELAY=0.1

# Logging
LOG_LEVEL=INFO
```

## Scheduling

The automated scheduler runs the following tasks:

- **Intraday Updates**: Every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
- **Market Close Update**: Daily at 4:00 PM ET (final prices)
- **Daily Update**: Daily at 6:00 PM ET (complete day's data)
- **Weekly Update**: Sunday at 2:00 AM ET (comprehensive weekly sync)

### Custom Schedules

```python
from scizor.database.scheduler import DataScheduler

scheduler = DataScheduler()
scheduler.add_custom_schedule("10:30", "intraday_update")
scheduler.start()
```

## Database Schema

### Tables

**symbols**: Symbol metadata
- symbol, name, sector, industry, exchange, market_cap, etc.

**stock_data**: OHLCV price data
- symbol, date, open, high, low, close, volume, adjusted_close

**data_update_log**: Operation tracking
- symbol, update_type, status, records_processed, timestamps

**technical_indicators**: Pre-calculated indicators
- symbol, date, indicator_name, indicator_value, parameters

**market_calendar**: Trading calendar
- date, exchange, is_trading_day, market_open, market_close

## API Usage

```python
from scizor.database.collector import StockDataCollector
from scizor.database.models import get_session, StockData

# Initialize collector
collector = StockDataCollector()

# Add symbols
symbols = [
    {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology'}
]
collector.add_symbols(symbols)

# Update data
from datetime import datetime, timedelta
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
collector.update_symbol_data('AAPL', start_date, end_date)

# Query data
session = get_session()
data = session.query(StockData).filter_by(symbol='AAPL').all()
session.close()
```

## Performance Tips

1. **Batch Processing**: Use appropriate batch sizes for your system
   ```bash
   python -m scizor.database update-all --batch-size 10
   ```

2. **Database Optimization**: Use PostgreSQL for high-volume data
   ```bash
   # PostgreSQL with connection pooling
   DATABASE_URL="postgresql://user:pass@localhost/scizor?pool_size=20&max_overflow=30"
   ```

3. **Parallel Processing**: Adjust max workers in collector
   ```python
   collector = StockDataCollector(max_workers=10)
   ```

4. **Rate Limiting**: Respect data provider limits
   ```python
   # Add delays between requests
   time.sleep(0.1)  # 100ms delay
   ```

## Monitoring & Logging

Logs are stored in `logs/` directory:

- `scizor.log`: Main application log
- `scheduler.log`: Scheduler operations (if using system service)
- `scheduler.error.log`: Scheduler errors

### Log Levels
```bash
# Set log level via environment
export LOG_LEVEL=DEBUG
python -m scizor.database update AAPL
```

## Troubleshooting

### Common Issues

**1. Yahoo Finance Rate Limiting**
```bash
# Add delay between requests
export YF_REQUEST_DELAY=0.5
```

**2. Database Connection Issues**
```bash
# Check database URL
python -c "from scizor.database.models import get_session; print('DB OK')"
```

**3. Memory Issues with Large Datasets**
```bash
# Reduce batch size
python -m scizor.database update-all --batch-size 3
```

**4. Missing Data**
```bash
# Check data update logs
python -c "
from scizor.database.models import get_session, DataUpdateLog
session = get_session()
logs = session.query(DataUpdateLog).filter_by(status='failed').all()
for log in logs: print(f'{log.symbol}: {log.error_message}')
"
```

## Integration with Trading System

The data collection system integrates seamlessly with the main Scizor trading framework:

```python
from scizor.data.providers import DatabaseProvider
from scizor.strategies.moving_average import MovingAverageCrossover

# Use database as data provider
data_provider = DatabaseProvider('sqlite:///scizor_data.db')

# Create strategy
strategy = MovingAverageCrossover(symbols=['AAPL', 'GOOGL'])

# Run backtest with database data
from scizor.backtest.engine import BacktestEngine
engine = BacktestEngine()
results = engine.run_backtest(strategy, data_provider, ['AAPL'], start_date, end_date)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.
