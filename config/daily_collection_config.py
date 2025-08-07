#!/usr/bin/env python3
"""
Configuration for Daily Market Data Collection
"""

# IBKR Connection Settings
IBKR_HOST = "127.0.0.1"
IBKR_PORTS = [4002, 4001, 7497]  # Try Paper Trading first, then Gateway, then TWS
IBKR_CLIENT_ID = 100  # Unique client ID for daily collection

# TWS API Pacing Settings (from TWS API documentation)
MAX_REQUESTS_PER_BATCH = 50  # Max 60 per 10 minutes, leaving buffer
BATCH_DELAY_SECONDS = 600    # 10 minutes between batches
REQUEST_DELAY_SECONDS = 6    # Small delay between individual requests

# Data Collection Settings
DEFAULT_DURATION = "1 D"      # 1 day of data
DEFAULT_BAR_SIZE = "1 day"    # Daily bars
DEFAULT_WHAT_TO_SHOW = "TRADES"  # TRADES data includes OHLCV
USE_REGULAR_TRADING_HOURS = True  # Only collect RTH data
REQUEST_TIMEOUT = 30.0        # Timeout for individual requests

# Logging Configuration
LOG_FILE = "/tmp/daily_market_data.log"
LOG_LEVEL = "INFO"

# Market Hours (for determining previous trading day)
MARKET_CLOSE_HOUR = 16  # 4 PM local time
MARKET_CLOSE_MINUTE = 0

# Retry Settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Exchange Mappings for Contract Creation
EXCHANGE_MAPPINGS = {
    "ASX": {
        "exchange": "ASX",
        "primary_exchange": "ASX",
        "currency": "AUD",
        "timezone": "Australia/Sydney"
    },
    "NASDAQ": {
        "exchange": "SMART",
        "primary_exchange": "NASDAQ", 
        "currency": "USD",
        "timezone": "US/Eastern"
    },
    "NYSE": {
        "exchange": "SMART",
        "primary_exchange": "NYSE",
        "currency": "USD",
        "timezone": "US/Eastern"
    },
    "LSE": {
        "exchange": "SMART",
        "primary_exchange": "LSE",
        "currency": "GBP",
        "timezone": "Europe/London"
    },
    "TSE": {
        "exchange": "SMART",
        "primary_exchange": "TSE",
        "currency": "JPY",
        "timezone": "Asia/Tokyo"
    },
    "HKEX": {
        "exchange": "SMART",
        "primary_exchange": "SEHK",
        "currency": "HKD",
        "timezone": "Asia/Hong_Kong"
    },
    "EURONEXT": {
        "exchange": "SMART",
        "primary_exchange": "EURONEXT",
        "currency": "EUR",
        "timezone": "Europe/Paris"
    },
    "TSX": {
        "exchange": "SMART",
        "primary_exchange": "TSE",
        "currency": "CAD",
        "timezone": "America/Toronto"
    }
}

# Timezone Mappings for IBKR Date Formatting
# IBKR expects timezone-aware date strings to avoid deprecation warnings
TIMEZONE_MAPPINGS = {
    "ASX": "Australia/Sydney",
    "NASDAQ": "US/Eastern", 
    "NYSE": "US/Eastern",
    "LSE": "Europe/London",
    "TSE": "Asia/Tokyo",
    "HKEX": "Asia/Hong_Kong",
    "EURONEXT": "Europe/Paris",
    "TSX": "America/Toronto"
}

# Security Type Mappings
SECURITY_TYPE_MAPPINGS = {
    "STOCK": "STK",
    "ETF": "STK",  # ETFs are treated as stocks in IBKR
    "INDEX": "IND",
    "FOREX": "CASH",
    "FUTURE": "FUT",
    "OPTION": "OPT",
    "BOND": "BOND",
    "COMMODITY": "CMDTY",
    "CFD": "CFD"
}
