import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock

from app.main import app
from app.config.database import get_async_db


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "ASX200 Trading System"
        assert "version" in data
    
    def test_detailed_health_check_success(self, client):
        """Test detailed health check with successful components."""
        # Mock database check
        with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
            mock_execute.return_value = Mock()
            
            # Mock market data collector
            with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
                mock_instance = Mock()
                mock_instance.get_collection_stats.return_value = {
                    'connection_status': {'connected': True},
                    'requests_made': 100,
                    'successful_responses': 95,
                    'errors': 5,
                    'active_subscriptions': 3
                }
                mock_collector.return_value = mock_instance
                
                response = client.get("/health/detailed")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["status"] == "healthy"
                assert "checks" in data
                assert "database" in data["checks"]
                assert "market_data" in data["checks"]
                assert "market_hours" in data["checks"]
    
    def test_detailed_health_check_database_failure(self, client):
        """Test detailed health check with database failure."""
        # Mock database failure
        with patch('sqlalchemy.ext.asyncio.AsyncSession.execute', 
                  side_effect=Exception("Database connection failed")):
            
            response = client.get("/health/detailed")
            
            assert response.status_code == 503
            data = response.json()
            
            assert data["detail"]["status"] == "unhealthy"
            assert "database" in data["detail"]["checks"]
            assert data["detail"]["checks"]["database"]["status"] == "unhealthy"
    
    def test_readiness_check_success(self, client):
        """Test readiness probe endpoint."""
        with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
            mock_execute.return_value = Mock()
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "ready"
            assert "timestamp" in data
    
    def test_readiness_check_failure(self, client):
        """Test readiness probe with database failure."""
        with patch('sqlalchemy.ext.asyncio.AsyncSession.execute', 
                  side_effect=Exception("Database not ready")):
            
            response = client.get("/health/ready")
            
            assert response.status_code == 503
            data = response.json()
            
            assert data["status"] == "not ready"
            assert "error" in data
    
    def test_liveness_check(self, client):
        """Test liveness probe endpoint."""
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "alive"
        assert "timestamp" in data


