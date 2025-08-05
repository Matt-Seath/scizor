"""Backtest execution API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.connection import get_db
from shared.database.models import Strategy, Backtest
from shared.models.schemas import APIResponse, BacktestCreate, BacktestResponse
from ..services.engine import BacktestEngine

router = APIRouter()


@router.get("/", response_model=List[BacktestResponse])
async def list_backtests(
    strategy_id: Optional[int] = Query(None, description="Filter by strategy ID"),
    status: Optional[str] = Query(None, description="Filter by status (running, completed, failed)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of backtests to return"),
    offset: int = Query(0, ge=0, description="Number of backtests to skip"),
    db: AsyncSession = Depends(get_db)
):
    """List backtests with optional filtering."""
    try:
        query = db.query(Backtest)
        
        if strategy_id:
            query = query.filter(Backtest.strategy_id == strategy_id)
        if status:
            query = query.filter(Backtest.status == status)
            
        query = query.order_by(Backtest.created_at.desc()).offset(offset).limit(limit)
        backtests = await query.all()
        
        return [
            BacktestResponse(
                id=backtest.id,
                strategy_id=backtest.strategy_id,
                name=backtest.name,
                start_date=backtest.start_date,
                end_date=backtest.end_date,
                initial_capital=backtest.initial_capital,
                status=backtest.status,
                progress=backtest.progress or 0,
                total_return=backtest.total_return,
                sharpe_ratio=backtest.sharpe_ratio,
                max_drawdown=backtest.max_drawdown,
                created_at=backtest.created_at,
                completed_at=backtest.completed_at
            )
            for backtest in backtests
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve backtests: {str(e)}")


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get backtest by ID."""
    try:
        backtest = await db.get(Backtest, backtest_id)
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        return BacktestResponse(
            id=backtest.id,
            strategy_id=backtest.strategy_id,
            name=backtest.name,
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            initial_capital=backtest.initial_capital,
            status=backtest.status,
            progress=backtest.progress or 0,
            total_return=backtest.total_return,
            sharpe_ratio=backtest.sharpe_ratio,
            max_drawdown=backtest.max_drawdown,
            win_rate=backtest.win_rate,
            profit_factor=backtest.profit_factor,
            created_at=backtest.created_at,
            completed_at=backtest.completed_at,
            error_message=backtest.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve backtest: {str(e)}")


@router.post("/", response_model=APIResponse)
async def create_backtest(
    backtest: BacktestCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Create and start a new backtest."""
    try:
        # Verify strategy exists
        strategy = await db.get(Strategy, backtest.strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        if not strategy.active:
            raise HTTPException(status_code=400, detail="Strategy is not active")
            
        # Validate date range
        if backtest.start_date >= backtest.end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
            
        # Create backtest record
        new_backtest = Backtest(
            strategy_id=backtest.strategy_id,
            name=backtest.name or f"Backtest {strategy.name} {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            initial_capital=backtest.initial_capital,
            commission=backtest.commission,
            slippage=backtest.slippage,
            symbols=backtest.symbols,
            parameters=backtest.parameters,
            status="queued",
            progress=0,
            created_at=datetime.now()
        )
        
        db.add(new_backtest)
        await db.commit()
        await db.refresh(new_backtest)
        
        # Start backtest in background
        background_tasks.add_task(run_backtest, new_backtest.id)
        
        return APIResponse(
            success=True,
            message="Backtest created and queued for execution",
            data={"backtest_id": new_backtest.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create backtest: {str(e)}")


@router.post("/{backtest_id}/start", response_model=APIResponse)
async def start_backtest(
    backtest_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start or restart a backtest."""
    try:
        backtest = await db.get(Backtest, backtest_id)
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        if backtest.status == "running":
            raise HTTPException(status_code=400, detail="Backtest is already running")
            
        # Reset backtest status
        backtest.status = "queued"
        backtest.progress = 0
        backtest.error_message = None
        await db.commit()
        
        # Start backtest in background
        background_tasks.add_task(run_backtest, backtest_id)
        
        return APIResponse(
            success=True,
            message="Backtest started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start backtest: {str(e)}")


@router.post("/{backtest_id}/stop", response_model=APIResponse)
async def stop_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Stop a running backtest."""
    try:
        backtest = await db.get(Backtest, backtest_id)
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        if backtest.status != "running":
            raise HTTPException(status_code=400, detail="Backtest is not running")
            
        # Update backtest status
        backtest.status = "stopped"
        await db.commit()
        
        # Signal backtest engine to stop (would be implemented in engine)
        engine = BacktestEngine()
        await engine.stop_backtest(backtest_id)
        
        return APIResponse(
            success=True,
            message="Backtest stopped"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop backtest: {str(e)}")


@router.delete("/{backtest_id}", response_model=APIResponse)
async def delete_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a backtest."""
    try:
        backtest = await db.get(Backtest, backtest_id)
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        if backtest.status == "running":
            raise HTTPException(status_code=400, detail="Cannot delete running backtest")
            
        await db.delete(backtest)
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Backtest deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete backtest: {str(e)}")


@router.get("/{backtest_id}/progress", response_model=Dict[str, Any])
async def get_backtest_progress(
    backtest_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get real-time progress of a running backtest."""
    try:
        backtest = await db.get(Backtest, backtest_id)
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        return {
            "backtest_id": backtest.id,
            "status": backtest.status,
            "progress": backtest.progress or 0,
            "current_date": backtest.current_date.isoformat() if backtest.current_date else None,
            "trades_executed": backtest.trades_executed or 0,
            "current_return": backtest.current_return or 0.0,
            "current_drawdown": backtest.current_drawdown or 0.0,
            "estimated_completion": None,  # Would calculate based on progress
            "last_updated": backtest.updated_at.isoformat() if backtest.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backtest progress: {str(e)}")


@router.post("/{backtest_id}/clone", response_model=APIResponse)
async def clone_backtest(
    backtest_id: int,
    name: Optional[str] = Query(None, description="Name for the cloned backtest"),
    db: AsyncSession = Depends(get_db)
):
    """Clone an existing backtest with the same parameters."""
    try:
        original = await db.get(Backtest, backtest_id)
        
        if not original:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
        # Create clone
        clone_name = name or f"{original.name} (Clone)"
        
        cloned_backtest = Backtest(
            strategy_id=original.strategy_id,
            name=clone_name,
            start_date=original.start_date,
            end_date=original.end_date,
            initial_capital=original.initial_capital,
            commission=original.commission,
            slippage=original.slippage,
            symbols=original.symbols,
            parameters=original.parameters,
            status="queued",
            progress=0,
            created_at=datetime.now()
        )
        
        db.add(cloned_backtest)
        await db.commit()
        await db.refresh(cloned_backtest)
        
        return APIResponse(
            success=True,
            message="Backtest cloned successfully",
            data={"backtest_id": cloned_backtest.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clone backtest: {str(e)}")


async def run_backtest(backtest_id: int):
    """Background task to execute a backtest."""
    try:
        engine = BacktestEngine()
        await engine.run_backtest(backtest_id)
        
    except Exception as e:
        # Update backtest with error status
        async with get_db() as db:
            backtest = await db.get(Backtest, backtest_id)
            if backtest:
                backtest.status = "failed"
                backtest.error_message = str(e)
                await db.commit()
