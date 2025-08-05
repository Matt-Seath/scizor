# Scizor - Unified Trading System

A comprehensive trading system built as a microservices architecture with three main components that can be deployed together or separately. The system integrates with Interactive Brokers (IBKR) API for real-time market data and trading execution.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Farmer   │    │   Backtester    │    │  Algo Trader    │
│   (Collector)   │    │   (Engine)      │    │   (Live)        │
│                 │    │                 │    │                 │
│ • Market Data   │───▶│ • Strategy Test │───▶│ • Live Trading  │
│ • Historical    │    │ • Performance   │    │ • Monitoring    │
│ • Real-time     │    │ • Metrics       │    │ • Risk Mgmt     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                    ┌─────────────────┐
                    │  Shared Database │
                    │                 │
                    │ • Market Data   │
                    │ • Strategies    │
                    │ • Trades        │
                    │ • Performance   │
                    └─────────────────┘
```

## Services

### 1. Data Farmer (Collection Service)
- **Port**: 8000
- **Purpose**: Collect, process, and store market data from Interactive Brokers
- **Features**: Real-time data streaming, historical data collection, data quality management

### 2. Backtester (Strategy Testing Engine)
- **Port**: 8001
- **Purpose**: Test trading strategies against historical data
- **Features**: Strategy framework, performance analytics, parameter optimization

### 3. Algo Trader (Live Trading Engine)
- **Port**: 8002
- **Purpose**: Execute live trading strategies with real-time monitoring
- **Features**: Strategy deployment, real-time execution, risk management

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis
- Interactive Brokers TWS or IB Gateway

### Development Setup

1. Clone and setup environment:
```bash
git clone <repository-url>
cd scizor
cp .env.example .env
# Edit .env with your configuration
```

2. Start infrastructure:
```bash
docker-compose up -d postgres redis
```

3. Install dependencies and run migrations:
```bash
pip install -r requirements.txt
python scripts/init_db.py
```

4. Start services:
```bash
# Terminal 1 - Data Farmer
cd services/data-farmer
python main.py

# Terminal 2 - Backtester
cd services/backtester
python main.py

# Terminal 3 - Algo Trader
cd services/algo-trader
python main.py
```

### Production Deployment

```bash
docker-compose up -d
```

## Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `IBKR_HOST`: Interactive Brokers TWS/Gateway host
- `IBKR_PORT`: Interactive Brokers TWS/Gateway port
- `IBKR_CLIENT_ID`: IBKR API client ID

### Interactive Brokers Setup
1. Install and configure TWS or IB Gateway
2. Enable API connections in Global Configuration
3. Set socket port (default: 7497 for TWS, 4001 for Gateway)
4. Add trusted IPs if connecting remotely

## API Endpoints

### Data Farmer (Port 8000)
- `GET /api/symbols` - List tracked symbols
- `POST /api/symbols` - Add new symbol to track
- `GET /api/data/{symbol}` - Get historical data
- `POST /api/collect/{symbol}` - Trigger data collection
- `GET /api/status` - Service health

### Backtester (Port 8001)
- `GET /api/strategies` - List strategies
- `POST /api/strategies` - Create new strategy
- `POST /api/backtest` - Run backtest
- `GET /api/results/{job_id}` - Get backtest results
- `POST /api/optimize` - Run parameter optimization

### Algo Trader (Port 8002)
- `POST /api/strategies/deploy` - Deploy strategy to live trading
- `GET /api/positions` - Current positions and P&L
- `POST /api/orders` - Place orders
- `GET /api/alerts` - Risk alerts
- `WebSocket /ws/live` - Real-time updates

## Database Schema

### Core Tables
- `symbols`: IBKR contract details and tracking info
- `market_data`: Time-series OHLCV data
- `strategies`: Strategy definitions and parameters
- `backtest_jobs`: Backtest configurations and results
- `live_strategies`: Deployed strategy instances
- `trades`: Live and simulated trade records
- `positions`: Current portfolio positions

## Development

### Project Structure
```
scizor/
├── services/
│   ├── data-farmer/     # Market data collection service
│   ├── backtester/      # Strategy testing engine
│   └── algo-trader/     # Live trading engine
├── shared/
│   ├── database/        # Database models and connections
│   ├── ibkr/           # IBKR API integration
│   ├── models/         # Shared data models
│   └── utils/          # Common utilities
├── scripts/            # Setup and utility scripts
├── tests/              # Test suites
└── docker-compose.yml  # Infrastructure setup
```

### Testing
```bash
# Run all tests
pytest

# Run specific service tests
pytest tests/data_farmer/
pytest tests/backtester/
pytest tests/algo_trader/
```

### Code Quality
```bash
# Format code
black .
isort .

# Type checking
mypy .

# Linting
flake8 .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This software is for educational and research purposes only. Trading involves significant risk and can result in substantial losses. Use at your own risk and always consult with qualified financial professionals before making trading decisions.
