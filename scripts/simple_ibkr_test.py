#!/usr/bin/env python3
"""
Simple test to debug IBKR connection state
"""

import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.ibkr.client import IBKRManager
from ibapi.contract import Contract

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Use DEBUG for more details
logger = logging.getLogger(__name__)


async def simple_connection_test():
    """Simple test of IBKR connection state."""
    
    logger.info("🚀 Starting simple IBKR connection test...")
    
    # Create IBKR manager
    ibkr_manager = IBKRManager(port=4002, client_id=4)
    
    try:
        logger.info("🔌 Connecting to IBKR API...")
        success = await ibkr_manager.connect()
        
        if not success:
            logger.error("❌ Failed to connect")
            return
        
        logger.info("✅ Connect method returned success")
        
        # Check connection state details
        logger.info(f"🔍 _is_connected: {ibkr_manager._is_connected}")
        logger.info(f"🔍 wrapper.connected: {ibkr_manager.wrapper.connected}")
        logger.info(f"🔍 wrapper.connection_ready: {ibkr_manager.wrapper.connection_ready}")
        logger.info(f"🔍 is_connected(): {ibkr_manager.is_connected()}")
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Check again
        logger.info("--- After 2 second wait ---")
        logger.info(f"🔍 _is_connected: {ibkr_manager._is_connected}")
        logger.info(f"🔍 wrapper.connected: {ibkr_manager.wrapper.connected}")
        logger.info(f"🔍 wrapper.connection_ready: {ibkr_manager.wrapper.connection_ready}")
        logger.info(f"🔍 is_connected(): {ibkr_manager.is_connected()}")
        
        if ibkr_manager.is_connected():
            logger.info("📡 Connection looks good, testing contract details request...")
            
            # Create simple contract
            contract = Contract()
            contract.symbol = "CBA"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "AUD"
            contract.primaryExchange = "ASX"
            
            # Check connection immediately before request
            logger.info(f"🔍 Pre-request is_connected(): {ibkr_manager.is_connected()}")
            
            try:
                contract_details = await ibkr_manager.get_contract_details(contract)
                logger.info(f"📊 Contract details result: {len(contract_details) if contract_details else 'None'}")
            except Exception as e:
                logger.error(f"❌ Contract details request failed: {e}")
            
            # Check connection after request
            logger.info(f"🔍 Post-request is_connected(): {ibkr_manager.is_connected()}")
            
        else:
            logger.error("❌ Connection check failed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await ibkr_manager.disconnect()
            logger.info("🔌 Disconnected")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(simple_connection_test())
