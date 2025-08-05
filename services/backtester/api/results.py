"""Results and trades API endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc

from shared.database.connection import get_db
from shared.database.models import Backtest, Trade
from shared.models.schemas import TradeResponse

router = APIRouter()


@router.get("/{backtest_id}/trades", response_model=List[TradeResponse])
async def get_backtest_trades(
    backtest_id: int,
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of trades to return"),
    offset: int = Query(0, ge=0, description="Number of trades to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get all trades from a backtest."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Get trades
        query = db.query(Trade).filter(
            Trade.backtest_id == backtest_id
        ).order_by(desc(Trade.timestamp)).offset(offset).limit(limit)
        
        trades = await query.all()
        
        return [
            TradeResponse(
                id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                timestamp=trade.timestamp,
                commission=trade.commission,
                pnl=trade.pnl,
                strategy_id=trade.strategy_id,
                backtest_id=trade.backtest_id
            )
            for trade in trades
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trades: {str(e)}")


@router.get("/{backtest_id}/summary", response_model=Dict[str, Any])
async def get_backtest_summary(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive summary of backtest results."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Get trade statistics
        trades = await db.query(Trade).filter(Trade.backtest_id == backtest_id).all()
        
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl and t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl and t.pnl < 0])
        
        total_pnl = sum([t.pnl for t in trades if t.pnl]) if trades else 0
        total_commission = sum([t.commission for t in trades if t.commission]) if trades else 0
        
        # Calculate additional metrics
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        avg_win = sum([t.pnl for t in trades if t.pnl and t.pnl > 0]) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum([t.pnl for t in trades if t.pnl and t.pnl < 0]) / losing_trades if losing_trades > 0 else 0
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if avg_loss != 0 and losing_trades > 0 else 0
        
        return {
            "backtest_id": backtest.id,
            "status": backtest.status,
            "period": {
                "start_date": backtest.start_date.isoformat(),
                "end_date": backtest.end_date.isoformat(),
                "duration_days": (backtest.end_date - backtest.start_date).days
            },
            "capital": {
                "initial_capital": float(backtest.initial_capital),
                "final_capital": float(backtest.initial_capital + total_pnl),
                "total_return": float(backtest.total_return) if backtest.total_return else 0,
                "total_return_pct": float(total_pnl / backtest.initial_capital * 100) if backtest.initial_capital else 0
            },
            "trades": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 2)
            },
            "performance": {
                "total_pnl": round(total_pnl, 2),
                "total_commission": round(total_commission, 2),
                "net_pnl": round(total_pnl - total_commission, 2),
                "sharpe_ratio": float(backtest.sharpe_ratio) if backtest.sharpe_ratio else 0,
                "max_drawdown": float(backtest.max_drawdown) if backtest.max_drawdown else 0,
                "max_drawdown_pct": float(backtest.max_drawdown / backtest.initial_capital * 100) if backtest.max_drawdown and backtest.initial_capital else 0
            },
            "execution": {
                "created_at": backtest.created_at.isoformat(),
                "completed_at": backtest.completed_at.isoformat() if backtest.completed_at else None,
                "execution_time": str(backtest.completed_at - backtest.created_at) if backtest.completed_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.get("/{backtest_id}/equity-curve", response_model=List[Dict[str, Any]])
async def get_equity_curve(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get equity curve data for plotting."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Get trades ordered by timestamp
        trades = await db.query(Trade).filter(
            Trade.backtest_id == backtest_id
        ).order_by(Trade.timestamp).all()
        
        if not trades:
            return []
            
        # Calculate cumulative equity
        equity_curve = []
        cumulative_pnl = 0
        current_equity = float(backtest.initial_capital)
        
        # Add starting point
        equity_curve.append({
            "timestamp": backtest.start_date.isoformat(),
            "equity": current_equity,
            "pnl": 0,
            "drawdown": 0,
            "trade_count": 0
        })
        
        peak_equity = current_equity
        
        for i, trade in enumerate(trades):
            if trade.pnl:
                cumulative_pnl += trade.pnl
                current_equity = float(backtest.initial_capital) + cumulative_pnl
                
                # Update peak for drawdown calculation
                if current_equity > peak_equity:
                    peak_equity = current_equity
                    
                drawdown = (peak_equity - current_equity) / peak_equity * 100 if peak_equity > 0 else 0
                
                equity_curve.append({
                    "timestamp": trade.timestamp.isoformat(),
                    "equity": round(current_equity, 2),
                    "pnl": round(cumulative_pnl, 2),
                    "drawdown": round(drawdown, 2),
                    "trade_count": i + 1
                })
                
        return equity_curve
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate equity curve: {str(e)}")


@router.get("/{backtest_id}/monthly-returns", response_model=List[Dict[str, Any]])
async def get_monthly_returns(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get monthly returns breakdown."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Get trades
        trades = await db.query(Trade).filter(
            Trade.backtest_id == backtest_id
        ).order_by(Trade.timestamp).all()
        
        if not trades:
            return []
            
        # Group trades by month
        monthly_data = {}
        
        for trade in trades:
            if trade.pnl:
                month_key = trade.timestamp.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "year": trade.timestamp.year,
                        "month": trade.timestamp.month,
                        "month_name": trade.timestamp.strftime("%B"),
                        "pnl": 0,
                        "trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0
                    }
                
                monthly_data[month_key]["pnl"] += trade.pnl
                monthly_data[month_key]["trades"] += 1
                
                if trade.pnl > 0:
                    monthly_data[month_key]["winning_trades"] += 1
                else:
                    monthly_data[month_key]["losing_trades"] += 1
        
        # Convert to list and calculate percentages
        monthly_returns = []
        for month_key in sorted(monthly_data.keys()):
            data = monthly_data[month_key]
            win_rate = (data["winning_trades"] / data["trades"] * 100) if data["trades"] > 0 else 0
            
            monthly_returns.append({
                "period": month_key,
                "year": data["year"],
                "month": data["month"],
                "month_name": data["month_name"],
                "pnl": round(data["pnl"], 2),
                "return_pct": round(data["pnl"] / backtest.initial_capital * 100, 2),
                "trades": data["trades"],
                "win_rate": round(win_rate, 2)
            })
            
        return monthly_returns
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate monthly returns: {str(e)}")


@router.get("/{backtest_id}/drawdown-periods", response_model=List[Dict[str, Any]])
async def get_drawdown_periods(
    backtest_id: int,
    min_drawdown_pct: float = Query(1.0, description="Minimum drawdown percentage to include"),
    db: AsyncSession = Depends(get_db)
):
    """Get significant drawdown periods."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Get equity curve data
        equity_data = await get_equity_curve(backtest_id, db)
        
        if len(equity_data) < 2:
            return []
            
        # Find drawdown periods
        drawdown_periods = []
        in_drawdown = False
        drawdown_start = None
        peak_equity = equity_data[0]["equity"]
        max_drawdown_in_period = 0
        
        for point in equity_data[1:]:
            current_equity = point["equity"]
            
            # Update peak
            if current_equity > peak_equity:
                # End of drawdown period
                if in_drawdown and max_drawdown_in_period >= min_drawdown_pct:
                    drawdown_periods.append({
                        "start_date": drawdown_start,
                        "end_date": point["timestamp"],
                        "peak_equity": round(peak_equity, 2),
                        "trough_equity": round(current_equity, 2),
                        "max_drawdown_pct": round(max_drawdown_in_period, 2),
                        "max_drawdown_amount": round(peak_equity * max_drawdown_in_period / 100, 2),
                        "recovery_time_days": (datetime.fromisoformat(point["timestamp"]) - 
                                             datetime.fromisoformat(drawdown_start)).days if drawdown_start else 0
                    })
                    
                peak_equity = current_equity
                in_drawdown = False
                max_drawdown_in_period = 0
            else:
                # In drawdown
                if not in_drawdown:
                    drawdown_start = point["timestamp"]
                    in_drawdown = True
                    
                current_drawdown = (peak_equity - current_equity) / peak_equity * 100
                max_drawdown_in_period = max(max_drawdown_in_period, current_drawdown)
                
        return drawdown_periods
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate drawdown periods: {str(e)}")


@router.get("/{backtest_id}/export", response_model=Dict[str, Any])
async def export_backtest_results(
    backtest_id: int,
    format: str = Query("json", description="Export format (json, csv)"),
    db: AsyncSession = Depends(get_db)
):
    """Export backtest results in various formats."""
    try:
        # Get comprehensive backtest data
        summary = await get_backtest_summary(backtest_id, db)
        trades = await get_backtest_trades(backtest_id, limit=10000, db=db)
        equity_curve = await get_equity_curve(backtest_id, db)
        
        export_data = {
            "backtest_summary": summary,
            "trades": [trade.dict() for trade in trades],
            "equity_curve": equity_curve,
            "export_timestamp": datetime.now().isoformat(),
            "format": format
        }
        
        if format == "json":
            return export_data
        else:
            # For other formats, return download URL or processed data
            return {
                "message": f"Export in {format} format",
                "data": export_data,
                "download_url": f"/api/v1/results/{backtest_id}/download?format={format}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export results: {str(e)}")
