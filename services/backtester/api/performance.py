"""Performance analytics API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import statistics

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func

from shared.database.connection import get_db
from shared.database.models import Backtest, Trade, Strategy

router = APIRouter()


@router.get("/strategies/{strategy_id}/performance", response_model=Dict[str, Any])
async def get_strategy_performance(
    strategy_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive performance analytics for a strategy across all backtests."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Get all completed backtests for this strategy
        backtests = await db.query(Backtest).filter(
            Backtest.strategy_id == strategy_id,
            Backtest.status == "completed"
        ).all()
        
        if not backtests:
            raise HTTPException(status_code=404, detail="No completed backtests found for strategy")
            
        # Calculate aggregate performance metrics
        total_returns = [b.total_return for b in backtests if b.total_return]
        sharpe_ratios = [b.sharpe_ratio for b in backtests if b.sharpe_ratio]
        max_drawdowns = [b.max_drawdown for b in backtests if b.max_drawdown]
        
        # Get all trades for this strategy
        all_trades = await db.query(Trade).filter(
            Trade.strategy_id == strategy_id,
            Trade.backtest_id.in_([b.id for b in backtests])
        ).all()
        
        # Calculate trade statistics
        total_trades = len(all_trades)
        winning_trades = len([t for t in all_trades if t.pnl and t.pnl > 0])
        losing_trades = len([t for t in all_trades if t.pnl and t.pnl < 0])
        
        return {
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "backtests_count": len(backtests),
            "performance_summary": {
                "avg_return": round(statistics.mean(total_returns), 4) if total_returns else 0,
                "median_return": round(statistics.median(total_returns), 4) if total_returns else 0,
                "std_return": round(statistics.stdev(total_returns), 4) if len(total_returns) > 1 else 0,
                "min_return": round(min(total_returns), 4) if total_returns else 0,
                "max_return": round(max(total_returns), 4) if total_returns else 0,
                "avg_sharpe": round(statistics.mean(sharpe_ratios), 4) if sharpe_ratios else 0,
                "avg_max_drawdown": round(statistics.mean(max_drawdowns), 4) if max_drawdowns else 0
            },
            "trade_statistics": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(winning_trades / total_trades * 100, 2) if total_trades > 0 else 0,
                "avg_trades_per_backtest": round(total_trades / len(backtests), 1) if backtests else 0
            },
            "consistency_metrics": {
                "positive_backtests": len([b for b in backtests if b.total_return and b.total_return > 0]),
                "negative_backtests": len([b for b in backtests if b.total_return and b.total_return <= 0]),
                "consistency_ratio": round(len([b for b in backtests if b.total_return and b.total_return > 0]) / len(backtests) * 100, 2) if backtests else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get strategy performance: {str(e)}")


@router.get("/strategies/compare", response_model=Dict[str, Any])
async def compare_strategies(
    strategy_ids: List[int] = Query(..., description="List of strategy IDs to compare"),
    metric: str = Query("total_return", description="Metric to compare (total_return, sharpe_ratio, max_drawdown)"),
    db: AsyncSession = Depends(get_db)
):
    """Compare performance of multiple strategies."""
    try:
        if len(strategy_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 strategies required for comparison")
            
        comparison_data = []
        
        for strategy_id in strategy_ids:
            strategy = await db.get(Strategy, strategy_id)
            if not strategy:
                continue
                
            # Get completed backtests
            backtests = await db.query(Backtest).filter(
                Backtest.strategy_id == strategy_id,
                Backtest.status == "completed"
            ).all()
            
            if not backtests:
                continue
                
            # Calculate metrics based on selected metric
            if metric == "total_return":
                values = [b.total_return for b in backtests if b.total_return]
            elif metric == "sharpe_ratio":
                values = [b.sharpe_ratio for b in backtests if b.sharpe_ratio]
            elif metric == "max_drawdown":
                values = [b.max_drawdown for b in backtests if b.max_drawdown]
            else:
                values = [b.total_return for b in backtests if b.total_return]
                
            if values:
                comparison_data.append({
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "backtests_count": len(backtests),
                    "avg_value": round(statistics.mean(values), 4),
                    "median_value": round(statistics.median(values), 4),
                    "std_value": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
                    "min_value": round(min(values), 4),
                    "max_value": round(max(values), 4)
                })
                
        # Sort by average value (descending for returns, ascending for drawdown)
        reverse_sort = metric != "max_drawdown"
        comparison_data.sort(key=lambda x: x["avg_value"], reverse=reverse_sort)
        
        return {
            "metric": metric,
            "strategies_compared": len(comparison_data),
            "comparison_data": comparison_data,
            "best_strategy": comparison_data[0] if comparison_data else None,
            "worst_strategy": comparison_data[-1] if comparison_data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare strategies: {str(e)}")


@router.get("/risk-metrics/{backtest_id}", response_model=Dict[str, Any])
async def get_risk_metrics(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Calculate detailed risk metrics for a backtest."""
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
            return {"error": "No trades found for backtest"}
            
        # Calculate daily returns
        daily_pnl = {}
        for trade in trades:
            if trade.pnl:
                date_key = trade.timestamp.date()
                if date_key not in daily_pnl:
                    daily_pnl[date_key] = 0
                daily_pnl[date_key] += trade.pnl
                
        daily_returns = []
        cumulative_capital = float(backtest.initial_capital)
        
        for date in sorted(daily_pnl.keys()):
            daily_return = daily_pnl[date] / cumulative_capital
            daily_returns.append(daily_return)
            cumulative_capital += daily_pnl[date]
            
        if not daily_returns:
            return {"error": "No returns data available"}
            
        # Calculate risk metrics
        avg_daily_return = statistics.mean(daily_returns)
        std_daily_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
        
        # Annualized metrics (assuming 252 trading days)
        annualized_return = avg_daily_return * 252
        annualized_volatility = std_daily_return * (252 ** 0.5)
        
        # Sharpe ratio (assuming risk-free rate of 2%)
        risk_free_rate = 0.02
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility if annualized_volatility > 0 else 0
        
        # Sortino ratio (using downside deviation)
        negative_returns = [r for r in daily_returns if r < 0]
        downside_deviation = statistics.stdev(negative_returns) * (252 ** 0.5) if len(negative_returns) > 1 else 0
        sortino_ratio = (annualized_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(backtest.max_drawdown) if backtest.max_drawdown and backtest.max_drawdown != 0 else 0
        
        # Value at Risk (VaR) - 95% confidence
        sorted_returns = sorted(daily_returns)
        var_95 = sorted_returns[int(len(sorted_returns) * 0.05)] if len(sorted_returns) > 20 else 0
        
        # Maximum consecutive losing days
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        for ret in daily_returns:
            if ret < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
                
        return {
            "backtest_id": backtest.id,
            "return_metrics": {
                "total_return": float(backtest.total_return) if backtest.total_return else 0,
                "annualized_return": round(annualized_return * 100, 2),
                "avg_daily_return": round(avg_daily_return * 100, 4),
                "best_day": round(max(daily_returns) * 100, 2) if daily_returns else 0,
                "worst_day": round(min(daily_returns) * 100, 2) if daily_returns else 0
            },
            "risk_metrics": {
                "volatility": round(annualized_volatility * 100, 2),
                "max_drawdown": float(backtest.max_drawdown) if backtest.max_drawdown else 0,
                "value_at_risk_95": round(var_95 * 100, 2),
                "max_consecutive_losses": max_consecutive_losses
            },
            "risk_adjusted_returns": {
                "sharpe_ratio": round(sharpe_ratio, 3),
                "sortino_ratio": round(sortino_ratio, 3),
                "calmar_ratio": round(calmar_ratio, 3)
            },
            "trading_metrics": {
                "total_trading_days": len(daily_returns),
                "profitable_days": len([r for r in daily_returns if r > 0]),
                "losing_days": len([r for r in daily_returns if r < 0]),
                "flat_days": len([r for r in daily_returns if r == 0])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate risk metrics: {str(e)}")


@router.get("/portfolio-analysis", response_model=Dict[str, Any])
async def get_portfolio_analysis(
    strategy_ids: List[int] = Query(..., description="Strategy IDs to include in portfolio"),
    weights: Optional[List[float]] = Query(None, description="Portfolio weights (equal weight if not provided)"),
    rebalance_frequency: str = Query("monthly", description="Rebalancing frequency (daily, weekly, monthly)"),
    db: AsyncSession = Depends(get_db)
):
    """Analyze portfolio performance with multiple strategies."""
    try:
        if not strategy_ids:
            raise HTTPException(status_code=400, detail="At least one strategy required")
            
        # Set equal weights if not provided
        if not weights:
            weights = [1.0 / len(strategy_ids)] * len(strategy_ids)
        elif len(weights) != len(strategy_ids):
            raise HTTPException(status_code=400, detail="Number of weights must match number of strategies")
        elif abs(sum(weights) - 1.0) > 0.01:
            raise HTTPException(status_code=400, detail="Weights must sum to 1.0")
            
        portfolio_data = []
        
        for i, strategy_id in enumerate(strategy_ids):
            strategy = await db.get(Strategy, strategy_id)
            if not strategy:
                continue
                
            # Get most recent completed backtest
            backtest = await db.query(Backtest).filter(
                Backtest.strategy_id == strategy_id,
                Backtest.status == "completed"
            ).order_by(desc(Backtest.completed_at)).first()
            
            if backtest:
                portfolio_data.append({
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "weight": weights[i],
                    "total_return": float(backtest.total_return) if backtest.total_return else 0,
                    "sharpe_ratio": float(backtest.sharpe_ratio) if backtest.sharpe_ratio else 0,
                    "max_drawdown": float(backtest.max_drawdown) if backtest.max_drawdown else 0,
                    "weighted_return": (float(backtest.total_return) if backtest.total_return else 0) * weights[i]
                })
                
        if not portfolio_data:
            raise HTTPException(status_code=404, detail="No valid strategy data found")
            
        # Calculate portfolio metrics
        portfolio_return = sum([s["weighted_return"] for s in portfolio_data])
        
        # Simple portfolio metrics (would need more sophisticated correlation analysis)
        avg_sharpe = sum([s["sharpe_ratio"] * s["weight"] for s in portfolio_data])
        max_portfolio_drawdown = max([s["max_drawdown"] for s in portfolio_data])  # Conservative estimate
        
        return {
            "portfolio_composition": portfolio_data,
            "portfolio_metrics": {
                "total_return": round(portfolio_return, 4),
                "weighted_avg_sharpe": round(avg_sharpe, 3),
                "estimated_max_drawdown": round(max_portfolio_drawdown, 4),
                "diversification_ratio": round(len(strategy_ids) / sum([w**2 for w in weights]), 2)
            },
            "rebalancing": {
                "frequency": rebalance_frequency,
                "last_rebalance": datetime.now().isoformat(),
                "next_rebalance": (datetime.now() + timedelta(days=30)).isoformat()  # Example
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze portfolio: {str(e)}")


@router.get("/benchmarks/{backtest_id}", response_model=Dict[str, Any])
async def compare_to_benchmark(
    backtest_id: int,
    benchmark_symbol: str = Query("SPY", description="Benchmark symbol to compare against"),
    db: AsyncSession = Depends(get_db)
):
    """Compare backtest performance to a benchmark."""
    try:
        # Verify backtest exists
        backtest = await db.get(Backtest, backtest_id)
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # In a real implementation, would fetch benchmark data for the same period
        # For now, using approximate market returns
        benchmark_annual_return = 0.10  # 10% average for SPY
        benchmark_volatility = 0.16     # 16% volatility
        benchmark_sharpe = (benchmark_annual_return - 0.02) / benchmark_volatility
        
        # Calculate period return for benchmark
        period_days = (backtest.end_date - backtest.start_date).days
        benchmark_period_return = benchmark_annual_return * (period_days / 365)
        
        strategy_return = float(backtest.total_return) if backtest.total_return else 0
        strategy_sharpe = float(backtest.sharpe_ratio) if backtest.sharpe_ratio else 0
        
        return {
            "backtest_id": backtest.id,
            "benchmark_symbol": benchmark_symbol,
            "period": {
                "start_date": backtest.start_date.isoformat(),
                "end_date": backtest.end_date.isoformat(),
                "days": period_days
            },
            "performance_comparison": {
                "strategy_return": round(strategy_return * 100, 2),
                "benchmark_return": round(benchmark_period_return * 100, 2),
                "excess_return": round((strategy_return - benchmark_period_return) * 100, 2),
                "strategy_sharpe": round(strategy_sharpe, 3),
                "benchmark_sharpe": round(benchmark_sharpe, 3),
                "sharpe_difference": round(strategy_sharpe - benchmark_sharpe, 3)
            },
            "risk_comparison": {
                "strategy_max_drawdown": float(backtest.max_drawdown) if backtest.max_drawdown else 0,
                "benchmark_max_drawdown": -20.0,  # Approximate worst drawdown for SPY
                "beta": 1.0,  # Would calculate actual beta with benchmark data
                "alpha": round((strategy_return - benchmark_period_return) * 100, 2)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare to benchmark: {str(e)}")
