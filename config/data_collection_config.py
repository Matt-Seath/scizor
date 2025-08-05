#!/usr/bin/env python3
"""
SCIZOR Data Collection Configuration
Optimized for IBKR TWS API limits and practical data needs
"""

# Data Collection Tiers
COLLECTION_TIERS = {
    "tier_1_premium": {
        "symbols": [
            "CBA", "BHP", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG", "TLS", "WOW",
            "FMG", "RIO", "TCL", "COL", "WDS", "STO", "ALL", "XRO", "REA", "QAN"
        ],
        "timeframes": ["5min", "1day"],
        "priority": 1,
        "market_data_lines": 20,  # For 5min real-time
        "collection_method": "realtime"
    },
    
    "tier_2_standard": {
        "symbols": [
            # Next 30 most liquid ASX stocks
            "GMG", "JHX", "IAG", "CPU", "WOR", "ALX", "NCM", "MIN", "EDV", "COH",
            "AZJ", "QBE", "APA", "ASX", "AGL", "ORG", "ALD", "TAH", "CAR", "CWN",
            "IPL", "LLC", "CCL", "BSL", "AMP", "BAP", "BXB", "CHC", "DEG", "DXS"
        ],
        "timeframes": ["1day"],
        "priority": 2,
        "market_data_lines": 0,  # Historical only
        "collection_method": "historical_daily"
    },
    
    "tier_3_extended": {
        "symbols": "ALL_REMAINING_ASX200",  # ~150 remaining symbols
        "timeframes": ["1day"],
        "priority": 3,
        "market_data_lines": 0,  # Historical only
        "collection_method": "historical_daily"
    }
}

# API Limits and Configuration
API_CONFIG = {
    "max_market_data_lines": 100,  # IBKR default limit
    "reserved_lines_for_trading": 20,  # Keep some for live trading
    "available_lines_for_data": 80,  # Remaining for data collection
    
    "historical_request_delay": 2.0,  # Seconds between historical requests
    "max_historical_per_batch": 50,   # Historical requests per batch
    "batch_delay": 600,               # 10 minutes between batches
    
    "realtime_subscription_delay": 0.5,  # Delay between real-time subscriptions
}

# Collection Schedule
COLLECTION_SCHEDULE = {
    "market_hours": {
        "start": "09:30",  # AEST
        "end": "16:00",    # AEST
        "timezone": "Australia/Sydney"
    },
    
    "tier_1_realtime": {
        "frequency": "continuous",  # 5-minute bars during market hours
        "active_hours": "market_hours"
    },
    
    "tier_2_3_daily": {
        "frequency": "once_daily",
        "time": "17:00",  # After market close
        "method": "historical_batch"
    }
}

# Database Storage Strategy
STORAGE_CONFIG = {
    "single_table": True,  # Use existing market_data table
    "timeframe_separation": True,  # Different timeframe values
    "retention_policy": {
        "5min_data": "2_years",    # Keep 2 years of 5min data
        "daily_data": "10_years",  # Keep 10 years of daily data
        "cleanup_frequency": "monthly"
    }
}

# Estimated Storage Requirements
STORAGE_ESTIMATES = {
    "tier_1_5min": {
        "symbols": 20,
        "records_per_day": 20 * 79,  # 79 x 5min bars per trading day
        "records_per_year": 20 * 79 * 252,  # ~400K records
        "storage_per_year": "45MB"
    },
    
    "daily_all_symbols": {
        "symbols": 200,
        "records_per_day": 200,
        "records_per_year": 200 * 252,  # ~50K records
        "storage_per_year": "5MB"
    },
    
    "total_estimated": {
        "records_per_year": "450K",
        "storage_per_year": "50MB",
        "very_manageable": True
    }
}

# Implementation Notes
IMPLEMENTATION_NOTES = """
1. SINGLE TABLE APPROACH:
   - Use existing market_data table
   - Differentiate by timeframe column
   - Index on (symbol_id, timeframe, timestamp)

2. API LIMIT MANAGEMENT:
   - Use max 20 real-time subscriptions (well under 100 limit)
   - Historical requests for daily data (no ongoing line usage)
   - Rate limit historical requests (2 second delays)

3. COLLECTION PRIORITY:
   - Tier 1: Real-time 5min + daily (20 symbols)
   - Tier 2: Daily only (30 symbols) 
   - Tier 3: Daily only (150 symbols)

4. QUERIES OPTIMIZED:
   - SELECT * FROM market_data WHERE timeframe='5min' AND symbol_id=1
   - SELECT * FROM market_data WHERE timeframe='1day' 
   - Efficient for both backtesting and analysis

5. BENEFITS:
   ✅ Well under API limits
   ✅ Minimal storage requirements
   ✅ Single table simplicity
   ✅ Flexible for different strategies
   ✅ Expandable as account grows
"""
