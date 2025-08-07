# Daily Market Data Collection - Quick Reference

## Quick Start Commands

```bash
# Test the system (recommended first run)
python scripts/test_daily_collection.py

# Dry run to see what would be collected
python scripts/daily_market_data_collection.py --dry-run

# Collect data for yesterday (automatic)
python scripts/daily_market_data_collection.py

# Collect data for specific date
python scripts/daily_market_data_collection.py --date 2025-01-15
```

## Prerequisites Checklist

- [ ] IBKR TWS Gateway or TWS running
- [ ] Database populated with symbols
- [ ] Python environment configured
- [ ] Market data permissions in IBKR account

## Setup Cron Job (One-time)

```bash
# Make script executable
chmod +x scripts/daily_collection_cron.sh

# Edit crontab
crontab -e

# Add this line for daily 6 PM collection (weekdays)
0 18 * * 1-5 /Users/seath/github/scizor/scripts/daily_collection_cron.sh
```

## Check Collection Status

```sql
-- Recent collections
SELECT s.symbol, cl.status, cl.started_at, cl.error_message
FROM collection_logs cl
JOIN symbols s ON cl.symbol_id = s.id
WHERE cl.started_at >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY cl.started_at DESC;

-- Data coverage
SELECT COUNT(*) as symbols_with_data, MAX(timestamp) as latest_data
FROM market_data
WHERE timeframe = '1day';
```

## Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| Can't connect to IBKR | Check TWS/Gateway is running on port 4001 or 7497 |
| Market data permissions | Verify subscriptions in IBKR account |
| Database errors | Check PostgreSQL is running |
| Slow collection | Normal - 309 symbols takes ~100 minutes |

## Log Locations

- Application: `/tmp/daily_market_data.log`
- Cron job: `/tmp/daily_market_data_cron.log`

## Expected Runtime

- **309 symbols**: ~100 minutes total
- **Batch processing**: 50 symbols per 10-minute batch
- **7 batches**: Complete collection in ~1.5 hours

## Success Indicators

✅ All tests pass  
✅ No connection errors in logs  
✅ Market data records created in database  
✅ Collection logs show "completed" status
