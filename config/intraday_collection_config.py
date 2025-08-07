"""
Configuration for intraday data collection (5-minute bars, etc.)

This configuration file defines settings for collecting high-frequency market data
for symbols in the watchlist.
"""

import os
from datetime import time

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://scizor_user:scizor_password@localhost:5432/scizor_db")

# IBKR Configuration
IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("IBKR_PORT", "4002"))  # Paper trading port
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID_INTRADAY", "11"))  # Different client ID for intraday collection

# Collection Settings
TIMEFRAMES = {
    "5min": {
        "bar_size": "5 mins",
        "duration": "2 D",  # Collect 2 days of 5min data per request
        "what_to_show": "TRADES",
        "use_rth": True,  # Regular trading hours only
        "collection_interval": 300,  # 5 minutes in seconds
        "max_requests_per_batch": 30,  # Conservative for 5min bars
        "pacing_delay": 20  # 20 seconds between requests
    },
    "1min": {
        "bar_size": "1 min",
        "duration": "1 D",  # Collect 1 day of 1min data per request
        "what_to_show": "TRADES",
        "use_rth": True,
        "collection_interval": 60,  # 1 minute in seconds
        "max_requests_per_batch": 20,  # More conservative for 1min bars
        "pacing_delay": 30  # 30 seconds between requests
    }
}

# Market Hours (for scheduling collections)
# ASX Market Hours (AEST/AEDT)
ASX_MARKET_OPEN = time(10, 0)  # 10:00 AM
ASX_MARKET_CLOSE = time(16, 0)  # 4:00 PM

# NASDAQ Market Hours (EST/EDT converted to local)
NASDAQ_MARKET_OPEN = time(23, 30)  # 11:30 PM (previous day in AEST)
NASDAQ_MARKET_CLOSE = time(6, 0)   # 6:00 AM (next day in AEST)

# Collection Schedule
COLLECTION_SCHEDULE = {
    "5min_collection_times": [
        "10:05",  # 5 minutes after ASX open
        "12:00",  # Midday
        "14:00",  # Afternoon
        "16:05",  # 5 minutes after ASX close
        "00:00",  # Midnight (during NASDAQ hours)
        "03:00",  # 3 AM (during NASDAQ hours)
        "06:05"   # 5 minutes after NASDAQ close
    ],
    "catchup_times": [
        "17:00",  # Evening catchup
        "07:00"   # Morning catchup
    ]
}

# Retry and Error Handling
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds
CONNECTION_TIMEOUT = 30  # seconds
REQUEST_TIMEOUT = 60  # seconds

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "intraday_collection.log")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Data Quality Checks
QUALITY_CHECKS = {
    "min_volume_threshold": 1000,  # Minimum volume for valid bar
    "max_price_change_pct": 0.20,  # Maximum 20% price change between bars
    "required_ohlc_fields": ["open", "high", "low", "close", "volume"],
    "validate_ohlc_relationships": True  # Ensure high >= open,close and low <= open,close
}

# Performance Settings
BATCH_SIZE = 50  # Number of bars to insert in single DB operation
MAX_CONCURRENT_REQUESTS = 3  # Maximum concurrent IBKR requests
COLLECTION_BUFFER_DAYS = 1  # Days of overlap to ensure no gaps

# Watchlist Management
DEFAULT_WATCHLIST_NAME = "high_frequency"
MAX_SYMBOLS_PER_WATCHLIST = 50  # Limit to manage API load
PRIORITY_LEVELS = {
    1: "Critical",    # Highest priority symbols
    2: "High",        # Important symbols
    3: "Medium",      # Standard tracking
    4: "Low",         # Background collection
    5: "Maintenance"  # Minimal collection
}

# Data Storage
INTRADAY_DATA_RETENTION_DAYS = 90  # Keep 90 days of intraday data
COMPRESSION_ENABLED = True  # Enable data compression for storage
ARCHIVE_OLD_DATA = True  # Archive data older than retention period

# Monitoring and Alerts
ENABLE_MONITORING = True
ALERT_THRESHOLDS = {
    "max_collection_failures": 5,  # Alert after 5 consecutive failures
    "max_data_gap_minutes": 30,    # Alert if data gap > 30 minutes
    "min_daily_collection_pct": 0.8  # Alert if < 80% of expected data collected
}

# API Rate Limiting (Conservative for intraday data)
RATE_LIMITS = {
    "requests_per_minute": 6,  # 6 requests per minute
    "requests_per_hour": 200,  # 200 requests per hour
    "daily_request_limit": 2000  # 2000 requests per day
}

# Data Collection Priorities by Exchange
EXCHANGE_PRIORITIES = {
    "ASX": {
        "trading_hours": (ASX_MARKET_OPEN, ASX_MARKET_CLOSE),
        "timezone": "Australia/Sydney",
        "priority_adjustment": 0  # No adjustment for local exchange
    },
    "NASDAQ": {
        "trading_hours": (NASDAQ_MARKET_OPEN, NASDAQ_MARKET_CLOSE),
        "timezone": "America/New_York", 
        "priority_adjustment": 1  # Slightly lower priority due to timezone
    }
}

# Emergency Settings
EMERGENCY_STOP_FILE = "/tmp/stop_intraday_collection"
MAX_MEMORY_USAGE_MB = 512  # Stop collection if memory usage exceeds this
MAX_DISK_USAGE_PCT = 90    # Stop collection if disk usage exceeds this percentage

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
