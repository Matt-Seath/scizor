"""Pydantic models for API requests and responses."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class TimeFrame(str, Enum):
    """Supported timeframes for market data."""
    
    SECOND_1 = "1sec"
    SECOND_5 = "5secs"
    SECOND_10 = "10secs"
    SECOND_15 = "15secs"
    SECOND_30 = "30secs"
    MINUTE_1 = "1min"
    MINUTE_2 = "2mins"
    MINUTE_3 = "3mins"
    MINUTE_5 = "5mins"
    MINUTE_10 = "10mins"
    MINUTE_15 = "15mins"
    MINUTE_20 = "20mins"
    MINUTE_30 = "30mins"
    HOUR_1 = "1hour"
    HOUR_2 = "2hours"
    HOUR_3 = "3hours"
    HOUR_4 = "4hours"
    HOUR_8 = "8hours"
    DAY_1 = "1day"
    WEEK_1 = "1week"
    MONTH_1 = "1month"


class SecurityTypeEnum(str, Enum):
    """Security types."""
    
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    BOND = "BOND"
    COMMODITY = "CMDTY"
    CFD = "CFD"


class OrderAction(str, Enum):
    """Order actions."""
    
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order types."""
    
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    TRAILING_STOP = "TRAIL"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"


class TimeInForce(str, Enum):
    """Time in force values."""
    
    DAY = "DAY"
    GOOD_TILL_CANCELLED = "GTC"
    IMMEDIATE_OR_CANCEL = "IOC"
    FILL_OR_KILL = "FOK"
    GOOD_TILL_DATE = "GTD"


# Base models
class ContractBase(BaseModel):
    """Base contract model."""
    
    symbol: str = Field(..., description="Instrument symbol")
    exchange: str = Field(default="SMART", description="Exchange")
    currency: str = Field(default="USD", description="Currency")
    security_type: SecurityTypeEnum = Field(default=SecurityTypeEnum.STOCK, description="Security type")
    contract_id: Optional[int] = Field(None, description="IBKR contract ID")
    local_symbol: Optional[str] = Field(None, description="Local symbol")
    trading_class: Optional[str] = Field(None, description="Trading class")
    multiplier: Optional[str] = Field(None, description="Contract multiplier")
    expiry: Optional[str] = Field(None, description="Expiry date")
    strike: Optional[float] = Field(None, description="Strike price")
    option_type: Optional[str] = Field(None, description="Option type (C/P)")


class OrderBase(BaseModel):
    """Base order model."""
    
    action: OrderAction = Field(..., description="Order action")
    order_type: OrderType = Field(..., description="Order type")
    quantity: int = Field(..., gt=0, description="Order quantity")
    limit_price: Optional[float] = Field(None, description="Limit price")
    stop_price: Optional[float] = Field(None, description="Stop price")
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    account: Optional[str] = Field(None, description="Account")
    outside_rth: bool = Field(default=False, description="Allow outside regular trading hours")
    hidden: bool = Field(default=False, description="Hidden order")
    all_or_none: bool = Field(default=False, description="All or none")


class MarketDataBar(BaseModel):
    """Market data bar model."""
    
    timestamp: datetime = Field(..., description="Bar timestamp")
    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: int = Field(default=0, description="Volume")
    wap: Optional[Decimal] = Field(None, description="Weighted average price")
    bar_count: int = Field(default=0, description="Number of trades")
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class TickData(BaseModel):
    """Real-time tick data model."""
    
    timestamp: datetime = Field(..., description="Tick timestamp")
    bid: Optional[float] = Field(None, description="Bid price")
    ask: Optional[float] = Field(None, description="Ask price")
    last: Optional[float] = Field(None, description="Last price")
    bid_size: Optional[int] = Field(None, description="Bid size")
    ask_size: Optional[int] = Field(None, description="Ask size")
    last_size: Optional[int] = Field(None, description="Last size")
    volume: Optional[int] = Field(None, description="Volume")


class Position(BaseModel):
    """Position model."""
    
    symbol: str = Field(..., description="Symbol")
    account: str = Field(..., description="Account")
    quantity: int = Field(..., description="Position size")
    avg_price: Decimal = Field(..., description="Average price")
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    market_value: Optional[Decimal] = Field(None, description="Market value")
    unrealized_pnl: Optional[Decimal] = Field(None, description="Unrealized P&L")
    realized_pnl: Optional[Decimal] = Field(None, description="Realized P&L")
    updated_at: datetime = Field(..., description="Last update time")


class Trade(BaseModel):
    """Trade execution model."""
    
    trade_id: int = Field(..., description="Trade ID")
    symbol: str = Field(..., description="Symbol")
    side: OrderAction = Field(..., description="Buy or sell")
    quantity: int = Field(..., description="Quantity")
    price: Decimal = Field(..., description="Execution price")
    commission: Decimal = Field(default=Decimal("0"), description="Commission paid")
    realized_pnl: Optional[Decimal] = Field(None, description="Realized P&L")
    execution_time: datetime = Field(..., description="Execution time")
    account: Optional[str] = Field(None, description="Account")
    order_id: Optional[int] = Field(None, description="Order ID")
    exec_id: Optional[str] = Field(None, description="Execution ID")


class StrategyParameters(BaseModel):
    """Strategy parameters model."""
    
    name: str = Field(..., description="Parameter name")
    value: Union[str, int, float, bool] = Field(..., description="Parameter value")
    description: Optional[str] = Field(None, description="Parameter description")
    type: str = Field(..., description="Parameter type")
    min_value: Optional[Union[int, float]] = Field(None, description="Minimum value")
    max_value: Optional[Union[int, float]] = Field(None, description="Maximum value")


