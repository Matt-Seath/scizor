#!/usr/bin/env python3
"""
Seed script to create watchlists from JSON configuration file
Reads watchlist data from app/data/seeds/watchlists.json
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from app.config.database import AsyncSessionLocal
from app.data.models.market import Watchlist, WatchlistSymbol, ContractDetail
from app.config.settings import settings
from sqlalchemy import select
import structlog

logger = structlog.get_logger(__name__)


def load_watchlists_from_json(json_file: str = "app/data/seeds/watchlists.json") -> list:
    """Load watchlist data from JSON file"""
    try:
        with open(json_file, 'r') as f:
            watchlists = json.load(f)
        logger.info("Loaded watchlists from JSON", file=json_file, count=len(watchlists))
        return watchlists
    except FileNotFoundError:
        logger.error("Watchlist JSON file not found", file=json_file)
        return []
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in watchlist file", file=json_file, error=str(e))
        return []


async def create_watchlists_from_json(json_file: str = "app/data/seeds/watchlists.json"):
    """Create watchlists from JSON configuration"""
    
    # Load watchlist data
    watchlist_configs = load_watchlists_from_json(json_file)
    if not watchlist_configs:
        return False
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Get all contract symbols from database for validation
            result = await db_session.execute(
                select(ContractDetail.symbol, ContractDetail.con_id, ContractDetail.long_name)
                .where(ContractDetail.exchange == 'ASX')
                .order_by(ContractDetail.symbol)
            )
            all_contracts = result.fetchall()
            
            if not all_contracts:
                logger.error("No contracts found in database. Run contract population first.")
                return False
            
            contract_lookup = {contract.symbol: contract.con_id for contract in all_contracts}
            logger.info("Found contracts for validation", count=len(contract_lookup))
            
            # Process each watchlist from JSON
            for watchlist_config in watchlist_configs:
                watchlist_name = watchlist_config.get("name")
                if not watchlist_name:
                    logger.warning("Skipping watchlist without name", config=watchlist_config)
                    continue
                
                # Check if watchlist already exists
                result = await db_session.execute(
                    select(Watchlist).where(Watchlist.name == watchlist_name)
                )
                existing_watchlist = result.scalar_one_or_none()
                
                if existing_watchlist:
                    logger.info("Watchlist already exists, skipping", name=watchlist_name)
                    continue
                
                # Create watchlist
                watchlist = Watchlist(
                    name=watchlist_name,
                    description=watchlist_config.get("description", ""),
                    is_active=watchlist_config.get("is_active", True)
                )
                
                db_session.add(watchlist)
                await db_session.flush()  # Get the ID
                
                # Add symbols to watchlist
                symbols_added = 0
                symbols_skipped = 0
                
                for symbol_config in watchlist_config.get("symbols", []):
                    symbol = symbol_config.get("symbol")
                    if not symbol:
                        logger.warning("Skipping symbol without name", config=symbol_config)
                        continue
                    
                    con_id = contract_lookup.get(symbol.upper())
                    if not con_id:
                        logger.warning("Symbol not found in contracts, skipping", 
                                     symbol=symbol, watchlist=watchlist_name)
                        symbols_skipped += 1
                        continue
                    
                    # Create watchlist symbol entry
                    watchlist_symbol = WatchlistSymbol(
                        watchlist_id=watchlist.id,
                        symbol=symbol.upper(),
                        con_id=con_id,
                        priority=symbol_config.get("priority", 1),
                        collect_intraday=symbol_config.get("collect_intraday", True),
                        timeframes=symbol_config.get("timeframes", "15min,1hour")
                    )
                    
                    db_session.add(watchlist_symbol)
                    symbols_added += 1
                
                logger.info("Created watchlist", 
                           name=watchlist_name,
                           symbols_added=symbols_added,
                           symbols_skipped=symbols_skipped,
                           is_active=watchlist.is_active)
            
            await db_session.commit()
            logger.info("Successfully created watchlists from JSON")
            return True
            
        except Exception as e:
            await db_session.rollback()
            logger.error("Error creating watchlists from JSON", error=str(e))
            return False


async def list_watchlists():
    """List all watchlists and their symbols"""
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Watchlist).order_by(Watchlist.name)
            )
            watchlists = result.scalars().all()
            
            if not watchlists:
                print("No watchlists found in database.")
                return
            
            print(f"\n📊 Found {len(watchlists)} watchlists:\n")
            
            for watchlist in watchlists:
                result = await db_session.execute(
                    select(WatchlistSymbol)
                    .where(WatchlistSymbol.watchlist_id == watchlist.id)
                    .order_by(WatchlistSymbol.priority.desc(), WatchlistSymbol.symbol)
                )
                symbols = result.scalars().all()
                
                status = "🟢 Active" if watchlist.is_active else "🔴 Inactive"
                intraday_count = len([s for s in symbols if s.collect_intraday])
                
                print(f"{status} {watchlist.name} ({len(symbols)} symbols)")
                print(f"  📝 Description: {watchlist.description}")
                print(f"  📈 Intraday collection: {intraday_count}/{len(symbols)} symbols")
                
                if symbols:
                    symbol_list = []
                    for s in symbols[:10]:  # Show first 10 symbols
                        timeframes = s.timeframes or "none"
                        intraday_marker = "📊" if s.collect_intraday else "📉"
                        symbol_list.append(f"{s.symbol}{intraday_marker}({timeframes})")
                    
                    if len(symbols) > 10:
                        symbol_list.append(f"... and {len(symbols) - 10} more")
                    
                    print(f"  🎯 Symbols: {', '.join(symbol_list)}")
                
                print(f"  📅 Created: {watchlist.created_at.strftime('%Y-%m-%d %H:%M')}")
                print()
                
        except Exception as e:
            logger.error("Error listing watchlists", error=str(e))


async def get_intraday_symbols():
    """Get all symbols configured for intraday collection"""
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Get symbols from active watchlists that have intraday collection enabled
            result = await db_session.execute(
                select(WatchlistSymbol.symbol, WatchlistSymbol.timeframes, 
                       WatchlistSymbol.priority, Watchlist.name.label('watchlist_name'))
                .join(Watchlist)
                .where(
                    Watchlist.is_active == True,
                    WatchlistSymbol.collect_intraday == True
                )
                .order_by(WatchlistSymbol.priority.desc(), WatchlistSymbol.symbol)
            )
            
            symbols = result.fetchall()
            
            if not symbols:
                print("No symbols configured for intraday collection.")
                return []
            
            print(f"\n📊 {len(symbols)} symbols configured for intraday collection:\n")
            
            by_priority = {}
            for symbol in symbols:
                priority = symbol.priority
                if priority not in by_priority:
                    by_priority[priority] = []
                by_priority[priority].append(symbol)
            
            all_symbols = []
            for priority in sorted(by_priority.keys(), reverse=True):
                priority_symbols = by_priority[priority]
                print(f"Priority {priority} ({len(priority_symbols)} symbols):")
                for symbol in priority_symbols:
                    print(f"  {symbol.symbol} - {symbol.timeframes} (from {symbol.watchlist_name})")
                    all_symbols.append({
                        'symbol': symbol.symbol,
                        'timeframes': symbol.timeframes.split(',') if symbol.timeframes else [],
                        'priority': symbol.priority,
                        'watchlist': symbol.watchlist_name
                    })
                print()
            
            return all_symbols
            
        except Exception as e:
            logger.error("Error getting intraday symbols", error=str(e))
            return []


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Manage watchlists for market data collection')
    parser.add_argument('--create', action='store_true', 
                       help='Create watchlists from JSON file')
    parser.add_argument('--list', action='store_true', 
                       help='List all watchlists')
    parser.add_argument('--intraday', action='store_true',
                       help='Show symbols configured for intraday collection')
    parser.add_argument('--json-file', type=str, default='app/data/seeds/watchlists.json',
                       help='Path to watchlists JSON file (default: app/data/seeds/watchlists.json)')
    args = parser.parse_args()
    
    if args.create:
        print(f"📁 Creating watchlists from {args.json_file}")
        success = await create_watchlists_from_json(args.json_file)
        if success:
            print("✅ Watchlists created successfully")
        else:
            print("❌ Failed to create watchlists")
            sys.exit(1)
    
    if args.list:
        await list_watchlists()
    
    if args.intraday:
        await get_intraday_symbols()
    
    if not args.create and not args.list and not args.intraday:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())