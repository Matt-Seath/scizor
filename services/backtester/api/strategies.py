"""Strategy management API endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.connection import get_db
from shared.database.models import Strategy
from shared.models.schemas import APIResponse, StrategyCreate, StrategyUpdate, StrategyResponse

router = APIRouter()


@router.get("/", response_model=List[StrategyResponse])
async def list_strategies(
    active_only: bool = Query(True, description="Return only active strategies"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of strategies to return"),
    offset: int = Query(0, ge=0, description="Number of strategies to skip"),
    db: AsyncSession = Depends(get_db)
):
    """List all strategies."""
    try:
        query = db.query(Strategy)
        
        if active_only:
            query = query.filter(Strategy.active == True)
            
        query = query.offset(offset).limit(limit)
        strategies = await query.all()
        
        return [
            StrategyResponse(
                id=strategy.id,
                name=strategy.name,
                description=strategy.description,
                strategy_type=strategy.strategy_type,
                parameters=strategy.parameters or {},
                active=strategy.active,
                created_at=strategy.created_at,
                updated_at=strategy.updated_at
            )
            for strategy in strategies
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve strategies: {str(e)}")


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get strategy by ID."""
    try:
        strategy = await db.get(Strategy, strategy_id)
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        return StrategyResponse(
            id=strategy.id,
            name=strategy.name,
            description=strategy.description,
            strategy_type=strategy.strategy_type,
            parameters=strategy.parameters or {},
            code=strategy.code,
            active=strategy.active,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve strategy: {str(e)}")


@router.post("/", response_model=APIResponse)
async def create_strategy(
    strategy: StrategyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new strategy."""
    try:
        # Check if strategy name already exists
        existing = await db.query(Strategy).filter(Strategy.name == strategy.name).first()
        if existing:
            raise HTTPException(status_code=409, detail="Strategy name already exists")
            
        # Validate strategy code if provided
        if strategy.code:
            await _validate_strategy_code(strategy.code)
            
        # Create new strategy
        new_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            strategy_type=strategy.strategy_type,
            parameters=strategy.parameters,
            code=strategy.code,
            active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_strategy)
        await db.commit()
        await db.refresh(new_strategy)
        
        return APIResponse(
            success=True,
            message="Strategy created successfully",
            data={"strategy_id": new_strategy.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create strategy: {str(e)}")


@router.put("/{strategy_id}", response_model=APIResponse)
async def update_strategy(
    strategy_id: int,
    strategy: StrategyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing strategy."""
    try:
        existing_strategy = await db.get(Strategy, strategy_id)
        
        if not existing_strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Check if new name conflicts with existing strategies
        if strategy.name and strategy.name != existing_strategy.name:
            name_exists = await db.query(Strategy).filter(
                Strategy.name == strategy.name,
                Strategy.id != strategy_id
            ).first()
            if name_exists:
                raise HTTPException(status_code=409, detail="Strategy name already exists")
                
        # Validate strategy code if provided
        if strategy.code:
            await _validate_strategy_code(strategy.code)
            
        # Update strategy fields
        if strategy.name is not None:
            existing_strategy.name = strategy.name
        if strategy.description is not None:
            existing_strategy.description = strategy.description
        if strategy.strategy_type is not None:
            existing_strategy.strategy_type = strategy.strategy_type
        if strategy.parameters is not None:
            existing_strategy.parameters = strategy.parameters
        if strategy.code is not None:
            existing_strategy.code = strategy.code
        if strategy.active is not None:
            existing_strategy.active = strategy.active
            
        existing_strategy.updated_at = datetime.now()
        
        await db.commit()
        
        return APIResponse(
            success=True,
            message="Strategy updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update strategy: {str(e)}")


@router.delete("/{strategy_id}", response_model=APIResponse)
async def delete_strategy(
    strategy_id: int,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) or hard delete"),
    db: AsyncSession = Depends(get_db)
):
    """Delete or deactivate a strategy."""
    try:
        strategy = await db.get(Strategy, strategy_id)
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        if soft_delete:
            # Soft delete - just deactivate
            strategy.active = False
            strategy.updated_at = datetime.now()
            await db.commit()
            message = "Strategy deactivated successfully"
        else:
            # Hard delete - check for dependencies first
            # (Would check for backtests using this strategy)
            await db.delete(strategy)
            await db.commit()
            message = "Strategy deleted successfully"
            
        return APIResponse(
            success=True,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete strategy: {str(e)}")


@router.post("/upload", response_model=APIResponse)
async def upload_strategy_file(
    file: UploadFile = File(...),
    name: str = Query(..., description="Strategy name"),
    description: str = Query("", description="Strategy description"),
    strategy_type: str = Query("custom", description="Strategy type"),
    db: AsyncSession = Depends(get_db)
):
    """Upload a strategy from a Python file."""
    try:
        # Validate file type
        if not file.filename.endswith('.py'):
            raise HTTPException(status_code=400, detail="Only Python files are allowed")
            
        # Read file content
        content = await file.read()
        code = content.decode('utf-8')
        
        # Validate strategy code
        await _validate_strategy_code(code)
        
        # Check if strategy name already exists
        existing = await db.query(Strategy).filter(Strategy.name == name).first()
        if existing:
            raise HTTPException(status_code=409, detail="Strategy name already exists")
            
        # Create new strategy
        new_strategy = Strategy(
            name=name,
            description=description,
            strategy_type=strategy_type,
            code=code,
            active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_strategy)
        await db.commit()
        await db.refresh(new_strategy)
        
        return APIResponse(
            success=True,
            message="Strategy uploaded successfully",
            data={"strategy_id": new_strategy.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload strategy: {str(e)}")


@router.post("/{strategy_id}/validate", response_model=APIResponse)
async def validate_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Validate strategy code and parameters."""
    try:
        strategy = await db.get(Strategy, strategy_id)
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        if not strategy.code:
            raise HTTPException(status_code=400, detail="Strategy has no code to validate")
            
        # Validate strategy code
        validation_result = await _validate_strategy_code(strategy.code)
        
        return APIResponse(
            success=True,
            message="Strategy validation completed",
            data=validation_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate strategy: {str(e)}")


@router.post("/{strategy_id}/copy", response_model=APIResponse)
async def copy_strategy(
    strategy_id: int,
    new_name: str = Query(..., description="New strategy name"),
    db: AsyncSession = Depends(get_db)
):
    """Create a copy of an existing strategy."""
    try:
        original_strategy = await db.get(Strategy, strategy_id)
        
        if not original_strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        # Check if new name already exists
        existing = await db.query(Strategy).filter(Strategy.name == new_name).first()
        if existing:
            raise HTTPException(status_code=409, detail="Strategy name already exists")
            
        # Create copy
        new_strategy = Strategy(
            name=new_name,
            description=f"Copy of {original_strategy.name}",
            strategy_type=original_strategy.strategy_type,
            parameters=original_strategy.parameters,
            code=original_strategy.code,
            active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_strategy)
        await db.commit()
        await db.refresh(new_strategy)
        
        return APIResponse(
            success=True,
            message="Strategy copied successfully",
            data={"strategy_id": new_strategy.id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to copy strategy: {str(e)}")


async def _validate_strategy_code(code: str) -> Dict[str, Any]:
    """Validate strategy code for security and correctness."""
    try:
        # Basic syntax check
        compile(code, '<string>', 'exec')
        
        # Check for forbidden imports/functions
        forbidden_imports = ['os', 'sys', 'subprocess', 'eval', 'exec', '__import__']
        for forbidden in forbidden_imports:
            if forbidden in code:
                raise ValueError(f"Forbidden import/function: {forbidden}")
                
        # Check for required functions
        required_functions = ['initialize', 'handle_data']
        missing_functions = []
        for func in required_functions:
            if f"def {func}" not in code:
                missing_functions.append(func)
                
        return {
            "valid": len(missing_functions) == 0,
            "syntax_valid": True,
            "missing_functions": missing_functions,
            "warnings": []
        }
        
    except SyntaxError as e:
        return {
            "valid": False,
            "syntax_valid": False,
            "error": str(e),
            "line": e.lineno if hasattr(e, 'lineno') else None
        }
    except ValueError as e:
        return {
            "valid": False,
            "syntax_valid": True,
            "error": str(e)
        }
