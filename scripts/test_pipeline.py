#!/usr/bin/env python3
"""
Test script to validate the complete data collection pipeline
"""
import sys
import os
import asyncio
import time
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

import requests
import structlog
from dotenv import load_dotenv

from app.config.settings import settings
from app.data.collectors.market_data import MarketDataCollector
from app.data.collectors.asx_contracts import get_liquid_stocks

logger = structlog.get_logger(__name__)


class PipelineTester:
    """Complete pipeline testing suite"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.test_results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "failures": []
        }
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and track results"""
        print(f"\n🧪 Running: {test_name}")
        self.test_results["tests_run"] += 1
        
        try:
            result = test_func()
            if result:
                print(f"   ✅ PASSED: {test_name}")
                self.test_results["tests_passed"] += 1
                return True
            else:
                print(f"   ❌ FAILED: {test_name}")
                self.test_results["tests_failed"] += 1
                self.test_results["failures"].append(test_name)
                return False
        except Exception as e:
            print(f"   💥 ERROR: {test_name} - {str(e)}")
            self.test_results["tests_failed"] += 1
            self.test_results["failures"].append(f"{test_name} ({str(e)})")
            return False
    
    def test_api_health(self) -> bool:
        """Test API health endpoints"""
        try:
            # Basic health check
            response = requests.get(f"{self.api_base}/health/", timeout=10)
            if response.status_code != 200:
                return False
            
            health_data = response.json()
            if health_data["status"] != "healthy":
                return False
            
            # Detailed health check
            response = requests.get(f"{self.api_base}/health/detailed", timeout=10)
            if response.status_code != 200:
                return False
            
            print(f"   📊 API Health: {health_data['status']}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"   🔌 API not accessible: {e}")
            return False
    
    def test_data_endpoints(self) -> bool:
        """Test data collection API endpoints"""
        try:
            # Test symbols endpoint
            response = requests.get(f"{self.api_base}/api/data/symbols", timeout=10)
            if response.status_code != 200:
                return False
            
            symbols_data = response.json()
            if len(symbols_data["asx200_symbols"]) == 0:
                return False
            
            print(f"   📈 Available symbols: {len(symbols_data['asx200_symbols'])}")
            
            # Test collection history endpoint
            response = requests.get(f"{self.api_base}/api/data/history?days=1", timeout=10)
            if response.status_code != 200:
                return False
            
            return True
            
        except Exception as e:
            print(f"   📊 Data endpoints error: {e}")
            return False
    
    def test_async_data_collector(self) -> bool:
        """Test the async data collector directly"""
        try:
            result = asyncio.run(self._async_test_collector())
            return result
        except Exception as e:
            print(f"   🔄 Async collector error: {e}")
            return False
    
    async def _async_test_collector(self) -> bool:
        """Async helper for data collector test"""
        try:
            collector = MarketDataCollector()
            
            # Test connection
            connected = await collector.start_collection()
            if not connected:
                print("   🔌 Failed to connect to IBKR")
                return False
            
            print("   ✅ IBKR connection established")
            
            # Test stats
            stats = collector.get_collection_stats()
            print(f"   📊 Connection stats: {stats['connection_status']['connected']}")
            
            # Test sample subscription (just 1 symbol for quick test)
            test_symbols = get_liquid_stocks(1)
            req_ids = await collector.subscribe_to_asx200_sample(1)
            
            if req_ids:
                print(f"   📡 Subscribed to {len(req_ids)} symbols for testing")
                
                # Wait a moment for data
                await asyncio.sleep(2)
                
                # Cancel subscriptions
                for req_id in req_ids:
                    collector.ibkr_client.cancel_market_data(req_id)
            
            await collector.stop_collection()
            print("   🔌 Disconnected from IBKR")
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ Collector test error: {e}")
            return False
    
    def test_celery_task_trigger(self) -> bool:
        """Test triggering Celery tasks via API"""
        try:
            # Trigger a sample data collection
            response = requests.post(
                f"{self.api_base}/api/data/trigger/sample?max_symbols=5",
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            task_data = response.json()
            task_id = task_data["task_id"]
            
            print(f"   🎯 Sample collection task triggered: {task_id}")
            
            # Check task status
            time.sleep(2)  # Give task a moment to start
            
            response = requests.get(f"{self.api_base}/api/data/status/{task_id}", timeout=10)
            if response.status_code != 200:
                return False
            
            status_data = response.json()
            print(f"   📋 Task status: {status_data['state']}")
            
            return True
            
        except Exception as e:
            print(f"   🎯 Celery task error: {e}")
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test database connectivity via API"""
        try:
            response = requests.get(f"{self.api_base}/health/ready", timeout=10)
            if response.status_code != 200:
                return False
            
            ready_data = response.json()
            if ready_data["status"] != "ready":
                return False
            
            print("   🗄️ Database connectivity confirmed")
            return True
            
        except Exception as e:
            print(f"   🗄️ Database test error: {e}")
            return False
    
    def run_full_test_suite(self):
        """Run complete test suite"""
        load_dotenv()
        
        print("🚀 ASX200 Trading System - Pipeline Test Suite")
        print("=" * 60)
        
        # Test sequence
        tests = [
            ("API Health Check", self.test_api_health),
            ("Database Connectivity", self.test_database_connectivity),
            ("Data API Endpoints", self.test_data_endpoints),
            ("IBKR Data Collector", self.test_async_data_collector),
            ("Celery Task Triggers", self.test_celery_task_trigger),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        # Summary
        print("\n" + "=" * 60)
        print("🏁 Test Suite Summary")
        print(f"   Tests Run: {self.test_results['tests_run']}")
        print(f"   Passed: {self.test_results['tests_passed']}")
        print(f"   Failed: {self.test_results['tests_failed']}")
        
        if self.test_results["failures"]:
            print("\n❌ Failed Tests:")
            for failure in self.test_results["failures"]:
                print(f"   - {failure}")
        
        success_rate = (self.test_results["tests_passed"] / 
                       self.test_results["tests_run"] * 100) if self.test_results["tests_run"] > 0 else 0
        
        print(f"\n📊 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Pipeline is ready for ASX200 data collection!")
            return True
        else:
            print("⚠️ Pipeline needs attention before production use")
            return False


def main():
    """Main test function"""
    try:
        tester = PipelineTester()
        success = tester.run_full_test_suite()
        
        if success:
            print("\n✨ Next steps:")
            print("   1. Start Docker services: docker-compose up -d")
            print("   2. Trigger daily collection: POST /api/data/trigger/daily")
            print("   3. Monitor via: GET /health/detailed")
            sys.exit(0)
        else:
            print("\n🔧 Troubleshooting needed before proceeding")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Test suite interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()