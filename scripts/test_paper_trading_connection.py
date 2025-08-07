#!/usr/bin/env python3
"""
Test IBKR Connection to Paper Trading Account

This script tests the connection to your IBKR paper trading account
and validates that we can retrieve basic information.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.ibkr.client import IBKRManager
from shared.ibkr.contracts import create_stock_contract
from ibapi.contract import Contract

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_ibkr_connection():
    """Test connection to IBKR paper trading account."""
    logger.info("🔌 Testing IBKR Paper Trading Connection...")
    
    try:
        # Create IBKR manager with paper trading port
        ibkr_manager = IBKRManager(
            host="127.0.0.1",
            port=4002,  # Paper trading port
            client_id=999  # Test client ID
        )
        
        # Connect
        logger.info("📡 Attempting to connect to IBKR Gateway on port 4002...")
        connected = await ibkr_manager.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to IBKR Gateway")
            return False
        
        logger.info("✅ Successfully connected to IBKR Gateway!")
        
        # Wait a moment for connection to stabilize
        await asyncio.sleep(2)
        
        # Test contract details request for a simple stock
        logger.info("📊 Testing contract details request...")
        test_contract = Contract()
        test_contract.symbol = "CBA"
        test_contract.secType = "STK"
        test_contract.exchange = "ASX"
        test_contract.currency = "AUD"
        
        contract_details = await ibkr_manager.get_contract_details(test_contract, timeout=15)
        
        if contract_details and len(contract_details) > 0:
            logger.info(f"✅ Successfully retrieved contract details for CBA")
            logger.info(f"📋 Contract ID: {contract_details[0].contract.conId}")
            logger.info(f"📋 Local Symbol: {contract_details[0].contract.localSymbol}")
        else:
            logger.warning("⚠️  No contract details returned for CBA")
        
        # Test historical data request for a simple case
        logger.info("📈 Testing historical data request...")
        end_date = "20250806 23:59:59"  # Yesterday
        
        try:
            bars = await ibkr_manager.get_historical_data(
                contract=test_contract,
                end_date=end_date,
                duration="1 D",
                bar_size="1 day", 
                what_to_show="TRADES",
                use_rth=True,
                timeout=20
            )
            
            if bars and len(bars) > 0:
                bar = bars[0]
                logger.info(f"✅ Successfully retrieved historical data for CBA")
                logger.info(f"📊 Date: {bar.date}")
                logger.info(f"📊 OHLC: {bar.open}/{bar.high}/{bar.low}/{bar.close}")
                logger.info(f"📊 Volume: {bar.volume}")
            else:
                logger.warning("⚠️  No historical data returned")
                
        except Exception as e:
            logger.warning(f"⚠️  Historical data request failed: {str(e)}")
        
        # Disconnect
        logger.info("🔌 Disconnecting from IBKR...")
        await ibkr_manager.disconnect()
        
        logger.info("✅ IBKR connection test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ IBKR connection test failed: {str(e)}")
        return False


async def test_small_collection():
    """Test a small collection of 3 symbols."""
    logger.info("🧪 Testing small market data collection...")
    
    try:
        # Import here to avoid circular imports
        from scripts.daily_market_data_collection import DailyMarketDataCollector
        from shared.database.connection import AsyncSessionLocal
        from shared.database.models import Symbol
        from sqlalchemy import select
        
        # Get first 3 ASX symbols for testing
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Symbol).where(
                    Symbol.exchange == "ASX"
                ).order_by(Symbol.priority.asc()).limit(3)
            )
            test_symbols = result.scalars().all()
        
        if not test_symbols:
            logger.error("❌ No ASX symbols found for testing")
            return False
        
        logger.info(f"📊 Testing collection for {len(test_symbols)} symbols:")
        for symbol in test_symbols:
            logger.info(f"   - {symbol.symbol} ({symbol.company_name})")
        
        # Create test collector
        collector = DailyMarketDataCollector(dry_run=False)
        
        # Override the connection settings for paper trading
        collector.ibkr_manager = None  # Reset to use paper trading port
        
        # Manually set up connection to paper trading
        collector.ibkr_manager = IBKRManager(
            host="127.0.0.1",
            port=4002,  # Paper trading
            client_id=101  # Different client ID
        )
        
        # Connect
        connected = await collector.ibkr_manager.connect()
        if not connected:
            logger.error("❌ Failed to connect for collection test")
            return False
        
        # Test collection for each symbol
        success_count = 0
        target_date = datetime(2025, 8, 6)  # Yesterday
        
        for symbol in test_symbols:
            try:
                logger.info(f"🔍 Testing collection for {symbol.symbol}...")
                
                # Create log entry
                log_id = await collector._create_collection_log(symbol.id, target_date)
                
                # Test the collection
                success = await collector._request_historical_data(symbol, target_date)
                
                if success:
                    success_count += 1
                    await collector._update_collection_log(log_id, "completed", None)
                    logger.info(f"✅ Successfully collected data for {symbol.symbol}")
                else:
                    await collector._update_collection_log(log_id, "failed", "Test collection failed")
                    logger.warning(f"⚠️  Failed to collect data for {symbol.symbol}")
                
                # Small delay between requests
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error testing {symbol.symbol}: {str(e)}")
        
        # Disconnect
        await collector.ibkr_manager.disconnect()
        
        logger.info(f"📊 Collection test results: {success_count}/{len(test_symbols)} successful")
        
        if success_count > 0:
            logger.info("✅ Market data collection test PASSED!")
            return True
        else:
            logger.error("❌ Market data collection test FAILED!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Collection test failed: {str(e)}")
        return False


async def main():
    """Run IBKR connection and collection tests."""
    logger.info("🚀 Starting IBKR Paper Trading Tests...")
    
    # Test 1: Basic connection
    logger.info("\n" + "="*60)
    logger.info("TEST 1: IBKR Connection Test")
    logger.info("="*60)
    
    connection_success = await test_ibkr_connection()
    
    if not connection_success:
        logger.error("❌ Connection test failed - skipping collection test")
        return False
    
    # Test 2: Small collection
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Small Collection Test")
    logger.info("="*60)
    
    collection_success = await test_small_collection()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    logger.info(f"Connection Test: {'✅ PASS' if connection_success else '❌ FAIL'}")
    logger.info(f"Collection Test: {'✅ PASS' if collection_success else '❌ FAIL'}")
    
    if connection_success and collection_success:
        logger.info("🎉 All tests passed! Paper trading connection is working!")
        logger.info("💡 You can now run the full daily collection with:")
        logger.info("   python scripts/daily_market_data_collection.py")
        return True
    else:
        logger.error("💥 Some tests failed. Check the logs above for details.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
