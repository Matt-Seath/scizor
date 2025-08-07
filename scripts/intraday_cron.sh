#!/bin/bash
"""
Cron job script for intraday data collection

This script is designed to be run from cron to collect intraday data
at regular intervals throughout the trading day.

Add to crontab with:
# Collect 5min data every 15 minutes during market hours
*/15 9-16 * * 1-5 /path/to/scizor/scripts/intraday_cron.sh 5min

# Collect 1min data every 5 minutes during market hours (if enabled)
*/5 9-16 * * 1-5 /path/to/scizor/scripts/intraday_cron.sh 1min

# Evening catchup at 5:30 PM
30 17 * * 1-5 /path/to/scizor/scripts/intraday_cron.sh 5min catchup
"""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_ENV="$PROJECT_ROOT/.venv/bin/python"
COLLECTION_SCRIPT="$SCRIPT_DIR/intraday_collection.py"
LOG_DIR="$PROJECT_ROOT/logs"
LOCK_FILE="/tmp/scizor_intraday.lock"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_DIR/intraday_cron.log"
}

# Function to check if collection is already running
check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        # Check if the process is still running
        if kill -0 $(cat "$LOCK_FILE") 2>/dev/null; then
            log_message "Collection already running (PID: $(cat "$LOCK_FILE"))"
            exit 1
        else
            # Remove stale lock file
            rm -f "$LOCK_FILE"
        fi
    fi
}

# Function to create lock file
create_lock() {
    echo $$ > "$LOCK_FILE"
}

# Function to remove lock file
remove_lock() {
    rm -f "$LOCK_FILE"
}

# Trap to ensure lock file is removed on exit
trap 'remove_lock; exit' INT TERM EXIT

# Main function
main() {
    local timeframe=${1:-"5min"}
    local mode=${2:-"normal"}
    
    log_message "Starting intraday collection: timeframe=$timeframe, mode=$mode"
    
    # Check if another collection is running
    check_lock
    
    # Create lock file
    create_lock
    
    # Determine collection parameters based on mode
    case "$mode" in
        "catchup")
            BACKFILL_DAYS=3
            WATCHLIST="default_intraday"
            log_message "Running catchup collection (3 days backfill)"
            ;;
        "test")
            BACKFILL_DAYS=1
            WATCHLIST="default_intraday"
            TEST_MODE="--test-mode"
            log_message "Running test collection"
            ;;
        *)
            BACKFILL_DAYS=1
            WATCHLIST="default_intraday"
            TEST_MODE=""
            log_message "Running normal collection"
            ;;
    esac
    
    # Check if Python environment exists
    if [ ! -f "$PYTHON_ENV" ]; then
        log_message "ERROR: Python environment not found at $PYTHON_ENV"
        exit 1
    fi
    
    # Check if collection script exists
    if [ ! -f "$COLLECTION_SCRIPT" ]; then
        log_message "ERROR: Collection script not found at $COLLECTION_SCRIPT"
        exit 1
    fi
    
    # Run the collection
    log_message "Executing: $PYTHON_ENV $COLLECTION_SCRIPT --timeframe $timeframe --watchlist $WATCHLIST --backfill $BACKFILL_DAYS $TEST_MODE"
    
    # Redirect output to log file
    if "$PYTHON_ENV" "$COLLECTION_SCRIPT" \
        --timeframe "$timeframe" \
        --watchlist "$WATCHLIST" \
        --backfill "$BACKFILL_DAYS" \
        $TEST_MODE \
        >> "$LOG_DIR/intraday_collection.log" 2>&1; then
        
        log_message "Collection completed successfully"
    else
        log_message "ERROR: Collection failed with exit code $?"
        exit 1
    fi
}

# Check command line arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <timeframe> [mode]"
    echo "  timeframe: 5min or 1min"
    echo "  mode: normal, catchup, or test (default: normal)"
    exit 1
fi

# Run main function
main "$@"
