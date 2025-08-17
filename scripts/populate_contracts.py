#!/usr/bin/env python3
"""
Script to populate contract_details table with ASX200 stock information
"""
import sys
import os
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.data.models.market import ContractDetail
from app.data.collectors.ibkr_client import IBKRClient
from app.data.collectors.asx_contracts import (
    get_asx200_symbols, 
    create_asx_stock_contract,
    get_liquid_stocks
)

logger = structlog.get_logger(__name__)


class ContractDetailsCollector:
    """Collect and store IBKR contract details for ASX200 stocks"""
    
    def __init__(self):
        self.ibkr_client = IBKRClient()
        self.contract_details_cache = {}
        self.collection_stats = {
            "requested": 0,
            "successful": 0,
            "failed": 0,
            "already_cached": 0
        }
    
    async def populate_contract_details(self, symbols: List[str] = None, 
                                      force_refresh: bool = False) -> Dict[str, any]:
        """
        Populate contract details table with ASX200 stock information
        
        Args:
            symbols: List of symbols to process (None for all ASX200)
            force_refresh: Whether to refresh existing contract details
            
        Returns:
            Dictionary with collection results
        """
        if symbols is None:
            symbols = get_asx200_symbols()
        
        logger.info("Starting contract details collection", 
                   symbols_count=len(symbols), force_refresh=force_refresh)
        
        try:
            # Connect to IBKR
            if not self.ibkr_client.connect_to_tws():
                logger.error("Failed to connect to IBKR TWS")
                return {
                    'success': False,
                    'error': 'Failed to connect to IBKR TWS'
                }
            
            logger.info("Connected to IBKR TWS successfully")
            
            # Check existing contract details if not forcing refresh
            existing_symbols = set()
            if not force_refresh:
                existing_symbols = await self._get_existing_contract_symbols()
                logger.info("Found existing contract details", count=len(existing_symbols))
            
            # Process each symbol
            failed_symbols = []
            successful_symbols = []
            
            for i, symbol in enumerate(symbols):
                try:
                    if symbol in existing_symbols and not force_refresh:
                        logger.debug("Skipping existing contract", symbol=symbol)
                        self.collection_stats["already_cached"] += 1
                        continue
                    
                    logger.info("Processing contract details", 
                               symbol=symbol, progress=f"{i+1}/{len(symbols)}")
                    
                    # Get contract details from IBKR
                    contract_details = await self._request_contract_details(symbol)
                    
                    if contract_details:
                        # Store in database
                        await self._store_contract_details(symbol, contract_details)
                        successful_symbols.append(symbol)
                        self.collection_stats["successful"] += 1
                        logger.info("Contract details stored", symbol=symbol)
                    else:
                        failed_symbols.append(symbol)
                        self.collection_stats["failed"] += 1
                        logger.warning("Failed to get contract details", symbol=symbol)
                    
                    self.collection_stats["requested"] += 1
                    
                    # Rate limiting - be conservative with contract detail requests
                    if i < len(symbols) - 1:
                        await asyncio.sleep(2)  # 2 second delay between requests
                        
                except Exception as e:
                    logger.error("Error processing symbol", symbol=symbol, error=str(e))
                    failed_symbols.append(symbol)
                    self.collection_stats["failed"] += 1
            
            # Disconnect from IBKR
            self.ibkr_client.disconnect_from_tws()
            logger.info("Disconnected from IBKR TWS")
            
            # Summary
            total_processed = len(successful_symbols) + len(failed_symbols)
            success_rate = (len(successful_symbols) / total_processed * 100) if total_processed > 0 else 0
            
            logger.info("Contract details collection completed", 
                       successful=len(successful_symbols),
                       failed=len(failed_symbols),
                       already_cached=self.collection_stats["already_cached"],
                       success_rate=f"{success_rate:.1f}%")
            
            return {
                'success': True,
                'symbols_processed': total_processed,
                'successful_symbols': successful_symbols,
                'failed_symbols': failed_symbols,
                'already_cached': self.collection_stats["already_cached"],
                'collection_stats': self.collection_stats,
                'success_rate': success_rate
            }
            
        except Exception as e:
            logger.error("Contract details collection failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_existing_contract_symbols(self) -> set:
        """Get symbols that already have contract details in database"""
        async with AsyncSessionLocal() as db_session:
            try:
                from sqlalchemy import select
                
                result = await db_session.execute(
                    select(ContractDetail.symbol).distinct()
                )
                
                existing_symbols = set(row[0] for row in result)
                return existing_symbols
                
            except Exception as e:
                logger.error("Error getting existing contract symbols", error=str(e))
                return set()
    
    async def _request_contract_details(self, symbol: str) -> Optional[Dict]:
        """Request contract details from IBKR for a symbol"""
        try:
            # Create contract
            contract = create_asx_stock_contract(symbol)
            
            # Setup contract details callback
            contract_details_received = asyncio.Event()
            received_details = {}
            
            def contract_details_callback(contract_details):
                """Callback to receive contract details from IBKR"""
                try:
                    details = contract_details.contract
                    summary = contract_details.summary
                    
                    received_details.update({
                        'con_id': details.conId,
                        'symbol': details.symbol,
                        'sec_type': details.secType,
                        'currency': details.currency,
                        'exchange': details.exchange,
                        'primary_exchange': details.primaryExchange,
                        'local_symbol': details.localSymbol,
                        'trading_class': details.tradingClass,
                        'min_tick': summary.minTick if hasattr(summary, 'minTick') else None,
                        'market_rule_ids': str(summary.marketRuleIds) if hasattr(summary, 'marketRuleIds') else None,
                        'contract_month': details.contractMonth if hasattr(details, 'contractMonth') else None,
                        'last_trading_day': details.lastTradingDay if hasattr(details, 'lastTradingDay') else None,
                        'time_zone_id': summary.timeZoneId if hasattr(summary, 'timeZoneId') else None
                    })
                    
                    logger.debug("Contract details received", 
                               symbol=symbol, con_id=details.conId)
                    
                except Exception as e:
                    logger.error("Error in contract details callback", 
                               symbol=symbol, error=str(e))
            
            # Request contract details (the IBKR client handles the end callback internally)
            req_id = self.ibkr_client.request_contract_details(contract, contract_details_callback)
            
            if not req_id:
                logger.error("Failed to submit contract details request", symbol=symbol)
                return None
            
            # Wait for the request to complete by checking if it's still pending
            timeout = 30.0
            start_time = time.time()
            
            while req_id in self.ibkr_client.pending_requests and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
            
            if req_id in self.ibkr_client.pending_requests:
                logger.warning("Contract details request timed out", symbol=symbol)
                return None
            
            if received_details:
                return received_details
            else:
                logger.warning("No contract details received", symbol=symbol)
                return None
                
        except Exception as e:
            logger.error("Error requesting contract details", symbol=symbol, error=str(e))
            return None
    
    async def _store_contract_details(self, symbol: str, details: Dict) -> bool:
        """Store contract details in database"""
        async with AsyncSessionLocal() as db_session:
            try:
                # Create ContractDetail object
                contract_detail = ContractDetail(
                    symbol=details['symbol'],
                    con_id=details['con_id'],
                    sec_type=details['sec_type'],
                    currency=details['currency'],
                    exchange=details['exchange'],
                    primary_exchange=details['primary_exchange'],
                    local_symbol=details['local_symbol'],
                    trading_class=details['trading_class'],
                    min_tick=details['min_tick'],
                    market_rule_ids=details['market_rule_ids'],
                    contract_month=details['contract_month'],
                    last_trading_day=details['last_trading_day'],
                    time_zone_id=details['time_zone_id'],
                    updated_at=datetime.now()
                )
                
                # Use UPSERT to handle duplicates
                stmt = insert(ContractDetail).values(
                    symbol=details['symbol'],
                    con_id=details['con_id'],
                    sec_type=details['sec_type'],
                    currency=details['currency'],
                    exchange=details['exchange'],
                    primary_exchange=details['primary_exchange'],
                    local_symbol=details['local_symbol'],
                    trading_class=details['trading_class'],
                    min_tick=details['min_tick'],
                    market_rule_ids=details['market_rule_ids'],
                    contract_month=details['contract_month'],
                    last_trading_day=details['last_trading_day'],
                    time_zone_id=details['time_zone_id'],
                    updated_at=datetime.now()
                )
                
                # Update on conflict (if con_id already exists)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['con_id'],
                    set_={
                        'symbol': stmt.excluded.symbol,
                        'sec_type': stmt.excluded.sec_type,
                        'currency': stmt.excluded.currency,
                        'exchange': stmt.excluded.exchange,
                        'primary_exchange': stmt.excluded.primary_exchange,
                        'local_symbol': stmt.excluded.local_symbol,
                        'trading_class': stmt.excluded.trading_class,
                        'min_tick': stmt.excluded.min_tick,
                        'market_rule_ids': stmt.excluded.market_rule_ids,
                        'contract_month': stmt.excluded.contract_month,
                        'last_trading_day': stmt.excluded.last_trading_day,
                        'time_zone_id': stmt.excluded.time_zone_id,
                        'updated_at': stmt.excluded.updated_at
                    }
                )
                
                await db_session.execute(stmt)
                await db_session.commit()
                
                logger.debug("Contract details stored in database", 
                           symbol=symbol, con_id=details['con_id'])
                return True
                
            except Exception as e:
                await db_session.rollback()
                logger.error("Error storing contract details", 
                           symbol=symbol, error=str(e))
                return False


