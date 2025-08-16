from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from functools import wraps
from typing import Callable, Dict, Any
import structlog

from app.config.settings import settings

logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('trading_system_requests_total', 
                       'Total requests', ['method', 'endpoint', 'status'])

REQUEST_DURATION = Histogram('trading_system_request_duration_seconds',
                           'Request duration', ['method', 'endpoint'])

ACTIVE_CONNECTIONS = Gauge('trading_system_active_connections',
                         'Active IBKR connections')

MARKET_DATA_POINTS = Counter('trading_system_market_data_points_total',
                           'Market data points received', ['symbol'])

TRADE_SIGNALS = Counter('trading_system_trade_signals_total',
                       'Trade signals generated', ['symbol', 'signal_type', 'strategy'])

ORDERS_PLACED = Counter('trading_system_orders_placed_total',
                       'Orders placed', ['symbol', 'side', 'order_type'])

ORDERS_FILLED = Counter('trading_system_orders_filled_total',
                       'Orders filled', ['symbol', 'side'])

PORTFOLIO_VALUE = Gauge('trading_system_portfolio_value',
                       'Current portfolio value')

UNREALIZED_PNL = Gauge('trading_system_unrealized_pnl',
                      'Unrealized P&L')

REALIZED_PNL = Gauge('trading_system_realized_pnl',
                    'Realized P&L')

RISK_EXPOSURE = Gauge('trading_system_risk_exposure',
                     'Total risk exposure')

POSITION_COUNT = Gauge('trading_system_positions_count',
                      'Number of open positions')

API_ERRORS = Counter('trading_system_api_errors_total',
                    'API errors', ['error_code', 'error_type'])

RATE_LIMIT_HITS = Counter('trading_system_rate_limit_hits_total',
                         'Rate limit violations', ['limit_type'])


class MetricsCollector:
    """Collects and manages application metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics_enabled = settings.enable_metrics
        
        if self.metrics_enabled:
            # Start Prometheus metrics server
            try:
                start_http_server(settings.prometheus_port)
                logger.info("Prometheus metrics server started", 
                           port=settings.prometheus_port)
            except Exception as e:
                logger.error("Failed to start metrics server", error=str(e))
                self.metrics_enabled = False
    
    def record_request(self, method: str, endpoint: str, status_code: int, 
                      duration: float):
        """Record HTTP request metrics"""
        if not self.metrics_enabled:
            return
        
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, 
                           status=str(status_code)).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
    
    def record_market_data_point(self, symbol: str):
        """Record market data point received"""
        if not self.metrics_enabled:
            return
        
        MARKET_DATA_POINTS.labels(symbol=symbol).inc()
    
    def record_trade_signal(self, symbol: str, signal_type: str, strategy: str):
        """Record trade signal generation"""
        if not self.metrics_enabled:
            return
        
        TRADE_SIGNALS.labels(symbol=symbol, signal_type=signal_type, 
                           strategy=strategy).inc()
    
    def record_order_placed(self, symbol: str, side: str, order_type: str):
        """Record order placement"""
        if not self.metrics_enabled:
            return
        
        ORDERS_PLACED.labels(symbol=symbol, side=side, 
                           order_type=order_type).inc()
    
    def record_order_filled(self, symbol: str, side: str):
        """Record order fill"""
        if not self.metrics_enabled:
            return
        
        ORDERS_FILLED.labels(symbol=symbol, side=side).inc()
    
    def update_portfolio_metrics(self, portfolio_value: float, 
                               unrealized_pnl: float, realized_pnl: float):
        """Update portfolio metrics"""
        if not self.metrics_enabled:
            return
        
        PORTFOLIO_VALUE.set(portfolio_value)
        UNREALIZED_PNL.set(unrealized_pnl)
        REALIZED_PNL.set(realized_pnl)
    
    def update_risk_metrics(self, total_exposure: float, position_count: int):
        """Update risk metrics"""
        if not self.metrics_enabled:
            return
        
        RISK_EXPOSURE.set(total_exposure)
        POSITION_COUNT.set(position_count)
    
    def record_api_error(self, error_code: int, error_type: str):
        """Record API error"""
        if not self.metrics_enabled:
            return
        
        API_ERRORS.labels(error_code=str(error_code), 
                         error_type=error_type).inc()
    
    def record_rate_limit_hit(self, limit_type: str):
        """Record rate limit violation"""
        if not self.metrics_enabled:
            return
        
        RATE_LIMIT_HITS.labels(limit_type=limit_type).inc()
    
    def update_connection_status(self, connected: bool):
        """Update connection status"""
        if not self.metrics_enabled:
            return
        
        ACTIVE_CONNECTIONS.set(1 if connected else 0)
    
    def get_uptime(self) -> float:
        """Get application uptime in seconds"""
        return time.time() - self.start_time


# Global metrics collector instance
metrics_collector = MetricsCollector()


def track_request_metrics(func: Callable) -> Callable:
    """Decorator to track HTTP request metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Extract request info (this is a simplified version)
            method = "GET"  # Would need to extract from request
            endpoint = func.__name__
            status_code = 200
            
            metrics_collector.record_request(method, endpoint, status_code, duration)
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            metrics_collector.record_request("GET", func.__name__, 500, duration)
            raise
    
    return wrapper


def track_trading_metrics(metric_type: str):
    """Decorator to track trading-related metrics"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Record specific metric based on type
            if metric_type == "signal" and result:
                metrics_collector.record_trade_signal(
                    result.get("symbol", "UNKNOWN"),
                    result.get("signal_type", "UNKNOWN"),
                    result.get("strategy", "UNKNOWN")
                )
            elif metric_type == "order" and result:
                metrics_collector.record_order_placed(
                    result.get("symbol", "UNKNOWN"),
                    result.get("side", "UNKNOWN"),
                    result.get("order_type", "UNKNOWN")
                )
            
            return result
        
        return wrapper
    return decorator