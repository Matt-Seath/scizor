"""
Main entry point for the stock data collection application.
"""

import sys
import argparse
from datetime import datetime, timedelta
from scizor.database.collector import StockDataCollector
from scizor.database.models import create_database


def main():
    """Main entry point for the data collector."""
    parser = argparse.ArgumentParser(
        description='Scizor Stock Data Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database
  python -m scizor.database init

  # Add symbols
  python -m scizor.database add AAPL GOOGL MSFT

  # Update specific symbols
  python -m scizor.database update AAPL GOOGL --start-date 2024-01-01

  # Update all symbols
  python -m scizor.database update-all

  # Backfill 2 years of data
  python -m scizor.database backfill AAPL --days 730

  # Show database summary
  python -m scizor.database summary

  # Run real-time updates
  python -m scizor.database realtime --interval 15
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Common arguments
    def add_common_args(subparser):
        subparser.add_argument('--database-url', default='sqlite:///scizor_data.db',
                             help='Database URL (default: sqlite:///scizor_data.db)')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    add_common_args(init_parser)
    init_parser.add_argument('--no-samples', action='store_true',
                           help='Skip adding sample symbols')
    
    # Add symbols command
    add_parser = subparsers.add_parser('add', help='Add symbols to track')
    add_parser.add_argument('symbols', nargs='+', help='Stock symbols to add')
    add_common_args(add_parser)
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update specific symbols')
    update_parser.add_argument('symbols', nargs='+', help='Stock symbols to update')
    update_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    update_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    add_common_args(update_parser)
    
    # Update all command
    update_all_parser = subparsers.add_parser('update-all', help='Update all symbols')
    update_all_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    update_all_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    update_all_parser.add_argument('--batch-size', type=int, default=10,
                                 help='Batch size for parallel processing')
    add_common_args(update_all_parser)
    
    # Backfill command
    backfill_parser = subparsers.add_parser('backfill', help='Backfill historical data')
    backfill_parser.add_argument('symbols', nargs='+', help='Stock symbols to backfill')
    backfill_parser.add_argument('--days', type=int, default=365,
                               help='Number of days to backfill')
    add_common_args(backfill_parser)
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show database summary')
    add_common_args(summary_parser)
    
    # Real-time command
    realtime_parser = subparsers.add_parser('realtime', help='Run real-time updates')
    realtime_parser.add_argument('--interval', type=int, default=15,
                               help='Update interval in minutes')
    add_common_args(realtime_parser)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # Execute commands
    if args.command == 'init':
        print("Initializing database...")
        create_database(args.database_url)
        print("✅ Database tables created!")
        
        if not args.no_samples:
            collector = StockDataCollector(args.database_url)
            sample_symbols = [
                {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
                {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
                {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'},
                {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'sector': 'Automotive', 'exchange': 'NASDAQ'},
                {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF', 'exchange': 'NYSE'},
            ]
            collector.add_symbols(sample_symbols)
            print("✅ Added sample symbols!")
    
    elif args.command == 'add':
        collector = StockDataCollector(args.database_url)
        symbol_data = [{'symbol': symbol.upper()} for symbol in args.symbols]
        collector.add_symbols(symbol_data)
        print(f"✅ Added {len(args.symbols)} symbols")
    
    elif args.command == 'update':
        collector = StockDataCollector(args.database_url)
        
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else None
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else None
        
        for symbol in args.symbols:
            symbol = symbol.upper()
            print(f"Updating {symbol}...")
            success = collector.update_symbol_data(symbol, start_date, end_date)
            print(f"  {'✅ Success' if success else '❌ Failed'}")
    
    elif args.command == 'update-all':
        collector = StockDataCollector(args.database_url)
        
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else None
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else None
        
        print("🚀 Starting bulk update for all symbols...")
        collector.update_all_symbols(start_date, end_date, args.batch_size)
        print("✅ Bulk update completed!")
    
    elif args.command == 'backfill':
        collector = StockDataCollector(args.database_url)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        
        print(f"📈 Backfilling {args.days} days of data...")
        
        for symbol in args.symbols:
            symbol = symbol.upper()
            print(f"Backfilling {symbol}...")
            success = collector.update_symbol_data(symbol, start_date, end_date, "backfill")
            print(f"  {'✅ Success' if success else '❌ Failed'}")
    
    elif args.command == 'summary':
        collector = StockDataCollector(args.database_url)
        summary = collector.get_data_summary()
        
        print("📊 Stock Data Summary")
        print("=" * 80)
        print(f"Total Records: {summary['total_records']:,}")
        print(f"Active Symbols: {summary['active_symbols']}")
        print()
        print(f"{'Symbol':<8} {'Name':<30} {'Records':<10} {'Latest Date'}")
        print("-" * 80)
        
        for symbol, details in summary['symbols'].items():
            name = (details['name'] or 'N/A')[:29]
            records = details['record_count']
            latest = details['latest_date'] or 'No data'
            print(f"{symbol:<8} {name:<30} {records:<10} {latest}")
    
    elif args.command == 'realtime':
        collector = StockDataCollector(args.database_url)
        
        print(f"🔄 Starting real-time updates every {args.interval} minutes...")
        print("Press Ctrl+C to stop")
        
        import time
        
        try:
            while True:
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"📡 Updating data at {current_time}")
                
                # Update with just today's data
                today = datetime.now().date()
                start_date = datetime.combine(today, datetime.min.time())
                end_date = datetime.now()
                
                collector.update_all_symbols(start_date, end_date)
                
                print(f"✅ Update completed. Next update in {args.interval} minutes.")
                time.sleep(args.interval * 60)
                
        except KeyboardInterrupt:
            print("\n🛑 Real-time updates stopped.")


if __name__ == "__main__":
    main()