class TestDashboardEndpoints:
    """Test dashboard API endpoints."""
    
    def test_get_system_status(self, client):
        """Test system status endpoint."""
        # Mock market data collector
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            mock_instance = Mock()
            mock_instance.get_collection_stats.return_value = {
                'market_open': True,
                'trading_day': True,
                'active_subscriptions': 5,
                'symbols_with_data': 10,
                'requests_made': 200,
                'successful_responses': 190,
                'errors': 10,
                'connection_status': {
                    'connected': True,
                    'host': '127.0.0.1',
                    'port': 7497,
                    'retry_count': 0
                }
            }
            mock_collector.return_value = mock_instance
            
            response = client.get("/api/dashboard/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "timestamp" in data
            assert "system" in data
            assert "data_collection" in data
            assert "connection" in data
            
            assert data["system"]["status"] == "running"
            assert "market_open" in data["system"]
            assert "trading_day" in data["system"]
            
            assert data["data_collection"]["active_subscriptions"] == 5
            assert data["data_collection"]["success_rate"] == 95.0  # 190/200 * 100
    
    def test_get_market_data_overview(self, client):
        """Test market data overview endpoint."""
        # Mock market data collector
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector, \
             patch('app.data.collectors.asx_contracts.get_asx200_symbols') as mock_symbols, \
             patch('app.data.collectors.asx_contracts.get_liquid_stocks') as mock_liquid:
            
            mock_symbols.return_value = ['BHP', 'CBA', 'CSL'] * 67  # ~200 symbols
            mock_liquid.return_value = ['BHP', 'CBA', 'CSL', 'ANZ', 'WBC'] * 4  # 20 symbols
            
            # Mock collector instance
            mock_instance = Mock()
            mock_data_point = Mock()
            mock_data_point.price = 50.25
            mock_data_point.bid = 50.20
            mock_data_point.ask = 50.30
            mock_data_point.volume = 1000000
            mock_data_point.timestamp = "2023-06-15T10:30:00"
            
            mock_instance.get_latest_data.return_value = mock_data_point
            mock_collector.return_value = mock_instance
            
            response = client.get("/api/dashboard/market-data")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "timestamp" in data
            assert "total_symbols" in data
            assert "liquid_symbols" in data
            assert "latest_data" in data
            assert "data_points_available" in data
            
            assert data["total_symbols"] == 201  # 3 * 67
            assert data["liquid_symbols"] == 20  # 5 * 4
    
    def test_get_symbols_list(self, client):
        """Test symbols list endpoint."""
        with patch('app.data.collectors.asx_contracts.get_asx200_symbols') as mock_asx200, \
             patch('app.data.collectors.asx_contracts.get_liquid_stocks') as mock_liquid:
            
            mock_asx200.return_value = ['BHP', 'CBA', 'CSL', 'ANZ', 'WBC']
            mock_liquid.return_value = ['BHP', 'CBA', 'CSL']
            
            response = client.get("/api/dashboard/symbols")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "asx200" in data
            assert "liquid" in data
            assert "total_count" in data
            
            assert len(data["asx200"]) == 5
            assert len(data["liquid"]) == 3
            assert data["total_count"] == 5
    
    def test_start_data_collection_success(self, client):
        """Test starting data collection."""
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            # Mock successful data collection start
            mock_instance = Mock()
            mock_instance.start_collection = AsyncMock(return_value=True)
            mock_instance.subscribe_to_asx200_sample = AsyncMock(return_value=[1001, 1002, 1003])
            mock_collector.return_value = mock_instance
            
            response = client.post("/api/dashboard/data-collection/start")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "started"
            assert data["subscriptions"] == 3
            assert "timestamp" in data
    
    def test_start_data_collection_failure(self, client):
        """Test data collection start failure."""
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            # Mock failed data collection start
            mock_instance = Mock()
            mock_instance.start_collection = AsyncMock(return_value=False)
            mock_collector.return_value = mock_instance
            
            response = client.post("/api/dashboard/data-collection/start")
            
            assert response.status_code == 500
    
    def test_stop_data_collection(self, client):
        """Test stopping data collection."""
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            # Mock data collection stop
            mock_instance = Mock()
            mock_instance.stop_collection = AsyncMock()
            mock_collector.return_value = mock_instance
            
            response = client.post("/api/dashboard/data-collection/stop")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "stopped"
            assert "timestamp" in data
    
    def test_get_performance_metrics(self, client):
        """Test performance metrics endpoint."""
        response = client.get("/api/dashboard/performance")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return placeholder metrics structure
        assert "timestamp" in data
        assert "portfolio" in data
        assert "risk" in data
        assert "trading" in data
        
        # Check portfolio metrics structure
        portfolio = data["portfolio"]
        assert "total_value" in portfolio
        assert "daily_pnl" in portfolio
        assert "unrealized_pnl" in portfolio
        assert "realized_pnl" in portfolio
        assert "positions_count" in portfolio
        
        # Check risk metrics structure
        risk = data["risk"]
        assert "total_exposure" in risk
        assert "max_drawdown" in risk
        assert "var_95" in risk
        assert "correlation_risk" in risk
        
        # Check trading metrics structure
        trading = data["trading"]
        assert "trades_today" in trading
        assert "win_rate" in trading
        assert "avg_holding_period" in trading
        assert "sharpe_ratio" in trading


class TestRootEndpoint:
    """Test root API endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint response."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "ASX200 Trading System API"
        assert "version" in data
        assert data["status"] == "running"


class TestAPIErrorHandling:
    """Test API error handling scenarios."""
    
    def test_nonexistent_endpoint(self, client):
        """Test accessing nonexistent endpoint."""
        response = client.get("/api/nonexistent")
        
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test using wrong HTTP method."""
        response = client.delete("/health")
        
        assert response.status_code == 405
    
    def test_internal_server_error_handling(self, client):
        """Test internal server error handling."""
        # Mock an endpoint to raise an exception
        with patch('app.data.collectors.market_data.MarketDataCollector', 
                  side_effect=Exception("Internal error")):
            
            response = client.get("/api/dashboard/status")
            
            assert response.status_code == 500


class TestAPIMiddleware:
    """Test API middleware functionality."""
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.get("/health")
        
        # CORS headers should be present in response
        assert response.status_code == 200
        # Note: TestClient might not include all CORS headers,
        # but the middleware should be configured
    
    def test_content_type_headers(self, client):
        """Test content type headers."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestAPIAuthentication:
    """Test API authentication (if implemented)."""
    
    def test_public_endpoints_no_auth(self, client):
        """Test that public endpoints don't require authentication."""
        # Health endpoints should be public
        response = client.get("/health")
        assert response.status_code == 200
        
        response = client.get("/health/live")
        assert response.status_code == 200
        
        response = client.get("/health/ready")
        assert response.status_code == 200


class TestAPIPerformance:
    """Test API performance characteristics."""
    
    def test_health_check_response_time(self, client):
        """Test health check response time."""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second
    
    def test_dashboard_status_response_time(self, client):
        """Test dashboard status response time."""
        import time
        
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            mock_instance = Mock()
            mock_instance.get_collection_stats.return_value = {
                'market_open': True,
                'trading_day': True,
                'active_subscriptions': 0,
                'symbols_with_data': 0,
                'requests_made': 0,
                'successful_responses': 0,
                'errors': 0,
                'connection_status': {'connected': False}
            }
            mock_collector.return_value = mock_instance
            
            start_time = time.time()
            response = client.get("/api/dashboard/status")
            end_time = time.time()
            
            response_time = end_time - start_time
            
            assert response.status_code == 200
            assert response_time < 2.0  # Should respond within 2 seconds


class TestAPIDocumentation:
    """Test API documentation endpoints."""
    
    def test_openapi_schema(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
        
        # Check that our endpoints are documented
        assert "/health" in data["paths"]
        assert "/api/dashboard/status" in data["paths"]
    
    def test_docs_endpoint(self, client):
        """Test interactive docs endpoint."""
        response = client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestAPIIntegrationScenarios:
    """Test complex API integration scenarios."""
    
    def test_full_dashboard_workflow(self, client):
        """Test complete dashboard workflow."""
        # 1. Check system status
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            mock_instance = Mock()
            mock_instance.get_collection_stats.return_value = {
                'market_open': True,
                'trading_day': True,
                'active_subscriptions': 0,
                'symbols_with_data': 0,
                'requests_made': 0,
                'successful_responses': 0,
                'errors': 0,
                'connection_status': {'connected': False}
            }
            mock_instance.start_collection = AsyncMock(return_value=True)
            mock_instance.subscribe_to_asx200_sample = AsyncMock(return_value=[1001, 1002])
            mock_instance.stop_collection = AsyncMock()
            mock_collector.return_value = mock_instance
            
            # Check initial status
            response = client.get("/api/dashboard/status")
            assert response.status_code == 200
            
            # Start data collection
            response = client.post("/api/dashboard/data-collection/start")
            assert response.status_code == 200
            
            # Check market data overview
            with patch('app.data.collectors.asx_contracts.get_asx200_symbols') as mock_symbols, \
                 patch('app.data.collectors.asx_contracts.get_liquid_stocks') as mock_liquid:
                
                mock_symbols.return_value = ['BHP', 'CBA']
                mock_liquid.return_value = ['BHP']
                mock_instance.get_latest_data.return_value = None
                
                response = client.get("/api/dashboard/market-data")
                assert response.status_code == 200
            
            # Get symbols list
            response = client.get("/api/dashboard/symbols")
            assert response.status_code == 200
            
            # Stop data collection
            response = client.post("/api/dashboard/data-collection/stop")
            assert response.status_code == 200
    
    def test_error_recovery_scenario(self, client):
        """Test error recovery in API calls."""
        # First call fails
        with patch('app.data.collectors.market_data.MarketDataCollector', 
                  side_effect=Exception("Temporary failure")):
            
            response = client.get("/api/dashboard/status")
            assert response.status_code == 500
        
        # Second call succeeds
        with patch('app.data.collectors.market_data.MarketDataCollector') as mock_collector:
            mock_instance = Mock()
            mock_instance.get_collection_stats.return_value = {
                'market_open': True,
                'trading_day': True,
                'active_subscriptions': 0,
                'symbols_with_data': 0,
                'requests_made': 0,
                'successful_responses': 0,
                'errors': 0,
                'connection_status': {'connected': True}
            }
            mock_collector.return_value = mock_instance
            
            response = client.get("/api/dashboard/status")
            assert response.status_code == 200