"""
Command-line interface for the stock data collector.
"""

import asyncio
from datetime import datetime, timedelta
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import List

from scizor.database.collector import StockDataCollector

app = typer.Typer()
console = Console()


@app.command()
def add_symbols(
    symbols: List[str] = typer.Argument(..., help="Stock symbols to add"),
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Add stock symbols to track."""
    collector = StockDataCollector(database_url)
    
    symbol_data = [{'symbol': symbol.upper()} for symbol in symbols]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Adding symbols...", total=None)
        collector.add_symbols(symbol_data)
        progress.update(task, completed=True)
    
    console.print(f"✅ Added {len(symbols)} symbols to database", style="green")


@app.command()
def update(
    symbols: List[str] = typer.Argument(..., help="Stock symbols to update"),
    start_date: str = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(None, help="End date (YYYY-MM-DD)"),
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Update data for specific symbols."""
    collector = StockDataCollector(database_url)
    
    # Parse dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
    
    with Progress(console=console) as progress:
        task = progress.add_task("Updating symbols...", total=len(symbols))
        
        for symbol in symbols:
            symbol = symbol.upper()
            success = collector.update_symbol_data(symbol, start_dt, end_dt)
            
            if success:
                console.print(f"✅ Updated {symbol}", style="green")
            else:
                console.print(f"❌ Failed to update {symbol}", style="red")
                
            progress.advance(task)


@app.command()
def update_all(
    start_date: str = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(None, help="End date (YYYY-MM-DD)"),
    batch_size: int = typer.Option(10, help="Batch size for parallel processing"),
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Update data for all active symbols."""
    collector = StockDataCollector(database_url)
    
    # Parse dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
    
    console.print("🚀 Starting bulk update for all symbols...", style="blue")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Updating all symbols...", total=None)
        collector.update_all_symbols(start_dt, end_dt, batch_size)
        progress.update(task, completed=True)
    
    console.print("✅ Bulk update completed!", style="green")


@app.command()
def backfill(
    symbols: List[str] = typer.Argument(..., help="Stock symbols to backfill"),
    days: int = typer.Option(365, help="Number of days to backfill"),
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Backfill historical data for symbols."""
    collector = StockDataCollector(database_url)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    console.print(f"📈 Backfilling {days} days of data...", style="blue")
    
    with Progress(console=console) as progress:
        task = progress.add_task("Backfilling data...", total=len(symbols))
        
        for symbol in symbols:
            symbol = symbol.upper()
            success = collector.update_symbol_data(
                symbol, start_date, end_date, "backfill"
            )
            
            if success:
                console.print(f"✅ Backfilled {symbol}", style="green")
            else:
                console.print(f"❌ Failed to backfill {symbol}", style="red")
                
            progress.advance(task)


@app.command()
def summary(
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Show database summary."""
    collector = StockDataCollector(database_url)
    summary = collector.get_data_summary()
    
    # Create summary table
    table = Table(title="Stock Data Summary", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Records", justify="right", style="yellow")
    table.add_column("Latest Date", style="blue")
    
    for symbol, details in summary['symbols'].items():
        table.add_row(
            symbol,
            details['name'] or "N/A",
            str(details['record_count']),
            details['latest_date'] or "No data"
        )
    
    console.print(table)
    console.print(f"\n📊 Total Records: {summary['total_records']:,}")
    console.print(f"📈 Active Symbols: {summary['active_symbols']}")


@app.command()
def init_db(
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL"),
    sample_symbols: bool = typer.Option(True, help="Add sample symbols")
):
    """Initialize database with tables."""
    from scizor.database.models import create_database
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Creating database...", total=None)
        create_database(database_url)
        progress.update(task, completed=True)
    
    console.print("✅ Database tables created!", style="green")
    
    if sample_symbols:
        # Add some popular symbols
        collector = StockDataCollector(database_url)
        sample_data = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'},
            {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'sector': 'Automotive', 'exchange': 'NASDAQ'},
            {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF', 'exchange': 'NYSE'},
            {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'ETF', 'exchange': 'NASDAQ'},
        ]
        
        collector.add_symbols(sample_data)
        console.print("✅ Added sample symbols!", style="green")


@app.command()
def realtime_update(
    interval_minutes: int = typer.Option(15, help="Update interval in minutes"),
    database_url: str = typer.Option("sqlite:///scizor_data.db", help="Database URL")
):
    """Run continuous real-time data updates."""
    collector = StockDataCollector(database_url)
    
    console.print(f"🔄 Starting real-time updates every {interval_minutes} minutes...", style="blue")
    console.print("Press Ctrl+C to stop", style="yellow")
    
    try:
        while True:
            console.print(f"📡 Updating data at {datetime.now().strftime('%H:%M:%S')}", style="cyan")
            
            # Update with just today's data
            today = datetime.now().date()
            start_date = datetime.combine(today, datetime.min.time())
            end_date = datetime.now()
            
            collector.update_all_symbols(start_date, end_date)
            
            console.print(f"✅ Update completed. Next update in {interval_minutes} minutes.", style="green")
            
            # Sleep for specified interval
            import time
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        console.print("\n🛑 Real-time updates stopped.", style="red")


if __name__ == "__main__":
    app()
