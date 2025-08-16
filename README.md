# ASX200 Swing Trading Algorithm

> **⚠️ IMPORTANT DISCLAIMER**: This is an automated algorithmic trading system that involves real financial risk. Trading involves the possibility of financial loss. Only use this system with capital you can afford to lose. Past performance does not guarantee future results.

An automated swing trading system for ASX200 stocks using the IBKR TWS API. Designed for professional day-traders seeking consistent returns with minimal manual intervention.

## 🎯 Project Overview

**Primary Goal**: Generate consistent returns (15-25% annually) through automated swing trading with minimal maintenance  
**Target Market**: ASX200 stocks only  
**Trading Style**: Swing trading (2-10 day holding periods)  
**Risk Management**: Conservative approach with strict risk controls  

### Key Features

- 🤖 **Fully Automated**: Minimal manual intervention required
- 📊 **Multiple Strategies**: Momentum breakout, mean reversion, and earnings momentum
- 🛡️ **Risk Management**: Comprehensive position sizing and stop-loss management
- 📈 **Real-time Monitoring**: Live performance tracking and alerting
- 🔄 **Backtesting**: Historical strategy validation and optimization
- 🐳 **Docker Support**: Containerized deployment for consistency

## 🏗️ Technical Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Python 3.11+ | Core trading logic and data processing |
| **Web Framework** | FastAPI | High-performance API with automatic docs |
| **Database** | PostgreSQL 15+ | ACID-compliant financial data storage |
| **Task Queue** | Celery + Redis | Reliable scheduled operations |
| **Market Data** | IBKR TWS API | Real-time and historical market data |
| **Deployment** | Docker + Compose | Consistent multi-environment deployment |
| **Monitoring** | Prometheus + Grafana | System health and performance metrics |
| **Testing** | pytest | Comprehensive unit and integration tests |

## 📋 Requirements

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose
- IBKR TWS or Gateway (running locally or remotely)

### IBKR Data Subscription

**CRITICAL**: Live trading requires paid market data subscriptions:

- **ASX Real-time Data**: ~$45 AUD/month (required for production)
- **Development**: Free delayed data available (15-20 min delay)
- **Paper Trading**: Use delayed data for strategy validation

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/asx200-trading-algorithm.git
cd asx200-trading-algorithm

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trading_db

# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # TWS: 7497, Gateway: 4001
IBKR_CLIENT_ID=1

# Trading Configuration
MAX_POSITIONS=5
MAX_RISK_PER_TRADE=0.02
DAILY_LOSS_LIMIT=0.03
```

### 3. Start with Docker

```bash
# Start all services
docker-compose up -d

# Initialize database
docker-compose exec app python scripts/setup_db.py

# Verify installation
curl http://localhost:8000/health
```

### 4. Access Dashboard

- **API Documentation**: http://localhost:8000/docs
- **Trading Dashboard**: http://localhost:8000/dashboard
- **Grafana Monitoring**: http://localhost:3000

## 📊 Trading Strategies

### 1. Momentum Breakout
- **Logic**: 20-day high breakout with volume confirmation
- **Entry**: Price breaks 20-day high + volume > 1.5x average + RSI > 50
- **Target**: 5-7 day holding period
- **Risk**: 2-3x ATR stop loss

### 2. Mean Reversion
- **Logic**: Oversold bounce with technical confirmation
- **Entry**: RSI < 30 + bounce off lower Bollinger Band + volume confirmation
- **Target**: Return to 20-day moving average
- **Risk**: Time-based stop (5 days) or 3% stop loss

### 3. Earnings Momentum
- **Logic**: Post-earnings drift capture
- **Entry**: Earnings surprise > 5% + positive analyst revisions
- **Target**: 5-day momentum capture
- **Risk**: Event-based stop on negative news

## 🛡️ Risk Management

### Position Sizing
- **Method**: Kelly Criterion with 0.25 maximum fraction
- **Individual Trade**: Maximum 2% portfolio risk
- **Total Exposure**: Maximum 20% of portfolio
- **Concurrent Positions**: Maximum 5 positions

### Stop Loss Rules
- **Technical**: 2-3x ATR-based dynamic stops
- **Time-based**: Maximum 14 days for swing trades
- **Profit Protection**: Trailing stops after 1.5R profit

### Portfolio Limits
- **Daily Loss**: 3% of portfolio (system shutdown)
- **Monthly Drawdown**: 10% maximum
- **Correlation**: Maximum 0.7 between positions

## 📈 Performance Targets

| Metric | Target | Monitoring |
|--------|--------|------------|
| **Annual Return** | 15-25% | Daily tracking |
| **Sharpe Ratio** | >1.2 | Weekly calculation |
| **Maximum Drawdown** | <15% | Real-time monitoring |
| **Win Rate** | 45-55% | Monthly analysis |
| **Average Hold** | 5-7 days | Strategy-specific |

## 🔧 Development

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install
```

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running IBKR TWS)
pytest tests/integration/ -v

# Coverage report
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/ tests/
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/

# Security scan
bandit -r app/
```

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   IBKR TWS/GW   │───▶│  Data Collector │───▶│   PostgreSQL    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     FastAPI     │◀───│  Signal Engine  │◀───│  Technical Proc │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │    │ Order Manager   │───▶│   Risk Engine   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔍 Monitoring & Alerts

### System Health
- **Uptime**: >99.5% target
- **Data Collection**: >99% success rate
- **Order Execution**: >98% success rate
- **Response Time**: <500ms API, <5s signals

### Alert Types
- **Critical**: System down, risk breach, execution errors
- **Warning**: Performance below targets, correlation alerts
- **Info**: Daily performance summaries, weekly reports

## 📚 Documentation

- **[API Documentation](docs/api.md)**: Endpoint specifications
- **[Strategy Guide](docs/strategies.md)**: Detailed strategy explanations  
- **[Deployment Guide](docs/deployment.md)**: Production deployment instructions
- **[Development Setup](docs/development.md)**: Local development environment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure:
- ✅ All tests pass (`pytest`)
- ✅ Code is formatted (`black`, `isort`)
- ✅ Type hints are complete (`mypy`)
- ✅ Documentation is updated

## ⚖️ Legal & Compliance

### Risk Disclosures
- **Financial Risk**: All trading involves risk of financial loss
- **System Risk**: Automated systems can fail or produce unexpected results
- **Market Risk**: Past performance does not guarantee future results
- **Monitoring Required**: Regular oversight and intervention may be necessary

### Regulatory Compliance
- Designed for compliance with ASX trading rules
- Maintains audit trail for all trading decisions
- Implements required record-keeping for professional trading
- Regular compliance monitoring and reporting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support & Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/asx200-trading-algorithm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/asx200-trading-algorithm/discussions)
- **Email**: trading-support@yourdomain.com

---

## ⚠️ Final Warning

**This software is provided "as-is" without warranty of any kind. Use at your own risk. Only trade with capital you can afford to lose. Ensure you understand the risks involved in algorithmic trading before using this system.**

**Always test thoroughly in paper trading mode before deploying with real capital.**