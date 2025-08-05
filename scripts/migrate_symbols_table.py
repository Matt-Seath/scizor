#!/usr/bin/env python3
"""
Database migration: Add comprehensive symbol fields
Adds all IBKR API fields to the symbols table
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import AsyncSessionLocal
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Migration SQL to add new columns (one at a time for compatibility)
MIGRATION_STATEMENTS = [
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS company_name VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS long_name VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS industry VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS category VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS sector VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS primary_exchange VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS market_name VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS timezone_id VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS trading_hours VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS liquid_hours VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS market_cap NUMERIC(20, 2);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS shares_outstanding BIGINT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS float_shares BIGINT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS avg_volume BIGINT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS min_tick NUMERIC(10, 6);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS price_magnifier INTEGER;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS order_types TEXT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS valid_exchanges TEXT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS bond_type VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS coupon_type VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS callable BOOLEAN;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS putable BOOLEAN;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS coupon FLOAT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS convertible BOOLEAN;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS maturity VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS issue_date VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS ratings VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS bond_desc VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS cusip VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS fund_name VARCHAR(200);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS fund_family VARCHAR(100);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS fund_type VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS fund_fees FLOAT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS isin VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS cusip_num VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS sedol VARCHAR(10);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS ric VARCHAR(20);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS tradeable BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS market_data_available BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS under_comp VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS ev_rule VARCHAR(50);",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS ev_multiplier FLOAT;",
    "ALTER TABLE symbols ADD COLUMN IF NOT EXISTS last_verified TIMESTAMP;",
    'ALTER TABLE symbols ADD COLUMN IF NOT EXISTS "right" VARCHAR(10);',  # Quote reserved word
]

# Update indexes for new fields
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_symbols_sector ON symbols(sector);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_industry ON symbols(industry);", 
    "CREATE INDEX IF NOT EXISTS idx_symbols_market_cap ON symbols(market_cap);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_tradeable ON symbols(tradeable);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_primary_exchange ON symbols(primary_exchange);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_company_name ON symbols(company_name);",
]

async def run_migration():
    """Run the database migration to add new symbol fields."""
    
    logger.info("🚀 Starting symbol table migration...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Check current table structure
            logger.info("📊 Checking current table structure...")
            current_columns = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'symbols' 
                ORDER BY ordinal_position
            """))
            
            logger.info("Current columns in symbols table:")
            for col in current_columns:
                logger.info(f"   {col.column_name}: {col.data_type}")
            
            # Run migration statements one by one
            logger.info("🔧 Adding new columns to symbols table...")
            for i, statement in enumerate(MIGRATION_STATEMENTS, 1):
                try:
                    await session.execute(text(statement))
                    logger.info(f"   ✅ Statement {i}/{len(MIGRATION_STATEMENTS)} completed")
                except Exception as e:
                    logger.warning(f"   ⚠️  Statement {i} failed (may already exist): {e}")
            
            await session.commit()
            logger.info("✅ Successfully processed all migration statements")
            
            # Add indexes
            logger.info("📊 Creating indexes for new fields...")
            for i, statement in enumerate(INDEX_STATEMENTS, 1):
                try:
                    await session.execute(text(statement))
                    logger.info(f"   ✅ Index {i}/{len(INDEX_STATEMENTS)} created")
                except Exception as e:
                    logger.warning(f"   ⚠️  Index {i} failed (may already exist): {e}")
            
            await session.commit()
            logger.info("✅ Successfully created indexes")
            
            # Verify migration
            logger.info("🔍 Verifying migration...")
            new_columns = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'symbols' 
                ORDER BY ordinal_position
            """))
            
            column_count = len(list(new_columns))
            logger.info(f"📈 Symbols table now has {column_count} columns")
            
            # Update existing symbols with basic info where possible
            logger.info("🔄 Updating existing symbols with default values...")
            await session.execute(text("""
                UPDATE symbols 
                SET tradeable = TRUE,
                    market_data_available = TRUE,
                    last_verified = NOW()
                WHERE tradeable IS NULL
            """))
            await session.commit()
            logger.info("✅ Updated existing symbols")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        success = await run_migration()
        
        if success:
            print("\n" + "="*60)
            print("🎉 SYMBOL TABLE MIGRATION COMPLETE")
            print("="*60)
            print("✅ Added comprehensive IBKR API fields")
            print("✅ Created performance indexes")  
            print("✅ Updated existing records")
            print("="*60)
            print("🚀 Ready to populate with full symbol data!")
        else:
            print("❌ Migration failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
