import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.data.collectors.ibkr_client import IBKRClient, RateLimiter
from app.data.collectors.asx_contracts import create_asx_stock_contract


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests=50, time_window=1)
        
        assert limiter.max_requests == 50
        assert limiter.time_window == 1
        assert limiter.tokens == 50
        assert limiter.last_update > 0
    
    def test_acquire_token_success(self):
        """Test successful token acquisition."""
        limiter = RateLimiter(max_requests=10, time_window=1)
        
        # Should be able to acquire tokens initially
        assert limiter.acquire() == True
        assert limiter.tokens == 9
        
        # Should be able to acquire more tokens
        assert limiter.acquire() == True
        assert limiter.tokens == 8
    
    def test_acquire_token_exhausted(self):
        """Test token acquisition when exhausted."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Exhaust tokens
        assert limiter.acquire() == True
        assert limiter.acquire() == True
        
        # Should fail to acquire more tokens
        assert limiter.acquire() == False
        assert limiter.tokens < 1
    
    def test_token_replenishment(self):
        """Test token replenishment over time."""
        limiter = RateLimiter(max_requests=10, time_window=1)
        
        # Exhaust all tokens
        for _ in range(10):
            limiter.acquire()
        
        # Should have no tokens
        assert limiter.acquire() == False
        
        # Mock time passing
        original_time = time.time
        with patch('time.time', return_value=original_time() + 1.1):  # 1.1 seconds later
            # Should be able to acquire tokens again
            assert limiter.acquire() == True
    
    def test_wait_for_token(self):
        """Test waiting for token availability."""
        limiter = RateLimiter(max_requests=1, time_window=1)
        
        # Exhaust token
        limiter.acquire()
        
        # Mock time progression for wait_for_token
        with patch('time.time') as mock_time, \
             patch('time.sleep') as mock_sleep:
            
            # Simulate time progression
            time_values = [100.0, 100.1, 100.2, 100.3, 101.1]  # Last value allows token acquisition
            mock_time.side_effect = time_values
            
            limiter.wait_for_token()
            
            # Should have called sleep multiple times
            assert mock_sleep.call_count >= 1


class TestIBKRClient:
    """Test IBKR client functionality."""
    
    def test_client_initialization(self):
        """Test IBKR client initialization."""
        client = IBKRClient()
        
        # Should have proper configuration
        assert client.host == "127.0.0.1"
        assert client.port in [7497, 7496]  # Live or paper trading port
        assert client.client_id == 1
        
        # Should have rate limiters
        assert isinstance(client.rate_limiter, RateLimiter)
        assert isinstance(client.historical_limiter, RateLimiter)
        
        # Should be initialized as disconnected
        assert client.is_connected == False
        assert client.next_valid_order_id is None
    
    def test_get_next_request_id(self):
        """Test request ID generation."""
        client = IBKRClient()
        
        first_id = client.get_next_request_id()
        second_id = client.get_next_request_id()
        
        assert second_id == first_id + 1
        assert first_id >= 1000  # Should start from base value
    
    @patch('app.data.collectors.ibkr_client.EClient.connect')
    def test_connect_to_tws_success(self, mock_connect):
        """Test successful TWS connection."""
        client = IBKRClient()
        
        # Mock successful connection
        def mock_connection_success(*args, **kwargs):
            client.is_connected = True
        
        mock_connect.side_effect = mock_connection_success
        
        result = client.connect_to_tws()
        
        assert result == True
        assert client.is_connected == True
        mock_connect.assert_called_once_with(client.host, client.port, client.client_id)
    
    @patch('app.data.collectors.ibkr_client.EClient.connect')
    def test_connect_to_tws_timeout(self, mock_connect):
        """Test TWS connection timeout."""
        client = IBKRClient()
        
        # Mock connection that never completes
        mock_connect.return_value = None
        
        with patch('time.sleep'):  # Speed up the test
            result = client.connect_to_tws()
        
        assert result == False
        assert client.is_connected == False
    
    @patch('app.data.collectors.ibkr_client.EClient.connect')
    def test_connect_to_tws_exception(self, mock_connect):
        """Test TWS connection with exception."""
        client = IBKRClient()
        
        # Mock connection exception
        mock_connect.side_effect = Exception("Connection failed")
        
        result = client.connect_to_tws()
        
        assert result == False
        assert client.is_connected == False
    
    @patch('app.data.collectors.ibkr_client.EClient.disconnect')
    def test_disconnect_from_tws(self, mock_disconnect):
        """Test TWS disconnection."""
        client = IBKRClient()
        client.is_connected = True
        
        client.disconnect_from_tws()
        
        assert client.is_connected == False
        mock_disconnect.assert_called_once()
    
    def test_ensure_connection_already_connected(self):
        """Test ensure connection when already connected."""
        client = IBKRClient()
        client.is_connected = True
        
        result = client.ensure_connection()
        
        assert result == True
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.connect_to_tws')
    def test_ensure_connection_reconnect_success(self, mock_connect):
        """Test ensure connection with successful reconnection."""
        client = IBKRClient()
        client.is_connected = False
        
        mock_connect.return_value = True
        
        result = client.ensure_connection()
        
        assert result == True
        mock_connect.assert_called_once()
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.connect_to_tws')
    def test_ensure_connection_max_retries(self, mock_connect):
        """Test ensure connection with max retries exceeded."""
        client = IBKRClient()
        client.is_connected = False
        client.connection_retry_count = 5  # Exceed max retries
        
        result = client.ensure_connection()
        
        assert result == False
        mock_connect.assert_not_called()
    
    def test_next_valid_id_callback(self):
        """Test nextValidId callback."""
        client = IBKRClient()
        
        order_id = 2000
        client.nextValidId(order_id)
        
        assert client.next_valid_order_id == order_id
        assert client.is_connected == True
    
    def test_connection_ack_callback(self):
        """Test connectAck callback."""
        client = IBKRClient()
        
        # Should not raise exception
        client.connectAck()
    
    def test_connection_closed_callback(self):
        """Test connectionClosed callback."""
        client = IBKRClient()
        client.is_connected = True
        
        client.connectionClosed()
        
        assert client.is_connected == False
    
    def test_error_callback_rate_limit(self):
        """Test error callback with rate limit violation."""
        client = IBKRClient()
        
        with patch('time.sleep') as mock_sleep:
            client.error(reqId=1001, errorCode=100, errorString="Rate limit exceeded")
            
            # Should pause briefly on rate limit
            mock_sleep.assert_called_once()
    
    def test_error_callback_connection_lost(self):
        """Test error callback with connection lost."""
        client = IBKRClient()
        client.is_connected = True
        
        client.error(reqId=1001, errorCode=1100, errorString="Connection lost")
        
        assert client.is_connected == False
    
    def test_error_callback_connection_restored(self):
        """Test error callback with connection restored."""
        client = IBKRClient()
        client.is_connected = False
        
        # Test data maintained
        client.error(reqId=1001, errorCode=1102, errorString="Connection restored")
        assert client.is_connected == True
        
        # Test data lost
        client.error(reqId=1001, errorCode=1101, errorString="Connection restored, data lost")
        assert client.is_connected == True
    
    def test_tick_price_callback(self):
        """Test tickPrice callback."""
        client = IBKRClient()
        
        # Set up callback
        callback = Mock()
        req_id = 1001
        client.market_data_callbacks[req_id] = callback
        
        client.tickPrice(req_id, tickType=4, price=50.25, attrib=None)
        
        callback.assert_called_once_with('price', 4, 50.25, None)
    
    def test_tick_size_callback(self):
        """Test tickSize callback."""
        client = IBKRClient()
        
        # Set up callback
        callback = Mock()
        req_id = 1001
        client.market_data_callbacks[req_id] = callback
        
        client.tickSize(req_id, tickType=8, size=1000)
        
        callback.assert_called_once_with('size', 8, 1000, None)
    
    def test_historical_data_callback(self):
        """Test historicalData callback."""
        client = IBKRClient()
        
        # Set up callback
        callback = Mock()
        req_id = 1001
        client.historical_data_callbacks[req_id] = callback
        
        # Mock bar data
        mock_bar = Mock()
        client.historicalData(req_id, mock_bar)
        
        callback.assert_called_once_with(mock_bar)
    
    def test_historical_data_end_callback(self):
        """Test historicalDataEnd callback."""
        client = IBKRClient()
        
        # Set up callback
        callback = Mock()
        req_id = 1001
        client.historical_data_callbacks[req_id] = callback
        client.pending_requests.add(req_id)
        
        client.historicalDataEnd(req_id, start="20230101", end="20231231")
        
        # Should clean up callback and pending request
        assert req_id not in client.historical_data_callbacks
        assert req_id not in client.pending_requests
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.ensure_connection')
    @patch('app.data.collectors.ibkr_client.EClient.reqMktData')
    def test_request_market_data_success(self, mock_req_data, mock_ensure_conn):
        """Test successful market data request."""
        client = IBKRClient()
        
        # Mock successful connection
        mock_ensure_conn.return_value = True
        
        # Mock rate limiter
        client.rate_limiter.acquire = Mock(return_value=True)
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        req_id = client.request_market_data(contract, callback)
        
        assert req_id is not None
        assert req_id in client.market_data_callbacks
        assert req_id in client.pending_requests
        mock_req_data.assert_called_once()
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.ensure_connection')
    def test_request_market_data_no_connection(self, mock_ensure_conn):
        """Test market data request without connection."""
        client = IBKRClient()
        
        # Mock failed connection
        mock_ensure_conn.return_value = False
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        req_id = client.request_market_data(contract, callback)
        
        assert req_id is None
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.ensure_connection')
    @patch('app.data.collectors.ibkr_client.EClient.reqHistoricalData')
    def test_request_historical_data_success(self, mock_req_hist, mock_ensure_conn):
        """Test successful historical data request."""
        client = IBKRClient()
        
        # Mock successful connection
        mock_ensure_conn.return_value = True
        
        # Mock rate limiter
        client.historical_limiter.acquire = Mock(return_value=True)
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        req_id = client.request_historical_data(contract, "1 M", "1 day", callback)
        
        assert req_id is not None
        assert req_id in client.historical_data_callbacks
        assert req_id in client.pending_requests
        mock_req_hist.assert_called_once()
    
    @patch('app.data.collectors.ibkr_client.IBKRClient.ensure_connection')
    def test_request_historical_data_rate_limited(self, mock_ensure_conn):
        """Test historical data request when rate limited."""
        client = IBKRClient()
        
        # Mock successful connection
        mock_ensure_conn.return_value = True
        
        # Mock rate limiter exhausted
        client.historical_limiter.acquire = Mock(return_value=False)
        client.historical_limiter.wait_for_token = Mock()
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        with patch('app.data.collectors.ibkr_client.EClient.reqHistoricalData') as mock_req:
            req_id = client.request_historical_data(contract, "1 M", "1 day", callback)
            
            # Should wait for token and then proceed
            client.historical_limiter.wait_for_token.assert_called_once()
            assert req_id is not None
    
    @patch('app.data.collectors.ibkr_client.EClient.cancelMktData')
    def test_cancel_market_data(self, mock_cancel):
        """Test market data cancellation."""
        client = IBKRClient()
        
        # Set up active subscription
        req_id = 1001
        callback = Mock()
        client.market_data_callbacks[req_id] = callback
        client.pending_requests.add(req_id)
        
        client.cancel_market_data(req_id)
        
        # Should clean up and cancel
        assert req_id not in client.market_data_callbacks
        assert req_id not in client.pending_requests
        mock_cancel.assert_called_once_with(req_id)
    
    def test_get_connection_status(self):
        """Test connection status reporting."""
        client = IBKRClient()
        client.is_connected = True
        client.connection_retry_count = 2
        client.pending_requests.add(1001)
        client.pending_requests.add(1002)
        
        status = client.get_connection_status()
        
        assert status['connected'] == True
        assert status['host'] == client.host
        assert status['port'] == client.port
        assert status['client_id'] == client.client_id
        assert status['retry_count'] == 2
        assert status['pending_requests'] == 2
        assert 'rate_limiter_tokens' in status
        assert 'historical_limiter_tokens' in status


class TestIBKRClientIntegration:
    """Test IBKR client integration scenarios."""
    
    def test_client_with_mock_tws(self, mock_ibkr_client):
        """Test client functionality with mock TWS."""
        # This test uses the mock client from conftest.py
        assert mock_ibkr_client.is_connected == True
        
        # Test market data request
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        req_id = mock_ibkr_client.request_market_data(contract, callback)
        assert req_id is not None
        assert req_id in mock_ibkr_client.market_data_callbacks
    
    def test_multiple_requests_rate_limiting(self):
        """Test multiple requests with rate limiting."""
        client = IBKRClient()
        
        # Mock connection
        client.is_connected = True
        
        # Set very low rate limit for testing
        client.rate_limiter = RateLimiter(max_requests=2, time_window=1)
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        with patch('app.data.collectors.ibkr_client.EClient.reqMktData'):
            # First two requests should succeed
            req_id1 = client.request_market_data(contract, callback)
            req_id2 = client.request_market_data(contract, callback)
            
            assert req_id1 is not None
            assert req_id2 is not None
            
            # Third request should wait for rate limit
            with patch.object(client.rate_limiter, 'wait_for_token') as mock_wait:
                req_id3 = client.request_market_data(contract, callback)
                
                mock_wait.assert_called_once()
                assert req_id3 is not None
    
    def test_error_handling_during_requests(self):
        """Test error handling during API requests."""
        client = IBKRClient()
        client.is_connected = True
        client.rate_limiter.acquire = Mock(return_value=True)
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        # Mock request method to raise exception
        with patch('app.data.collectors.ibkr_client.EClient.reqMktData', 
                  side_effect=Exception("API Error")):
            
            req_id = client.request_market_data(contract, callback)
            
            # Should handle error gracefully
            assert req_id is None
    
    def test_reconnection_scenario(self):
        """Test automatic reconnection scenario."""
        client = IBKRClient()
        
        # Start disconnected
        client.is_connected = False
        client.connection_retry_count = 0
        
        # Mock successful reconnection
        with patch.object(client, 'connect_to_tws', return_value=True):
            result = client.ensure_connection()
            
            assert result == True
            assert client.connection_retry_count == 1
    
    def test_callback_cleanup_on_error(self):
        """Test callback cleanup when requests fail."""
        client = IBKRClient()
        client.is_connected = True
        
        contract = create_asx_stock_contract('BHP')
        callback = Mock()
        
        # Mock ensure_connection to fail
        with patch.object(client, 'ensure_connection', return_value=False):
            req_id = client.request_market_data(contract, callback)
            
            # Should not have added callback on failure
            assert req_id is None
            assert len(client.market_data_callbacks) == 0