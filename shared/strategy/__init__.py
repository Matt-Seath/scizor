"""
Strategy framework for the trading system.

This module provides the foundation for creating and managing trading strategies,
including base classes, technical indicators, portfolio management, validation,
and backtesting capabilities.
"""

from .base import BaseStrategy, StrategySignal, StrategyConfig, StrategyMetrics, SignalType, OrderType
from .indicators import TechnicalIndicators
from .portfolio import Portfolio, Position, Trade
from .validation import StrategyValidator, ValidationError

__all__ = [
    # Base classes
    'BaseStrategy',
    'StrategySignal', 
    'StrategyConfig',
    'StrategyMetrics',
    'SignalType',
    'OrderType',
    
    # Technical analysis
    'TechnicalIndicators',
    
    # Portfolio management
    'Portfolio',
    'Position', 
    'Trade',
    
    # Validation
    'StrategyValidator',
    'ValidationError',
]

# Version information
__version__ = '0.1.0'
__author__ = 'Scizor Trading System'
