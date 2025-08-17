import logging
import sys
from pathlib import Path
import structlog

from app.config.settings import settings


def setup_logging():
    """Configure structured logging for the application"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "trading_system.log")
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logger = structlog.get_logger(__name__)
    logger.info("Logging configured", 
               level=settings.log_level, 
               debug=settings.debug)


class TradingSystemLogger:
    """Specialized logger for trading system events"""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
    
    def log_trade_signal(self, symbol: str, signal_type: str, price: float, 
                        confidence: float, strategy: str):
        """Log trading signal generation"""
        self.logger.info(
            "Trade signal generated",
            symbol=symbol,
            signal_type=signal_type,
            price=price,
            confidence=confidence,
            strategy=strategy,
            event_type="TRADE_SIGNAL"
        )
    
    def log_order_placement(self, symbol: str, side: str, quantity: int, 
                           price: float, order_type: str, order_id: str):
        """Log order placement"""
        self.logger.info(
            "Order placed",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            order_id=order_id,
            event_type="ORDER_PLACED"
        )
    
    def log_order_fill(self, symbol: str, side: str, quantity: int, 
                      fill_price: float, order_id: str, commission: float):
        """Log order execution"""
        self.logger.info(
            "Order filled",
            symbol=symbol,
            side=side,
            quantity=quantity,
            fill_price=fill_price,
            order_id=order_id,
            commission=commission,
            event_type="ORDER_FILLED"
        )
    
    def log_position_update(self, symbol: str, position_size: int, 
                           avg_cost: float, unrealized_pnl: float):
        """Log position changes"""
        self.logger.info(
            "Position updated",
            symbol=symbol,
            position_size=position_size,
            avg_cost=avg_cost,
            unrealized_pnl=unrealized_pnl,
            event_type="POSITION_UPDATE"
        )
    
    def log_risk_violation(self, violation_type: str, current_value: float, 
                          limit_value: float, action_taken: str):
        """Log risk management violations"""
        self.logger.warning(
            "Risk limit violation",
            violation_type=violation_type,
            current_value=current_value,
            limit_value=limit_value,
            action_taken=action_taken,
            event_type="RISK_VIOLATION"
        )
    
    def log_market_data_error(self, symbol: str, error_code: int, 
                             error_message: str):
        """Log market data errors"""
        self.logger.error(
            "Market data error",
            symbol=symbol,
            error_code=error_code,
            error_message=error_message,
            event_type="DATA_ERROR"
        )
    
    def log_connection_event(self, event_type: str, status: str, 
                           retry_count: int = 0):
        """Log connection events"""
        self.logger.info(
            "Connection event",
            connection_event_type=event_type,
            status=status,
            retry_count=retry_count,
            event_type="CONNECTION"
        )
    
    def log_performance_metric(self, metric_name: str, metric_value: float, 
                              period: str):
        """Log performance metrics"""
        self.logger.info(
            "Performance metric",
            metric_name=metric_name,
            metric_value=metric_value,
            period=period,
            event_type="PERFORMANCE"
        )


def get_trading_logger(name: str) -> TradingSystemLogger:
    """Get a trading system logger instance"""
    return TradingSystemLogger(name)