#!/usr/bin/env python3
"""
Test script for the daily market data collection system.

This script performs basic validation of the daily collection system:
1. Checks database connectivity
2. Verifies symbols are available
3. Tests IBKR connection (if available)
4. Runs a dry-run simulation
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, MarketData
from scripts.daily_market_data_collection import DailyMarketDataCollector
from sqlalchemy import select, func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_database_connectivity():
    """Test database connectivity and symbol availability."""
    logger.info("🗄️  Testing database connectivity...")
    
    try:
        await init_db()
        logger.info("✅ Database connection successful")
        
        # Check symbols
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(func.count(Symbol.id)))
            symbol_count = result.scalar()
            
            logger.info(f"📊 Found {symbol_count} symbols in database")
            
            if symbol_count == 0:
                logger.warning("⚠️  No symbols found in database")
                return False
            
            # Get a sample of symbols
            result = await session.execute(
                select(Symbol).where(Symbol.active == True).limit(5)
            )
            sample_symbols = result.scalars().all()
            
            logger.info("📋 Sample symbols:")
            for symbol in sample_symbols:
                logger.info(f"   - {symbol.symbol} ({symbol.exchange}, {symbol.security_type.value})")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Database connectivity test failed: {str(e)}")
        return False


async def test_market_data_schema():
    """Test market data table schema."""
    logger.info("📊 Testing market data schema...")
    
    try:
        async with AsyncSessionLocal() as session:
            # Check if there's any existing market data
            result = await session.execute(select(func.count(MarketData.id)))
            data_count = result.scalar()
            
            logger.info(f"📈 Found {data_count} market data records")
            
            if data_count > 0:
                # Get a sample record
                result = await session.execute(
                    select(MarketData).limit(1)
                )
                sample_data = result.scalar()
                
                if sample_data:
                    logger.info(f"📋 Sample data: {sample_data.symbol.symbol if sample_data.symbol else 'N/A'} "
                               f"on {sample_data.timestamp.strftime('%Y-%m-%d')} - "
                               f"Close: {sample_data.close}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Market data schema test failed: {str(e)}")
        return False


async def test_dry_run_collection():
    """Test the collection system in dry-run mode."""
    logger.info("🔍 Testing dry-run collection...")
    
    try:
        collector = DailyMarketDataCollector(dry_run=True)
        
        # Test with a specific date (yesterday)
        yesterday = datetime.now() - timedelta(days=1)
        
        success = await collector.collect_daily_data(target_date=yesterday)
        
        if success:
            logger.info("✅ Dry-run collection test successful")
            return True
        else:
            logger.error("❌ Dry-run collection test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Dry-run collection test failed: {str(e)}")
        return False


async def test_contract_creation():
    """Test contract creation for different symbol types."""
    logger.info("📋 Testing contract creation...")
    
    try:
        async with AsyncSessionLocal() as session:
            # Get symbols of different types
            result = await session.execute(
                select(Symbol).where(Symbol.active == True).limit(10)
            )
            symbols = result.scalars().all()
            
            if not symbols:
                logger.warning("⚠️  No symbols available for contract testing")
                return False
            
            collector = DailyMarketDataCollector(dry_run=True)
            
            for symbol in symbols:
                try:
                    contract = collector._create_contract_for_symbol(symbol)
                    logger.info(f"✅ Created contract for {symbol.symbol}: "
                               f"secType={contract.secType}, exchange={contract.exchange}")
                except Exception as e:
                    logger.error(f"❌ Failed to create contract for {symbol.symbol}: {str(e)}")
                    return False
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Contract creation test failed: {str(e)}")
        return False


async def main():
    """Run all tests."""
    logger.info("🧪 Starting daily market data collection tests...")
    
    tests = [
        ("Database Connectivity", test_database_connectivity),
        ("Market Data Schema", test_market_data_schema),
        ("Contract Creation", test_contract_creation),
        ("Dry-Run Collection", test_dry_run_collection),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            result = await test_func()
            results[test_name] = result
            
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} CRASHED: {str(e)}")
            results[test_name] = False
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Daily collection system is ready.")
    else:
        logger.error("💥 Some tests failed. Check the logs above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