async def populate_liquid_stocks(force_refresh: bool = False):
    """Populate contract details for most liquid ASX stocks"""
    print("🚀 Populating Contract Details for Liquid ASX Stocks")
    print("=" * 60)
    
    collector = ContractDetailsCollector()
    
    # Start with top 20 liquid stocks for testing
    liquid_symbols = get_liquid_stocks(20)
    
    print(f"📊 Processing {len(liquid_symbols)} liquid stocks:")
    print(f"   Symbols: {', '.join(liquid_symbols)}")
    print(f"   Force refresh: {force_refresh}")
    print()
    
    result = await collector.populate_contract_details(liquid_symbols, force_refresh)
    
    if result['success']:
        print("✅ Contract details collection completed successfully!")
        print(f"   📈 Successful: {len(result['successful_symbols'])}")
        print(f"   ❌ Failed: {len(result['failed_symbols'])}")
        print(f"   📦 Already cached: {result['already_cached']}")
        print(f"   🎯 Success rate: {result['success_rate']:.1f}%")
        
        if result['successful_symbols']:
            print(f"\n✅ Successfully processed symbols:")
            for symbol in result['successful_symbols']:
                print(f"   - {symbol}")
        
        if result['failed_symbols']:
            print(f"\n❌ Failed symbols:")
            for symbol in result['failed_symbols']:
                print(f"   - {symbol}")
        
        return True
    else:
        print(f"❌ Contract details collection failed: {result.get('error', 'Unknown error')}")
        return False


