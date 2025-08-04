"""
Scizor - Headless Algorithmic Trading Framework
"""

__version__ = "0.1.0"
__author__ = "Matt Seath"
__email__ = "matt@example.com"

from scizor.core.engine import TradingEngine
from scizor.strategies.base import BaseStrategy
from scizor.data.providers import YahooFinanceProvider
from scizor.broker.ib import InteractiveBrokersAdapter

__all__ = [
    "TradingEngine",
    "BaseStrategy", 
    "YahooFinanceProvider",
    "InteractiveBrokersAdapter"
]
