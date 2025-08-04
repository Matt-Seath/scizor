# Scizor - Headless Algorithmic Trading Framework

A modern, headless algorithmic trading framework built with Python for backtesting, strategy development, live trading, and comprehensive market data management.

## Features

### 🎯 Core Trading Features
- **Strategy Framework**: Pluggable strategy system with base classes for easy extension
- **Backtesting Engine**: Powered by Backtrader for comprehensive strategy testing
- **Live Trading**: Interactive Brokers integration via ib_insync for headless execution
- **Portfolio Management**: Real-time portfolio tracking and risk management
- **Monitoring**: Trade monitoring and performance analytics

### 📊 Data Management
- **Multi-Source Data Collection**: Yahoo Finance, Interactive Brokers, and extensible providers
- **Robust Database Storage**: SQLite, PostgreSQL, and MySQL support
- **Automated Scheduling**: Built-in scheduler for regular data updates
- **Real-time Data**: Continuous market data collection during trading hours
- **Data Quality Monitoring**: Comprehensive data validation and gap detection

### ⚙️ System Features
- **Configuration Management**: YAML-based configuration with environment overrides
- **Comprehensive Logging**: Detailed logging with configurable levels
- **CLI Interface**: Easy-to-use command-line tools
- **Service Integration**: SystemD and LaunchD service support

## Quick Start

### 1. Installation & Setup

```bash
# Clone repository
git clone <repository>
cd scizor

# Run automated setup
./setup.sh

# Or manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Setup & Data Collection

```bash
# Initialize database with sample symbols
python -m scizor.database init

# Add your own symbols
python -m scizor.database add AAPL GOOGL MSFT TSLA NVDA

# Backfill historical data (1 year)
python -m scizor.database backfill AAPL GOOGL MSFT TSLA --days 365

# Start automated data collection
python -m scizor.database.scheduler
```

### 3. Run a Backtest

```bash
# Simple moving average crossover backtest
python -m scizor.backtest --strategy MovingAverageCrossover --symbol AAPL --start 2023-01-01 --end 2023-12-31
```

### 4. Live Trading (Paper Mode)

```bash
# Start live trading with paper account
python -m scizor.live --strategy MovingAverageCrossover --mode paper
```

## Project Structure

```
scizor/
├── scizor/                     # Main package
│   ├── core/                   # Core trading engine
│   ├── strategies/             # Trading strategies
│   ├── data/                   # Data providers and management
│   ├── database/              # Database models and data collection
│   ├── portfolio/             # Portfolio and risk management
│   ├── backtest/              # Backtesting engine
│   ├── broker/                # Broker integrations (IB, etc.)
│   ├── monitoring/            # Trade monitoring and analytics
│   └── config/                # Configuration management
├── config/                    # Configuration files
├── examples/                  # Usage examples
├── docs/                      # Documentation
├── logs/                      # Log files
└── tests/                     # Unit tests
```

## Data Collection System

The standalone data collection system can operate independently of the trading framework:

### Database Commands

```bash
# Initialize database
python -m scizor.database init

# Add symbols to track
python -m scizor.database add AAPL GOOGL MSFT TSLA

# Update data for specific symbols
python -m scizor.database update AAPL GOOGL --start-date 2024-01-01

# Update all tracked symbols
python -m scizor.database update-all

# Backfill historical data
python -m scizor.database backfill AAPL --days 365

# Show database summary
python -m scizor.database summary

# Real-time updates (every 15 minutes)
python -m scizor.database realtime --interval 15
```

### Automated Scheduling

The scheduler automatically collects data:
- **Intraday**: Every 15 minutes during market hours
- **Daily**: Complete day's data after market close
- **Weekly**: Comprehensive weekly data sync

```bash
# Start scheduler daemon
python -m scizor.database.scheduler

# Install as system service (Linux)
sudo systemctl enable scizor-scheduler
sudo systemctl start scizor-scheduler

# Install as system service (macOS)
launchctl load ~/Library/LaunchAgents/com.scizor.scheduler.plist
```

## Configuration

### Main Configuration (config/config.yaml)

```yaml
trading:
  initial_capital: 100000
  commission:
    rate: 0.001
  risk:
    max_position_size: 0.1
    stop_loss: 0.02

data:
  default_provider: "yahoo"
  cache_duration: 3600

interactive_brokers:
  host: "127.0.0.1"
  port: 7497  # Paper trading
  paper_trading: true
```

### Environment Variables (.env)

```bash
# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1

