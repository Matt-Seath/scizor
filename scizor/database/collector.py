"""
Stock data collector and database populator.
"""

import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging
from concurrent.futures import ThreadPoolExecutor
import time

from scizor.database.models import StockData, Symbol, DataUpdateLog, get_session, create_database


class StockDataCollector:
    """Collects and stores stock market data."""
    
    def __init__(self, database_url: str = "sqlite:///scizor_data.db", max_workers: int = 5):
        self.database_url = database_url
        self.max_workers = max_workers
        
        # Ensure database exists
        create_database(database_url)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_session(self) -> Session:
        """Get database session."""
        return get_session(self.database_url)
    
    def add_symbols(self, symbols: List[Dict[str, str]]):
        """
        Add symbols to track.
        
        Args:
            symbols: List of symbol dictionaries with keys: symbol, name, sector, exchange
        """
        session = self.get_session()
        
        try:
            for symbol_data in symbols:
                # Check if symbol already exists
                existing = session.query(Symbol).filter_by(symbol=symbol_data['symbol']).first()
                
                if not existing:
                    symbol = Symbol(
                        symbol=symbol_data['symbol'],
                        name=symbol_data.get('name', ''),
                        sector=symbol_data.get('sector', ''),
                        exchange=symbol_data.get('exchange', ''),
                        currency=symbol_data.get('currency', 'USD')
                    )
                    session.add(symbol)
                    self.logger.info(f"Added new symbol: {symbol_data['symbol']}")
                else:
                    # Update existing symbol info
                    for key, value in symbol_data.items():
                        if hasattr(existing, key) and value:
                            setattr(existing, key, value)
                    existing.last_updated = datetime.utcnow()
                    self.logger.info(f"Updated symbol: {symbol_data['symbol']}")
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error adding symbols: {e}")
            raise
        finally:
            session.close()
    
    def fetch_stock_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch stock data from Yahoo Finance.
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval (1d, 1h, etc.)
            
        Returns:
            DataFrame with stock data or None if error
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=False
            )
            
            if data.empty:
                self.logger.warning(f"No data returned for {symbol}")
                return None
                
            # Reset index to get date as column
            data.reset_index(inplace=True)
            data['Symbol'] = symbol
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def store_stock_data(self, symbol: str, data: pd.DataFrame) -> tuple:
        """
        Store stock data in database.
        
        Args:
            symbol: Stock symbol
            data: DataFrame with stock data
            
        Returns:
            Tuple of (records_inserted, records_updated)
        """
        session = self.get_session()
        records_inserted = 0
        records_updated = 0
        
        try:
            for _, row in data.iterrows():
                # Check if record already exists
                existing = session.query(StockData).filter(
                    and_(
                        StockData.symbol == symbol,
                        StockData.date == row['Date']
                    )
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = row['Open']
                    existing.high = row['High']
                    existing.low = row['Low']
                    existing.close = row['Close']
                    existing.volume = row['Volume']
                    existing.adjusted_close = row.get('Adj Close', row['Close'])
                    existing.updated_at = datetime.utcnow()
                    records_updated += 1
                else:
                    # Insert new record
                    stock_data = StockData(
                        symbol=symbol,
                        date=row['Date'],
                        open=row['Open'],
                        high=row['High'],
                        low=row['Low'],
                        close=row['Close'],
                        volume=row['Volume'],
                        adjusted_close=row.get('Adj Close', row['Close'])
                    )
                    session.add(stock_data)
                    records_inserted += 1
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error storing data for {symbol}: {e}")
            raise
        finally:
            session.close()
            
        return records_inserted, records_updated
    
    def log_update_operation(
        self, 
        symbol: str, 
        update_type: str, 
        start_date: datetime = None,
        end_date: datetime = None,
        status: str = "pending"
    ) -> int:
        """
        Log data update operation.
        
        Returns:
            Log entry ID
        """
        session = self.get_session()
        
        try:
            log_entry = DataUpdateLog(
                symbol=symbol,
                update_type=update_type,
                start_date=start_date,
                end_date=end_date,
                status=status
            )
            session.add(log_entry)
            session.commit()
            
            return log_entry.id
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error logging update operation: {e}")
            raise
        finally:
            session.close()
    
    def update_log_status(
        self, 
        log_id: int, 
        status: str, 
        records_processed: int = 0,
        records_inserted: int = 0,
        records_updated: int = 0,
        error_message: str = None
    ):
        """Update log entry status."""
        session = self.get_session()
        
        try:
            log_entry = session.query(DataUpdateLog).filter_by(id=log_id).first()
            if log_entry:
                log_entry.status = status
                log_entry.records_processed = records_processed
                log_entry.records_inserted = records_inserted
                log_entry.records_updated = records_updated
                log_entry.error_message = error_message
                
                if status in ['completed', 'failed']:
                    log_entry.completed_at = datetime.utcnow()
                
                session.commit()
                
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating log status: {e}")
        finally:
            session.close()
    
    def update_symbol_data(
        self, 
        symbol: str, 
        start_date: datetime = None, 
        end_date: datetime = None,
        update_type: str = "historical"
    ) -> bool:
        """
        Update data for a single symbol.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (defaults to 1 year ago)
            end_date: End date (defaults to today)
            update_type: Type of update for logging
            
        Returns:
            True if successful, False otherwise
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()
            
        # Log the update operation
        log_id = self.log_update_operation(symbol, update_type, start_date, end_date, "running")
        
        try:
            # Fetch data
            data = self.fetch_stock_data(symbol, start_date, end_date)
            
            if data is None or data.empty:
                self.update_log_status(log_id, "failed", error_message="No data fetched")
                return False
            
            # Store data
            records_inserted, records_updated = self.store_stock_data(symbol, data)
            
            # Update log
            self.update_log_status(
                log_id, 
                "completed",
                records_processed=len(data),
                records_inserted=records_inserted,
                records_updated=records_updated
            )
            
            self.logger.info(f"Updated {symbol}: {records_inserted} inserted, {records_updated} updated")
            return True
            
        except Exception as e:
            self.update_log_status(log_id, "failed", error_message=str(e))
            self.logger.error(f"Failed to update {symbol}: {e}")
            return False
    
    def update_all_symbols(
        self, 
        start_date: datetime = None, 
        end_date: datetime = None,
        batch_size: int = 10
    ):
        """
        Update data for all active symbols.
        
        Args:
            start_date: Start date for data update
            end_date: End date for data update
            batch_size: Number of symbols to process in parallel
        """
        session = self.get_session()
        
        try:
            # Get all active symbols
            symbols = session.query(Symbol).filter_by(is_active=True).all()
            symbol_list = [s.symbol for s in symbols]
            
            self.logger.info(f"Updating data for {len(symbol_list)} symbols")
            
            # Process in batches
            for i in range(0, len(symbol_list), batch_size):
                batch = symbol_list[i:i + batch_size]
                
                # Use ThreadPoolExecutor for parallel processing
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as executor:
                    futures = [
                        executor.submit(self.update_symbol_data, symbol, start_date, end_date)
                        for symbol in batch
                    ]
                    
                    # Wait for batch to complete
                    for future in futures:
                        future.result()
                
                # Small delay between batches to be respectful to data provider
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error updating all symbols: {e}")
        finally:
            session.close()
    
    def get_latest_data_date(self, symbol: str) -> Optional[datetime]:
        """Get the latest date for which we have data for a symbol."""
        session = self.get_session()
        
        try:
            latest = session.query(StockData).filter_by(symbol=symbol).order_by(StockData.date.desc()).first()
            return latest.date if latest else None
        finally:
            session.close()
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of data in database."""
        session = self.get_session()
        
        try:
            # Count records per symbol
            symbol_counts = {}
            symbols = session.query(Symbol).filter_by(is_active=True).all()
            
            for symbol in symbols:
                count = session.query(StockData).filter_by(symbol=symbol.symbol).count()
                latest_date = self.get_latest_data_date(symbol.symbol)
                
                symbol_counts[symbol.symbol] = {
                    'record_count': count,
                    'latest_date': latest_date.strftime('%Y-%m-%d') if latest_date else None,
                    'name': symbol.name
                }
            
            total_records = session.query(StockData).count()
            
            return {
                'total_records': total_records,
                'active_symbols': len(symbols),
                'symbols': symbol_counts
            }
            
        finally:
            session.close()


# CLI interface for standalone usage
def main():
    """Main function for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Data Collector')
    parser.add_argument('command', choices=['add-symbols', 'update', 'update-all', 'summary'],
                       help='Command to execute')
    parser.add_argument('--symbols', nargs='+', help='Stock symbols to process')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--database-url', type=str, default='sqlite:///scizor_data.db',
                       help='Database URL')
    
    args = parser.parse_args()
    
    collector = StockDataCollector(args.database_url)
    
    if args.command == 'add-symbols':
        if not args.symbols:
            print("Error: --symbols required for add-symbols command")
            return
            
        symbols = [{'symbol': s} for s in args.symbols]
        collector.add_symbols(symbols)
        print(f"Added {len(symbols)} symbols")
        
    elif args.command == 'update':
        if not args.symbols:
            print("Error: --symbols required for update command")
            return
            
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else None
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else None
        
        for symbol in args.symbols:
            success = collector.update_symbol_data(symbol, start_date, end_date)
            print(f"Update {symbol}: {'Success' if success else 'Failed'}")
            
    elif args.command == 'update-all':
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else None
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else None
        
        collector.update_all_symbols(start_date, end_date)
        print("Update completed for all symbols")
        
    elif args.command == 'summary':
        summary = collector.get_data_summary()
        print(f"Total records: {summary['total_records']}")
        print(f"Active symbols: {summary['active_symbols']}")
        print("\nSymbol details:")
        for symbol, details in summary['symbols'].items():
            print(f"  {symbol}: {details['record_count']} records, latest: {details['latest_date']}")


if __name__ == "__main__":
    main()
