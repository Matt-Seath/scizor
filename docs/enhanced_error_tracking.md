# Enhanced Error Tracking System

This document describes the enhanced error tracking capabilities added to the SCIZOR data collection system.

## Overview

The enhanced error tracking system provides detailed analysis and categorization of errors that occur during data collection, enabling better debugging, monitoring, and system reliability improvements.

## Database Schema Changes

### New CollectionLog Columns

The `collection_logs` table has been enhanced with the following columns:

```sql
-- IBKR-specific error code (e.g., 200, 162, 1100)
error_code INTEGER

-- Categorized error type (e.g., "SECURITY_NOT_FOUND", "CONNECTION_ERROR")
error_type VARCHAR(50)

-- IBKR request ID for tracking specific requests
ibkr_request_id INTEGER

-- Number of retry attempts for this collection
retry_count INTEGER DEFAULT 0

-- Detailed error information in JSON format
error_details JSONB
```

### Performance Indexes

New indexes have been created for efficient querying:

- `idx_collection_logs_error_code` - For filtering by error codes
- `idx_collection_logs_error_type` - For grouping by error types
- `idx_collection_logs_retry_count` - For analyzing retry patterns
- `idx_collection_logs_started_at` - For time-based queries
- `idx_collection_logs_status_date` - For status and date combinations

## Error Analysis Components

### 1. ErrorAnalyzer Class (`shared/utils/error_analysis.py`)

The `ErrorAnalyzer` provides comprehensive error categorization:

#### IBKR Error Code Mapping
```python
IBKR_ERROR_CATEGORIES = {
    200: "no_security_definition",        # Symbol not found
    162: "historical_data_query_error",   # Data query issues
    1100: "connectivity_lost",            # Connection problems
    # ... and many more
}
```

#### Error Severity Classification
- **Critical**: System-stopping errors (connection failures)
- **High**: Symbol-specific issues (delisted stocks)
- **Medium**: Retryable errors (rate limiting)
- **Low**: Temporary issues (brief disconnections)

#### Key Methods
- `analyze_error()` - Comprehensive error analysis
- `format_error_summary()` - Human-readable error summaries
- `get_common_error_patterns()` - Known error patterns and solutions

### 2. Enhanced Daily Collection Script

The daily collection script now captures detailed error information:

#### New Return Format
```python
success, error_info = await self._request_historical_data(symbol, target_date)
```

#### Error Information Structure
```python
error_info = {
    "error_type": "IBKR_ERROR",
    "error_message": "No security definition found",
    "error_code": 200,
    "request_id": 12345,
    "symbol": "DELISTED_STOCK",
    "timestamp": "2025-08-07T10:30:00"
}
```

### 3. Collection Error Analyzer (`scripts/analyze_collection_errors.py`)

Provides comprehensive error analysis and reporting:

#### Features
- **Recent Error Analysis**: Last 7 days by default
- **Error Trends**: 30-day trend analysis
- **Pattern Recognition**: Identifies common error patterns
- **Recommendations**: Actionable suggestions for improvement
- **Problematic Symbol Detection**: Identifies symbols with multiple failures

#### Usage
```bash
python3 scripts/analyze_collection_errors.py
```

#### Sample Output
```
📊 COLLECTION ERROR ANALYSIS REPORT
======================================================================

📈 SUMMARY
   • Total Errors: 127
   • Average Daily Errors: 18.1
   • Peak Error Day: 2025-08-06 (45 errors)

🔢 TOP ERROR CODES
   • Code 200: 89 errors (70.1%) - no_security_definition
   • Code 162: 23 errors (18.1%) - historical_data_query_error
   • Code 1100: 15 errors (11.8%) - connectivity_lost

💡 RECOMMENDATIONS
   1. 🚨 89 'No security definition' errors - Consider running symbol cleanup
   2. 📊 12 symbols with multiple failures - Investigate these symbols
```

## Error Detail Structure

The `error_details` JSONB column stores comprehensive error information:

