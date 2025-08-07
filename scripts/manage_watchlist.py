#!/usr/bin/env python3
"""
Watchlist Management Script

This script helps manage the watchlist for enhanced data collection.
You can add/remove symbols, create different watchlists, and configure
collection settings for intraday data.

Usage:
    python manage_watchlist.py add --symbol AAPL --name "tech_stocks" --priority 1
    python manage_watchlist.py remove --symbol AAPL --name "tech_stocks"
    python manage_watchlist.py list --name "tech_stocks"
    python manage_watchlist.py create-default
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, Watchlist
from sqlalchemy import select, and_, delete
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WatchlistManager:
    """Manages watchlist operations."""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        await init_db()
        self.session = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def add_symbol(self, symbol: str, watchlist_name: str, priority: int = 3,
                        collect_5min: bool = True, collect_1min: bool = False,
                        collect_tick: bool = False, notes: str = None) -> bool:
        """Add a symbol to a watchlist."""
        try:
            # Find the symbol
            symbol_result = await self.session.execute(
                select(Symbol).where(Symbol.symbol == symbol.upper())
            )
            symbol_obj = symbol_result.scalar_one_or_none()
            
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False
            
            # Check if already in watchlist
            existing_result = await self.session.execute(
                select(Watchlist).where(
                    and_(
                        Watchlist.symbol_id == symbol_obj.id,
                        Watchlist.name == watchlist_name,
                        Watchlist.active == True
                    )
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                logger.warning(f"Symbol {symbol} already in watchlist '{watchlist_name}'")
                return False
            
            # Create watchlist entry
            watchlist_entry = Watchlist(
                symbol_id=symbol_obj.id,
                name=watchlist_name,
                priority=priority,
                collect_5min=collect_5min,
                collect_1min=collect_1min,
                collect_tick=collect_tick,
                notes=notes
            )
            
            self.session.add(watchlist_entry)
            await self.session.commit()
            
            logger.info(f"✅ Added {symbol} to watchlist '{watchlist_name}' with priority {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding symbol {symbol}: {e}")
            await self.session.rollback()
            return False
    
    async def remove_symbol(self, symbol: str, watchlist_name: str) -> bool:
        """Remove a symbol from a watchlist."""
        try:
            # Find the symbol
            symbol_result = await self.session.execute(
                select(Symbol).where(Symbol.symbol == symbol.upper())
            )
            symbol_obj = symbol_result.scalar_one_or_none()
            
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False
            
            # Find and deactivate watchlist entry
            await self.session.execute(
                delete(Watchlist).where(
                    and_(
                        Watchlist.symbol_id == symbol_obj.id,
                        Watchlist.name == watchlist_name
                    )
                )
            )
            
            await self.session.commit()
            logger.info(f"✅ Removed {symbol} from watchlist '{watchlist_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error removing symbol {symbol}: {e}")
            await self.session.rollback()
            return False
    
    async def list_watchlist(self, watchlist_name: Optional[str] = None) -> List[dict]:
        """List symbols in watchlist(s)."""
        try:
            if watchlist_name:
                # List specific watchlist
                result = await self.session.execute(
                    select(Watchlist, Symbol).join(Symbol).where(
                        and_(
                            Watchlist.name == watchlist_name,
                            Watchlist.active == True
                        )
                    ).order_by(Watchlist.priority, Symbol.symbol)
                )
                watchlist_data = result.all()
                
                symbols = []
                for watchlist_entry, symbol in watchlist_data:
                    symbols.append({
                        'symbol': symbol.symbol,
                        'name': symbol.company_name,
                        'exchange': symbol.exchange,
                        'priority': watchlist_entry.priority,
                        'collect_5min': watchlist_entry.collect_5min,
                        'collect_1min': watchlist_entry.collect_1min,
                        'collect_tick': watchlist_entry.collect_tick,
                        'notes': watchlist_entry.notes,
                        'created_at': watchlist_entry.created_at
                    })
                
                return symbols
            else:
                # List all watchlists
                result = await self.session.execute(
                    select(Watchlist.name, Watchlist.symbol_id).where(
                        Watchlist.active == True
                    ).distinct()
                )
                
                watchlists = {}
                for name, _ in result.all():
                    if name not in watchlists:
                        watchlists[name] = await self.list_watchlist(name)
                
                return watchlists
                
        except Exception as e:
            logger.error(f"Error listing watchlist: {e}")
            return []
    
    async def create_default_watchlist(self) -> bool:
        """Create a default watchlist with popular symbols."""
        logger.info("Creating default watchlist...")
        
        # Default symbols for intraday tracking
        default_symbols = [
            # ASX Top performers
            {"symbol": "CBA", "priority": 1, "notes": "Major bank, high liquidity"},
            {"symbol": "BHP", "priority": 1, "notes": "Mining giant, commodity exposure"},
            {"symbol": "CSL", "priority": 1, "notes": "Healthcare leader"},
            {"symbol": "ANZ", "priority": 2, "notes": "Major bank"},
            {"symbol": "WBC", "priority": 2, "notes": "Major bank"},
            {"symbol": "NAB", "priority": 2, "notes": "Major bank"},
            {"symbol": "WES", "priority": 2, "notes": "Retail conglomerate"},
            {"symbol": "MQG", "priority": 2, "notes": "Investment bank"},
            {"symbol": "TLS", "priority": 3, "notes": "Telecom leader"},
            {"symbol": "WOW", "priority": 3, "notes": "Supermarket chain"},
            
            # US Tech giants
            {"symbol": "AAPL", "priority": 1, "notes": "Apple - tech leader"},
            {"symbol": "MSFT", "priority": 1, "notes": "Microsoft - cloud leader"},
            {"symbol": "GOOGL", "priority": 1, "notes": "Google - search/cloud"},
            {"symbol": "AMZN", "priority": 1, "notes": "Amazon - e-commerce/cloud"},
            {"symbol": "TSLA", "priority": 1, "notes": "Tesla - EV leader"},
            {"symbol": "META", "priority": 2, "notes": "Meta - social media"},
            {"symbol": "NVDA", "priority": 1, "notes": "NVIDIA - AI/chips"},
            {"symbol": "NFLX", "priority": 2, "notes": "Netflix - streaming"},
            
            # ETFs for diversification
            {"symbol": "VAS", "priority": 2, "notes": "ASX 200 ETF"},
            {"symbol": "VGS", "priority": 2, "notes": "International shares ETF"},
            {"symbol": "NDQ", "priority": 2, "notes": "NASDAQ 100 ETF"},
            {"symbol": "IVV", "priority": 2, "notes": "S&P 500 ETF"}
        ]
        
        success_count = 0
        for symbol_data in default_symbols:
            success = await self.add_symbol(
                symbol=symbol_data["symbol"],
                watchlist_name="default_intraday",
                priority=symbol_data["priority"],
                collect_5min=True,
                collect_1min=False,  # Start with 5min only
                notes=symbol_data["notes"]
            )
            if success:
                success_count += 1
        
        logger.info(f"✅ Created default watchlist with {success_count}/{len(default_symbols)} symbols")
        return success_count > 0
    
    async def update_symbol_settings(self, symbol: str, watchlist_name: str, **kwargs) -> bool:
        """Update collection settings for a symbol in watchlist."""
        try:
            # Find the symbol
            symbol_result = await self.session.execute(
                select(Symbol).where(Symbol.symbol == symbol.upper())
            )
            symbol_obj = symbol_result.scalar_one_or_none()
            
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False
            
            # Find watchlist entry
            watchlist_result = await self.session.execute(
                select(Watchlist).where(
                    and_(
                        Watchlist.symbol_id == symbol_obj.id,
                        Watchlist.name == watchlist_name,
                        Watchlist.active == True
                    )
                )
            )
            watchlist_entry = watchlist_result.scalar_one_or_none()
            
            if not watchlist_entry:
                logger.error(f"Symbol {symbol} not found in watchlist '{watchlist_name}'")
                return False
            
            # Update settings
            for key, value in kwargs.items():
                if hasattr(watchlist_entry, key):
                    setattr(watchlist_entry, key, value)
                    logger.info(f"Updated {symbol}.{key} = {value}")
            
            watchlist_entry.updated_at = datetime.now()
            await self.session.commit()
            
            logger.info(f"✅ Updated settings for {symbol} in watchlist '{watchlist_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating symbol {symbol}: {e}")
            await self.session.rollback()
            return False


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Manage trading watchlists")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Add symbol command
    add_parser = subparsers.add_parser("add", help="Add symbol to watchlist")
    add_parser.add_argument("--symbol", required=True, help="Symbol to add")
    add_parser.add_argument("--name", required=True, help="Watchlist name")
    add_parser.add_argument("--priority", type=int, default=3, help="Priority (1=highest, 5=lowest)")
    add_parser.add_argument("--5min", action="store_true", default=True, help="Collect 5min bars")
    add_parser.add_argument("--1min", action="store_true", help="Collect 1min bars")
    add_parser.add_argument("--tick", action="store_true", help="Collect tick data")
    add_parser.add_argument("--notes", help="Notes about this symbol")
    
    # Remove symbol command
    remove_parser = subparsers.add_parser("remove", help="Remove symbol from watchlist")
    remove_parser.add_argument("--symbol", required=True, help="Symbol to remove")
    remove_parser.add_argument("--name", required=True, help="Watchlist name")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List watchlist contents")
    list_parser.add_argument("--name", help="Specific watchlist name (optional)")
    
    # Create default command
    subparsers.add_parser("create-default", help="Create default watchlist")
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update symbol settings")
    update_parser.add_argument("--symbol", required=True, help="Symbol to update")
    update_parser.add_argument("--name", required=True, help="Watchlist name")
    update_parser.add_argument("--priority", type=int, help="New priority")
    update_parser.add_argument("--5min", type=bool, help="Collect 5min bars")
    update_parser.add_argument("--1min", type=bool, help="Collect 1min bars")
    update_parser.add_argument("--notes", help="New notes")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    async with WatchlistManager() as manager:
        if args.command == "add":
            await manager.add_symbol(
                symbol=args.symbol,
                watchlist_name=args.name,
                priority=args.priority,
                collect_5min=getattr(args, '5min', True),
                collect_1min=getattr(args, '1min', False),
                collect_tick=args.tick,
                notes=args.notes
            )
        
        elif args.command == "remove":
            await manager.remove_symbol(args.symbol, args.name)
        
        elif args.command == "list":
            if args.name:
                symbols = await manager.list_watchlist(args.name)
                print(f"\n📊 Watchlist: {args.name}")
                print("=" * 80)
                if symbols:
                    print(f"{'Symbol':<8} {'Name':<30} {'Exchange':<8} {'Priority':<8} {'5min':<5} {'1min':<5} {'Notes':<20}")
                    print("-" * 80)
                    for symbol in symbols:
                        print(f"{symbol['symbol']:<8} {symbol['name'][:30]:<30} {symbol['exchange']:<8} "
                              f"{symbol['priority']:<8} {'✓' if symbol['collect_5min'] else '✗':<5} "
                              f"{'✓' if symbol['collect_1min'] else '✗':<5} {(symbol['notes'] or '')[:20]:<20}")
                else:
                    print("No symbols found in this watchlist")
            else:
                watchlists = await manager.list_watchlist()
                if isinstance(watchlists, dict):
                    for name, symbols in watchlists.items():
                        print(f"\n📊 Watchlist: {name} ({len(symbols)} symbols)")
                        print("-" * 40)
                        for symbol in symbols[:5]:  # Show first 5
                            print(f"  {symbol['symbol']} - {symbol['name'][:30]} (P{symbol['priority']})")
                        if len(symbols) > 5:
                            print(f"  ... and {len(symbols) - 5} more")
        
        elif args.command == "create-default":
            await manager.create_default_watchlist()
        
        elif args.command == "update":
            updates = {}
            if args.priority is not None:
                updates['priority'] = args.priority
            if getattr(args, '5min', None) is not None:
                updates['collect_5min'] = getattr(args, '5min')
            if getattr(args, '1min', None) is not None:
                updates['collect_1min'] = getattr(args, '1min')
            if args.notes is not None:
                updates['notes'] = args.notes
            
            await manager.update_symbol_settings(args.symbol, args.name, **updates)


if __name__ == "__main__":
    asyncio.run(main())
