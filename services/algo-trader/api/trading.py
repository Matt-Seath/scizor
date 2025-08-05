"""Trading execution API endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.connection import get_db
from shared.database.models import Strategy, Trade, Position
from shared.models.schemas import APIResponse, OrderCreate, ContractBase
from ..services.trader import AlgoTrader

router = APIRouter()


def get_trader() -> AlgoTrader:
    """Get the trader instance."""
    # This would be injected from the main app
    return AlgoTrader()


@router.post("/strategies/{strategy_id}/start", response_model=APIResponse)
async def start_strategy(
    strategy_id: int,
    background_tasks: BackgroundTasks,
    allocation: float = Query(10000.0, description="Capital allocation for strategy"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Start live trading for a strategy."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        if not strategy.active:
            raise HTTPException(status_code=400, detail="Strategy is not active")
            
        # Check if strategy is already running
        if await trader.is_strategy_running(strategy_id):
            raise HTTPException(status_code=400, detail="Strategy is already running")
            
        # Start strategy execution
        background_tasks.add_task(trader.start_strategy, strategy_id, allocation)
        
        return APIResponse(
            success=True,
            message=f"Strategy {strategy.name} started with ${allocation:,.2f} allocation"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start strategy: {str(e)}")


@router.post("/strategies/{strategy_id}/stop", response_model=APIResponse)
async def stop_strategy(
    strategy_id: int,
    liquidate_positions: bool = Query(True, description="Liquidate all positions when stopping"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Stop live trading for a strategy."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Check if strategy is running
        if not await trader.is_strategy_running(strategy_id):
            raise HTTPException(status_code=400, detail="Strategy is not running")
            
        # Stop strategy execution
        await trader.stop_strategy(strategy_id, liquidate_positions)
        
        return APIResponse(
            success=True,
            message=f"Strategy {strategy.name} stopped"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop strategy: {str(e)}")


@router.get("/strategies/running", response_model=List[Dict[str, Any]])
async def get_running_strategies(
    trader: AlgoTrader = Depends(get_trader)
):
    """Get all currently running strategies."""
    try:
        running_strategies = await trader.get_running_strategies()
        
        return [
            {
                "strategy_id": strategy["id"],
                "strategy_name": strategy["name"],
                "allocation": strategy["allocation"],
                "current_pnl": strategy["current_pnl"],
                "open_positions": strategy["open_positions"],
                "orders_today": strategy["orders_today"],
                "started_at": strategy["started_at"],
                "status": strategy["status"]
            }
            for strategy in running_strategies
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get running strategies: {str(e)}")


@router.post("/orders/submit", response_model=APIResponse)
async def submit_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Submit a trading order."""
    try:
        # Validate order
        if order.quantity <= 0:
            raise HTTPException(status_code=400, detail="Order quantity must be positive")
            
        # Submit order through trader
        order_id = await trader.submit_order(order)
        
        return APIResponse(
            success=True,
            message="Order submitted successfully",
            data={"order_id": order_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit order: {str(e)}")


@router.post("/orders/{order_id}/cancel", response_model=APIResponse)
async def cancel_order(
    order_id: int,
    trader: AlgoTrader = Depends(get_trader)
):
    """Cancel a pending order."""
    try:
        success = await trader.cancel_order(order_id)
        
        if success:
            return APIResponse(
                success=True,
                message="Order cancelled successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to cancel order")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")


@router.get("/status", response_model=Dict[str, Any])
async def get_trading_status(
    trader: AlgoTrader = Depends(get_trader)
):
    """Get overall trading system status."""
    try:
        status = await trader.get_status()
        
        return {
            "system_status": status.get("status", "unknown"),
            "connection_status": status.get("connection_status", "disconnected"),
            "total_strategies": status.get("total_strategies", 0),
            "running_strategies": status.get("running_strategies", 0),
            "total_positions": status.get("total_positions", 0),
            "pending_orders": status.get("pending_orders", 0),
            "daily_pnl": status.get("daily_pnl", 0.0),
            "total_equity": status.get("total_equity", 0.0),
            "available_funds": status.get("available_funds", 0.0),
            "last_updated": status.get("last_updated"),
            "trading_hours": status.get("trading_hours", False),
            "market_status": status.get("market_status", "unknown")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trading status: {str(e)}")


@router.post("/emergency-stop", response_model=APIResponse)
async def emergency_stop(
    reason: str = Query(..., description="Reason for emergency stop"),
    trader: AlgoTrader = Depends(get_trader)
):
    """Emergency stop all trading activities."""
    try:
        await trader.emergency_stop(reason)
        
        return APIResponse(
            success=True,
            message=f"Emergency stop executed: {reason}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute emergency stop: {str(e)}")


@router.post("/resume-trading", response_model=APIResponse)
async def resume_trading(
    trader: AlgoTrader = Depends(get_trader)
):
    """Resume trading after emergency stop."""
    try:
        await trader.resume_trading()
        
        return APIResponse(
            success=True,
            message="Trading resumed"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume trading: {str(e)}")


@router.get("/performance/live", response_model=Dict[str, Any])
async def get_live_performance(
    strategy_id: Optional[int] = Query(None, description="Strategy ID for specific performance"),
    timeframe: str = Query("1d", description="Timeframe for performance data"),
    trader: AlgoTrader = Depends(get_trader)
):
    """Get live trading performance metrics."""
    try:
        performance = await trader.get_live_performance(strategy_id, timeframe)
        
        return {
            "timeframe": timeframe,
            "strategy_id": strategy_id,
            "performance_data": performance.get("data", {}),
            "metrics": {
                "total_pnl": performance.get("total_pnl", 0.0),
                "realized_pnl": performance.get("realized_pnl", 0.0),
                "unrealized_pnl": performance.get("unrealized_pnl", 0.0),
                "total_trades": performance.get("total_trades", 0),
                "win_rate": performance.get("win_rate", 0.0),
                "avg_trade": performance.get("avg_trade", 0.0),
                "best_trade": performance.get("best_trade", 0.0),
                "worst_trade": performance.get("worst_trade", 0.0)
            },
            "last_updated": performance.get("last_updated")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get live performance: {str(e)}")


@router.post("/rebalance", response_model=APIResponse)
async def rebalance_portfolio(
    background_tasks: BackgroundTasks,
    strategy_allocations: Dict[int, float] = Query(..., description="New strategy allocations"),
    trader: AlgoTrader = Depends(get_trader)
):
    """Rebalance portfolio allocations across strategies."""
    try:
        # Validate allocations sum to 1.0 or reasonable total
        total_allocation = sum(strategy_allocations.values())
        if abs(total_allocation - 1.0) > 0.01 and total_allocation > 1.0:
            raise HTTPException(status_code=400, detail="Invalid allocation percentages")
            
        # Start rebalancing in background
        background_tasks.add_task(trader.rebalance_portfolio, strategy_allocations)
        
        return APIResponse(
            success=True,
            message="Portfolio rebalancing initiated"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start rebalancing: {str(e)}")


@router.get("/market-hours", response_model=Dict[str, Any])
async def get_market_hours(
    trader: AlgoTrader = Depends(get_trader)
):
    """Get current market hours and trading status."""
    try:
        market_info = await trader.get_market_hours()
        
        return {
            "current_time": datetime.now().isoformat(),
            "market_open": market_info.get("market_open", False),
            "trading_hours": market_info.get("trading_hours", {}),
            "next_open": market_info.get("next_open"),
            "next_close": market_info.get("next_close"),
            "market_status": market_info.get("status", "unknown"),
            "timezone": market_info.get("timezone", "UTC")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get market hours: {str(e)}")


@router.post("/strategies/{strategy_id}/pause", response_model=APIResponse)
async def pause_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Pause a running strategy without liquidating positions."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Pause strategy
        await trader.pause_strategy(strategy_id)
        
        return APIResponse(
            success=True,
            message=f"Strategy {strategy.name} paused"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause strategy: {str(e)}")


@router.post("/strategies/{strategy_id}/resume", response_model=APIResponse)
async def resume_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Resume a paused strategy."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Resume strategy
        await trader.resume_strategy(strategy_id)
        
        return APIResponse(
            success=True,
            message=f"Strategy {strategy.name} resumed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume strategy: {str(e)}")
