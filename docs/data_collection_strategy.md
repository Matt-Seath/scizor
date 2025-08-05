# SCIZOR Data Collection Strategy

## Overview
Optimal market data collection strategy for algorithmic trading and backtesting.

## Timeframe Strategy

### Primary: 5-Minute Bars
- **Frequency**: Continuous during market hours (9:30 AM - 4:00 PM AEST)
- **Symbols**: All active symbols in database
- **Storage**: ~288 records per symbol per day
- **Use Cases**: 
  - Intraday strategy development
  - Real-time monitoring
  - Most backtesting scenarios
  - Technical indicator calculations

### Secondary: Daily Bars  
- **Frequency**: Once daily after market close
- **Symbols**: All symbols including less liquid
- **Storage**: 1 record per symbol per day
- **Use Cases**:
  - Position sizing
  - Longer-term trend analysis
  - Portfolio rebalancing
  - Risk management

### Specialized: Tick Data
- **Frequency**: Real-time tick-by-tick
- **Symbols**: Top 20 most liquid (ASX20)
- **Storage**: High volume (1000s per symbol per day)
- **Use Cases**:
  - High-frequency trading
  - Order book analysis
  - Precise entry/exit timing
  - Market microstructure research

## Symbol Selection Priority

### Tier 1: ASX 20 (Always Collect)
Top 20 most liquid stocks - all timeframes including tick data

### Tier 2: ASX 50 (5min + Daily)
Next 30 liquid stocks - 5-minute and daily bars

### Tier 3: ASX 200 (Daily Only)
Remaining 150 stocks - daily bars only

## Data Collection Schedule

```
09:30 - 16:00  : Continuous 5min bars (Tier 1 + 2)
09:30 - 16:00  : Tick data (Tier 1 only)
16:30          : Daily bars (All tiers)
18:00          : Data validation and cleanup
```

## Storage Estimates

| Timeframe | Symbols | Records/Day | Records/Year | Storage/Year |
|-----------|---------|-------------|--------------|--------------|
| 5min      | 50      | 14,400      | 3.7M         | ~400MB       |
| Daily     | 200     | 200         | 52K          | ~5MB         |
| Tick      | 20      | 50,000      | 13M          | ~1.5GB       |
| **Total** |         |             | **16.8M**    | **~2GB**     |

## Implementation Notes

- Use `timeframe="5min"` for primary strategy development
- Use `timeframe="1day"` for portfolio-level analysis  
- Use `timeframe="tick"` only for HFT or specialized research
- Prioritize data quality over quantity
- Implement proper error handling and gap detection
- Store all timestamps in UTC for consistency
