"""
Example usage scripts for the stock data collection system.
"""

# Example 1: Basic data collection setup
def setup_basic_collection():
    """Set up basic data collection for popular stocks."""
    from scizor.database.collector import StockDataCollector
    from datetime import datetime, timedelta
    
    # Initialize collector
    collector = StockDataCollector()
    
    # Define symbols to track
    symbols = [
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
        {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'},
        {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'sector': 'Automotive', 'exchange': 'NASDAQ'},
        {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'},
        {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF', 'exchange': 'NYSE'},
        {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'ETF', 'exchange': 'NASDAQ'},
    ]
    
    # Add symbols
    collector.add_symbols(symbols)
    print(f"Added {len(symbols)} symbols to database")
    
    # Backfill 1 year of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    print("Starting data backfill (this may take a while)...")
    for symbol_data in symbols:
        symbol = symbol_data['symbol']
        print(f"Updating {symbol}...")
        success = collector.update_symbol_data(symbol, start_date, end_date, "backfill")
        print(f"  {'✅ Success' if success else '❌ Failed'}")
    
    # Show summary
    summary = collector.get_data_summary()
    print(f"\nData collection complete!")
    print(f"Total records: {summary['total_records']:,}")
    print(f"Active symbols: {summary['active_symbols']}")


# Example 2: Query and analyze collected data
def analyze_collected_data():
    """Analyze data that has been collected."""
    from scizor.database.models import get_session, StockData, Symbol
    from sqlalchemy import func
    import pandas as pd
    
    session = get_session()
    
    try:
        # Get all symbols and their data counts
        symbols = session.query(Symbol).filter_by(is_active=True).all()
        
        print("Symbol Analysis:")
        print("-" * 50)
        
        for symbol in symbols:
            # Count records
            count = session.query(StockData).filter_by(symbol=symbol.symbol).count()
            
            # Get latest and earliest dates
            latest = session.query(func.max(StockData.date)).filter_by(symbol=symbol.symbol).scalar()
            earliest = session.query(func.min(StockData.date)).filter_by(symbol=symbol.symbol).scalar()
            
            # Get latest price
            latest_record = session.query(StockData).filter_by(symbol=symbol.symbol).order_by(StockData.date.desc()).first()
            latest_price = latest_record.close if latest_record else 0
            
            print(f"{symbol.symbol:6} | {count:5,} records | {latest_price:8.2f} | {earliest} to {latest}")
        
        # Example: Get AAPL data as DataFrame
        print("\nExample: AAPL Recent Data")
        print("-" * 30)
        
        aapl_data = session.query(StockData).filter_by(symbol='AAPL').order_by(StockData.date.desc()).limit(10).all()
        
        if aapl_data:
            for record in aapl_data:
                print(f"{record.date.strftime('%Y-%m-%d')} | O:{record.open:7.2f} H:{record.high:7.2f} L:{record.low:7.2f} C:{record.close:7.2f} V:{record.volume:>10,}")
        
        # Calculate some basic statistics
        print("\nBasic Statistics:")
        print("-" * 20)
        
        for symbol in ['AAPL', 'GOOGL', 'MSFT']:
            records = session.query(StockData).filter_by(symbol=symbol).order_by(StockData.date.desc()).limit(30).all()
            
            if records:
                prices = [r.close for r in records]
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                volatility = (max_price - min_price) / avg_price * 100
                
                print(f"{symbol:6} | Avg: ${avg_price:7.2f} | Range: ${min_price:7.2f} - ${max_price:7.2f} | Vol: {volatility:5.1f}%")
    
    finally:
        session.close()


# Example 3: Set up automated data collection
def setup_automated_collection():
    """Set up automated data collection with custom schedule."""
    from scizor.database.scheduler import DataScheduler
    import threading
    import time
    
    # Create scheduler
    scheduler = DataScheduler()
    
    # Add custom schedules
    scheduler.add_custom_schedule("09:45", "intraday_update")  # 15 min after market open
    scheduler.add_custom_schedule("12:00", "intraday_update")  # Noon update
    scheduler.add_custom_schedule("15:45", "intraday_update")  # 15 min before close
    
    # Start scheduler
    print("Starting automated data collection...")
    scheduler.start()
    
    # Get schedule info
    info = scheduler.get_schedule_info()
    print(f"Scheduler running with {info['total_jobs']} jobs")
    
    try:
        # Run for a while (in real usage, this would run indefinitely)
        print("Scheduler is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped.")


# Example 4: Monitor data quality
def monitor_data_quality():
    """Monitor data quality and completeness."""
    from scizor.database.models import get_session, StockData, Symbol, DataUpdateLog
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    session = get_session()
    
    try:
        print("Data Quality Report")
        print("=" * 50)
        
        # Check for gaps in data
        symbols = session.query(Symbol).filter_by(is_active=True).all()
        
        for symbol in symbols[:5]:  # Check first 5 symbols
            # Get all dates for this symbol
            records = session.query(StockData.date).filter_by(symbol=symbol.symbol).order_by(StockData.date).all()
            dates = [r.date.date() for r in records]
            
            if len(dates) < 2:
                continue
                
            # Check for gaps (missing weekdays)
            gaps = []
            for i in range(1, len(dates)):
                current_date = dates[i]
                prev_date = dates[i-1]
                
                # Calculate expected business days between dates
                delta = current_date - prev_date
                if delta.days > 3:  # More than 3 days gap (weekend + holiday)
                    gaps.append((prev_date, current_date, delta.days))
            
            print(f"\n{symbol.symbol} ({symbol.name})")
            print(f"  Total records: {len(dates)}")
            print(f"  Date range: {dates[0]} to {dates[-1]}")
            
            if gaps:
                print(f"  Data gaps found: {len(gaps)}")
                for gap in gaps[:3]:  # Show first 3 gaps
                    print(f"    {gap[0]} to {gap[1]} ({gap[2]} days)")
            else:
                print("  No significant gaps found")
        
        # Check recent update logs
        print(f"\nRecent Update Operations")
        print("-" * 30)
        
        recent_logs = session.query(DataUpdateLog).order_by(DataUpdateLog.started_at.desc()).limit(10).all()
        
        for log in recent_logs:
            status_emoji = "✅" if log.status == "completed" else "❌" if log.status == "failed" else "⏳"
            print(f"{status_emoji} {log.symbol:6} | {log.update_type:12} | {log.started_at.strftime('%Y-%m-%d %H:%M')} | {log.records_inserted} inserted")
        
        # Summary statistics
        print(f"\nSummary Statistics")
        print("-" * 20)
        
        total_records = session.query(StockData).count()
        total_symbols = session.query(Symbol).filter_by(is_active=True).count()
        
        # Failed operations in last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        failed_ops = session.query(DataUpdateLog).filter(
            DataUpdateLog.started_at >= yesterday,
            DataUpdateLog.status == 'failed'
        ).count()
        
        print(f"Total records: {total_records:,}")
        print(f"Active symbols: {total_symbols}")
        print(f"Failed operations (24h): {failed_ops}")
        
        # Calculate data freshness
        print(f"\nData Freshness")
        print("-" * 15)
        
        for symbol in ['AAPL', 'SPY', 'QQQ']:
            latest = session.query(StockData).filter_by(symbol=symbol).order_by(StockData.date.desc()).first()
            if latest:
                age = datetime.now().date() - latest.date.date()
                freshness = "🟢 Current" if age.days <= 1 else "🟡 Stale" if age.days <= 7 else "🔴 Old"
                print(f"{symbol:6} | {latest.date.date()} | {age.days} days old | {freshness}")
    
    finally:
        session.close()


# Example 5: Export data for external analysis
def export_data_for_analysis():
    """Export data in various formats for external analysis."""
    from scizor.database.models import get_session, StockData
    import pandas as pd
    import os
    
    session = get_session()
    
    try:
        # Create exports directory
        os.makedirs('exports', exist_ok=True)
        
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
        
        for symbol in symbols:
            print(f"Exporting {symbol} data...")
            
            # Query data
            records = session.query(StockData).filter_by(symbol=symbol).order_by(StockData.date).all()
            
            if not records:
                print(f"  No data found for {symbol}")
                continue
            
            # Convert to DataFrame
            data = []
            for record in records:
                data.append({
                    'Date': record.date,
                    'Open': record.open,
                    'High': record.high,
                    'Low': record.low,
                    'Close': record.close,
                    'Volume': record.volume,
                    'Adj_Close': record.adjusted_close
                })
            
            df = pd.DataFrame(data)
            df.set_index('Date', inplace=True)
            
            # Export to CSV
            csv_file = f'exports/{symbol}_data.csv'
            df.to_csv(csv_file)
            
            # Export to JSON
            json_file = f'exports/{symbol}_data.json'
            df.to_json(json_file, orient='index', date_format='iso')
            
            # Export summary stats
            stats = {
                'symbol': symbol,
                'record_count': len(df),
                'date_range': {
                    'start': df.index.min().isoformat(),
                    'end': df.index.max().isoformat()
                },
                'price_stats': {
                    'avg_close': df['Close'].mean(),
                    'min_close': df['Close'].min(),
                    'max_close': df['Close'].max(),
                    'volatility': df['Close'].std()
                },
                'volume_stats': {
                    'avg_volume': df['Volume'].mean(),
                    'total_volume': df['Volume'].sum()
                }
            }
            
            stats_file = f'exports/{symbol}_stats.json'
            import json
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
            
            print(f"  ✅ Exported {len(df)} records to {csv_file}, {json_file}, {stats_file}")
        
        print(f"\n✅ Data export completed. Files saved in 'exports/' directory.")
    
    finally:
        session.close()


if __name__ == "__main__":
    print("Stock Data Collection Examples")
    print("=" * 40)
    
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python examples.py <example_number>")
        print("\nAvailable examples:")
        print("1 - Basic data collection setup")
        print("2 - Analyze collected data")
        print("3 - Set up automated collection")
        print("4 - Monitor data quality")
        print("5 - Export data for analysis")
        sys.exit(1)
    
    example = sys.argv[1]
    
    if example == "1":
        setup_basic_collection()
    elif example == "2":
        analyze_collected_data()
    elif example == "3":
        setup_automated_collection()
    elif example == "4":
        monitor_data_quality()
    elif example == "5":
        export_data_for_analysis()
    else:
        print(f"Unknown example: {example}")
        sys.exit(1)
