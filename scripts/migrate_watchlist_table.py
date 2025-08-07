#!/usr/bin/env python3
"""
Database migration to add the watchlist table for intraday data collection.

This script adds the new watchlist table to track symbols for enhanced data collection.
"""

import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal, engine
from shared.database.models import Base, Watchlist
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_watchlist_table():
    """Create the watchlist table."""
    try:
        # Initialize database connection
        await init_db()
        
        logger.info("Creating watchlist table...")
        
        # Create the table using SQLAlchemy
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Watchlist table created successfully")
        
        # Verify the table was created
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'watchlist'")
            )
            count = result.scalar()
            
            if count > 0:
                logger.info("✅ Watchlist table verified in database")
            else:
                logger.error("❌ Watchlist table not found after creation")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating watchlist table: {e}")
        return False


async def main():
    """Main execution function."""
    try:
        logger.info("🚀 Starting database migration for watchlist table")
        
        success = await create_watchlist_table()
        
        if success:
            print("\n" + "="*60)
            print("🎯 DATABASE MIGRATION COMPLETE")
            print("="*60)
            print("✅ Watchlist table created successfully")
            print("✅ Ready for intraday data collection setup")
            print("="*60)
            print("Next steps:")
            print("1. Run: python scripts/manage_watchlist.py create-default")
            print("2. Add symbols: python scripts/manage_watchlist.py add --symbol AAPL --name my_watchlist")
            print("3. Start collection: python scripts/intraday_collection.py --timeframe 5min")
        else:
            print("❌ Migration failed")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
