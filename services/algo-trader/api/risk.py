"""Risk management API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc

from shared.database.connection import get_db
from shared.database.models import Position, Order, RiskLimit
from shared.models.schemas import APIResponse
from ..services.trader import AlgoTrader

router = APIRouter()


def get_trader() -> AlgoTrader:
    """Get the trader instance."""
    return AlgoTrader()


@router.get("/limits", response_model=List[Dict[str, Any]])
async def get_risk_limits(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get all risk limits."""
    try:
        query = db.query(RiskLimit)
        
        if strategy_id:
            query = query.filter(RiskLimit.strategy_id == strategy_id)
            
        limits = await query.all()
        
        return [
            {
                "id": limit.id,
                "strategy_id": limit.strategy_id,
                "limit_type": limit.limit_type,
                "limit_value": limit.limit_value,
                "current_value": limit.current_value,
                "threshold_warning": limit.threshold_warning,
                "is_active": limit.is_active,
                "created_at": limit.created_at
            }
            for limit in limits
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve risk limits: {str(e)}")


@router.post("/limits", response_model=APIResponse)
async def create_risk_limit(
    strategy_id: int,
    limit_type: str,
    limit_value: float,
    threshold_warning: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a new risk limit."""
    try:
        # Validate limit type
        valid_types = ["max_position_size", "max_daily_loss", "max_drawdown", "max_exposure", "var_limit"]
        if limit_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid limit type. Must be one of: {valid_types}")
            
        risk_limit = RiskLimit(
            strategy_id=strategy_id,
            limit_type=limit_type,
            limit_value=limit_value,
            threshold_warning=threshold_warning or limit_value * 0.8,
            is_active=True
        )
        
        db.add(risk_limit)
        await db.commit()
        await db.refresh(risk_limit)
        
        return APIResponse(
            success=True,
            message=f"Risk limit created for {limit_type}",
            data={"limit_id": risk_limit.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create risk limit: {str(e)}")


@router.put("/limits/{limit_id}", response_model=APIResponse)
async def update_risk_limit(
    limit_id: int,
    limit_value: Optional[float] = None,
    threshold_warning: Optional[float] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing risk limit."""
    try:
        risk_limit = await db.get(RiskLimit, limit_id)
        
        if not risk_limit:
            raise HTTPException(status_code=404, detail="Risk limit not found")
            
        if limit_value is not None:
            risk_limit.limit_value = limit_value
        if threshold_warning is not None:
            risk_limit.threshold_warning = threshold_warning
        if is_active is not None:
            risk_limit.is_active = is_active
            
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Risk limit updated"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update risk limit: {str(e)}")


@router.delete("/limits/{limit_id}", response_model=APIResponse)
async def delete_risk_limit(
    limit_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a risk limit."""
    try:
        risk_limit = await db.get(RiskLimit, limit_id)
        
        if not risk_limit:
            raise HTTPException(status_code=404, detail="Risk limit not found")
            
        await db.delete(risk_limit)
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Risk limit deleted"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete risk limit: {str(e)}")


@router.get("/check", response_model=Dict[str, Any])
async def check_risk_compliance(
    strategy_id: Optional[int] = Query(None, description="Check specific strategy"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Check current risk compliance status."""
    try:
        risk_status = await trader.check_risk_compliance(strategy_id)
        
        return {
            "overall_status": "compliant" if risk_status["compliant"] else "violation",
            "risk_score": risk_status.get("risk_score", 0),
            "checks": risk_status.get("checks", []),
            "violations": risk_status.get("violations", []),
            "warnings": risk_status.get("warnings", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check risk compliance: {str(e)}")


@router.get("/exposure", response_model=Dict[str, Any])
async def get_risk_exposure(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Calculate current risk exposure metrics."""
    try:
        query = db.query(Position).filter(Position.quantity != 0)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.all()
        
        if not positions:
            return {
                "total_exposure": 0,
                "long_exposure": 0,
                "short_exposure": 0,
                "net_exposure": 0,
                "leverage": 0,
                "concentration": {},
                "var_1d": 0,
                "var_5d": 0
            }
            
        # Calculate exposure metrics
        long_exposure = sum([p.market_value for p in positions if p.quantity > 0 and p.market_value])
        short_exposure = abs(sum([p.market_value for p in positions if p.quantity < 0 and p.market_value]))
        gross_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure
        
        # Calculate concentration by symbol
        symbol_exposure = {}
        for position in positions:
            if position.market_value:
                symbol_exposure[position.symbol] = abs(position.market_value)
                
        total_exposure = sum(symbol_exposure.values())
        concentration = {
            symbol: round(exposure / total_exposure * 100, 2)
            for symbol, exposure in symbol_exposure.items()
            if total_exposure > 0
        }
        
        # Sort by concentration
        concentration = dict(sorted(concentration.items(), key=lambda x: x[1], reverse=True))
        
        # Simple VaR calculation (would be more sophisticated in practice)
        daily_volatility = 0.02  # Assume 2% daily volatility
        var_1d = gross_exposure * daily_volatility * 1.65  # 95% confidence
        var_5d = var_1d * (5 ** 0.5)  # Scale by sqrt of time
        
        return {
            "total_exposure": round(gross_exposure, 2),
            "long_exposure": round(long_exposure, 2),
            "short_exposure": round(short_exposure, 2),
            "net_exposure": round(net_exposure, 2),
            "leverage": round(gross_exposure / max(abs(net_exposure), 1), 2),
            "concentration": concentration,
            "var_1d_95": round(var_1d, 2),
            "var_5d_95": round(var_5d, 2),
            "max_concentration": max(concentration.values()) if concentration else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate risk exposure: {str(e)}")


@router.get("/drawdown", response_model=Dict[str, Any])
async def calculate_drawdown(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """Calculate drawdown metrics."""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        query = db.query(Position).filter(Position.updated_at >= start_date)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.order_by(Position.updated_at).all()
        
        if not positions:
            return {
                "max_drawdown": 0,
                "current_drawdown": 0,
                "drawdown_duration": 0,
                "recovery_factor": 0
            }
            
        # Calculate daily portfolio values
        daily_values = {}
        
        for position in positions:
            date_key = position.updated_at.date()
            
            if date_key not in daily_values:
                daily_values[date_key] = 0
                
            # Add unrealized + realized P&L
            daily_values[date_key] += (position.unrealized_pnl or 0) + (position.realized_pnl or 0)
            
        # Convert to sorted list of values
        sorted_dates = sorted(daily_values.keys())
        values = [daily_values[date] for date in sorted_dates]
        
        if not values:
            return {
                "max_drawdown": 0,
                "current_drawdown": 0,
                "drawdown_duration": 0,
                "recovery_factor": 0
            }
            
        # Calculate running maximum and drawdowns
        running_max = values[0]
        max_drawdown = 0
        current_drawdown = 0
        drawdown_start = None
        max_drawdown_duration = 0
        current_drawdown_duration = 0
        
        for i, value in enumerate(values):
            if value > running_max:
                running_max = value
                if drawdown_start is not None:
                    # End of drawdown period
                    max_drawdown_duration = max(max_drawdown_duration, current_drawdown_duration)
                    drawdown_start = None
                    current_drawdown_duration = 0
            else:
                if drawdown_start is None:
                    drawdown_start = i
                    current_drawdown_duration = 1
                else:
                    current_drawdown_duration += 1
                    
                drawdown = (running_max - value) / running_max if running_max > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
                
                # Current drawdown (if we're still in one)
                if i == len(values) - 1:
                    current_drawdown = drawdown
                    
        # Recovery factor (total return / max drawdown)
        total_return = (values[-1] - values[0]) / abs(values[0]) if values[0] != 0 else 0
        recovery_factor = total_return / max_drawdown if max_drawdown > 0 else 0
        
        return {
            "max_drawdown": round(max_drawdown * 100, 2),  # As percentage
            "current_drawdown": round(current_drawdown * 100, 2),
            "drawdown_duration": max_drawdown_duration,
            "recovery_factor": round(recovery_factor, 2),
            "analysis_period": days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate drawdown: {str(e)}")


@router.post("/emergency-stop", response_model=APIResponse)
async def emergency_stop(
    strategy_id: Optional[int] = Query(None, description="Stop specific strategy only"),
    reason: str = Query(..., description="Reason for emergency stop"),
    trader: AlgoTrader = Depends(get_trader)
):
    """Emergency stop - cancel all orders and close all positions."""
    try:
        result = await trader.emergency_stop(strategy_id, reason)
        
        return APIResponse(
            success=True,
            message=f"Emergency stop executed: {reason}",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute emergency stop: {str(e)}")


@router.get("/stress-test", response_model=Dict[str, Any])
async def run_stress_test(
    scenario: str = Query("market_crash", description="Stress test scenario"),
    strategy_id: Optional[int] = Query(None, description="Test specific strategy"),
    db: AsyncSession = Depends(get_db)
):
    """Run stress test scenarios on current portfolio."""
    try:
        query = db.query(Position).filter(Position.quantity != 0)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.all()
        
        if not positions:
            return {
                "scenario": scenario,
                "impact": 0,
                "positions_affected": 0,
                "recommendation": "No positions to test"
            }
            
        # Define stress scenarios
        scenarios = {
            "market_crash": {"equity_shock": -0.20, "volatility_spike": 2.0},
            "interest_rate_spike": {"rate_shock": 0.02, "duration_impact": -0.10},
            "liquidity_crisis": {"bid_ask_widen": 3.0, "volume_drop": -0.50},
            "flash_crash": {"instant_drop": -0.10, "recovery": 0.05},
            "sector_rotation": {"tech_drop": -0.15, "value_rise": 0.08}
        }
        
        if scenario not in scenarios:
            raise HTTPException(status_code=400, detail=f"Unknown scenario. Available: {list(scenarios.keys())}")
            
        scenario_params = scenarios[scenario]
        
        # Calculate impact based on scenario
        total_impact = 0
        positions_affected = 0
        
        for position in positions:
            if not position.market_value:
                continue
                
            position_impact = 0
            
            if scenario == "market_crash":
                # Assume all positions affected by market shock
                position_impact = position.market_value * scenario_params["equity_shock"]
                
            elif scenario == "interest_rate_spike":
                # Assume rate-sensitive assets affected more
                position_impact = position.market_value * scenario_params["duration_impact"]
                
            elif scenario == "liquidity_crisis":
                # Impact based on position size (larger = more liquidity impact)
                liquidity_factor = min(abs(position.market_value) / 100000, 1.0)  # Scale by position size
                position_impact = position.market_value * -0.05 * liquidity_factor
                
            elif scenario == "flash_crash":
                # Instant drop followed by partial recovery
                drop_impact = position.market_value * scenario_params["instant_drop"]
                recovery_impact = abs(drop_impact) * scenario_params["recovery"]
                position_impact = drop_impact + recovery_impact
                
            total_impact += position_impact
            if position_impact != 0:
                positions_affected += 1
                
        # Generate recommendation
        impact_percentage = (total_impact / sum([abs(p.market_value) for p in positions if p.market_value])) * 100
        
        if impact_percentage < -5:
            recommendation = "High risk - consider reducing exposure"
        elif impact_percentage < -2:
            recommendation = "Moderate risk - monitor closely"
        else:
            recommendation = "Low risk - within acceptable limits"
            
        return {
            "scenario": scenario,
            "total_impact": round(total_impact, 2),
            "impact_percentage": round(impact_percentage, 2),
            "positions_affected": positions_affected,
            "total_positions": len(positions),
            "recommendation": recommendation,
            "scenario_parameters": scenario_params
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run stress test: {str(e)}")


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_risk_alerts(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    db: AsyncSession = Depends(get_db)
):
    """Get current risk alerts and warnings."""
    try:
        alerts = []
        
        # Check risk limits
        query = db.query(RiskLimit).filter(RiskLimit.is_active == True)
        
        if strategy_id:
            query = query.filter(RiskLimit.strategy_id == strategy_id)
            
        limits = await query.all()
        
        for limit in limits:
            if limit.current_value is None:
                continue
                
            # Check if limit is breached
            if limit.current_value >= limit.limit_value:
                alerts.append({
                    "type": "limit_breach",
                    "severity": "critical",
                    "message": f"{limit.limit_type} limit breached: {limit.current_value} >= {limit.limit_value}",
                    "strategy_id": limit.strategy_id,
                    "timestamp": datetime.now()
                })
            elif limit.current_value >= limit.threshold_warning:
                alerts.append({
                    "type": "limit_warning",
                    "severity": "high",
                    "message": f"{limit.limit_type} approaching limit: {limit.current_value} >= {limit.threshold_warning}",
                    "strategy_id": limit.strategy_id,
                    "timestamp": datetime.now()
                })
                
        # Check position concentration
        position_query = db.query(Position).filter(Position.quantity != 0)
        if strategy_id:
            position_query = position_query.filter(Position.strategy_id == strategy_id)
            
        positions = await position_query.all()
        
        if positions:
            total_value = sum([abs(p.market_value) for p in positions if p.market_value])
            
            for position in positions:
                if position.market_value and total_value > 0:
                    concentration = abs(position.market_value) / total_value
                    
                    if concentration > 0.3:  # 30% concentration threshold
                        alerts.append({
                            "type": "concentration_risk",
                            "severity": "high" if concentration > 0.5 else "medium",
                            "message": f"High concentration in {position.symbol}: {concentration*100:.1f}%",
                            "strategy_id": position.strategy_id,
                            "timestamp": datetime.now()
                        })
                        
        # Filter by severity if requested
        if severity:
            alerts = [alert for alert in alerts if alert["severity"] == severity]
            
        # Sort by severity and timestamp
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["timestamp"]), reverse=True)
        
        return alerts[:50]  # Limit to 50 most recent alerts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get risk alerts: {str(e)}")


@router.post("/validate-order", response_model=Dict[str, Any])
async def validate_order_risk(
    symbol: str,
    quantity: float,
    order_type: str,
    strategy_id: Optional[int] = None,
    trader: AlgoTrader = Depends(get_trader)
):
    """Validate if an order passes risk checks before execution."""
    try:
        validation_result = await trader.validate_order_risk(
            symbol, quantity, order_type, strategy_id
        )
        
        return {
            "valid": validation_result["valid"],
            "risk_score": validation_result.get("risk_score", 0),
            "checks": validation_result.get("checks", []),
            "warnings": validation_result.get("warnings", []),
            "rejections": validation_result.get("rejections", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate order risk: {str(e)}")
