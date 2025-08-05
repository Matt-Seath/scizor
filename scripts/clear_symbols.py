#!/usr/bin/env python3
"""
Clear Symbols Table
Simple script to clear the symbols table before fresh population
"""

import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import AsyncSessionLocal
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clear_symbols_table():
    """Clear all symbols from the table (and related market data)."""
    logger.info("🗑️  Clearing symbols table and related data...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Get counts before deletion
            symbols_result = await session.execute(text("SELECT COUNT(*) FROM symbols"))
            symbols_count = symbols_result.scalar()
            
            market_data_result = await session.execute(text("SELECT COUNT(*) FROM market_data"))
            market_data_count = market_data_result.scalar()
            
            logger.info(f"📊 Found {symbols_count} symbols and {market_data_count} market data records")
            
            if symbols_count > 0 or market_data_count > 0:
                # Clear market data first (due to foreign key constraints)
                if market_data_count > 0:
                    logger.info("🧹 Clearing market data first...")
                    await session.execute(text("DELETE FROM market_data"))
                    logger.info(f"✅ Cleared {market_data_count} market data records")
                
                # Then clear symbols
                if symbols_count > 0:
                    logger.info("🧹 Clearing symbols...")
                    await session.execute(text("DELETE FROM symbols"))
                    logger.info(f"✅ Cleared {symbols_count} symbols")
                
                await session.commit()
                
                # Verify deletion
                symbols_verify = await session.execute(text("SELECT COUNT(*) FROM symbols"))
                market_data_verify = await session.execute(text("SELECT COUNT(*) FROM market_data"))
                
                remaining_symbols = symbols_verify.scalar()
                remaining_market_data = market_data_verify.scalar()
                
                if remaining_symbols == 0 and remaining_market_data == 0:
                    logger.info("✅ All tables successfully cleared")
                else:
                    logger.warning(f"⚠️  {remaining_symbols} symbols and {remaining_market_data} market data records still remain")
            else:
                logger.info("📊 Tables are already empty")
                
        except Exception as e:
            logger.error(f"❌ Error clearing tables: {e}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        await clear_symbols_table()
        
        print("\n" + "="*50)
        print("🧹 SYMBOLS & MARKET DATA CLEARED")
        print("="*50)
        print("✅ Ready for fresh symbol population")
        print("🚀 Run fresh_symbol_population.py next")
        print("="*50)
        
    except Exception as e:
        logger.error(f"❌ Failed to clear symbols table: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
