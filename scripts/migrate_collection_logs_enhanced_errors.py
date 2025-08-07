#!/usr/bin/env python3
"""
Migrate collection_logs table to add enhanced error tracking columns.
This script adds new columns for better error analysis and debugging.
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
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_collection_logs():
    """Add enhanced error tracking columns to collection_logs table."""
    
    logger.info("🔄 Starting collection_logs table migration...")
    
    # Initialize database
    await init_db()
    
    # SQL commands to add new columns
    migration_commands = [
        "ALTER TABLE collection_logs ADD COLUMN IF NOT EXISTS error_code INTEGER;",
        "ALTER TABLE collection_logs ADD COLUMN IF NOT EXISTS error_type VARCHAR(50);", 
        "ALTER TABLE collection_logs ADD COLUMN IF NOT EXISTS ibkr_request_id INTEGER;",
        "ALTER TABLE collection_logs ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;",
        "ALTER TABLE collection_logs ADD COLUMN IF NOT EXISTS error_details JSONB;"
    ]
    
    # Create indexes for better query performance
    index_commands = [
        "CREATE INDEX IF NOT EXISTS idx_collection_logs_error_code ON collection_logs(error_code);",
        "CREATE INDEX IF NOT EXISTS idx_collection_logs_error_type ON collection_logs(error_type);",
        "CREATE INDEX IF NOT EXISTS idx_collection_logs_retry_count ON collection_logs(retry_count);",
        "CREATE INDEX IF NOT EXISTS idx_collection_logs_started_at ON collection_logs(started_at);",
        "CREATE INDEX IF NOT EXISTS idx_collection_logs_status_date ON collection_logs(status, started_at);"
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            logger.info("📝 Adding new columns...")
            
            # Execute migration commands
            for i, command in enumerate(migration_commands, 1):
                logger.info(f"   {i}. {command}")
                await session.execute(text(command))
            
            logger.info("🔍 Creating performance indexes...")
            
            # Execute index commands  
            for i, command in enumerate(index_commands, 1):
                logger.info(f"   {i}. {command}")
                await session.execute(text(command))
                
            await session.commit()
            
            # Verify the migration
            logger.info("✅ Verifying migration...")
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'collection_logs' 
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            logger.info("📊 Current collection_logs table structure:")
            for col in columns:
                logger.info(f"   • {col[0]} ({col[1]}) - {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
            
            # Check indexes
            index_result = await session.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'collection_logs'
                ORDER BY indexname;
            """))
            
            indexes = index_result.fetchall()
            logger.info("🔍 Current collection_logs indexes:")
            for idx in indexes:
                logger.info(f"   • {idx[0]}")
                
            logger.info("🎉 Collection logs migration completed successfully!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during migration: {str(e)}")
            await session.rollback()
            raise


async def main():
    """Main execution function."""
    try:
        await migrate_collection_logs()
        
        print("\n" + "="*60)
        print("🎯 COLLECTION LOGS MIGRATION COMPLETE")
        print("="*60)
        print("✨ New columns added:")
        print("   • error_code (INTEGER) - IBKR error codes")
        print("   • error_type (VARCHAR) - Categorized error types")
        print("   • ibkr_request_id (INTEGER) - IBKR request tracking")
        print("   • retry_count (INTEGER) - Retry attempt counter")
        print("   • error_details (JSONB) - Detailed error information")
        print("🔍 Performance indexes created for better querying")
        print("="*60)
        print("✅ Enhanced error tracking is now available!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
