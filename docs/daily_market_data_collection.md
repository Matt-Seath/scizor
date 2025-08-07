# Daily Market Data Collection System

## Overview

This system provides automated daily collection of market data for all symbols in the Scizor database using the Interactive Brokers TWS API. It follows TWS API best practices and pacing requirements to ensure reliable data collection.

## Features

- **Comprehensive Symbol Support**: Collects data for all active symbols (ASX 200, NASDAQ, ETFs)
- **TWS API Compliance**: Respects pacing limitations (max 60 requests per 10 minutes)
- **Robust Error Handling**: Comprehensive logging and retry mechanisms
- **Flexible Scheduling**: Can be run manually or via cron job
- **Dry Run Mode**: Test the system without actually collecting data
- **Batch Processing**: Processes symbols in batches to respect API limits
- **Duplicate Prevention**: Skips symbols that already have data for the target date

## System Requirements

### Software Requirements
- Python 3.8+
- PostgreSQL database with Scizor schema
- IBKR TWS Gateway or TWS application
- Required Python packages (see requirements.txt)

### IBKR Requirements
- Active IBKR account with market data permissions
- TWS Gateway or TWS application running
- API permissions enabled in TWS/Gateway settings

## Configuration

### Database Setup
Ensure your database contains symbols to collect data for:
```bash
# Populate symbols if not already done
python scripts/populate_symbols.py
```

### IBKR Setup
1. Start IBKR TWS Gateway or TWS application
2. Ensure API settings are configured:
   - Enable ActiveX and Socket Clients
   - Set Socket Port (4001 for Gateway, 7497 for TWS)
   - Trust this IP address: 127.0.0.1
3. Log in with valid credentials

### Configuration Files
- `config/daily_collection_config.py`: Main configuration settings
- Modify settings as needed for your environment

## Usage

### Manual Execution

#### Basic Usage
```bash
# Collect data for previous trading day
python scripts/daily_market_data_collection.py

# Collect data for specific date
python scripts/daily_market_data_collection.py --date 2025-01-15

# Dry run (test without collecting)
python scripts/daily_market_data_collection.py --dry-run
```

#### Test the System
```bash
# Run comprehensive tests
python scripts/test_daily_collection.py
```

### Automated Execution (Cron Job)

#### Setup Cron Job
```bash
# Edit crontab
crontab -e

# Add one of these entries:

# Option 1: Run daily at 6 PM after market close (weekdays only)
0 18 * * 1-5 /Users/seath/github/scizor/scripts/daily_collection_cron.sh

# Option 2: Run daily at 7 AM for previous day data (Tue-Sat for Mon-Fri data)
0 7 * * 2-6 /Users/seath/github/scizor/scripts/daily_collection_cron.sh

# Option 3: Run twice daily for redundancy
0 18 * * 1-5 /Users/seath/github/scizor/scripts/daily_collection_cron.sh
0 7 * * 2-6 /Users/seath/github/scizor/scripts/daily_collection_cron.sh
```

#### Cron Job Features
- Automatic logging to `/tmp/daily_market_data_cron.log`
- Email notifications (if configured)
- Cleanup of old log files
- Error handling and notification

## API Pacing and Limits

The system respects TWS API limitations:

### Historical Data Limits
- **Small Bar Sizes** (1 day and smaller): 60 requests per 10 minutes
- **Large Bar Sizes** (larger than 1 day): 60 requests per 10 minutes

### Our Implementation
- **Batch Size**: 50 requests per batch (leaves buffer)
- **Batch Delay**: 10 minutes between batches
- **Request Delay**: 6 seconds between individual requests
- **Timeout**: 30 seconds per request

### Calculation Example
With 309 symbols:
- Batches needed: 309 ÷ 50 = 7 batches
- Total time: 7 batches × 10 minutes = ~70 minutes
- Plus individual request delays: ~30 minutes
- **Total runtime**: ~100 minutes for all symbols

## Data Storage

