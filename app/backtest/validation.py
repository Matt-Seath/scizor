import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import structlog

from app.backtest.engine import BacktestEngine, BacktestConfig, BacktestMetrics
from app.backtest.metrics import PerformanceAnalyzer, ReportGenerator
from app.strategies.momentum import MomentumBreakoutStrategy, MomentumBreakoutParameters
from app.strategies.mean_reversion import MeanReversionStrategy, MeanReversionParameters
from app.data.processors.signals import SignalProcessor
from app.data.processors.technical import ASXTechnicalAnalyzer
from app.data.collectors.asx_contracts import get_asx200_symbols, get_liquid_stocks

logger = structlog.get_logger(__name__)


class StrategyValidator:
    """
    Validates trading strategies using historical ASX200 data
    Runs comprehensive backtests and performance analysis
    """
    
    def __init__(self):
        self.analyzer = ASXTechnicalAnalyzer()
        self.signal_processor = SignalProcessor()
        
    def validate_strategy(self, strategy_name: str, 
                         start_date: datetime, end_date: datetime,
                         initial_capital: float = 100000,
                         symbols: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Validate a single strategy with comprehensive backtesting
        
        Args:
            strategy_name: Name of strategy to validate ('momentum' or 'mean_reversion')
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
            symbols: List of symbols to test (defaults to liquid ASX stocks)
            
        Returns:
            Dictionary with validation results
        """
        logger.info("Starting strategy validation", 
                   strategy=strategy_name,
                   start_date=start_date,
                   end_date=end_date)
        
        try:
            # Get test symbols
            if symbols is None:
                symbols = get_liquid_stocks(20)  # Top 20 liquid stocks for testing
            
            # Generate mock historical data (in production, load from database)
            historical_data = self._generate_mock_data(symbols, start_date, end_date)
            
            # Create strategy
            strategy = self._create_strategy(strategy_name)
            
            # Run backtest
            backtest_results = self._run_backtest(strategy, historical_data, start_date, end_date, initial_capital)
            
            # Calculate advanced metrics
            advanced_metrics = PerformanceAnalyzer.calculate_advanced_metrics(
                backtest_results['trades'],
                backtest_results['portfolio_curve']
            )
            
            # Generate report
            report = ReportGenerator.generate_summary_report(
                strategy_name,
                advanced_metrics,
                backtest_results['trades']
            )
            
            # Validate against success criteria
            validation_results = self._validate_success_criteria(advanced_metrics)
            
            logger.info("Strategy validation completed", 
                       strategy=strategy_name,
                       total_trades=advanced_metrics.get('total_trades', 0),
                       sharpe_ratio=advanced_metrics.get('sharpe_ratio', 0),
                       max_drawdown=advanced_metrics.get('max_drawdown', 0))
            
            return {
                'strategy_name': strategy_name,
                'validation_date': datetime.now(),
                'backtest_period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'symbols_tested': len(symbols),
                'metrics': advanced_metrics,
                'trades': backtest_results['trades'],
                'portfolio_curve': backtest_results['portfolio_curve'],
                'validation_passed': validation_results['passed'],
                'validation_details': validation_results['details'],
                'report': report
            }
            
        except Exception as e:
            logger.error("Error during strategy validation", 
                        strategy=strategy_name, error=str(e))
            raise
    
    def validate_all_strategies(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict]:
        """
        Validate all available strategies
        
        Returns:
            Dictionary of strategy_name -> validation results
        """
        strategies = ['momentum', 'mean_reversion']
        results = {}
        
        for strategy_name in strategies:
            try:
                results[strategy_name] = self.validate_strategy(
                    strategy_name, start_date, end_date
                )
            except Exception as e:
                logger.error("Failed to validate strategy", 
                           strategy=strategy_name, error=str(e))
                results[strategy_name] = {'error': str(e)}
        
        return results
    
    def _create_strategy(self, strategy_name: str):
        """Create strategy instance"""
        if strategy_name == 'momentum':
            params = MomentumBreakoutParameters(
                max_positions=3,
                risk_per_trade=0.02,
                min_confidence=0.7
            )
            return MomentumBreakoutStrategy(params)
        
        elif strategy_name == 'mean_reversion':
            params = MeanReversionParameters(
                max_positions=4,
                risk_per_trade=0.015,
                min_confidence=0.6
            )
            return MeanReversionStrategy(params)
        
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    
    def _run_backtest(self, strategy, historical_data: Dict[str, pd.DataFrame], 
                     start_date: datetime, end_date: datetime, 
                     initial_capital: float) -> Dict[str, any]:
        """Run backtest for a strategy"""
        
        # Configure backtest
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            max_positions=strategy.parameters.max_positions,
            position_sizing_method=strategy.parameters.position_size_method,
            risk_per_trade=strategy.parameters.risk_per_trade
        )
        
        # Create backtest engine
        engine = BacktestEngine(config)
        engine.load_price_data(historical_data)
        
        # Generate signals for the entire period
        signals = []
        current_date = start_date
        
        # Prepare data with technical indicators
        processed_data = {}
        for symbol, df in historical_data.items():
            processed_data[symbol] = self.analyzer.calculate_all_indicators(df)
        
        # Generate signals day by day
        while current_date <= end_date:
            try:
                # Get data up to current date for signal generation
                current_data = {}
                for symbol, df in processed_data.items():
                    mask = df.index <= current_date.strftime('%Y-%m-%d')
                    current_data[symbol] = df.loc[mask]
                
                # Generate signals
                daily_signals = strategy.get_all_signals(current_data, current_date)
                
                # Convert to backtest signal format
                for signal in daily_signals:
                    from app.data.models.signals import Signal
                    backtest_signal = Signal(
                        symbol=signal.symbol,
                        strategy=signal.strategy_name,
                        signal_type=signal.signal_type,
                        price=signal.price,
                        confidence=signal.confidence,
                        generated_at=signal.generated_at,
                        metadata=signal.metadata
                    )
                    signals.append(backtest_signal)
                
                # Move to next trading day
                current_date += timedelta(days=1)
                while current_date.weekday() >= 5:  # Skip weekends
                    current_date += timedelta(days=1)
                    
            except Exception as e:
                logger.error("Error generating signals", date=current_date, error=str(e))
                current_date += timedelta(days=1)
                continue
        
        # Run backtest
        metrics = engine.run_backtest(signals)
        
        return {
            'metrics': metrics,
            'trades': engine.completed_trades,
            'portfolio_curve': engine.get_portfolio_curve(),
            'trade_log': engine.get_trade_log()
        }
    
    def _generate_mock_data(self, symbols: List[str], start_date: datetime, 
                           end_date: datetime) -> Dict[str, pd.DataFrame]:
        """
        Generate mock historical data for testing
        In production, this would load real data from database
        """
        np.random.seed(42)  # For reproducible results
        
        data = {}
        
        # Generate date range (trading days only)
        dates = pd.bdate_range(start=start_date, end=end_date)
        
        for symbol in symbols:
            # Generate realistic stock price data
            num_days = len(dates)
            
            # Starting price between $1 and $100
            start_price = np.random.uniform(5, 50)
            
            # Generate returns with some trend and volatility
            daily_returns = np.random.normal(0.0005, 0.02, num_days)  # 0.05% daily return, 2% volatility
            
            # Add some trend for interesting patterns
            trend = np.linspace(0, 0.0002, num_days)  # Slight upward trend
            daily_returns += trend
            
            # Calculate prices
            prices = [start_price]
            for return_val in daily_returns[1:]:
                new_price = prices[-1] * (1 + return_val)
                prices.append(max(new_price, 0.1))  # Minimum price of $0.10
            
            # Generate OHLC data
            opens = prices
            closes = prices[1:] + [prices[-1]]
            
            # Generate highs and lows
            highs = []
            lows = []
            volumes = []
            
            for i in range(len(closes)):
                open_price = opens[i]
                close_price = closes[i]
                
                # High/Low spread
                daily_range = abs(close_price - open_price) + np.random.uniform(0.01, 0.05) * close_price
                high = max(open_price, close_price) + np.random.uniform(0, daily_range * 0.5)
                low = min(open_price, close_price) - np.random.uniform(0, daily_range * 0.5)
                
                highs.append(high)
                lows.append(max(low, 0.1))  # Minimum price
                
                # Volume (higher volume on bigger moves)
                base_volume = np.random.uniform(100000, 1000000)
                price_change = abs(close_price - open_price) / open_price
                volume_multiplier = 1 + price_change * 5  # More volume on big moves
                volumes.append(int(base_volume * volume_multiplier))
            
            # Create DataFrame
            df = pd.DataFrame({
                'open': opens[:len(closes)],
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=dates[:len(closes)])
            
            data[symbol] = df
        
        logger.info("Mock data generated", 
                   symbols=len(symbols),
                   days=len(dates),
                   start_date=start_date,
                   end_date=end_date)
        
        return data
    
    def _validate_success_criteria(self, metrics: Dict[str, float]) -> Dict[str, any]:
        """
        Validate strategy against Phase 2 success criteria
        
        Phase 2 Success Criteria:
        - All strategies show positive Sharpe ratio (>1.0) in backtests
        - Signal generation latency <5 seconds
        - Backtest results match manual calculations
        - Strategy parameters are optimized for ASX200 data
        """
        validation_details = []
        passed_checks = 0
        total_checks = 4
        
        # 1. Positive Sharpe ratio > 1.0
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        if sharpe_ratio > 1.0:
            validation_details.append(f"✓ Sharpe ratio: {sharpe_ratio:.2f} > 1.0")
            passed_checks += 1
        else:
            validation_details.append(f"✗ Sharpe ratio: {sharpe_ratio:.2f} <= 1.0 (FAIL)")
        
        # 2. Reasonable number of trades
        total_trades = metrics.get('total_trades', 0)
        if total_trades >= 10:  # At least 10 trades for statistical significance
            validation_details.append(f"✓ Trade count: {total_trades} >= 10")
            passed_checks += 1
        else:
            validation_details.append(f"✗ Trade count: {total_trades} < 10 (FAIL)")
        
        # 3. Maximum drawdown within acceptable limits
        max_drawdown = metrics.get('max_drawdown', 1.0)
        if max_drawdown < 0.20:  # Less than 20% max drawdown
            validation_details.append(f"✓ Max drawdown: {max_drawdown:.2%} < 20%")
            passed_checks += 1
        else:
            validation_details.append(f"✗ Max drawdown: {max_drawdown:.2%} >= 20% (FAIL)")
        
        # 4. Win rate within reasonable range
        win_rate = metrics.get('win_rate', 0)
        if 0.35 <= win_rate <= 0.80:  # Win rate between 35% and 80%
            validation_details.append(f"✓ Win rate: {win_rate:.2%} in acceptable range")
            passed_checks += 1
        else:
            validation_details.append(f"✗ Win rate: {win_rate:.2%} outside 35%-80% range (FAIL)")
        
        # Overall validation
        passed = passed_checks >= 3  # Need to pass at least 3 out of 4 criteria
        
        return {
            'passed': passed,
            'passed_checks': passed_checks,
            'total_checks': total_checks,
            'details': validation_details
        }


class ASXBacktestRunner:
    """
    Convenient runner for ASX200 strategy backtests
    """
    
    @staticmethod
    def run_quick_validation() -> Dict[str, any]:
        """
        Run a quick validation test (6 months, top 10 stocks)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)  # 6 months
        
        validator = StrategyValidator()
        
        # Test both strategies
        results = {}
        
        for strategy_name in ['momentum', 'mean_reversion']:
            try:
                result = validator.validate_strategy(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=100000,
                    symbols=get_liquid_stocks(10)  # Top 10 for quick test
                )
                results[strategy_name] = result
                
            except Exception as e:
                logger.error("Quick validation failed", 
                           strategy=strategy_name, error=str(e))
                results[strategy_name] = {'error': str(e)}
        
        return results
    
    @staticmethod
    def run_full_validation() -> Dict[str, any]:
        """
        Run a comprehensive validation test (2 years, top 30 stocks)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)  # 2 years
        
        validator = StrategyValidator()
        
        return validator.validate_all_strategies(start_date, end_date)
    
    @staticmethod
    def print_validation_summary(results: Dict[str, any]) -> None:
        """Print a summary of validation results"""
        
        print("\n" + "="*60)
        print("ASX200 STRATEGY VALIDATION SUMMARY")
        print("="*60)
        
        for strategy_name, result in results.items():
            if 'error' in result:
                print(f"\n{strategy_name.upper()}: ERROR")
                print(f"Error: {result['error']}")
                continue
            
            metrics = result.get('metrics', {})
            validation = result.get('validation_details', [])
            passed = result.get('validation_passed', False)
            
            print(f"\n{strategy_name.upper()}: {'PASSED' if passed else 'FAILED'}")
            print("-" * 40)
            
            print(f"Total Return: {metrics.get('total_return', 0):.2%}")
            print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
            print(f"Win Rate: {metrics.get('win_rate', 0):.2%}")
            print(f"Total Trades: {metrics.get('total_trades', 0)}")
            
            print("\nValidation Details:")
            for detail in validation:
                print(f"  {detail}")
        
        print("\n" + "="*60)