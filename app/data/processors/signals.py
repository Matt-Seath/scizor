from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.strategies.base import BaseStrategy, StrategySignal, StrategyValidator
from app.strategies.momentum import MomentumBreakoutStrategy, MomentumBreakoutParameters
from app.strategies.mean_reversion import MeanReversionStrategy, MeanReversionParameters
from app.data.processors.technical import ASXTechnicalAnalyzer
from app.data.models.signals import Signal
from app.data.models.market import DailyPrice
from app.utils.logging import get_trading_logger

logger = structlog.get_logger(__name__)
trading_logger = get_trading_logger(__name__)


class SignalProcessor:
    """
    Processes and validates trading signals from multiple strategies
    Manages signal prioritization, conflict resolution, and database storage
    """
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.analyzer = ASXTechnicalAnalyzer()
        self.validator = StrategyValidator()
        
        # Initialize default strategies
        self._initialize_strategies()
        
        logger.info("Signal processor initialized", 
                   strategies=list(self.strategies.keys()))
    
    def _initialize_strategies(self) -> None:
        """Initialize default trading strategies"""
        try:
            # Momentum breakout strategy
            momentum_params = MomentumBreakoutParameters(
                max_positions=2,
                risk_per_trade=0.02,
                min_confidence=0.75
            )
            self.strategies['momentum'] = MomentumBreakoutStrategy(momentum_params)
            
            # Mean reversion strategy
            mean_rev_params = MeanReversionParameters(
                max_positions=3,
                risk_per_trade=0.015,
                min_confidence=0.65
            )
            self.strategies['mean_reversion'] = MeanReversionStrategy(mean_rev_params)
            
        except Exception as e:
            logger.error("Error initializing strategies", error=str(e))
    
    def add_strategy(self, name: str, strategy: BaseStrategy) -> None:
        """Add a custom strategy to the processor"""
        self.strategies[name] = strategy
        logger.info("Strategy added", name=name, type=type(strategy).__name__)
    
    def remove_strategy(self, name: str) -> None:
        """Remove a strategy from the processor"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info("Strategy removed", name=name)
    
    def enable_strategy(self, name: str) -> None:
        """Enable a strategy"""
        if name in self.strategies:
            self.strategies[name].parameters.enabled = True
            logger.info("Strategy enabled", name=name)
    
    def disable_strategy(self, name: str) -> None:
        """Disable a strategy"""
        if name in self.strategies:
            self.strategies[name].parameters.enabled = False
            logger.info("Strategy disabled", name=name)
    
    async def generate_signals(self, market_data: Dict[str, pd.DataFrame], 
                              current_date: datetime) -> List[StrategySignal]:
        """
        Generate signals from all enabled strategies
        
        Args:
            market_data: Dictionary of symbol -> DataFrame with OHLCV + indicators
            current_date: Current trading date
            
        Returns:
            List of validated and prioritized signals
        """
        all_signals = []
        
        # Prepare data with technical indicators
        processed_data = self._prepare_technical_data(market_data)
        
        # Generate signals from each strategy
        for strategy_name, strategy in self.strategies.items():
            if not strategy.parameters.enabled:
                continue
            
            try:
                strategy_signals = strategy.get_all_signals(processed_data, current_date)
                
                # Validate each signal
                validated_signals = []
                for signal in strategy_signals:
                    if self.validator.validate_signal(signal):
                        validated_signals.append(signal)
                    else:
                        logger.warning("Invalid signal generated", 
                                     strategy=strategy_name,
                                     symbol=signal.symbol,
                                     signal_type=signal.signal_type)
                
                all_signals.extend(validated_signals)
                
                logger.debug("Strategy signals generated", 
                           strategy=strategy_name,
                           signals=len(strategy_signals),
                           validated=len(validated_signals))
                
            except Exception as e:
                logger.error("Error generating signals from strategy", 
                           strategy=strategy_name, error=str(e))
        
        # Resolve conflicts and prioritize signals
        final_signals = self._resolve_signal_conflicts(all_signals)
        
        # Log final signal summary
        if final_signals:
            signal_summary = self._summarize_signals(final_signals)
            logger.info("Final signals generated", **signal_summary)
            
            # Log individual signals for audit trail
            for signal in final_signals:
                trading_logger.log_trade_signal(
                    symbol=signal.symbol,
                    signal_type=signal.signal_type,
                    price=signal.price,
                    confidence=signal.confidence,
                    strategy=signal.strategy_name
                )
        
        return final_signals
    
    def _prepare_technical_data(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Prepare market data with technical indicators"""
        processed_data = {}
        
        for symbol, df in market_data.items():
            try:
                # Calculate all technical indicators
                df_with_indicators = self.analyzer.calculate_all_indicators(df)
                processed_data[symbol] = df_with_indicators
                
            except Exception as e:
                logger.error("Error calculating indicators", symbol=symbol, error=str(e))
                # Use original data if indicator calculation fails
                processed_data[symbol] = df
        
        return processed_data
    
    def _resolve_signal_conflicts(self, signals: List[StrategySignal]) -> List[StrategySignal]:
        """
        Resolve conflicts between signals from different strategies
        
        Priority rules:
        1. Exit signals always take priority over entry signals
        2. Higher confidence signals take priority
        3. Momentum strategy has priority in trending markets
        4. Mean reversion has priority in sideways markets
        """
        if not signals:
            return []
        
        # Group signals by symbol
        symbol_signals: Dict[str, List[StrategySignal]] = {}
        for signal in signals:
            if signal.symbol not in symbol_signals:
                symbol_signals[signal.symbol] = []
            symbol_signals[signal.symbol].append(signal)
        
        final_signals = []
        
        for symbol, symbol_signal_list in symbol_signals.items():
            if len(symbol_signal_list) == 1:
                # No conflict
                final_signals.append(symbol_signal_list[0])
                continue
            
            # Resolve conflicts for this symbol
            resolved_signal = self._resolve_symbol_conflicts(symbol, symbol_signal_list)
            if resolved_signal:
                final_signals.append(resolved_signal)
        
        return final_signals
    
    def _resolve_symbol_conflicts(self, symbol: str, 
                                 signals: List[StrategySignal]) -> Optional[StrategySignal]:
        """Resolve conflicts for a single symbol"""
        try:
            # 1. Exit signals always win
            exit_signals = [s for s in signals if s.signal_type in ["SELL", "CLOSE"]]
            if exit_signals:
                # Take highest confidence exit signal
                return max(exit_signals, key=lambda x: x.confidence)
            
            # 2. Only entry signals remain - check for BUY conflicts
            buy_signals = [s for s in signals if s.signal_type == "BUY"]
            if not buy_signals:
                return None
            
            if len(buy_signals) == 1:
                return buy_signals[0]
            
            # 3. Multiple BUY signals - use strategy priority and confidence
            # For now, take highest confidence signal
            best_signal = max(buy_signals, key=lambda x: x.confidence)
            
            logger.debug("Signal conflict resolved", 
                        symbol=symbol,
                        chosen_strategy=best_signal.strategy_name,
                        chosen_confidence=best_signal.confidence,
                        total_signals=len(signals))
            
            return best_signal
            
        except Exception as e:
            logger.error("Error resolving signal conflicts", symbol=symbol, error=str(e))
            return None
    
    def _summarize_signals(self, signals: List[StrategySignal]) -> Dict[str, any]:
        """Create summary statistics for signals"""
        if not signals:
            return {}
        
        buy_signals = [s for s in signals if s.signal_type == "BUY"]
        sell_signals = [s for s in signals if s.signal_type in ["SELL", "CLOSE"]]
        
        strategy_counts = {}
        for signal in signals:
            strategy_counts[signal.strategy_name] = strategy_counts.get(signal.strategy_name, 0) + 1
        
        return {
            'total_signals': len(signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'avg_confidence': sum(s.confidence for s in signals) / len(signals),
            'strategy_breakdown': strategy_counts,
            'symbols': [s.symbol for s in signals]
        }
    
    async def save_signals_to_db(self, signals: List[StrategySignal], 
                                db_session: AsyncSession) -> List[Signal]:
        """
        Save signals to database
        
        Args:
            signals: List of strategy signals to save
            db_session: Database session
            
        Returns:
            List of saved Signal objects
        """
        saved_signals = []
        
        try:
            for strategy_signal in signals:
                # Convert StrategySignal to database Signal model
                db_signal = Signal(
                    symbol=strategy_signal.symbol,
                    strategy=strategy_signal.strategy_name,
                    signal_type=strategy_signal.signal_type,
                    price=strategy_signal.price,
                    confidence=strategy_signal.confidence,
                    metadata=strategy_signal.metadata,
                    generated_at=strategy_signal.generated_at,
                    status='PENDING'
                )
                
                db_session.add(db_signal)
                saved_signals.append(db_signal)
            
            await db_session.commit()
            
            logger.info("Signals saved to database", count=len(saved_signals))
            
        except Exception as e:
            await db_session.rollback()
            logger.error("Error saving signals to database", error=str(e))
            raise
        
        return saved_signals
    
    async def get_historical_signals(self, db_session: AsyncSession, 
                                   start_date: datetime, end_date: datetime,
                                   symbol: Optional[str] = None,
                                   strategy: Optional[str] = None) -> List[Signal]:
        """
        Retrieve historical signals from database
        
        Args:
            db_session: Database session
            start_date: Start date for signal retrieval
            end_date: End date for signal retrieval
            symbol: Optional symbol filter
            strategy: Optional strategy filter
            
        Returns:
            List of historical signals
        """
        try:
            query = db_session.query(Signal).filter(
                Signal.generated_at >= start_date,
                Signal.generated_at <= end_date
            )
            
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            
            if strategy:
                query = query.filter(Signal.strategy == strategy)
            
            signals = await query.all()
            
            logger.debug("Historical signals retrieved", 
                        count=len(signals),
                        start_date=start_date,
                        end_date=end_date)
            
            return signals
            
        except Exception as e:
            logger.error("Error retrieving historical signals", error=str(e))
            return []
    
    def get_strategy_status(self) -> Dict[str, any]:
        """Get status of all strategies"""
        status = {}
        
        for name, strategy in self.strategies.items():
            status[name] = strategy.get_strategy_status()
        
        return status
    
    def reset_all_strategies(self) -> None:
        """Reset position tracking for all strategies (for backtesting)"""
        for strategy in self.strategies.values():
            strategy.reset_positions()
        
        logger.info("All strategies reset")


class SignalValidator:
    """Enhanced signal validation with market context"""
    
    @staticmethod
    def validate_market_conditions(signals: List[StrategySignal], 
                                 market_data: Dict[str, pd.DataFrame]) -> List[StrategySignal]:
        """
        Validate signals against current market conditions
        
        Args:
            signals: List of signals to validate
            market_data: Current market data
            
        Returns:
            List of validated signals
        """
        validated_signals = []
        
        for signal in signals:
            try:
                if signal.symbol not in market_data:
                    continue
                
                df = market_data[signal.symbol]
                latest = df.iloc[-1]
                
                # Check for sufficient liquidity
                if 'volume' in latest.index:
                    daily_volume_aud = latest['volume'] * latest['close']
                    if daily_volume_aud < 100000:  # Minimum $100k daily volume
                        logger.warning("Signal rejected - insufficient liquidity", 
                                     symbol=signal.symbol,
                                     volume_aud=daily_volume_aud)
                        continue
                
                # Check for extreme volatility (gap risk)
                if len(df) >= 2:
                    prev_close = df.iloc[-2]['close']
                    current_open = latest.get('open', latest['close'])
                    gap_percent = abs(current_open - prev_close) / prev_close
                    
                    if gap_percent > 0.15:  # 15% gap
                        logger.warning("Signal rejected - extreme gap", 
                                     symbol=signal.symbol,
                                     gap_percent=gap_percent)
                        continue
                
                # Check for price/volume anomalies
                if 'volume_ratio' in latest.index:
                    if latest['volume_ratio'] > 10:  # Extreme volume spike
                        logger.warning("Signal rejected - extreme volume", 
                                     symbol=signal.symbol,
                                     volume_ratio=latest['volume_ratio'])
                        continue
                
                validated_signals.append(signal)
                
            except Exception as e:
                logger.error("Error validating signal market conditions", 
                           symbol=signal.symbol, error=str(e))
                continue
        
        return validated_signals