### Market Data Table Schema
```sql
CREATE TABLE market_data (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER REFERENCES symbols(id),
    timestamp TIMESTAMP NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    open NUMERIC(10,4) NOT NULL,
    high NUMERIC(10,4) NOT NULL,
    low NUMERIC(10,4) NOT NULL,
    close NUMERIC(10,4) NOT NULL,
    volume INTEGER DEFAULT 0,
    wap NUMERIC(10,4),
    bar_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Collection Logs
The system maintains logs of collection attempts:
```sql
CREATE TABLE collection_logs (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER REFERENCES symbols(id),
    collection_type VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    records_collected INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

## Monitoring and Troubleshooting

### Log Files
- **Application Log**: `/tmp/daily_market_data.log`
- **Cron Job Log**: `/tmp/daily_market_data_cron.log`

### Common Issues

#### 1. IBKR Connection Failures
```
Error: Could not connect to IBKR on any port
```
**Solutions**:
- Ensure TWS Gateway or TWS is running
- Check API settings in TWS/Gateway
- Verify port numbers (4001 for Gateway, 7497 for TWS)
- Check firewall settings

#### 2. Market Data Permission Errors
```
Error 354: Requested market data is not subscribed
```
**Solutions**:
- Verify market data subscriptions in IBKR account
- Check if real-time or delayed data is available
- Ensure account has appropriate permissions

#### 3. Pacing Violations
```
Error 162: Historical Market Data Service error message
```
**Solutions**:
- Reduce batch size in configuration
- Increase delays between requests
- Wait for pacing window to reset

#### 4. Database Connection Issues
```
Error: Database connectivity test failed
```
**Solutions**:
- Check PostgreSQL is running
- Verify database credentials
- Ensure database schema is up to date

### Monitoring Queries

#### Check Recent Collections
```sql
SELECT 
    s.symbol,
    s.exchange,
    cl.status,
    cl.started_at,
    cl.completed_at,
    cl.error_message
FROM collection_logs cl
JOIN symbols s ON cl.symbol_id = s.id
WHERE cl.started_at >= CURRENT_DATE
ORDER BY cl.started_at DESC;
```

#### Check Market Data Coverage
```sql
SELECT 
    s.symbol,
    s.exchange,
    COUNT(md.id) as data_points,
    MAX(md.timestamp) as latest_data
FROM symbols s
LEFT JOIN market_data md ON s.id = md.symbol_id 
    AND md.timeframe = '1day'
WHERE s.active = true
GROUP BY s.id, s.symbol, s.exchange
ORDER BY latest_data DESC NULLS LAST;
```

#### Collection Statistics
```sql
SELECT 
    DATE(cl.started_at) as collection_date,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN cl.status = 'completed' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN cl.status = 'failed' THEN 1 ELSE 0 END) as failed,
    AVG(EXTRACT(EPOCH FROM (cl.completed_at - cl.started_at))) as avg_duration_seconds
FROM collection_logs cl
WHERE cl.collection_type = 'historical'
    AND cl.started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(cl.started_at)
ORDER BY collection_date DESC;
```

## Performance Optimization

### Reduce Collection Time
1. **Prioritize Symbols**: Use the `priority` field in symbols table
2. **Parallel Processing**: Consider running multiple instances with different symbol subsets
3. **Incremental Updates**: Only collect missing dates

### Example Priority-Based Collection
```python
# Collect high-priority symbols first
python scripts/daily_market_data_collection.py --priority-only

# Collect remaining symbols later
python scripts/daily_market_data_collection.py --low-priority
```

## Security Considerations

1. **IBKR Credentials**: Never store credentials in code
2. **Database Access**: Use environment variables for database credentials
3. **API Keys**: Secure any API keys used
4. **Log Files**: Ensure log files don't contain sensitive information
5. **Network Security**: Restrict TWS API access to trusted IPs

## Backup and Recovery

### Database Backups
```bash
# Backup market data
pg_dump -t market_data scizor_db > market_data_backup.sql

# Backup collection logs
pg_dump -t collection_logs scizor_db > collection_logs_backup.sql
```

### Recovery Procedures
```bash
# Restore market data
psql scizor_db < market_data_backup.sql

# Re-run failed collections
python scripts/daily_market_data_collection.py --retry-failed
```

## Development and Testing

### Test Suite
```bash
# Run all tests
python scripts/test_daily_collection.py

# Test specific components
python -m pytest tests/test_data_collection.py
```

### Development Mode
```bash
# Debug mode with verbose logging
python scripts/daily_market_data_collection.py --debug --dry-run
```

## Future Enhancements

1. **Real-time Data Integration**: Extend to collect intraday data
2. **Multiple Timeframes**: Support 1min, 5min, 1hour bars
3. **Data Quality Checks**: Validate collected data
4. **Performance Metrics**: Track collection performance
5. **Alert System**: Advanced monitoring and alerting
6. **Web Dashboard**: GUI for monitoring collections

## Support

For issues or questions:
1. Check log files for error messages
2. Run test suite to identify problems
3. Review IBKR API documentation
4. Check database connectivity and permissions

## Version History

- **v1.0**: Initial implementation with basic daily collection
- **v1.1**: Added comprehensive error handling and logging
- **v1.2**: Implemented TWS API pacing compliance
- **v1.3**: Added cron job support and monitoring

---

*Last updated: January 2025*
