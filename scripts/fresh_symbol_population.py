#!/usr/bin/env python3
"""
Fresh Symbol Population from TWS API
Clears existing symbols and populates with complete IBKR contract data
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol, SecurityType
from shared.ibkr.client import IBKRManager
from ibapi.contract import Contract, ContractDetails
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Symbol lists to populate from IBKR API (Testing with just CBA first)
TARGET_SYMBOLS = {
    "ASX": [
        "CBA"  # Test with just CBA first
    ],
    "NASDAQ": [
        # Disabled for testing
    ]
}


class SymbolContractFetcher:
    """Fetches contract details from IBKR API and stores in database."""
    
    def __init__(self):
        self.ibkr_manager = None
        self.contract_cache = {}
        self.request_delay = 2.0  # Reduced delay between API requests
        self.connection_retries = 3
        self.client_id_counter = 1  # Track client IDs to ensure uniqueness
        
    async def connect_ibkr(self):
        """Connect to IBKR API with retries."""
        for attempt in range(self.connection_retries):
            try:
                logger.info(f"🔌 Connecting to IBKR API (attempt {attempt + 1}/{self.connection_retries})...")
                # Use unique client ID for each connection attempt
                self.client_id_counter += 1
                self.ibkr_manager = IBKRManager(port=4002, client_id=self.client_id_counter)
                
                success = await self.ibkr_manager.connect()
                if not success:
                    raise Exception("Failed to connect to IBKR API")
                
                # Give the connection time to stabilize
                await asyncio.sleep(3)
                
                logger.info("✅ Connected to IBKR API")
                return True
                
            except Exception as e:
                logger.error(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if self.ibkr_manager:
                    try:
                        await self.ibkr_manager.disconnect()
                        # Wait longer for connection to fully close
                        await asyncio.sleep(5)
                    except:
                        pass
                    self.ibkr_manager = None
                
                if attempt < self.connection_retries - 1:
                    wait_time = (attempt + 1) * 5  # Increasing wait time
                    logger.info(f"⏰ Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("❌ All connection attempts failed")
                    return False
        
        return False
    
    def create_stock_contract(self, symbol: str, exchange: str, currency: str) -> Contract:
        """Create a stock contract for IBKR API."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"  # Use SMART routing
        contract.currency = currency
        
        # Set primary exchange based on the exchange parameter
        if exchange == "ASX":
            contract.primaryExchange = "ASX"
        elif exchange == "NASDAQ":
            contract.primaryExchange = "NASDAQ"
        else:
            contract.primaryExchange = exchange
            
        return contract
    
    async def fetch_contract_details(self, symbol: str, exchange: str, currency: str) -> Optional[ContractDetails]:
        """Fetch contract details from IBKR API with fresh connection approach."""
        max_retries = 2  # Reduced retries since we're using fresh connections
        
        for attempt in range(max_retries):
            # Use a completely fresh connection for each symbol to avoid socket timeouts
            fresh_manager = None
            try:
                logger.info(f"📡 Fetching contract details for {symbol} ({exchange}) - attempt {attempt + 1}")
                
                # Create fresh connection for this request
                self.client_id_counter += 1
                fresh_manager = IBKRManager(port=4002, client_id=self.client_id_counter)
                
                logger.info(f"🔌 Creating fresh connection (client ID {self.client_id_counter}) for {symbol}")
                success = await fresh_manager.connect()
                if not success:
                    logger.error(f"❌ Fresh connection failed for {symbol}")
                    continue
                
                # Give connection time to stabilize
                await asyncio.sleep(2)
                
                # Create contract
                contract = self.create_stock_contract(symbol, exchange, currency)
                
                # Request contract details with fresh connection
                try:
                    contract_details = await asyncio.wait_for(
                        fresh_manager.get_contract_details(contract), 
                        timeout=30.0  # Shorter timeout with fresh connection
                    )
                    
                    if contract_details:
                        logger.info(f"✅ Retrieved details for {symbol} with fresh connection")
                        return contract_details[0]  # Return first match
                    else:
                        logger.warning(f"⚠️ No contract details found for {symbol}")
                        continue
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Fresh connection timeout for {symbol}")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Error with fresh connection for {symbol} (attempt {attempt + 1}): {e}")
                continue
            finally:
                # Always disconnect the fresh connection
                if fresh_manager:
                    try:
                        await fresh_manager.disconnect()
                        await asyncio.sleep(1)  # Brief pause between connections
                    except:
                        pass
        
        # If all attempts failed, return None (no static data)
        logger.error(f"❌ All attempts failed for {symbol} - no live data available")
        return None
    
    async def ensure_connection(self) -> bool:
        """Ensure IBKR connection is active, reconnect if needed."""
        try:
            if self.ibkr_manager is None:
                logger.info("🔄 IBKR manager not initialized, connecting...")
                return await self.connect_ibkr()
            
            # Don't check connection immediately after API requests - give it time
            # The connection might be briefly unavailable during processing
            return True  # Trust the connection for now
            
        except Exception as e:
            logger.error(f"❌ Connection check failed: {e}")
            return False
    
    def extract_symbol_data(self, symbol: str, exchange: str, currency: str, 
                          contract_details: Optional[ContractDetails]) -> Dict:
        """Extract comprehensive symbol data from contract details."""
        
        # Base data (always present)
        symbol_data = {
            "symbol": symbol,
            "exchange": exchange,
            "currency": currency,
            "security_type": SecurityType.STOCK,
            "active": True,
            "tradeable": True,
            "market_data_available": True,
            "last_verified": datetime.now(timezone.utc).replace(tzinfo=None)  # Remove timezone info for DB
        }
        
        if not contract_details:
            # Return None if no contract details - don't add static data
            logger.warning(f"⚠️ No live contract details available for {symbol} - skipping")
            return None
        
        # Extract from contract details
        contract = contract_details.contract
        details = contract_details
        
        # Basic contract info
        symbol_data.update({
            "contract_id": contract.conId,
            "local_symbol": contract.localSymbol,
            "trading_class": contract.tradingClass,
            "multiplier": contract.multiplier,
            "primary_exchange": contract.primaryExchange,
        })
        
        # Company information
        if hasattr(details, 'longName') and details.longName:
            symbol_data["company_name"] = details.longName
            symbol_data["long_name"] = details.longName
        else:
            symbol_data["company_name"] = f"{symbol} Corp"
        
        # Market information
        if hasattr(details, 'timeZoneId'):
            symbol_data["timezone_id"] = details.timeZoneId
        if hasattr(details, 'tradingHours'):
            symbol_data["trading_hours"] = details.tradingHours
        if hasattr(details, 'liquidHours'):
            symbol_data["liquid_hours"] = details.liquidHours
        
        # Trading details
        if hasattr(details, 'minTick'):
            symbol_data["min_tick"] = float(details.minTick)
        if hasattr(details, 'priceMagnifier'):
            symbol_data["price_magnifier"] = details.priceMagnifier
        if hasattr(details, 'orderTypes'):
            symbol_data["order_types"] = details.orderTypes
        if hasattr(details, 'validExchanges'):
            symbol_data["valid_exchanges"] = details.validExchanges
        
        # Additional identifiers
        if hasattr(details, 'cusip'):
            symbol_data["cusip"] = details.cusip
        if hasattr(details, 'isin'):
            symbol_data["isin"] = details.isin
        
        # Market name mapping
        if exchange == "ASX":
            symbol_data["market_name"] = "Australian Securities Exchange"
            symbol_data["sector"] = self._guess_asx_sector(symbol)
        elif exchange == "NASDAQ":
            symbol_data["market_name"] = "NASDAQ Stock Market"
            symbol_data["sector"] = self._guess_nasdaq_sector(symbol)
        
        return symbol_data
    
    def _guess_asx_sector(self, symbol: str) -> str:
        """Guess ASX sector based on symbol (fallback)."""
        # Major bank symbols
        if symbol in ["CBA", "ANZ", "WBC", "NAB", "MQG"]:
            return "Financials"
        # Mining companies
        elif symbol in ["BHP", "RIO", "FMG", "NCM", "MIN"]:
            return "Materials"
        # Healthcare
        elif symbol in ["CSL", "COH", "RMD", "SHL"]:
            return "Health Care"
        # Technology
        elif symbol in ["XRO", "WTC", "CPU", "ALU"]:
            return "Technology"
        # Energy
        elif symbol in ["WDS", "STO", "ORG", "AGL"]:
            return "Energy"
        # Retail/Consumer
        elif symbol in ["WOW", "COL", "WES", "HVN"]:
            return "Consumer Staples"
        else:
            return "Unknown"
    
    def _guess_nasdaq_sector(self, symbol: str) -> str:
        """Guess NASDAQ sector based on symbol (fallback)."""
        # Tech giants
        if symbol in ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "NVDA", "ADBE", "ORCL", "INTC", "AMD"]:
            return "Technology"
        # E-commerce/Consumer
        elif symbol in ["AMZN", "TSLA", "EBAY", "COST", "SBUX"]:
            return "Consumer Discretionary"
        # Healthcare/Biotech
        elif symbol in ["GILD", "AMGN", "BIIB", "REGN", "VRTX", "MRNA"]:
            return "Health Care"
        # Communication/Media
        elif symbol in ["NFLX", "ROKU", "SPOT", "SNAP"]:
            return "Communication Services"
        # Fintech
        elif symbol in ["PYPL", "SQ", "FISV"]:
            return "Financials"
        else:
            return "Technology"  # Default for NASDAQ
    
    async def disconnect_ibkr(self):
        """Disconnect from IBKR API."""
        if self.ibkr_manager:
            await self.ibkr_manager.disconnect()
            logger.info("🔌 Disconnected from IBKR API")
    
    async def reconnect_ibkr(self):
        """Reconnect to IBKR API after connection issues."""
        logger.info("🔄 Reconnecting to IBKR API...")
        try:
            if self.ibkr_manager:
                await self.ibkr_manager.disconnect()
                await asyncio.sleep(2)  # Wait for clean disconnect
        except:
            pass
        
        self.ibkr_manager = None
        return await self.connect_ibkr()


