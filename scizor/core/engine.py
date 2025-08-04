"""
Core trading engine and orchestration.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger

from scizor.config.settings import Settings
from scizor.strategies.base import BaseStrategy
from scizor.data.providers import DataProvider
from scizor.broker.base import BaseBroker
from scizor.portfolio.manager import PortfolioManager
from scizor.monitoring.metrics import MetricsCollector


class TradingEngine:
    """
    Main trading engine that orchestrates all components.
    """
    
    def __init__(
        self,
        strategy: BaseStrategy,
        data_provider: DataProvider,
        broker: BaseBroker,
        settings: Settings
    ):
        self.strategy = strategy
        self.data_provider = data_provider
        self.broker = broker
        self.settings = settings
        
        self.portfolio_manager = PortfolioManager(
            initial_capital=settings.trading.initial_capital,
            risk_settings=settings.trading.risk
        )
        
        self.metrics_collector = MetricsCollector()
        
        self._running = False
        self._last_update = None
        
    async def start(self):
        """Start the trading engine."""
        logger.info("Starting trading engine...")
        
        # Initialize components
        await self.broker.connect()
        self.strategy.set_data_provider(self.data_provider)
        self.strategy.set_portfolio_manager(self.portfolio_manager)
        
        self._running = True
        logger.info("Trading engine started successfully")
        
    async def stop(self):
        """Stop the trading engine."""
        logger.info("Stopping trading engine...")
        self._running = False
        await self.broker.disconnect()
        logger.info("Trading engine stopped")
        
    async def run_single_iteration(self, current_time: datetime = None):
        """Run a single trading iteration."""
        if current_time is None:
            current_time = datetime.now()
            
        try:
            # Get latest market data
            symbols = self.strategy.get_required_symbols()
            market_data = await self.data_provider.get_latest_data(symbols)
            
            # Run strategy logic
            signals = self.strategy.generate_signals(market_data, current_time)
            
            # Process signals and manage portfolio
            for signal in signals:
                await self._process_signal(signal)
                
            # Update metrics
            portfolio_value = self.portfolio_manager.get_total_value()
            self.metrics_collector.record_portfolio_value(portfolio_value, current_time)
            
            self._last_update = current_time
            
        except Exception as e:
            logger.error(f"Error in trading iteration: {e}")
            raise
            
    async def _process_signal(self, signal: Dict[str, Any]):
        """Process a trading signal."""
        symbol = signal['symbol']
        action = signal['action']  # 'buy', 'sell', 'hold'
        quantity = signal.get('quantity', 0)
        
        if action == 'buy':
            await self.broker.place_buy_order(symbol, quantity)
            self.portfolio_manager.add_position(symbol, quantity)
            
        elif action == 'sell':
            await self.broker.place_sell_order(symbol, quantity)
            self.portfolio_manager.reduce_position(symbol, quantity)
            
        logger.info(f"Processed signal: {action} {quantity} shares of {symbol}")
        
    async def run_live(self, update_frequency: int = 60):
        """
        Run the engine in live mode with specified update frequency.
        
        Args:
            update_frequency: Update frequency in seconds
        """
        logger.info(f"Starting live trading with {update_frequency}s update frequency")
        
        while self._running:
            try:
                await self.run_single_iteration()
                await asyncio.sleep(update_frequency)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in live trading loop: {e}")
                await asyncio.sleep(update_frequency)
                
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            'running': self._running,
            'last_update': self._last_update,
            'portfolio_value': self.portfolio_manager.get_total_value(),
            'positions': self.portfolio_manager.get_positions(),
            'metrics': self.metrics_collector.get_summary()
        }
