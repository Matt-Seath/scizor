"""Symbols management API endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.connection import get_db
from shared.database.models import Symbol
from shared.models.schemas import APIResponse, ContractBase

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_symbols(
    active_only: bool = Query(True, description="Return only active symbols"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of symbols to return"),
    offset: int = Query(0, ge=0, description="Number of symbols to skip"),
    db: AsyncSession = Depends(get_db)
):
    """List tracked symbols."""
    try:
        query = db.query(Symbol)
        
        if active_only:
            query = query.filter(Symbol.active == True)
            
        query = query.offset(offset).limit(limit)
        symbols = await query.all()
        
        return [
            {
                "id": symbol.id,
                "symbol": symbol.symbol,
                "exchange": symbol.exchange,
                "currency": symbol.currency,
                "security_type": symbol.security_type,
                "contract_id": symbol.contract_id,
                "active": symbol.active,
                "created_at": symbol.created_at.isoformat() if symbol.created_at else None,
                "updated_at": symbol.updated_at.isoformat() if symbol.updated_at else None,
            }
            for symbol in symbols
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve symbols: {str(e)}")


@router.get("/{symbol_id}", response_model=dict)
async def get_symbol(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get symbol by ID."""
    try:
        symbol = await db.get(Symbol, symbol_id)
        
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        return {
            "id": symbol.id,
            "symbol": symbol.symbol,
            "exchange": symbol.exchange,
            "currency": symbol.currency,
            "security_type": symbol.security_type,
            "contract_id": symbol.contract_id,
            "local_symbol": symbol.local_symbol,
            "trading_class": symbol.trading_class,
            "multiplier": symbol.multiplier,
            "expiry": symbol.expiry,
            "strike": symbol.strike,
            "option_type": symbol.option_type,
            "active": symbol.active,
            "created_at": symbol.created_at.isoformat() if symbol.created_at else None,
            "updated_at": symbol.updated_at.isoformat() if symbol.updated_at else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve symbol: {str(e)}")


@router.post("/", response_model=APIResponse)
async def add_symbol(
    contract: ContractBase,
    db: AsyncSession = Depends(get_db)
):
    """Add a new symbol to track."""
    try:
        # Check if symbol already exists
        existing = await db.query(Symbol).filter(
            Symbol.symbol == contract.symbol,
            Symbol.exchange == contract.exchange,
            Symbol.currency == contract.currency,
            Symbol.security_type == contract.security_type
        ).first()
        
        if existing:
            raise HTTPException(status_code=409, detail="Symbol already exists")
            
        # Create new symbol
        symbol = Symbol(
            symbol=contract.symbol,
            exchange=contract.exchange,
            currency=contract.currency,
            security_type=contract.security_type,
            contract_id=contract.contract_id,
            local_symbol=contract.local_symbol,
            trading_class=contract.trading_class,
            multiplier=contract.multiplier,
            expiry=contract.expiry,
            strike=contract.strike,
            option_type=contract.option_type,
            active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(symbol)
        await db.commit()
        await db.refresh(symbol)
        
        return APIResponse(
            success=True,
            message="Symbol added successfully",
            data={"symbol_id": symbol.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add symbol: {str(e)}")


@router.put("/{symbol_id}", response_model=APIResponse)
async def update_symbol(
    symbol_id: int,
    contract: ContractBase,
    db: AsyncSession = Depends(get_db)
):
    """Update symbol information."""
    try:
        symbol = await db.get(Symbol, symbol_id)
        
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        # Update symbol fields
        symbol.symbol = contract.symbol
        symbol.exchange = contract.exchange
        symbol.currency = contract.currency
        symbol.security_type = contract.security_type
        symbol.contract_id = contract.contract_id
        symbol.local_symbol = contract.local_symbol
        symbol.trading_class = contract.trading_class
        symbol.multiplier = contract.multiplier
        symbol.expiry = contract.expiry
        symbol.strike = contract.strike
        symbol.option_type = contract.option_type
        symbol.updated_at = datetime.now()
        
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Symbol updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update symbol: {str(e)}")


@router.delete("/{symbol_id}", response_model=APIResponse)
async def delete_symbol(
    symbol_id: int,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) or hard delete"),
    db: AsyncSession = Depends(get_db)
):
    """Delete or deactivate a symbol."""
    try:
        symbol = await db.get(Symbol, symbol_id)
        
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        if soft_delete:
            # Soft delete - just deactivate
            symbol.active = False
            symbol.updated_at = datetime.now()
            await db.commit()
            message = "Symbol deactivated successfully"
        else:
            # Hard delete
            await db.delete(symbol)
            await db.commit()
            message = "Symbol deleted successfully"
            
        return APIResponse(
            success=True,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete symbol: {str(e)}")


@router.post("/{symbol_id}/activate", response_model=APIResponse)
async def activate_symbol(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Activate a symbol."""
    try:
        symbol = await db.get(Symbol, symbol_id)
        
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        symbol.active = True
        symbol.updated_at = datetime.now()
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Symbol activated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to activate symbol: {str(e)}")


@router.post("/{symbol_id}/deactivate", response_model=APIResponse)
async def deactivate_symbol(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a symbol."""
    try:
        symbol = await db.get(Symbol, symbol_id)
        
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
            
        symbol.active = False
        symbol.updated_at = datetime.now()
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Symbol deactivated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to deactivate symbol: {str(e)}")
