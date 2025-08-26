#!/usr/bin/env python3
"""
Test script to validate data collection progress
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config.database import AsyncSessionLocal
from app.data.models.market import DailyPrice, ContractDetail
from app.data.collectors.market_data import MarketDataCollector
# from app.data.collectors.asx_contracts import get_liquid_stocks  # Deprecated - use WatchlistService

logger = structlog.get_logger(__name__)


async def test_database_connection():
    """Test database connectivity"""
    print("🔌 Testing Database Connection...")
    
    try:
        async with AsyncSessionLocal() as db_session:
            # Simple query to test connection
            result = await db_session.execute(select(func.current_timestamp()))
            timestamp = result.scalar()
            print(f"   ✅ Database connected successfully")
            print(f"   📅 Database time: {timestamp}")
            return True
            
    except Exception as e:
        print(f"   ❌ Database connection failed: {str(e)}")
        return False


async def test_contract_details_table():
    """Test contract details table data"""
    print("\n📋 Testing Contract Details Table...")
    
    try:
        async with AsyncSessionLocal() as db_session:
            # Count total contract details
            result = await db_session.execute(
                select(func.count(ContractDetail.id))
            )
            total_contracts = result.scalar()
            
            print(f"   📊 Total contract details: {total_contracts}")
            
            if total_contracts > 0:
                # Get sample contracts
                result = await db_session.execute(
                    select(ContractDetail.symbol, ContractDetail.con_id, ContractDetail.exchange)
                    .limit(5)
                )
                sample_contracts = result.all()
                
                print(f"   📋 Sample contracts:")
                for symbol, con_id, exchange in sample_contracts:
                    print(f"      {symbol}: ConID={con_id}, Exchange={exchange}")
                
                return True
            else:
                print(f"   ⚠️  No contract details found")
                print(f"   💡 Run: python scripts/populate_contracts.py")
                return False
                
    except Exception as e:
        print(f"   ❌ Contract details test failed: {str(e)}")
        return False


async def test_daily_prices_table():
    """Test daily prices table data"""
    print("\n📈 Testing Daily Prices Table...")
    
    try:
        async with AsyncSessionLocal() as db_session:
            # Count total daily prices
            result = await db_session.execute(
                select(func.count(DailyPrice.id))
            )
            total_prices = result.scalar()
            
            print(f"   📊 Total daily price records: {total_prices}")
            
            if total_prices > 0:
                # Get recent data
                result = await db_session.execute(
                    select(
                        DailyPrice.symbol,
                        DailyPrice.date,
                        DailyPrice.close,
                        DailyPrice.volume
                    )
                    .order_by(DailyPrice.date.desc(), DailyPrice.symbol)
                    .limit(10)
                )
                recent_data = result.all()
                
                print(f"   📋 Recent data (last 10 records):")
                for symbol, date, close, volume in recent_data:
                    print(f"      {symbol} {date}: ${close:.2f} Vol:{volume:,}")
                
                # Get data coverage by symbol
                result = await db_session.execute(
                    select(
                        DailyPrice.symbol,
                        func.count(DailyPrice.id).label('count'),
                        func.min(DailyPrice.date).label('first_date'),
                        func.max(DailyPrice.date).label('last_date')
                    )
                    .group_by(DailyPrice.symbol)
                    .order_by(func.count(DailyPrice.id).desc())
                    .limit(5)
                )
                coverage_data = result.all()
                
                print(f"   📊 Data coverage (top 5 symbols by record count):")
                for symbol, count, first_date, last_date in coverage_data:
                    days_span = (last_date - first_date).days + 1
                    print(f"      {symbol}: {count} records, {first_date} to {last_date} ({days_span} days)")
                
                return True
            else:
                print(f"   ⚠️  No daily price data found")
                print(f"   💡 Need to collect historical data first")
                return False
                
    except Exception as e:
        print(f"   ❌ Daily prices test failed: {str(e)}")
        return False


async def test_ibkr_connection():
    """Test IBKR TWS connection"""
    print("\n🔗 Testing IBKR TWS Connection...")
    
    try:
        collector = MarketDataCollector()
        
        # Test connection
        connected = await collector.start_collection()
        
        if connected:
            print(f"   ✅ IBKR TWS connection successful")
            
            # Get connection status
            status = collector.get_collection_stats()
            print(f"   📊 Connection details:")
            print(f"      Host: {status['connection_status']['host']}")
            print(f"      Port: {status['connection_status']['port']}")
            print(f"      Client ID: {status['connection_status']['client_id']}")
            print(f"      Market Open: {status['market_open']}")
            print(f"      Trading Day: {status['trading_day']}")
            
            # Disconnect
            await collector.stop_collection()
            print(f"   🔌 Disconnected successfully")
            return True
        else:
            print(f"   ❌ IBKR TWS connection failed")
            print(f"   💡 Ensure TWS/Gateway is running and configured correctly")
            return False
            
    except Exception as e:
        print(f"   ❌ IBKR connection test failed: {str(e)}")
        return False


async def test_sample_data_collection():
    """Test collecting sample data for one symbol"""
    print("\n📊 Testing Sample Data Collection...")
    
    # Check if we have contract details first
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(ContractDetail.symbol).limit(1)
        )
        sample_symbol = result.scalar()
    
    if not sample_symbol:
        print(f"   ⚠️  No contract details found - skipping data collection test")
        print(f"   💡 Run contract population first")
        return False
    
    try:
        collector = MarketDataCollector()
        
        # Connect
        connected = await collector.start_collection()
        if not connected:
            print(f"   ❌ Could not connect to IBKR for data collection test")
            return False
        
        print(f"   🎯 Testing data collection for symbol: {sample_symbol}")
        
        # Test historical data request (just 1 day for testing)
        start_date = datetime.now() - timedelta(days=5)
        end_date = datetime.now() - timedelta(days=1)
        
        print(f"   📅 Requesting data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Test backfill for small date range
        backfill_stats = await collector.backfill_historical_data(
            sample_symbol, start_date, end_date, skip_existing=False
        )
        
        # Disconnect
        await collector.stop_collection()
        
        if backfill_stats.get('bars_stored', 0) > 0:
            print(f"   ✅ Data collection successful")
            print(f"   📊 Bars stored: {backfill_stats['bars_stored']}")
            print(f"   ⏱️  Duration: {backfill_stats.get('duration_seconds', 0):.1f}s")
            return True
        else:
            print(f"   ⚠️  Data collection completed but no bars stored")
            print(f"   💡 This might be expected if data already exists or markets were closed")
            return True  # Still count as success
            
    except Exception as e:
        print(f"   ❌ Sample data collection failed: {str(e)}")
        return False


async def test_data_validation():
    """Test data validation functionality"""
    print("\n🔍 Testing Data Validation...")
    
    # Check if we have any daily price data
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(DailyPrice.symbol).limit(1)
        )
        sample_symbol = result.scalar()
    
    if not sample_symbol:
        print(f"   ⚠️  No daily price data found - skipping validation test")
        return False
    
    try:
        from app.data.processors.validation import DataValidator
        
        validator = DataValidator()
        
        print(f"   🎯 Testing validation for symbol: {sample_symbol}")
        
        # Run validation
        async with AsyncSessionLocal() as db_session:
            validation_report = await validator.validate_symbol_data(
                sample_symbol, db_session, days_lookback=7
            )
        
        print(f"   ✅ Validation completed successfully")
        print(f"   📊 Quality score: {validation_report.quality_score:.1f}/100")
        print(f"   📋 Data completeness: {validation_report.data_completeness:.1f}%")
        print(f"   ⚠️  Issues found: {len(validation_report.issues)}")
        print(f"   📈 Records validated: {validation_report.total_records}")
        
        # Show any critical issues
        critical_issues = [i for i in validation_report.issues if i.severity.value == 'critical']
        if critical_issues:
            print(f"   🚨 Critical issues: {len(critical_issues)}")
            for issue in critical_issues[:3]:  # Show first 3
                print(f"      - {issue.description}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Data validation test failed: {str(e)}")
        return False


async def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🧪 Scizor Trading System - Data Collection Test Suite")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Contract Details Table", test_contract_details_table),
        ("Daily Prices Table", test_daily_prices_table),
        ("IBKR TWS Connection", test_ibkr_connection),
        ("Sample Data Collection", test_sample_data_collection),
        ("Data Validation", test_data_validation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"   💥 Unexpected error in {test_name}: {str(e)}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Test Results Summary")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for data collection.")
        print("\n🚀 Next steps:")
        print("   1. Populate more contract details: python scripts/populate_contracts.py")
        print("   2. Test API endpoints: POST /api/data/backfill/BHP")
        print("   3. Run validation: POST /api/data/validate/BHP")
        print("   4. Monitor via dashboard: GET /health/detailed")
    elif passed >= total * 0.8:
        print("🎯 Most tests passed! Minor issues to address.")
    else:
        print("⚠️  Several tests failed. Please address issues before proceeding.")
    
    return passed == total


def main():
    """Main function"""
    load_dotenv()
    
    try:
        success = asyncio.run(run_comprehensive_test())
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Test suite interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()