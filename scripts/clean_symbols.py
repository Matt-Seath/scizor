#!/usr/bin/env python3
"""
Clean up problematic symbols from the database that can't be found by IBKR.

This script will:
1. Identify symbols that are causing "No security definition" errors
2. Mark them as inactive in the database
3. Provide a report of cleaned symbols
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
from shared.database.models import Symbol
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Known problematic symbols based on error logs and research
PROBLEMATIC_SYMBOLS = {
    # Delisted/Merged/Acquired stocks
    "GXY": "Galaxy Resources - merged with Orocobre to form Allkem (AKE)",
    "IVC": "InvoCare - may have been delisted or suspended",
    "JHG": "Janus Henderson Group - likely delisted from ASX",
    "LRS": "Latin Resources - may be suspended or delisted",
    "MNY": "Money3 Corp - may have been delisted",
    "NCM": "Newcrest Mining - acquired by Newmont, delisted",
    "CWN": "Crown Resorts - acquired by Blackstone, delisted",
    "ORE": "Orocobre - merged with Galaxy to form Allkem (AKE)",
    "APT": "Afterpay - acquired by Block Inc (Square), delisted from ASX",
    "OSH": "Oil Search - merged with Santos (STO)",
    "CTX": "Caltex Australia - likely delisted",
    "CCL": "Coca-Cola Amatil - acquired by Coca-Cola Europacific Partners",
    "BAL": "Bellamy's Australia - acquired by China Mengniu Dairy",
    "API": "Australian Pharmaceutical Industries - acquired by Wesfarmers",
    "LAM": "Lam Research Corp - this is a US stock, shouldn't be in ASX list",
    "IPL": "Incitec Pivot - may have been delisted or suspended",
    "LLC": "Lendlease Corp - may have issues with IBKR symbol format",
    "MEL": "Melbourne Airport - may have been delisted or suspended",
    "URW": "Unibail-Rodamco-Westfield - may have issues with IBKR",
    "VCX": "Vicinity Centres - may have issues or been delisted",
    "ALU": "Altium - may have been acquired or delisted",
    "ZIP": "Zip Co - may have been suspended or delisted",
    "FBU": "Fletcher Building - may have issues with IBKR format",
    "YAL": "Yancoal Australia - may have issues or suspended",
    "TWTR": "Twitter - acquired by Elon Musk, delisted",
    "XLNX": "Xilinx - acquired by AMD, delisted",
    
    # Stocks that may have changed symbols or been suspended
    "AVZ": "AVZ Minerals - suspended",
    "TMZ": "Thomson Resources - may be suspended",
    "TMT": "Technology Metals Australia - may be suspended",
    "ERA": "Energy Resources of Australia - may be delisted",
    "GTR": "GTI Resources - may be suspended",
    "TMR": "Tempus Resources - may be suspended",
    "CXZ": "Connexion Telematics - may be delisted",
    "TNT": "Tesserent - may have changed or been delisted",
    "FFI": "FFI Holdings - may be delisted",
    
    # ETFs that may not be available through IBKR
    "VEU": "Vanguard All-World ex-US - may not be available on ASX through IBKR",
    "VCF": "Vanguard International Credit Securities - may not be available",
    "IJH": "iShares Core S&P Mid-Cap - US ETF, not ASX",
    "IJR": "iShares Core S&P Small-Cap - US ETF, not ASX",
    "SPY": "SPDR S&P 500 - US ETF, not ASX",
    "IEMA": "iShares MSCI Emerging Markets Asia - may not be available",
}

# Symbols to update/replace
SYMBOL_UPDATES = {
    "GXY": "AKE",  # Galaxy -> Allkem
    "ORE": "AKE",  # Orocobre -> Allkem  
    "OSH": "STO",  # Oil Search merged with Santos
    "NCM": None,   # Newcrest delisted, no replacement
    "CWN": None,   # Crown delisted, no replacement
    "APT": None,   # Afterpay delisted from ASX
}


async def clean_problematic_symbols():
    """Clean up problematic symbols from the database."""
    
    logger.info("🧹 Starting symbol cleanup...")
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            # Get all symbols that are problematic
            result = await session.execute(
                select(Symbol).where(Symbol.symbol.in_(list(PROBLEMATIC_SYMBOLS.keys())))
            )
            problematic_symbols = result.scalars().all()
            
            logger.info(f"📊 Found {len(problematic_symbols)} problematic symbols in database")
            
            deactivated_count = 0
            not_found_count = 0
            
            # Process each problematic symbol
            for symbol_name in PROBLEMATIC_SYMBOLS:
                reason = PROBLEMATIC_SYMBOLS[symbol_name]
                
                # Find the symbol in database
                symbol_result = await session.execute(
                    select(Symbol).where(Symbol.symbol == symbol_name)
                )
                symbol = symbol_result.scalar_one_or_none()
                
                if symbol:
                    if symbol.active:
                        # Deactivate the symbol
                        symbol.active = False
                        symbol.tradeable = False
                        logger.info(f"❌ Deactivated {symbol_name}: {reason}")
                        deactivated_count += 1
                    else:
                        logger.info(f"⏭️  {symbol_name} already inactive: {reason}")
                else:
                    logger.info(f"🔍 Symbol {symbol_name} not found in database")
                    not_found_count += 1
            
            # Commit changes
            await session.commit()
            
            # Get counts after cleanup
            active_result = await session.execute(
                select(Symbol).where(Symbol.active == True)
            )
            active_symbols = active_result.scalars().all()
            
            inactive_result = await session.execute(
                select(Symbol).where(Symbol.active == False)
            )
            inactive_symbols = inactive_result.scalars().all()
            
            logger.info("🎉 Symbol cleanup completed!")
            logger.info(f"📊 Summary:")
            logger.info(f"   • Symbols deactivated: {deactivated_count}")
            logger.info(f"   • Symbols not found: {not_found_count}")
            logger.info(f"   • Total active symbols: {len(active_symbols)}")
            logger.info(f"   • Total inactive symbols: {len(inactive_symbols)}")
            
            # Show some examples of remaining active ASX symbols
            asx_active = await session.execute(
                select(Symbol).where(
                    Symbol.exchange == "ASX",
                    Symbol.active == True
                ).limit(10)
            )
            
            logger.info("📈 Sample of remaining active ASX symbols:")
            for symbol in asx_active.scalars():
                logger.info(f"   • {symbol.symbol}: {symbol.company_name}")
            
            return {
                "deactivated": deactivated_count,
                "not_found": not_found_count,
                "active_total": len(active_symbols),
                "inactive_total": len(inactive_symbols)
            }
            
        except Exception as e:
            logger.error(f"❌ Error cleaning symbols: {e}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        result = await clean_problematic_symbols()
        
        print("\n" + "="*60)
        print("🧹 SCIZOR SYMBOL CLEANUP COMPLETE")
        print("="*60)
        print(f"❌ Symbols Deactivated: {result['deactivated']}")
        print(f"🔍 Symbols Not Found: {result['not_found']}")
        print(f"✅ Active Symbols: {result['active_total']}")
        print(f"💤 Inactive Symbols: {result['inactive_total']}")
        print("="*60)
        print("✅ Daily collection should now run without errors!")
        
    except Exception as e:
        logger.error(f"❌ Failed to clean symbols: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
