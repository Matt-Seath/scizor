#!/usr/bin/env python3
"""
Professional ASX Watchlist Setup Script

This script populates the database with the professionally curated 18-stock ASX 
portfolio optimized for IBKR free-tier constraints. This implements the strategy
documented in docs/asx_stock_selection_strategy.md.

Professional 18-Stock Portfolio:
- Tier 1 (8 stocks): Core blue chips - highest priority, 5min + 1min collection
- Tier 2 (6 stocks): Growth/Resources - high priority, 5min collection  
- Tier 3 (4 stocks): Technology - medium priority, 5min collection

Usage:
    python scripts/populate_asx_professional_watchlist.py
    python scripts/populate_asx_professional_watchlist.py --force  # Override existing
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, Watchlist
from sqlalchemy import select, and_, delete
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Professional 18-Stock ASX Portfolio Configuration
PROFESSIONAL_ASX_PORTFOLIO = {
    "tier_1_core": {
        "stocks": ["CBA", "BHP", "CSL", "WBC", "ANZ", "NAB", "WOW", "WES"],
        "priority": 1,
        "collect_5min": True,
        "collect_1min": True,
        "notes": "Tier 1: Core blue chip - maximum data collection for best opportunities"
    },
    "tier_2_growth": {
        "stocks": ["RIO", "MQG", "FMG", "TLS", "TCL", "COL"],
        "priority": 2,
        "collect_5min": True,
        "collect_1min": False,
        "notes": "Tier 2: Growth/Resources - 5min data for swing trading"
    },
    "tier_3_technology": {
        "stocks": ["XRO", "WTC", "APT", "ZIP"],
        "priority": 3,
        "collect_5min": True,
        "collect_1min": False,
        "notes": "Tier 3: Technology - opportunity tracking and momentum plays"
    }
}

WATCHLIST_NAME = "asx_professional"


class ProfessionalWatchlistManager:
    """Manages the professional ASX watchlist configuration."""
    
    def __init__(self):
        self.session = None
        self.created_count = 0
        self.updated_count = 0
        self.error_count = 0
        
    async def __aenter__(self):
        await init_db()
        self.session = AsyncSessionLocal()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def verify_symbols_exist(self, symbols: List[str]) -> Dict[str, bool]:
        """Verify that all required symbols exist in the database."""
        logger.info(f"Verifying {len(symbols)} symbols exist in database...")
        
        symbol_status = {}
        for symbol in symbols:
            result = await self.session.execute(
                select(Symbol).where(Symbol.symbol == symbol.upper())
            )
            symbol_obj = result.scalar_one_or_none()
            symbol_status[symbol] = symbol_obj is not None
            
            if not symbol_obj:
                logger.warning(f"⚠️  Symbol {symbol} not found in database")
            else:
                logger.debug(f"✅ Symbol {symbol} found: {symbol_obj.company_name}")
        
        missing_symbols = [s for s, exists in symbol_status.items() if not exists]
        if missing_symbols:
            logger.error(f"❌ Missing symbols: {missing_symbols}")
            logger.error("Please run 'python scripts/populate_symbols.py' first to add these symbols")
            return symbol_status
        
        logger.info("✅ All symbols verified in database")
        return symbol_status
    
    async def clear_existing_watchlist(self, force: bool = False) -> bool:
        """Clear existing professional watchlist if it exists."""
        try:
            # Check if watchlist exists
            result = await self.session.execute(
                select(Watchlist).where(Watchlist.name == WATCHLIST_NAME)
            )
            existing_entries = result.all()
            
            if existing_entries and not force:
                logger.warning(f"Professional watchlist '{WATCHLIST_NAME}' already exists with {len(existing_entries)} entries")
                logger.warning("Use --force to override existing watchlist")
                return False
            
            if existing_entries:
                logger.info(f"🗑️  Clearing existing watchlist '{WATCHLIST_NAME}' with {len(existing_entries)} entries")
                await self.session.execute(
                    delete(Watchlist).where(Watchlist.name == WATCHLIST_NAME)
                )
                await self.session.commit()
                logger.info("✅ Existing watchlist cleared")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing existing watchlist: {e}")
            await self.session.rollback()
            return False
    
    async def add_tier_to_watchlist(self, tier_name: str, tier_config: Dict) -> int:
        """Add a tier of stocks to the professional watchlist."""
        logger.info(f"📊 Adding {tier_name}: {len(tier_config['stocks'])} stocks at priority {tier_config['priority']}")
        
        added_count = 0
        for symbol in tier_config["stocks"]:
            try:
                # Get symbol from database
                result = await self.session.execute(
                    select(Symbol).where(Symbol.symbol == symbol.upper())
                )
                symbol_obj = result.scalar_one_or_none()
                
                if not symbol_obj:
                    logger.error(f"❌ Symbol {symbol} not found in database")
                    self.error_count += 1
                    continue
                
                # Create watchlist entry
                watchlist_entry = Watchlist(
                    symbol_id=symbol_obj.id,
                    name=WATCHLIST_NAME,
                    priority=tier_config["priority"],
                    collect_5min=tier_config["collect_5min"],
                    collect_1min=tier_config["collect_1min"],
                    collect_tick=False,  # No tick data for now
                    notes=tier_config["notes"],
                    active=True,
                    start_date=datetime.now()
                )
                
                self.session.add(watchlist_entry)
                added_count += 1
                self.created_count += 1
                
                logger.info(f"  ✅ Added {symbol} ({symbol_obj.company_name[:30]}...)")
                
            except IntegrityError as e:
                logger.warning(f"  ⚠️  {symbol} already in watchlist (skipping)")
                await self.session.rollback()
                self.session = AsyncSessionLocal()  # Get fresh session
                continue
            except Exception as e:
                logger.error(f"  ❌ Error adding {symbol}: {e}")
                self.error_count += 1
                await self.session.rollback()
                self.session = AsyncSessionLocal()  # Get fresh session
                continue
        
        # Commit the tier
        try:
            await self.session.commit()
            logger.info(f"✅ {tier_name} committed: {added_count} stocks added")
        except Exception as e:
            logger.error(f"❌ Error committing {tier_name}: {e}")
            await self.session.rollback()
            return 0
        
        return added_count
    
    async def populate_professional_watchlist(self, force: bool = False) -> bool:
        """Populate the complete professional ASX watchlist."""
        logger.info("🚀 Starting Professional ASX Watchlist Setup")
        logger.info("=" * 60)
        
        # Collect all symbols for verification
        all_symbols = []
        for tier_config in PROFESSIONAL_ASX_PORTFOLIO.values():
            all_symbols.extend(tier_config["stocks"])
        
        # Verify all symbols exist
        symbol_status = await self.verify_symbols_exist(all_symbols)
        missing_symbols = [s for s, exists in symbol_status.items() if not exists]
        
        if missing_symbols:
            logger.error(f"❌ Cannot proceed: {len(missing_symbols)} symbols missing from database")
            return False
        
        # Clear existing watchlist if needed
        if not await self.clear_existing_watchlist(force):
            return False
        
        # Add each tier
        total_added = 0
        for tier_name, tier_config in PROFESSIONAL_ASX_PORTFOLIO.items():
            added = await self.add_tier_to_watchlist(tier_name, tier_config)
            total_added += added
        
        # Summary
        logger.info("=" * 60)
        logger.info("🎯 Professional ASX Watchlist Setup Complete!")
        logger.info(f"📊 Total stocks added: {self.created_count}")
        logger.info(f"⚠️  Errors encountered: {self.error_count}")
        
        if self.created_count > 0:
            logger.info(f"✅ Professional watchlist '{WATCHLIST_NAME}' ready for trading!")
            logger.info("")
            logger.info("📋 Summary by tier:")
            for tier_name, tier_config in PROFESSIONAL_ASX_PORTFOLIO.items():
                logger.info(f"  {tier_name}: {len(tier_config['stocks'])} stocks (Priority {tier_config['priority']})")
            
            logger.info("")
            logger.info("🔧 Next steps:")
            logger.info("1. Verify watchlist: python scripts/manage_watchlist.py list --name asx_professional")
            logger.info("2. Start data collection: python scripts/intraday_collection.py --watchlist asx_professional")
            logger.info("3. Deploy professional service: docker-compose -f docker-compose.professional.yml up -d")
            
            return True
        else:
            logger.error("❌ No stocks were added to the watchlist")
            return False
    
    async def verify_watchlist_setup(self) -> None:
        """Verify the professional watchlist setup is correct."""
        logger.info("🔍 Verifying professional watchlist setup...")
        
        result = await self.session.execute(
            select(Watchlist, Symbol).join(Symbol).where(
                and_(
                    Watchlist.name == WATCHLIST_NAME,
                    Watchlist.active == True
                )
            ).order_by(Watchlist.priority, Symbol.symbol)
        )
        
        watchlist_data = result.all()
        
        if not watchlist_data:
            logger.error(f"❌ No entries found in watchlist '{WATCHLIST_NAME}'")
            return
        
        logger.info(f"📊 Professional Watchlist '{WATCHLIST_NAME}' ({len(watchlist_data)} stocks):")
        logger.info("-" * 80)
        
        by_priority = {}
        for watchlist_entry, symbol in watchlist_data:
            priority = watchlist_entry.priority
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append({
                'symbol': symbol.symbol,
                'name': symbol.company_name,
                'collect_5min': watchlist_entry.collect_5min,
                'collect_1min': watchlist_entry.collect_1min
            })
        
        for priority in sorted(by_priority.keys()):
            tier_name = {1: "Tier 1 (Core)", 2: "Tier 2 (Growth)", 3: "Tier 3 (Tech)"}.get(priority, f"Tier {priority}")
            stocks = by_priority[priority]
            logger.info(f"{tier_name}: {len(stocks)} stocks")
            
            for stock in stocks:
                timeframes = []
                if stock['collect_5min']:
                    timeframes.append("5min")
                if stock['collect_1min']:
                    timeframes.append("1min")
                timeframe_str = "+".join(timeframes)
                
                logger.info(f"  {stock['symbol']:4} - {stock['name'][:40]:40} [{timeframe_str}]")
            logger.info("")


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Setup Professional ASX Watchlist")
    parser.add_argument("--force", action="store_true", 
                       help="Override existing watchlist")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify existing watchlist setup")
    
    args = parser.parse_args()
    
    try:
        async with ProfessionalWatchlistManager() as manager:
            if args.verify_only:
                await manager.verify_watchlist_setup()
            else:
                success = await manager.populate_professional_watchlist(force=args.force)
                if success:
                    await manager.verify_watchlist_setup()
                    
    except KeyboardInterrupt:
        logger.info("\n⏹️  Setup cancelled by user")
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