async def populate_all_asx200(force_refresh: bool = False):
    """Populate contract details for all ASX200 stocks"""
    print("🚀 Populating Contract Details for All ASX200 Stocks")
    print("=" * 60)
    
    collector = ContractDetailsCollector()
    
    # Get all ASX200 symbols
    all_symbols = get_asx200_symbols()
    
    print(f"📊 Processing {len(all_symbols)} ASX200 stocks")
    print(f"   Force refresh: {force_refresh}")
    print("   ⚠️  This will take approximately {:.1f} minutes with rate limiting".format(len(all_symbols) * 2 / 60))
    print()
    
    # Confirm before proceeding
    confirm = input("Do you want to continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled.")
        return False
    
    result = await collector.populate_contract_details(all_symbols, force_refresh)
    
    if result['success']:
        print("✅ Contract details collection completed successfully!")
        print(f"   📈 Successful: {len(result['successful_symbols'])}")
        print(f"   ❌ Failed: {len(result['failed_symbols'])}")
        print(f"   📦 Already cached: {result['already_cached']}")
        print(f"   🎯 Success rate: {result['success_rate']:.1f}%")
        
        return True
    else:
        print(f"❌ Contract details collection failed: {result.get('error', 'Unknown error')}")
        return False


async def verify_contract_details():
    """Verify stored contract details"""
    print("🔍 Verifying Contract Details in Database")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db_session:
        try:
            from sqlalchemy import select, func
            
            # Get contract details count
            result = await db_session.execute(
                select(func.count(ContractDetail.id))
            )
            total_contracts = result.scalar()
            
            print(f"📊 Total contract details in database: {total_contracts}")
            
            if total_contracts > 0:
                # Get sample contract details
                result = await db_session.execute(
                    select(ContractDetail).limit(5)
                )
                sample_contracts = result.scalars().all()
                
                print("\n📋 Sample contract details:")
                for contract in sample_contracts:
                    print(f"   {contract.symbol}: ConID={contract.con_id}, Exchange={contract.exchange}")
                
                # Get symbols with contract details
                result = await db_session.execute(
                    select(ContractDetail.symbol).order_by(ContractDetail.symbol)
                )
                symbols_with_contracts = [row[0] for row in result]
                
                print(f"\n✅ Symbols with contract details ({len(symbols_with_contracts)}):")
                for i, symbol in enumerate(symbols_with_contracts):
                    if i % 10 == 0 and i > 0:
                        print()
                    print(f"{symbol:4}", end=" ")
                print("\n")
                
                return symbols_with_contracts
            else:
                print("❌ No contract details found in database")
                return []
                
        except Exception as e:
            logger.error("Error verifying contract details", error=str(e))
            print(f"❌ Error verifying contract details: {str(e)}")
            return []


def main():
    """Main function"""
    load_dotenv()
    
    print("📈 ASX200 Contract Details Population Tool")
    print("=" * 60)
    print()
    print("Options:")
    print("1. Populate liquid stocks (20 stocks, ~1 minute)")
    print("2. Populate all ASX200 (50 stocks, ~2 minutes)")  
    print("3. Verify existing contract details")
    print("4. Force refresh liquid stocks")
    print()
    
    try:
        choice = input("Select option (1-4): ").strip()
        
        if choice == "1":
            success = asyncio.run(populate_liquid_stocks(force_refresh=False))
        elif choice == "2":
            success = asyncio.run(populate_all_asx200(force_refresh=False))
        elif choice == "3":
            symbols = asyncio.run(verify_contract_details())
            success = len(symbols) > 0
        elif choice == "4":
            success = asyncio.run(populate_liquid_stocks(force_refresh=True))
        else:
            print("Invalid option selected.")
            return
        
        if success:
            print("\n🎉 Operation completed successfully!")
            print("\nNext steps:")
            print("1. Test data collection: python scripts/test_data_collection.py")
            print("2. Test backfill: POST /api/data/backfill/BHP")
            print("3. Validate data: POST /api/data/validate/BHP")
        else:
            print("\n⚠️  Operation completed with issues. Check logs for details.")
            
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")


if __name__ == "__main__":
    main()