```json
{
  "timestamp": "2025-08-07T10:30:00.123456",
  "error_code": 200,
  "error_message": "No security definition has been found for the request",
  "request_id": 12345,
  "error_category": "no_security_definition",
  "error_type": "SECURITY_NOT_FOUND",
  "severity": "high",
  "is_retryable": false,
  "suggested_action": "deactivate_symbol",
  "raw_details": {
    "error_code": 200,
    "error_message": "No security definition has been found for the request",
    "request_id": 12345
  },
  "message_keywords": ["no_security_definition"],
  "extracted_symbols": ["GXY"],
  "contains_symbol_reference": true
}
```

## Common Error Patterns

### 1. Security Not Found (Code 200)
**Cause**: Symbol delisted, merged, or suspended
**Solution**: Run symbol cleanup script to deactivate problematic symbols

### 2. Connection Issues (Codes 1100, 1102, 502, 503)
**Cause**: IBKR TWS/Gateway connectivity problems
**Solution**: Check connection stability, implement retry logic

### 3. Rate Limiting (Code 162, 420)
**Cause**: Too many requests or pacing violations
**Solution**: Increase delays between requests, implement backoff

## Monitoring and Alerting

### Daily Error Summary
Monitor the following metrics daily:
- Total error count
- Error rate percentage
- New error codes/types
- Problematic symbol count

### Alert Thresholds
- **Critical**: >5% error rate
- **Warning**: >10 errors for same symbol in 24 hours
- **Info**: New error codes detected

## Querying Error Data

### Most Common Errors (Last 7 Days)
```sql
SELECT 
    error_code,
    error_type,
    COUNT(*) as error_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
FROM collection_logs 
WHERE status = 'failed' 
    AND started_at >= NOW() - INTERVAL '7 days'
    AND error_code IS NOT NULL
GROUP BY error_code, error_type
ORDER BY error_count DESC;
```

### Problematic Symbols
```sql
SELECT 
    s.symbol,
    s.company_name,
    COUNT(*) as failure_count,
    MAX(cl.started_at) as last_failure
FROM collection_logs cl
JOIN symbols s ON cl.symbol_id = s.id
WHERE cl.status = 'failed'
    AND cl.started_at >= NOW() - INTERVAL '7 days'
GROUP BY s.id, s.symbol, s.company_name
HAVING COUNT(*) >= 3
ORDER BY failure_count DESC;
```

### Error Details Analysis
```sql
SELECT 
    error_details->>'error_category' as category,
    error_details->>'severity' as severity,
    COUNT(*) as count
FROM collection_logs
WHERE error_details IS NOT NULL
    AND started_at >= NOW() - INTERVAL '7 days'
GROUP BY 
    error_details->>'error_category',
    error_details->>'severity'
ORDER BY count DESC;
```

## Best Practices

### 1. Regular Monitoring
- Run error analysis weekly
- Monitor error trends daily
- Set up automated alerts for critical errors

### 2. Proactive Maintenance
- Clean up problematic symbols monthly
- Update error handling for new error patterns
- Review and adjust retry logic based on error analysis

### 3. Documentation
- Document new error patterns as they're discovered
- Update error categories for new IBKR error codes
- Maintain runbooks for common error scenarios

## Future Enhancements

### Planned Features
1. **Automated Symbol Cleanup**: Auto-deactivate symbols with persistent errors
2. **Error Prediction**: ML-based error prediction and prevention
3. **Real-time Alerting**: Slack/email notifications for critical errors
4. **Error Dashboard**: Web-based error monitoring dashboard
5. **Historical Analysis**: Long-term error pattern analysis

### Potential Improvements
- Error clustering and similarity detection
- Automated retry with exponential backoff
- Symbol health scoring based on error history
- Integration with IBKR status APIs for proactive error handling

## Migration and Deployment

The enhanced error tracking system has been deployed with:

1. ✅ Database schema migration (`migrate_collection_logs_enhanced_errors.py`)
2. ✅ Enhanced error analysis utilities
3. ✅ Updated daily collection script
4. ✅ Error analysis and reporting tools
5. ✅ Documentation and best practices

The system is backward compatible and existing functionality remains unchanged.
