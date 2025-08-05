#!/usr/bin/env python3
"""
SCIZOR Project Setup and Testing Script

This script helps you set up and test the SCIZOR trading system.
"""

import asyncio
import subprocess
import sys
import os
import time
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def print_banner():
    """Print the SCIZOR banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                          SCIZOR                              ║
    ║              Algorithmic Trading System                      ║
    ║                                                              ║
    ║  🔄 Data Farmer    - Market Data Collection                  ║
    ║  📊 Backtester     - Strategy Testing                       ║
    ║  ⚡ Algo Trader    - Live Trading Execution                  ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "asyncpg", 
        "pydantic", "redis", "pandas", "numpy", "ibapi"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed!")
    return True


def check_services():
    """Check if external services are available."""
    print("\n🔍 Checking external services...")
    
    # Check PostgreSQL
    try:
        import asyncpg
        print("  📊 PostgreSQL driver available")
    except ImportError:
        print("  ❌ PostgreSQL driver not available")
        return False
    
    # Check Redis
    try:
        import redis
        print("  🔄 Redis client available")
    except ImportError:
        print("  ❌ Redis client not available")
        return False
    
    print("✅ External service clients are available!")
    return True


def create_env_file():
    """Create a sample .env file if it doesn't exist."""
    env_file = PROJECT_ROOT / ".env"
    
    if env_file.exists():
        print("📝 .env file already exists")
        return
    
    print("📝 Creating sample .env file...")
    
    env_content = """# SCIZOR Configuration

# Database
DATABASE_URL=postgresql+asyncpg://scizor:scizor123@localhost:5432/scizor

# Redis
REDIS_URL=redis://localhost:6379/0

# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Service Ports
DATA_FARMER_PORT=8001
BACKTESTER_PORT=8002
ALGO_TRADER_PORT=8003

# Development
DEBUG=true
LOG_LEVEL=INFO

# Trading Configuration
ENABLE_PAPER_TRADING=true
MAX_DAILY_LOSS=1000.0
MAX_POSITION_SIZE=10000.0
"""
    
    with open(env_file, "w") as f:
        f.write(env_content)
    
    print("✅ Created .env file with default configuration")


def run_database_setup():
    """Set up the database using Docker Compose."""
    print("\n🐳 Setting up database with Docker Compose...")
    
    try:
        # Check if docker-compose.yml exists
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        if not compose_file.exists():
            print("❌ docker-compose.yml not found")
            return False
            
        # Start PostgreSQL and Redis
        subprocess.run([
            "docker-compose", "up", "-d", "postgres", "redis"
        ], check=True, cwd=PROJECT_ROOT)
        
        print("✅ Database services started")
        print("⏳ Waiting for services to be ready...")
        time.sleep(10)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start database services: {e}")
        return False
    except FileNotFoundError:
        print("❌ docker-compose command not found. Please install Docker Compose.")
        return False


def run_service(service_name, port):
    """Run a specific service."""
    print(f"\n🚀 Starting {service_name} service on port {port}...")
    
    service_path = PROJECT_ROOT / "services" / service_name
    main_file = service_path / "main.py"
    
    if not main_file.exists():
        print(f"❌ {main_file} not found")
        return None
    
    try:
        # Use uvicorn to run the service
        cmd = [
            sys.executable, "-m", "uvicorn", 
            f"services.{service_name}.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"✅ {service_name} started with PID {process.pid}")
        print(f"🌐 API available at: http://localhost:{port}")
        
        return process
        
    except Exception as e:
        print(f"❌ Failed to start {service_name}: {e}")
        return None


def test_api_endpoints():
    """Test API endpoints of all services."""
    print("\n🧪 Testing API endpoints...")
    
    import requests
    
    services = [
        ("Data Farmer", "http://localhost:8001/health"),
        ("Backtester", "http://localhost:8002/health"),
        ("Algo Trader", "http://localhost:8003/health")
    ]
    
    for service_name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"  ✅ {service_name} API is responding")
            else:
                print(f"  ❌ {service_name} API returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {service_name} API is not responding: {e}")


def main():
    """Main setup and testing function."""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check services
    if not check_services():
        sys.exit(1)
    
    # Create .env file
    create_env_file()
    
    print("\n" + "="*60)
    print("SETUP OPTIONS:")
    print("1. Setup database services (Docker)")
    print("2. Run all microservices")
    print("3. Test API endpoints")
    print("4. Full setup and test")
    print("0. Exit")
    print("="*60)
    
    choice = input("\nSelect an option (0-4): ").strip()
    
    if choice == "1":
        run_database_setup()
        
    elif choice == "2":
        print("\n🚀 Starting all microservices...")
        
        processes = []
        services = [
            ("data-farmer", 8001),
            ("backtester", 8002),
            ("algo-trader", 8003)
        ]
        
        for service_name, port in services:
            process = run_service(service_name, port)
            if process:
                processes.append((service_name, process))
            time.sleep(3)  # Wait between service starts
        
        if processes:
            print(f"\n✅ Started {len(processes)} services")
            print("\nPress Ctrl+C to stop all services...")
            
            try:
                # Wait for user to stop
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping all services...")
                for service_name, process in processes:
                    process.terminate()
                    print(f"  Stopped {service_name}")
                    
    elif choice == "3":
        test_api_endpoints()
        
    elif choice == "4":
        print("\n🎯 Running full setup and test...")
        
        # Setup database
        if run_database_setup():
            print("✅ Database setup complete")
            
            # Start services
            print("\n🚀 Starting services...")
            processes = []
            services = [
                ("data-farmer", 8001),
                ("backtester", 8002),
                ("algo-trader", 8003)
            ]
            
            for service_name, port in services:
                process = run_service(service_name, port)
                if process:
                    processes.append((service_name, process))
                time.sleep(5)  # Wait between service starts
            
            # Wait for services to be ready
            print("\n⏳ Waiting for services to be ready...")
            time.sleep(10)
            
            # Test endpoints
            test_api_endpoints()
            
            print("\n🎉 SCIZOR setup complete!")
            print("\nDocumentation:")
            print("  📖 Data Farmer API: http://localhost:8001/docs")
            print("  📖 Backtester API: http://localhost:8002/docs")
            print("  📖 Algo Trader API: http://localhost:8003/docs")
            
            print("\nPress Ctrl+C to stop all services...")
            
            try:
                # Wait for user to stop
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping all services...")
                for service_name, process in processes:
                    process.terminate()
                    print(f"  Stopped {service_name}")
        
    elif choice == "0":
        print("👋 Goodbye!")
        
    else:
        print("❌ Invalid option")


if __name__ == "__main__":
    main()
