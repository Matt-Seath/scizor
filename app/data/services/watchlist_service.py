"""
Watchlist service for database-driven symbol selection
Provides clean interface for market data collection tasks
"""

from datetime import datetime
from typing import List, Optional, Dict, Set
from dataclasses import dataclass
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.data.models.market import Watchlist, WatchlistSymbol, ContractDetail

logger = structlog.get_logger(__name__)


@dataclass
class SymbolInfo:
    """Clean data class for symbol information"""
    symbol: str
    con_id: int
    long_name: Optional[str] = None
    exchange: str = "ASX"
    currency: str = "AUD"


@dataclass  
class IntradaySymbol:
    """Symbol configured for intraday collection"""
    symbol: str
    con_id: int
    priority: int
    timeframes: List[str]
    watchlist_name: str
    long_name: Optional[str] = None


class WatchlistService:
    """
    Service for retrieving symbols from database-driven watchlists
    Replaces hard-coded symbol lists with flexible database queries
    """
    
    async def get_all_symbols_for_daily_collection(self, exchange: str = "ASX") -> List[SymbolInfo]:
        """
        Get ALL symbols from contract_details table for daily data collection
        
        Args:
            exchange: Exchange to filter by (default: ASX)
            
        Returns:
            List of all symbols available for daily collection
        """
        async with AsyncSessionLocal() as db_session:
            try:
                result = await db_session.execute(
                    select(
                        ContractDetail.symbol, 
                        ContractDetail.con_id,
                        ContractDetail.long_name,
                        ContractDetail.exchange,
                        ContractDetail.currency
                    )
                    .where(ContractDetail.exchange == exchange)
                    .order_by(ContractDetail.symbol)
                )
                
                contracts = result.fetchall()
                
                symbols = [
                    SymbolInfo(
                        symbol=contract.symbol,
                        con_id=contract.con_id,
                        long_name=contract.long_name,
                        exchange=contract.exchange,
                        currency=contract.currency or "AUD"
                    )
                    for contract in contracts
                ]
                
                logger.info("Retrieved symbols for daily collection", 
                           exchange=exchange, count=len(symbols))
                
                return symbols
                
            except Exception as e:
                logger.error("Error retrieving daily collection symbols", 
                           exchange=exchange, error=str(e))
                return []
    
    async def get_intraday_symbols(self, active_only: bool = True) -> List[IntradaySymbol]:
        """
        Get symbols configured for intraday data collection from watchlists
        
        Args:
            active_only: Only return symbols from active watchlists
            
        Returns:
            List of symbols configured for intraday collection, ordered by priority
        """
        async with AsyncSessionLocal() as db_session:
            try:
                # Build query conditions
                conditions = [WatchlistSymbol.collect_intraday == True]
                if active_only:
                    conditions.append(Watchlist.is_active == True)
                
                result = await db_session.execute(
                    select(
                        WatchlistSymbol.symbol,
                        WatchlistSymbol.con_id,
                        WatchlistSymbol.priority,
                        WatchlistSymbol.timeframes,
                        Watchlist.name.label('watchlist_name'),
                        ContractDetail.long_name
                    )
                    .join(Watchlist, WatchlistSymbol.watchlist_id == Watchlist.id)
                    .outerjoin(ContractDetail, WatchlistSymbol.con_id == ContractDetail.con_id)
                    .where(and_(*conditions))
                    .order_by(
                        WatchlistSymbol.priority.desc(),
                        WatchlistSymbol.symbol
                    )
                )
                
                rows = result.fetchall()
                
                # Remove duplicates while preserving highest priority
                seen_symbols: Set[str] = set()
                symbols = []
                
                for row in rows:
                    if row.symbol not in seen_symbols:
                        timeframes = []
                        if row.timeframes:
                            timeframes = [tf.strip() for tf in row.timeframes.split(',') if tf.strip()]
                        
                        symbols.append(IntradaySymbol(
                            symbol=row.symbol,
                            con_id=row.con_id,
                            priority=row.priority,
                            timeframes=timeframes,
                            watchlist_name=row.watchlist_name,
                            long_name=row.long_name
                        ))
                        
                        seen_symbols.add(row.symbol)
                
                logger.info("Retrieved intraday symbols", 
                           active_only=active_only, count=len(symbols),
                           unique_symbols=len(seen_symbols))
                
                return symbols
                
            except Exception as e:
                logger.error("Error retrieving intraday symbols", error=str(e))
                return []
    
    async def get_symbols_by_timeframe(self, timeframe: str, active_only: bool = True) -> List[IntradaySymbol]:
        """
        Get symbols that support a specific timeframe for intraday collection
        
        Args:
            timeframe: Timeframe to filter by (e.g., "5min", "15min", "1hour")
            active_only: Only return symbols from active watchlists
            
        Returns:
            List of symbols that support the specified timeframe
        """
        all_symbols = await self.get_intraday_symbols(active_only)
        
        filtered_symbols = [
            symbol for symbol in all_symbols 
            if timeframe in symbol.timeframes
        ]
        
        logger.info("Filtered symbols by timeframe", 
                   timeframe=timeframe, 
                   total_symbols=len(all_symbols),
                   filtered_count=len(filtered_symbols))
        
        return filtered_symbols
    
    async def get_high_priority_symbols(self, min_priority: int = 8, 
                                       active_only: bool = True) -> List[IntradaySymbol]:
        """
        Get high-priority symbols for focused data collection
        
        Args:
            min_priority: Minimum priority level (default: 8)
            active_only: Only return symbols from active watchlists
            
        Returns:
            List of high-priority symbols
        """
        all_symbols = await self.get_intraday_symbols(active_only)
        
        high_priority = [
            symbol for symbol in all_symbols 
            if symbol.priority >= min_priority
        ]
        
        logger.info("Retrieved high priority symbols", 
                   min_priority=min_priority, 
                   total_symbols=len(all_symbols),
                   high_priority_count=len(high_priority))
        
        return high_priority
    
    async def get_watchlist_summary(self) -> Dict:
        """
        Get summary statistics for all watchlists
        
        Returns:
            Dictionary with watchlist statistics
        """
        async with AsyncSessionLocal() as db_session:
            try:
                # Get watchlist counts
                watchlist_result = await db_session.execute(
                    select(Watchlist.is_active, Watchlist.id).select_from(Watchlist)
                )
                watchlists = watchlist_result.fetchall()
                
                # Get symbol counts  
                symbol_result = await db_session.execute(
                    select(
                        WatchlistSymbol.collect_intraday,
                        Watchlist.is_active
                    )
                    .join(Watchlist, WatchlistSymbol.watchlist_id == Watchlist.id)
                )
                symbols = symbol_result.fetchall()
                
                # Calculate statistics
                active_watchlists = sum(1 for w in watchlists if w.is_active)
                inactive_watchlists = sum(1 for w in watchlists if not w.is_active)
                
                intraday_symbols = sum(
                    1 for s in symbols 
                    if s.collect_intraday and s.is_active
                )
                
                daily_only_symbols = sum(
                    1 for s in symbols 
                    if not s.collect_intraday and s.is_active
                )
                
                return {
                    "total_watchlists": len(watchlists),
                    "active_watchlists": active_watchlists,
                    "inactive_watchlists": inactive_watchlists,
                    "intraday_symbols": intraday_symbols,
                    "daily_only_symbols": daily_only_symbols,
                    "total_active_symbols": intraday_symbols + daily_only_symbols
                }
                
            except Exception as e:
                logger.error("Error getting watchlist summary", error=str(e))
                return {}
    
    async def validate_symbol_exists(self, symbol: str) -> bool:
        """
        Validate that a symbol exists in contract_details
        
        Args:
            symbol: Symbol to validate
            
        Returns:
            True if symbol exists, False otherwise
        """
        async with AsyncSessionLocal() as db_session:
            try:
                result = await db_session.execute(
                    select(ContractDetail.symbol)
                    .where(ContractDetail.symbol == symbol.upper())
                    .limit(1)
                )
                
                exists = result.scalar_one_or_none() is not None
                
                logger.debug("Symbol validation", symbol=symbol, exists=exists)
                return exists
                
            except Exception as e:
                logger.error("Error validating symbol", symbol=symbol, error=str(e))
                return False