# Database
DATABASE_URL=sqlite:///scizor_data.db

# Notifications
SLACK_WEBHOOK_URL=your_webhook_url
```

## Examples

### Data Collection
```bash
# Run example data collection
python examples/data_collection.py 1  # Basic setup
python examples/data_collection.py 2  # Analyze data
python examples/data_collection.py 4  # Monitor quality
```

### Strategy Development
```python
from scizor.strategies.base import BaseStrategy, Signal
from scizor.strategies.moving_average import MovingAverageCrossover

# Create custom strategy
class MyStrategy(BaseStrategy):
    def get_required_symbols(self):
        return ['AAPL', 'GOOGL']
    
    def generate_signals(self, market_data, current_time):
        # Your strategy logic here
        return [Signal('AAPL', 'buy', 100)]

# Use built-in strategy
strategy = MovingAverageCrossover(short_window=10, long_window=20, symbols=['AAPL'])
```

### Database Integration
```python
from scizor.database.models import get_session, StockData

# Query historical data
session = get_session()
data = session.query(StockData).filter_by(symbol='AAPL').all()
session.close()

# Use with trading framework
from scizor.data.providers import DatabaseProvider
data_provider = DatabaseProvider('sqlite:///scizor_data.db')
```

## Monitoring & Analytics

### Real-time Monitoring
- Portfolio value tracking
- Trade execution monitoring  
- Performance metrics calculation
- Risk limit monitoring

### Analytics Dashboard (Optional)
```bash
# Enable dashboard in config
monitoring:
  enable_dashboard: true
  dashboard_port: 8000

# Access at http://localhost:8000
```

## Database Support

### Supported Databases
- **SQLite**: Default, file-based (recommended for development)
- **PostgreSQL**: Production-ready, supports high concurrency
- **MySQL**: Alternative production database

### Database Schema
- `symbols`: Symbol metadata and info
- `stock_data`: OHLCV price data with timestamps
- `data_update_log`: Operation tracking and audit trail
- `technical_indicators`: Pre-calculated indicators
- `market_calendar`: Trading calendar and market hours

## Performance & Scalability

### Data Collection Performance
- Parallel symbol processing (configurable batch sizes)
- Request rate limiting to respect API limits
- Automatic retry with exponential backoff
- Data deduplication and integrity checks

### Trading Performance
- Asynchronous order execution
- Real-time portfolio updates
- Efficient data structures for indicators
- Configurable update frequencies

## Production Deployment

### System Service Setup

**Linux (SystemD)**
```bash
# Install service
sudo cp scizor-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scizor-scheduler
sudo systemctl start scizor-scheduler
```

**macOS (LaunchD)**
```bash
# Install service
cp com.scizor.scheduler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.scizor.scheduler.plist
```

### Production Configuration
```yaml
# Use PostgreSQL for production
DATABASE_URL: "postgresql://user:pass@localhost:5432/scizor"

# Enable monitoring
monitoring:
  enable_dashboard: true
  enable_slack_notifications: true

# Production risk settings
trading:
  risk:
    max_position_size: 0.05  # More conservative
    max_drawdown: 0.10
```

## Documentation

- [Database System Documentation](docs/DATABASE.md) - Comprehensive data collection guide
- [Strategy Development Guide](docs/STRATEGIES.md) - Creating custom strategies
- [Broker Integration Guide](docs/BROKERS.md) - Setting up broker connections
- [Configuration Reference](docs/CONFIG.md) - Complete configuration options

## Troubleshooting

### Common Issues

**Data Collection Issues**
```bash
# Check data provider connectivity
python -c "import yfinance as yf; print(yf.Ticker('AAPL').info['regularMarketPrice'])"

# Check database connectivity
python -c "from scizor.database.models import get_session; print('DB OK')"

# Monitor failed operations
python -m scizor.database summary
```

**Trading Issues**
```bash
# Test IB connection
python -c "from ib_insync import IB; ib = IB(); ib.connect('127.0.0.1', 7497, 1); print('IB Connected')"

# Check portfolio status
python -c "from scizor.portfolio.manager import PortfolioManager; pm = PortfolioManager(100000); print(pm.get_performance_summary())"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt
pip install -e .

# Run tests
pytest tests/

# Code formatting
black scizor/
flake8 scizor/
```

## License

MIT License - see LICENSE file for details.

## Disclaimer

This software is for educational and research purposes only. Use at your own risk. Past performance does not guarantee future results. Always test strategies thoroughly before deploying with real money.
