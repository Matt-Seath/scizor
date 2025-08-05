"""Order management API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, and_

from shared.database.connection import get_db
from shared.database.models import Order
from shared.models.schemas import APIResponse, OrderResponse, OrderUpdate
from ..services.trader import AlgoTrader

router = APIRouter()


def get_trader() -> AlgoTrader:
    """Get the trader instance."""
    return AlgoTrader()


@router.get("/", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(None, description="Filter by order status (pending, filled, cancelled, rejected)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for order history"),
    end_date: Optional[datetime] = Query(None, description="End date for order history"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    db: AsyncSession = Depends(get_db)
):
    """List orders with optional filtering."""
    try:
        query = db.query(Order)
        
        # Apply filters
        if status:
            query = query.filter(Order.status == status)
        if symbol:
            query = query.filter(Order.symbol == symbol)
        if strategy_id:
            query = query.filter(Order.strategy_id == strategy_id)
        if start_date:
            query = query.filter(Order.timestamp >= start_date)
        if end_date:
            query = query.filter(Order.timestamp <= end_date)
            
        # Order by most recent first
        query = query.order_by(desc(Order.timestamp)).offset(offset).limit(limit)
        orders = await query.all()
        
        return [
            OrderResponse(
                id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
                price=order.price,
                status=order.status,
                filled_quantity=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                timestamp=order.timestamp,
                strategy_id=order.strategy_id,
                commission=order.commission,
                order_ref=order.order_ref
            )
            for order in orders
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve orders: {str(e)}")


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get order by ID."""
    try:
        order = await db.get(Order, order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        return OrderResponse(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            status=order.status,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            timestamp=order.timestamp,
            strategy_id=order.strategy_id,
            commission=order.commission,
            order_ref=order.order_ref,
            error_message=order.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve order: {str(e)}")


@router.put("/{order_id}/cancel", response_model=APIResponse)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Cancel a pending order."""
    try:
        # Get order from database
        order = await db.get(Order, order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        if order.status not in ["pending", "partially_filled"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel order with status: {order.status}")
            
        # Cancel order through trader
        success = await trader.cancel_order(order_id)
        
        if success:
            # Update order status in database
            order.status = "cancelled"
            order.updated_at = datetime.now()
            await db.commit()
            
            return APIResponse(
                success=True,
                message="Order cancelled successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to cancel order")
            
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")


@router.put("/{order_id}/modify", response_model=APIResponse)
async def modify_order(
    order_id: int,
    order_update: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Modify a pending order."""
    try:
        # Get order from database
        order = await db.get(Order, order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        if order.status not in ["pending", "partially_filled"]:
            raise HTTPException(status_code=400, detail=f"Cannot modify order with status: {order.status}")
            
        # Modify order through trader
        success = await trader.modify_order(order_id, order_update)
        
        if success:
            # Update order in database
            if order_update.quantity is not None:
                order.quantity = order_update.quantity
            if order_update.price is not None:
                order.price = order_update.price
            if order_update.order_type is not None:
                order.order_type = order_update.order_type
                
            order.updated_at = datetime.now()
            await db.commit()
            
            return APIResponse(
                success=True,
                message="Order modified successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to modify order")
            
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to modify order: {str(e)}")


@router.get("/status/summary", response_model=Dict[str, Any])
async def get_order_status_summary(
    timeframe: str = Query("1d", description="Timeframe for summary (1h, 1d, 1w, 1m)"),
    db: AsyncSession = Depends(get_db)
):
    """Get summary of order statuses over a timeframe."""
    try:
        # Calculate start time based on timeframe
        now = datetime.now()
        if timeframe == "1h":
            start_time = now - timedelta(hours=1)
        elif timeframe == "1d":
            start_time = now - timedelta(days=1)
        elif timeframe == "1w":
            start_time = now - timedelta(weeks=1)
        elif timeframe == "1m":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)
            
        # Get orders in timeframe
        orders = await db.query(Order).filter(
            Order.timestamp >= start_time
        ).all()
        
        # Calculate summary statistics
        total_orders = len(orders)
        status_counts = {}
        total_volume = 0
        filled_volume = 0
        total_commission = 0
        
        for order in orders:
            # Count by status
            status = order.status
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate volumes
            if order.quantity:
                total_volume += order.quantity
            if order.filled_quantity:
                filled_volume += order.filled_quantity
            if order.commission:
                total_commission += order.commission
                
        # Calculate fill rate
        fill_rate = (filled_volume / total_volume * 100) if total_volume > 0 else 0
        
        return {
            "timeframe": timeframe,
            "period": {
                "start": start_time.isoformat(),
                "end": now.isoformat()
            },
            "summary": {
                "total_orders": total_orders,
                "total_volume": round(total_volume, 2),
                "filled_volume": round(filled_volume, 2),
                "fill_rate": round(fill_rate, 2),
                "total_commission": round(total_commission, 2)
            },
            "status_breakdown": status_counts,
            "averages": {
                "avg_order_size": round(total_volume / total_orders, 2) if total_orders > 0 else 0,
                "avg_commission_per_order": round(total_commission / total_orders, 4) if total_orders > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get order summary: {str(e)}")


@router.get("/pending", response_model=List[OrderResponse])
async def get_pending_orders(
    db: AsyncSession = Depends(get_db)
):
    """Get all pending orders."""
    try:
        orders = await db.query(Order).filter(
            Order.status.in_(["pending", "partially_filled"])
        ).order_by(desc(Order.timestamp)).all()
        
        return [
            OrderResponse(
                id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
                price=order.price,
                status=order.status,
                filled_quantity=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                timestamp=order.timestamp,
                strategy_id=order.strategy_id,
                commission=order.commission,
                order_ref=order.order_ref
            )
            for order in orders
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pending orders: {str(e)}")


@router.get("/fills/recent", response_model=List[OrderResponse])
async def get_recent_fills(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    db: AsyncSession = Depends(get_db)
):
    """Get recently filled orders."""
    try:
        start_time = datetime.now() - timedelta(hours=hours)
        
        orders = await db.query(Order).filter(
            and_(
                Order.status.in_(["filled", "partially_filled"]),
                Order.timestamp >= start_time
            )
        ).order_by(desc(Order.timestamp)).all()
        
        return [
            OrderResponse(
                id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
                price=order.price,
                status=order.status,
                filled_quantity=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                timestamp=order.timestamp,
                strategy_id=order.strategy_id,
                commission=order.commission,
                order_ref=order.order_ref
            )
            for order in orders
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve recent fills: {str(e)}")


@router.post("/cancel-all", response_model=APIResponse)
async def cancel_all_pending_orders(
    strategy_id: Optional[int] = Query(None, description="Cancel orders for specific strategy only"),
    symbol: Optional[str] = Query(None, description="Cancel orders for specific symbol only"),
    db: AsyncSession = Depends(get_db),
    trader: AlgoTrader = Depends(get_trader)
):
    """Cancel all pending orders (optionally filtered by strategy or symbol)."""
    try:
        # Build query for pending orders
        query = db.query(Order).filter(
            Order.status.in_(["pending", "partially_filled"])
        )
        
        if strategy_id:
            query = query.filter(Order.strategy_id == strategy_id)
        if symbol:
            query = query.filter(Order.symbol == symbol)
            
        pending_orders = await query.all()
        
        if not pending_orders:
            return APIResponse(
                success=True,
                message="No pending orders to cancel"
            )
            
        # Cancel orders through trader
        cancelled_count = 0
        failed_count = 0
        
        for order in pending_orders:
            try:
                success = await trader.cancel_order(order.id)
                if success:
                    order.status = "cancelled"
                    order.updated_at = datetime.now()
                    cancelled_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
                
        await db.commit()
        
        return APIResponse(
            success=True,
            message=f"Cancelled {cancelled_count} orders, {failed_count} failed",
            data={
                "cancelled": cancelled_count,
                "failed": failed_count,
                "total": len(pending_orders)
            }
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel orders: {str(e)}")


@router.get("/analytics/performance", response_model=Dict[str, Any])
async def get_order_performance_analytics(
    timeframe: str = Query("1d", description="Timeframe for analytics"),
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get order execution performance analytics."""
    try:
        # Calculate start time
        now = datetime.now()
        if timeframe == "1h":
            start_time = now - timedelta(hours=1)
        elif timeframe == "1d":
            start_time = now - timedelta(days=1)
        elif timeframe == "1w":
            start_time = now - timedelta(weeks=1)
        else:
            start_time = now - timedelta(days=1)
            
        # Build query
        query = db.query(Order).filter(Order.timestamp >= start_time)
        if strategy_id:
            query = query.filter(Order.strategy_id == strategy_id)
            
        orders = await query.all()
        
        if not orders:
            return {"message": "No orders found in timeframe"}
            
        # Calculate analytics
        filled_orders = [o for o in orders if o.status == "filled"]
        rejected_orders = [o for o in orders if o.status == "rejected"]
        
        total_orders = len(orders)
        fill_rate = len(filled_orders) / total_orders * 100 if total_orders > 0 else 0
        reject_rate = len(rejected_orders) / total_orders * 100 if total_orders > 0 else 0
        
        # Calculate slippage for filled orders
        slippage_data = []
        for order in filled_orders:
            if order.price and order.avg_fill_price:
                slippage = abs(order.avg_fill_price - order.price) / order.price * 100
                slippage_data.append(slippage)
                
        avg_slippage = sum(slippage_data) / len(slippage_data) if slippage_data else 0
        
        return {
            "timeframe": timeframe,
            "analytics": {
                "total_orders": total_orders,
                "filled_orders": len(filled_orders),
                "rejected_orders": len(rejected_orders),
                "fill_rate": round(fill_rate, 2),
                "reject_rate": round(reject_rate, 2),
                "avg_slippage": round(avg_slippage, 4)
            },
            "execution_quality": {
                "fast_fills": len([o for o in filled_orders if True]),  # Would calculate actual speed
                "price_improvement": 0,  # Would calculate actual price improvement
                "market_impact": 0  # Would calculate market impact
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get order analytics: {str(e)}")