async def clear_symbols_table():
    """Clear existing symbols from the table."""
    logger.info("🗑️  Clearing existing symbols table...")
    
    async with AsyncSessionLocal() as session:
        # Get count before deletion
        count_result = await session.execute(text("SELECT COUNT(*) FROM symbols"))
        existing_count = count_result.scalar()
        logger.info(f"📊 Found {existing_count} existing symbols")
        
        if existing_count > 0:
            # Clear the table
            await session.execute(text("DELETE FROM symbols"))
            await session.commit()
            logger.info(f"✅ Cleared {existing_count} symbols from table")
        else:
            logger.info("📊 Symbols table already empty")


async def populate_symbols_from_api():
    """Populate symbols with fresh data from IBKR API."""
    
    logger.info("🚀 Starting fresh symbol population from IBKR API...")
    
    # Initialize database
    await init_db()
    
    # Clear existing symbols
    await clear_symbols_table()
    
    # Initialize contract fetcher (no persistent connection needed)
    fetcher = SymbolContractFetcher()
    
    try:
        total_added = 0
        total_failed = 0
        
        async with AsyncSessionLocal() as session:
            
            # Process ASX symbols
            logger.info("📈 Processing ASX symbols...")
            asx_symbols = TARGET_SYMBOLS["ASX"]
            
            for symbol in asx_symbols:
                try:
                    logger.info(f"� Processing symbol: {symbol}")
                    
                    # Fetch contract details with fresh connection for each symbol
                    contract_details = await fetcher.fetch_contract_details(
                        symbol, "ASX", "AUD"
                    )
                    
                    # Only proceed if we got actual contract details
                    if not contract_details:
                        logger.warning(f"⚠️ Skipping {symbol} - no live contract details")
                        total_failed += 1
                        continue
                    
                    # Extract symbol data
                    symbol_data = fetcher.extract_symbol_data(
                        symbol, "ASX", "AUD", contract_details
                    )
                    
                    # Only add if we have real data
                    if symbol_data:
                        new_symbol = Symbol(**symbol_data)
                        session.add(new_symbol)
                        total_added += 1
                        logger.info(f"✨ Added ASX: {symbol} - {symbol_data.get('company_name', symbol)}")
                        
                        # Commit immediately for each successful symbol
                        await session.commit()
                        logger.info(f"💾 Committed {symbol} to database")
                    else:
                        logger.warning(f"⚠️ Skipping {symbol} - failed to extract symbol data")
                        total_failed += 1
                    
                except Exception as e:
                    logger.error(f"❌ Failed to add ASX symbol {symbol}: {e}")
                    total_failed += 1
                    # Rollback and continue
                    await session.rollback()
            
            # Final verification
            final_count_result = await session.execute(text("SELECT COUNT(*) FROM symbols"))
            final_count = final_count_result.scalar()
            
            return {
                "asx_symbols": len(TARGET_SYMBOLS["ASX"]),
                "nasdaq_symbols": len(TARGET_SYMBOLS["NASDAQ"]),
                "total_attempted": len(TARGET_SYMBOLS["ASX"]) + len(TARGET_SYMBOLS["NASDAQ"]),
                "successfully_added": total_added,
                "failed": total_failed,
                "final_count": final_count
            }
            
    except Exception as e:
        logger.error(f"❌ Population failed: {e}")
        raise


async def main():
    """Main execution function."""
    try:
        result = await populate_symbols_from_api()
        
        print("\n" + "="*70)
        print("🎯 FRESH SYMBOL POPULATION FROM IBKR API COMPLETE")
        print("="*70)
        print(f"📊 ASX Symbols Attempted: {result['asx_symbols']}")
        print(f"💻 NASDAQ Symbols Attempted: {result['nasdaq_symbols']}")
        print(f"🌎 Total Symbols Attempted: {result['total_attempted']}")
        print(f"✅ Successfully Added: {result['successfully_added']}")
        print(f"❌ Failed: {result['failed']}")
        print(f"💾 Final Database Count: {result['final_count']}")
        print("="*70)
        
        if result['successfully_added'] > 0:
            print("✅ Symbol database populated with IBKR contract details!")
            print("🚀 Ready for comprehensive data collection!")
        else:
            print("⚠️  No symbols were successfully added. Check IBKR connection.")
        
    except Exception as e:
        logger.error(f"❌ Failed to populate symbols: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
