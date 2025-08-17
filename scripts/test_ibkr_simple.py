#!/usr/bin/env python3
"""
Simple IB Gateway connection test - just check if port is accessible
"""
import sys
import os
import socket
import time
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.config.settings import settings

def test_port_connection():
    """Test if IB Gateway port is accessible"""
    load_dotenv()
    
    print("🚀 Simple IB Gateway Port Test")
    print("=" * 40)
    
    host = settings.ibkr_host
    port = settings.ibkr_port
    
    print(f"Testing connection to {host}:{port}")
    print("(This should be IB Gateway paper trading port)")
    
    try:
        # Create a socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        
        # Try to connect
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✅ Port is accessible!")
            print("✅ IB Gateway appears to be running")
            return True
        else:
            print("❌ Port is not accessible")
            print("❌ IB Gateway may not be running or API is disabled")
            return False
            
    except socket.timeout:
        print("❌ Connection timed out")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def check_environment():
    """Check environment configuration"""
    print("\n📋 Environment Check")
    print("-" * 20)
    
    print(f"IBKR_HOST: {settings.ibkr_host}")
    print(f"IBKR_PORT: {settings.ibkr_port}")
    print(f"IBKR_CLIENT_ID: {settings.ibkr_client_id}")
    print(f"IBKR_PAPER_TRADING: {settings.ibkr_paper_trading}")
    print(f"TESTING mode: {settings.testing}")
    
    # Verify correct port for paper trading
    if settings.ibkr_paper_trading and settings.ibkr_port != 4002:
        print("⚠️ WARNING: Paper trading should use port 4002")
    
    if not settings.ibkr_paper_trading and settings.ibkr_port != 4001:
        print("⚠️ WARNING: Live trading should use port 4001")

def main():
    """Main test function"""
    print("🔍 IB Gateway Simple Connectivity Test\n")
    
    # Check environment
    check_environment()
    
    # Test port connectivity
    success = test_port_connection()
    
    print("\n" + "=" * 40)
    
    if success:
        print("🎉 Basic connectivity test PASSED!")
        print("\nThis means:")
        print("✅ IB Gateway is running")
        print("✅ Port is accessible")
        print("✅ Ready for API connection attempts")
        
        print("\nNext steps:")
        print("1. Try the full IBKR API connection test")
        print("2. Verify API settings in IB Gateway:")
        print("   - Enable 'ActiveX and Socket Clients'")
        print("   - Check 'Read-Only API' is disabled")
        print("   - Verify trusted IPs if needed")
        
        return True
    else:
        print("💥 Basic connectivity test FAILED!")
        print("\nTroubleshooting:")
        print("1. Start IB Gateway and log in")
        print("2. In IB Gateway, go to Configure → Settings → API")
        print("3. Enable 'ActiveX and Socket Clients'")
        print("4. Set Socket port to 4002 (paper trading)")
        print("5. Ensure 'Read-Only API' is unchecked")
        
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        sys.exit(1)