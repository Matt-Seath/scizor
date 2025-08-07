#!/bin/bash
"""
Daily Market Data Collection Cron Job Script

This script is designed to be run as a daily cron job to collect market data
for all symbols in the database using the IBKR TWS API.

Setup Instructions:
1. Ensure IBKR TWS Gateway or TWS is running on the system
2. Make this script executable: chmod +x daily_collection_cron.sh
3. Add to crontab for daily execution

Example crontab entries:
# Run daily at 6 PM after market close (ASX closes at 4 PM AEST)
0 18 * * 1-5 /Users/seath/github/scizor/scripts/daily_collection_cron.sh

# Run daily at 7 AM for previous day data
0 7 * * 2-6 /Users/seath/github/scizor/scripts/daily_collection_cron.sh

Note: Adjust timing based on your timezone and market schedules
"""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$SCRIPT_DIR/daily_market_data_collection.py"
LOG_FILE="/tmp/daily_market_data_cron.log"
NOTIFICATION_EMAIL=""  # Set this if you want email notifications

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to send notification (if email is configured)
send_notification() {
    local subject="$1"
    local message="$2"
    
    if [ -n "$NOTIFICATION_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$NOTIFICATION_EMAIL" 2>/dev/null || true
    fi
}

# Main execution
main() {
    log_message "Starting daily market data collection cron job"
    
    # Change to project directory
    cd "$PROJECT_ROOT" || {
        log_message "ERROR: Failed to change to project directory: $PROJECT_ROOT"
        send_notification "Daily Market Data Collection - ERROR" "Failed to change to project directory"
        exit 1
    }
    
    # Check if IBKR Gateway/TWS is running
    if ! pgrep -f "ibgateway\|tws" > /dev/null; then
        log_message "WARNING: IBKR Gateway/TWS does not appear to be running"
        log_message "Attempting to collect data anyway (may fail if not connected)"
    else
        log_message "IBKR Gateway/TWS is running"
    fi
    
    # Run the collection script
    log_message "Executing daily market data collection script"
    
    if python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1; then
        log_message "Daily market data collection completed successfully"
        send_notification "Daily Market Data Collection - SUCCESS" "Daily market data collection completed successfully"
    else
        log_message "ERROR: Daily market data collection failed"
        send_notification "Daily Market Data Collection - FAILURE" "Daily market data collection failed. Check logs for details."
        exit 1
    fi
    
    # Optional: Clean up old log files (keep last 30 days)
    find /tmp -name "daily_market_data*.log" -mtime +30 -delete 2>/dev/null || true
    
    log_message "Cron job completed"
}

# Execute main function
main "$@"
