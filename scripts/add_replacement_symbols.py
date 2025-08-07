#!/usr/bin/env python3
"""
Add replacement symbols for merged/acquired companies.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, SecurityType
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replacement symbols to add
REPLACEMENT_SYMBOLS = [
    # AKE is the merged entity of Galaxy Resources (GXY) and Orocobre (ORE)
    {"symbol": "AKE", "name": "Allkem Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 145},
    
    # Some strong ASX stocks that are definitely active
    {"symbol": "CSR", "name": "CSR Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 146},
    {"symbol": "ABC", "name": "Adelaide Brighton Ltd", "sector": "Materials", "market_cap": "Small", "priority": 147},
    {"symbol": "BLD", "name": "Boral Ltd", "sector": "Materials", "market_cap": "Mid", "priority": 148},
    {"symbol": "RWC", "name": "Reliance Worldwide Corp Ltd", "sector": "Industrials", "market_cap": "Mid", "priority": 149},
    {"symbol": "TNE", "name": "Technology One Ltd", "sector": "Technology", "market_cap": "Mid", "priority": 150},
    {"symbol": "ING", "name": "Inghams Group Ltd", "sector": "Consumer Staples", "market_cap": "Mid", "priority": 151},
    {"symbol": "A2M", "name": "The a2 Milk Company Ltd", "sector": "Consumer Staples", "market_cap": "Mid", "priority": 152},
    {"symbol": "BGA", "name": "Bega Cheese Ltd", "sector": "Consumer Staples", "market_cap": "Small", "priority": 153},
    {"symbol": "NAN", "name": "Nanosonics Ltd", "sector": "Health Care", "market_cap": "Small", "priority": 154},
    {"symbol": "SIG", "name": "Sigma Healthcare Ltd", "sector": "Health Care", "market_cap": "Small", "priority": 155},
    {"symbol": "PNI", "name": "Pinnacle Investment Management Group Ltd", "sector": "Financials", "market_cap": "Small", "priority": 156},
    {"symbol": "HUB", "name": "Hub24 Ltd", "sector": "Financials", "market_cap": "Mid", "priority": 157},
    {"symbol": "ELD", "name": "Elders Ltd", "sector": "Industrials", "market_cap": "Small", "priority": 158},
    {"symbol": "GNC", "name": "Graincorp Ltd", "sector": "Consumer Staples", "market_cap": "Small", "priority": 159},
    {"symbol": "NUF", "name": "Nufarm Ltd", "sector": "Materials", "market_cap": "Small", "priority": 160},
]


async def add_replacement_symbols():
    """Add replacement symbols to the database."""
    
    logger.info("➕ Adding replacement symbols...")
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            # Check existing symbols
            existing_result = await session.execute(select(Symbol))
            existing_symbols = {s.symbol for s in existing_result.scalars().all()}
            
            added_count = 0
            skipped_count = 0
            
            # Process replacement symbols
            for symbol_data in REPLACEMENT_SYMBOLS:
                if symbol_data["symbol"] not in existing_symbols:
                    new_symbol = Symbol(
                        symbol=symbol_data["symbol"],
                        company_name=symbol_data["name"],
                        exchange="ASX",
                        currency="AUD",
                        security_type=SecurityType.STOCK,
                        sector=symbol_data.get("sector", "Unknown"),
                        market_cap_category=symbol_data.get("market_cap", "Mid"),
                        local_symbol=f"{symbol_data['symbol']}.AX",  # IBKR format
                        active=True,
                        is_asx200=True,
                        priority=symbol_data.get("priority", 200),
                        min_tick=0.01,  # Standard ASX tick size
                        tradeable=True
                    )
                    session.add(new_symbol)
                    added_count += 1
                    logger.info(f"✨ Added replacement symbol: {symbol_data['symbol']} - {symbol_data['name']}")
                else:
                    # Check if it's inactive and reactivate it
                    symbol_result = await session.execute(
                        select(Symbol).where(Symbol.symbol == symbol_data["symbol"])
                    )
                    existing_symbol = symbol_result.scalar_one_or_none()
                    
                    if existing_symbol and not existing_symbol.active:
                        existing_symbol.active = True
                        existing_symbol.tradeable = True
                        logger.info(f"🔄 Reactivated symbol: {symbol_data['symbol']}")
                        added_count += 1
                    else:
                        skipped_count += 1
                        logger.info(f"⏭️  Skipped existing active symbol: {symbol_data['symbol']}")
            
            # Commit changes
            await session.commit()
            
            # Get final active count
            active_result = await session.execute(
                select(Symbol).where(Symbol.active == True)
            )
            active_count = len(active_result.scalars().all())
            
            logger.info("🎉 Replacement symbols added!")
            logger.info(f"📊 Summary:")
            logger.info(f"   • New symbols added/reactivated: {added_count}")
            logger.info(f"   • Existing symbols skipped: {skipped_count}")
            logger.info(f"   • Total active symbols: {active_count}")
            
            return {
                "added": added_count,
                "skipped": skipped_count,
                "active_total": active_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error adding replacement symbols: {e}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        result = await add_replacement_symbols()
        
        print("\n" + "="*60)
        print("➕ REPLACEMENT SYMBOLS ADDED")
        print("="*60)
        print(f"✨ Symbols Added/Reactivated: {result['added']}")
        print(f"⏭️  Symbols Skipped: {result['skipped']}")
        print(f"✅ Total Active Symbols: {result['active_total']}")
        print("="*60)
        print("✅ Symbol database is now cleaned and updated!")
        
    except Exception as e:
        logger.error(f"❌ Failed to add replacement symbols: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