class Strategy(BaseModel):
    """Strategy model."""
    
    id: Optional[int] = Field(None, description="Strategy ID")
    name: str = Field(..., description="Strategy name")
    description: Optional[str] = Field(None, description="Strategy description")
    code: str = Field(..., description="Strategy code")
    parameters: List[StrategyParameters] = Field(default=[], description="Strategy parameters")
    status: str = Field(default="inactive", description="Strategy status")
    created_at: Optional[datetime] = Field(None, description="Creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")


class BacktestConfig(BaseModel):
    """Backtest configuration model."""
    
    strategy_id: int = Field(..., description="Strategy ID")
    name: str = Field(..., description="Backtest name")
    symbols: List[str] = Field(..., description="List of symbols to test")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    initial_capital: Decimal = Field(default=Decimal("100000"), description="Initial capital")
    parameters: Dict[str, Union[str, int, float, bool]] = Field(default={}, description="Strategy parameters")
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class BacktestResult(BaseModel):
    """Backtest result model."""
    
    job_id: int = Field(..., description="Backtest job ID")
    status: str = Field(..., description="Backtest status")
    total_return: Optional[Decimal] = Field(None, description="Total return")
    annual_return: Optional[Decimal] = Field(None, description="Annualized return")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[Decimal] = Field(None, description="Maximum drawdown")
    win_rate: Optional[Decimal] = Field(None, description="Win rate")
    profit_factor: Optional[Decimal] = Field(None, description="Profit factor")
    total_trades: Optional[int] = Field(None, description="Total number of trades")
    winning_trades: Optional[int] = Field(None, description="Number of winning trades")
    losing_trades: Optional[int] = Field(None, description="Number of losing trades")
    avg_trade: Optional[Decimal] = Field(None, description="Average trade P&L")
    avg_win: Optional[Decimal] = Field(None, description="Average winning trade")
    avg_loss: Optional[Decimal] = Field(None, description="Average losing trade")
    largest_win: Optional[Decimal] = Field(None, description="Largest winning trade")
    largest_loss: Optional[Decimal] = Field(None, description="Largest losing trade")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")


class RiskMetrics(BaseModel):
    """Risk metrics model."""
    
    var_95: Optional[Decimal] = Field(None, description="95% Value at Risk")
    var_99: Optional[Decimal] = Field(None, description="99% Value at Risk")
    cvar_95: Optional[Decimal] = Field(None, description="95% Conditional VaR")
    cvar_99: Optional[Decimal] = Field(None, description="99% Conditional VaR")
    beta: Optional[Decimal] = Field(None, description="Beta")
    alpha: Optional[Decimal] = Field(None, description="Alpha")
    correlation: Optional[Decimal] = Field(None, description="Correlation with benchmark")
    skewness: Optional[Decimal] = Field(None, description="Skewness")
    kurtosis: Optional[Decimal] = Field(None, description="Kurtosis")
    downside_deviation: Optional[Decimal] = Field(None, description="Downside deviation")
    sortino_ratio: Optional[Decimal] = Field(None, description="Sortino ratio")
    calmar_ratio: Optional[Decimal] = Field(None, description="Calmar ratio")


class PerformanceMetrics(BaseModel):
    """Performance metrics model."""
    
    total_return: Decimal = Field(..., description="Total return")
    annual_return: Decimal = Field(..., description="Annualized return")
    volatility: Decimal = Field(..., description="Volatility")
    sharpe_ratio: Decimal = Field(..., description="Sharpe ratio")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown")
    max_drawdown_duration: Optional[int] = Field(None, description="Max drawdown duration in days")
    win_rate: Decimal = Field(..., description="Win rate")
    profit_factor: Decimal = Field(..., description="Profit factor")
    risk_metrics: Optional[RiskMetrics] = Field(None, description="Risk metrics")


class AlertBase(BaseModel):
    """Base alert model."""
    
    type: str = Field(..., description="Alert type")
    severity: str = Field(..., description="Severity level")
    message: str = Field(..., description="Alert message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Alert timestamp")
    acknowledged: bool = Field(default=False, description="Acknowledgment status")


class RiskAlert(AlertBase):
    """Risk alert model."""
    
    current_value: Optional[Decimal] = Field(None, description="Current value")
    threshold_value: Optional[Decimal] = Field(None, description="Threshold value")
    strategy_id: Optional[int] = Field(None, description="Associated strategy ID")
    symbol: Optional[str] = Field(None, description="Associated symbol")
    account: Optional[str] = Field(None, description="Associated account")
    action_taken: Optional[str] = Field(None, description="Action taken")


# API Response models
class HealthStatus(BaseModel):
    """Service health status model."""
    
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    version: str = Field(..., description="Service version")
    uptime: float = Field(..., description="Uptime in seconds")
    connections: Dict[str, bool] = Field(default={}, description="Connection statuses")
    
    
class APIResponse(BaseModel):
    """Standard API response model."""
    
    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")
    data: Optional[Union[Dict, List, str, int, float]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    
class PaginatedResponse(BaseModel):
    """Paginated response model."""
    
    data: List[Union[Dict, BaseModel]] = Field(..., description="Data items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        if 'total' in values and 'size' in values:
            return (values['total'] + values['size'] - 1) // values['size']
        return v
