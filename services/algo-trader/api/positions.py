"""Position management API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc

from shared.database.connection import get_db
from shared.database.models import Position
from shared.models.schemas import APIResponse, PositionResponse
from ..services.trader import AlgoTrader

router = APIRouter()


def get_trader() -> AlgoTrader:
    """Get the trader instance."""
    return AlgoTrader()


@router.get("/", response_model=List[PositionResponse])
async def list_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    open_only: bool = Query(True, description="Show only open positions"),
    db: AsyncSession = Depends(get_db)
):
    """List all positions with optional filtering."""
    try:
        query = db.query(Position)
        
        # Apply filters
        if symbol:
            query = query.filter(Position.symbol == symbol)
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
        if open_only:
            query = query.filter(Position.quantity != 0)
            
        positions = await query.order_by(desc(Position.updated_at)).all()
        
        return [
            PositionResponse(
                id=position.id,
                symbol=position.symbol,
                quantity=position.quantity,
                avg_price=position.avg_price,
                current_price=position.current_price,
                market_value=position.market_value,
                unrealized_pnl=position.unrealized_pnl,
                realized_pnl=position.realized_pnl,
                strategy_id=position.strategy_id,
                updated_at=position.updated_at
            )
            for position in positions
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve positions: {str(e)}")


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get position by ID."""
    try:
        position = await db.get(Position, position_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
            
        return PositionResponse(
            id=position.id,
            symbol=position.symbol,
            quantity=position.quantity,
            avg_price=position.avg_price,
            current_price=position.current_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            strategy_id=position.strategy_id,
            updated_at=position.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve position: {str(e)}")


@router.get("/symbol/{symbol}", response_model=PositionResponse)
async def get_position_by_symbol(
    symbol: str,
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get position for a specific symbol."""
    try:
        query = db.query(Position).filter(Position.symbol == symbol)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        position = await query.first()
        
        if not position:
            raise HTTPException(status_code=404, detail=f"No position found for symbol {symbol}")
            
        return PositionResponse(
            id=position.id,
            symbol=position.symbol,
            quantity=position.quantity,
            avg_price=position.avg_price,
            current_price=position.current_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            strategy_id=position.strategy_id,
            updated_at=position.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve position for {symbol}: {str(e)}")


@router.post("/{position_id}/close", response_model=APIResponse)
async def close_position(
    position_id: int,
    quantity: Optional[float] = Query(None, description="Quantity to close (None for full position)"),
    order_type: str = Query("MKT", description="Order type for closing"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Close a position (partially or completely)."""
    try:
        # Get position
        position = await db.get(Position, position_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
            
        if position.quantity == 0:
            raise HTTPException(status_code=400, detail="Position is already closed")
            
        # Determine quantity to close
        close_quantity = quantity if quantity is not None else abs(position.quantity)
        
        if close_quantity > abs(position.quantity):
            raise HTTPException(status_code=400, detail="Cannot close more than current position size")
            
        # Submit closing order through trader
        order_id = await trader.close_position(position_id, close_quantity, order_type)
        
        return APIResponse(
            success=True,
            message=f"Position closing order submitted",
            data={"order_id": order_id, "quantity": close_quantity}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")


@router.post("/symbol/{symbol}/close", response_model=APIResponse)
async def close_position_by_symbol(
    symbol: str,
    quantity: Optional[float] = Query(None, description="Quantity to close (None for full position)"),
    order_type: str = Query("MKT", description="Order type for closing"),
    strategy_id: Optional[int] = Query(None, description="Strategy ID filter"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Close position by symbol."""
    try:
        # Find position by symbol
        query = db.query(Position).filter(Position.symbol == symbol, Position.quantity != 0)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        position = await query.first()
        
        if not position:
            raise HTTPException(status_code=404, detail=f"No open position found for symbol {symbol}")
            
        # Close the position
        close_quantity = quantity if quantity is not None else abs(position.quantity)
        order_id = await trader.close_position(position.id, close_quantity, order_type)
        
        return APIResponse(
            success=True,
            message=f"Position closing order submitted for {symbol}",
            data={"order_id": order_id, "quantity": close_quantity}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close position for {symbol}: {str(e)}")


@router.post("/close-all", response_model=APIResponse)
async def close_all_positions(
    strategy_id: Optional[int] = Query(None, description="Close positions for specific strategy only"),
    order_type: str = Query("MKT", description="Order type for closing"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Close all open positions."""
    try:
        # Get all open positions
        query = db.query(Position).filter(Position.quantity != 0)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.all()
        
        if not positions:
            return APIResponse(
                success=True,
                message="No open positions to close"
            )
            
        # Close all positions
        closed_count = 0
        failed_count = 0
        order_ids = []
        
        for position in positions:
            try:
                order_id = await trader.close_position(position.id, abs(position.quantity), order_type)
                order_ids.append(order_id)
                closed_count += 1
            except Exception:
                failed_count += 1
                
        return APIResponse(
            success=True,
            message=f"Submitted {closed_count} closing orders, {failed_count} failed",
            data={
                "closed": closed_count,
                "failed": failed_count,
                "total": len(positions),
                "order_ids": order_ids
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close all positions: {str(e)}")


@router.get("/summary", response_model=Dict[str, Any])
async def get_positions_summary(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get summary of all positions."""
    try:
        query = db.query(Position)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.all()
        
        # Calculate summary statistics
        open_positions = [p for p in positions if p.quantity != 0]
        long_positions = [p for p in open_positions if p.quantity > 0]
        short_positions = [p for p in open_positions if p.quantity < 0]
        
        total_market_value = sum([p.market_value for p in open_positions if p.market_value])
        total_unrealized_pnl = sum([p.unrealized_pnl for p in open_positions if p.unrealized_pnl])
        total_realized_pnl = sum([p.realized_pnl for p in positions if p.realized_pnl])
        
        # Calculate exposure
        long_exposure = sum([p.market_value for p in long_positions if p.market_value and p.market_value > 0])
        short_exposure = abs(sum([p.market_value for p in short_positions if p.market_value and p.market_value < 0]))
        gross_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure
        
        return {
            "summary": {
                "total_positions": len(positions),
                "open_positions": len(open_positions),
                "long_positions": len(long_positions),
                "short_positions": len(short_positions)
            },
            "value": {
                "total_market_value": round(total_market_value, 2),
                "unrealized_pnl": round(total_unrealized_pnl, 2),
                "realized_pnl": round(total_realized_pnl, 2),
                "total_pnl": round(total_unrealized_pnl + total_realized_pnl, 2)
            },
            "exposure": {
                "long_exposure": round(long_exposure, 2),
                "short_exposure": round(short_exposure, 2),
                "gross_exposure": round(gross_exposure, 2),
                "net_exposure": round(net_exposure, 2),
                "leverage": round(gross_exposure / max(abs(net_exposure), 1), 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get positions summary: {str(e)}")


@router.put("/{position_id}/update-prices", response_model=APIResponse)
async def update_position_prices(
    position_id: int,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Update current prices for a position."""
    try:
        position = await db.get(Position, position_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
            
        # Update prices through trader
        updated = await trader.update_position_prices(position_id)
        
        if updated:
            await db.refresh(position)
            
            return APIResponse(
                success=True,
                message="Position prices updated",
                data={
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "unrealized_pnl": position.unrealized_pnl
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to update prices")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update position prices: {str(e)}")


@router.post("/update-all-prices", response_model=APIResponse)
async def update_all_position_prices(
    trader: AlgoTrader = Depends(get_trader)
):
    """Update current prices for all positions."""
    try:
        updated_count = await trader.update_all_position_prices()
        
        return APIResponse(
            success=True,
            message=f"Updated prices for {updated_count} positions"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update all position prices: {str(e)}")


@router.get("/pnl/history", response_model=List[Dict[str, Any]])
async def get_pnl_history(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get P&L history over time."""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        query = db.query(Position).filter(Position.updated_at >= start_date)
        
        if strategy_id:
            query = query.filter(Position.strategy_id == strategy_id)
            
        positions = await query.order_by(Position.updated_at).all()
        
        # Group by date and calculate daily P&L
        daily_pnl = {}
        
        for position in positions:
            date_key = position.updated_at.date()
            
            if date_key not in daily_pnl:
                daily_pnl[date_key] = {
                    "date": date_key.isoformat(),
                    "unrealized_pnl": 0,
                    "realized_pnl": 0,
                    "total_pnl": 0,
                    "positions_count": 0
                }
                
            daily_pnl[date_key]["unrealized_pnl"] += position.unrealized_pnl or 0
            daily_pnl[date_key]["realized_pnl"] += position.realized_pnl or 0
            daily_pnl[date_key]["total_pnl"] += (position.unrealized_pnl or 0) + (position.realized_pnl or 0)
            daily_pnl[date_key]["positions_count"] += 1
            
        # Convert to sorted list
        pnl_history = []
        for date_key in sorted(daily_pnl.keys()):
            data = daily_pnl[date_key]
            pnl_history.append({
                "date": data["date"],
                "unrealized_pnl": round(data["unrealized_pnl"], 2),
                "realized_pnl": round(data["realized_pnl"], 2),
                "total_pnl": round(data["total_pnl"], 2),
                "positions_count": data["positions_count"]
            })
            
        return pnl_history
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get P&L history: {str(e)}")
