#!/usr/bin/env python3
"""
Test script to fetch just CBA contract details from IBKR
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_cba_contract():
    """Test fetching CBA contract details only."""
    
    logger.info("🚀 Testing CBA contract details from IBKR API...")
    
    # Initialize IBKR manager
    ibkr_manager = IBKRManager(port=4002, client_id=3)
    
    try:
        # Connect to IBKR
        logger.info("🔌 Connecting to IBKR API...")
        success = await ibkr_manager.connect()
        if not success:
            logger.error("❌ Failed to connect to IBKR API")
            return
        
        logger.info("✅ Connected to IBKR API")
        
        # Wait a bit for connection to stabilize
        await asyncio.sleep(3)
        
        # Create CBA contract
        contract = Contract()
        contract.symbol = "CBA"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "AUD"
        contract.primaryExchange = "ASX"
        
        logger.info("📡 Requesting CBA contract details...")
        
        # Test the connection check first
        is_connected = ibkr_manager.is_connected()
        logger.info(f"🔍 Connection status check: {is_connected}")
        
        # Request contract details
        contract_details = await ibkr_manager.get_contract_details(contract)
        
        if contract_details:
            logger.info(f"✅ Successfully received {len(contract_details)} contract details for CBA")
            for i, detail in enumerate(contract_details):
                logger.info(f"📊 Detail {i+1}: {detail.contract.symbol} - Contract ID: {detail.contract.conId}")
                if hasattr(detail, 'longName') and detail.longName:
                    logger.info(f"📊 Company: {detail.longName}")
        else:
            logger.warning("⚠️ No contract details received for CBA")
        
        # Test connection status again
        is_connected_after = ibkr_manager.is_connected()
        logger.info(f"🔍 Connection status after request: {is_connected_after}")
        
    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        try:
            await ibkr_manager.disconnect()
            logger.info("🔌 Disconnected from IBKR API")
        except:
            pass


async def main():
    """Main execution function."""
    try:
        await test_cba_contract()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
