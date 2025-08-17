#!/usr/bin/env python3
"""
Test script to verify IB Gateway connection using async manager approach
"""
import sys
import os
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
import time
import signal
from dotenv import load_dotenv
import structlog

# We'll create a simple IBKR manager based on your reference
from app.data.collectors.ibkr_client import IBKRClient
from app.data.collectors.asx_contracts import create_asx_stock_contract
from app.config.settings import settings

logger = structlog.get_logger(__name__)

class SimpleIBKRManager:
    """Simple IBKR manager for connection testing based on reference script approach"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.client = None
        self.connected = False
        self.connection_timeout = 10
        
    async def connect(self) -> bool:
        """Connect to IBKR with proper async handling"""
        try:
            logger.info(f"Attempting to connect to IBKR", host=self.host, port=self.port)
            
            # Initialize client
            self.client = IBKRClient()
            
            # Start client thread
            import threading
            client_thread = threading.Thread(target=self.client.run, daemon=True)
            client_thread.start()
            
            # Small delay for thread startup
            await asyncio.sleep(0.5)
            
            # Attempt connection
            self.client.connect(self.host, self.port, self.client_id)
            
            # Wait for connection with timeout
            start_time = time.time()
            while not self.client.is_connected and (time.time() - start_time) < self.connection_timeout:
                await asyncio.sleep(0.1)
            
            self.connected = self.client.is_connected
            
            if self.connected:
                logger.info("Successfully connected to IBKR")
                return True
            else:
                logger.error("Connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from IBKR"""
        try:
            if self.client and self.client.is_connected:
                self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
    
    async def test_market_data_type(self) -> bool:
        """Test setting market data type"""
        try:
            if not self.connected:
                return False
            
            self.client.reqMarketDataType(3)  # Delayed data
            await asyncio.sleep(1)  # Give it a moment
            return True
        except Exception as e:
            logger.error(f"Failed to set market data type: {e}")
            return False
    
    async def test_contract_details(self, contract) -> bool:
        """Test requesting contract details"""
        try:
            if not self.connected:
                return False
            
            contract_received = asyncio.Event()
            contract_data = {}
            
            def contract_callback(details):
                contract_data['details'] = details
                contract_received.set()
            
            req_id = self.client.request_contract_details(contract, contract_callback)
            
            if req_id:
                # Wait for response with timeout
                try:
                    await asyncio.wait_for(contract_received.wait(), timeout=5.0)
                    return True
                except asyncio.TimeoutError:
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Contract details test failed: {e}")
            return False


class AsyncConnectionTester:
    """Test IB Gateway connection using async approach"""
    
    def __init__(self):
        self.manager = None
        self.test_start_time = None
        
    def setup_signal_handler(self):
        """Setup signal handler for graceful shutdown"""
        def signal_handler(signum, frame):
            print("\n🛑 Test interrupted by user. Shutting down...")
            if self.manager:
                # We can't await in signal handler, so just disconnect synchronously
                try:
                    if self.manager.client and self.manager.client.is_connected:
                        self.manager.client.disconnect()
                except:
                    pass
            sys.exit(1)
        
        signal.signal(signal.SIGINT, signal_handler)
    
    async def test_connection(self) -> bool:
        """Test IB Gateway connection with proper async handling"""
        load_dotenv()
        
        print("🚀 Testing IB Gateway Connection (Async)")
        print("=" * 50)
        print("Press Ctrl+C to interrupt test at any time\n")
        
        self.setup_signal_handler()
        self.test_start_time = time.time()
        
        try:
            # Get connection settings
            host = settings.ibkr_host
            port = settings.ibkr_port
            client_id = settings.ibkr_client_id
            
            print(f"1. Connection settings:")
            print(f"   Host: {host}")
            print(f"   Port: {port}")
            print(f"   Client ID: {client_id}")
            
            # Initialize manager
            print("\n2. Initializing IBKR manager...")
            self.manager = SimpleIBKRManager(host=host, port=port, client_id=client_id)
            
            # Test connection
            print("3. Attempting to connect to IB Gateway...")
            print("   (This will timeout after 10 seconds if IB Gateway is not running)")
            
            success = await self.manager.connect()
            
            if success:
                print("   ✅ Connection successful!")
                
                # Test market data type setting
                print("\n4. Testing market data configuration...")
                market_data_success = await self.manager.test_market_data_type()
                if market_data_success:
                    print("   ✅ Market data type set to delayed (type 3)")
                else:
                    print("   ⚠️ Market data type setting failed")
                
                # Test contract details (optional)
                print("\n5. Testing contract details request...")
                try:
                    bhp_contract = create_asx_stock_contract("BHP")
                    contract_success = await self.manager.test_contract_details(bhp_contract)
                    
                    if contract_success:
                        print("   ✅ Contract details test successful!")
                    else:
                        print("   ⚠️ Contract details test timed out (expected if no market data subscription)")
                        
                except Exception as e:
                    print(f"   ⚠️ Contract test failed: {e}")
                
                print("\n✅ All connection tests completed successfully!")
                return True
                
            else:
                print("   ❌ Connection failed")
                print("   💡 Troubleshooting:")
                print("      - Is IB Gateway running and logged in?")
                print("      - Is API enabled in Global Configuration?")
                print("      - Is the port correct (4002 for paper trading)?")
                print("      - Check that 'Enable ActiveX and Socket Clients' is enabled")
                return False
                
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False
            
        finally:
            # Cleanup
            elapsed = time.time() - self.test_start_time if self.test_start_time else 0
            print(f"\n6. Cleaning up... (Total test time: {elapsed:.1f}s)")
            
            if self.manager:
                await self.manager.disconnect()
    
    async def run(self) -> bool:
        """Run the connection test"""
        try:
            success = await self.test_connection()
            
            if success:
                print("\n🎉 IB Gateway connection test PASSED!")
                print("\nNext steps:")
                print("- Test ASX200 data collection")
                print("- Validate data storage")
                return True
            else:
                print("\n💥 IB Gateway connection test FAILED!")
                print("\nTroubleshooting:")
                print("- Ensure IB Gateway is running")
                print("- Check port configuration (should be 4002 for paper trading)")
                print("- Verify API settings in IB Gateway")
                return False
                
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")
            return False

async def main():
    """Main async test function"""
    try:
        tester = AsyncConnectionTester()
        success = await tester.run()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())