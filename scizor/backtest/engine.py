"""
Backtesting engine using Backtrader.
"""

import backtrader as bt
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd

from scizor.strategies.base import BaseStrategy
from scizor.data.providers import DataProvider


class BacktraderStrategy(bt.Strategy):
    """Adapter to run Scizor strategies in Backtrader."""
    
    def __init__(self, scizor_strategy: BaseStrategy):
        self.scizor_strategy = scizor_strategy
        self.trades = []
        
    def next(self):
        """Called for each bar/candle."""
        # Get current data
        current_time = self.datas[0].datetime.datetime(0)
        
        # Prepare market data for Scizor strategy
        market_data = {}
        
        # For simplicity, we'll use the first data feed
        # In a real implementation, you'd map all data feeds
        data = self.datas[0]
        
        # Create DataFrame for current data window
        df_data = {
            'Open': [data.open[0]],
            'High': [data.high[0]], 
            'Low': [data.low[0]],
            'Close': [data.close[0]],
            'Volume': [data.volume[0]]
        }
        
        symbol = getattr(data, '_name', 'UNKNOWN')
        market_data[symbol] = pd.DataFrame(df_data)
        
        # Generate signals
        try:
            signals = self.scizor_strategy.generate_signals(market_data, current_time)
            
            # Execute signals
            for signal in signals:
                if signal.action == 'buy' and not self.position:
                    self.buy(size=signal.quantity)
                elif signal.action == 'sell' and self.position:
                    self.sell(size=signal.quantity or self.position.size)
                    
        except Exception as e:
            print(f"Error generating signals: {e}")
    
    def notify_trade(self, trade):
        """Called when a trade is completed."""
        if trade.isclosed:
            self.trades.append({
                'date': self.datas[0].datetime.date(0),
                'pnl': trade.pnl,
                'pnl_comm': trade.pnlcomm
            })


class BacktestEngine:
    """Backtesting engine for Scizor strategies."""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.cerebro = None
        self.results = None
        
    def run_backtest(
        self,
        strategy: BaseStrategy,
        data_provider: DataProvider,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        commission: float = 0.001
    ) -> Dict[str, Any]:
        """
        Run a backtest for the given strategy.
        
        Args:
            strategy: Scizor strategy to test
            data_provider: Data provider for market data
            symbols: List of symbols to test
            start_date: Backtest start date
            end_date: Backtest end date
            commission: Commission rate
            
        Returns:
            Backtest results dictionary
        """
        # Initialize Cerebro
        self.cerebro = bt.Cerebro()
        
        # Set initial capital
        self.cerebro.broker.setcash(self.initial_capital)
        
        # Set commission
        self.cerebro.broker.setcommission(commission=commission)
        
        # Add strategy
        bt_strategy = BacktraderStrategy(strategy)
        self.cerebro.addstrategy(lambda: bt_strategy)
        
        # Add data feeds
        for symbol in symbols:
            try:
                # Get historical data
                data = data_provider.get_historical_data(
                    symbol, start_date, end_date
                )
                
                if data.empty:
                    print(f"Warning: No data for {symbol}")
                    continue
                
                # Convert to Backtrader format
                bt_data = bt.feeds.PandasData(
                    dataname=data,
                    name=symbol,
                    fromdate=start_date,
                    todate=end_date
                )
                
                self.cerebro.adddata(bt_data)
                
            except Exception as e:
                print(f"Error loading data for {symbol}: {e}")
                continue
        
        # Add analyzers
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # Run backtest
        print(f"Starting backtest from {start_date} to {end_date}")
        print(f"Initial capital: ${self.initial_capital:,.2f}")
        
        results = self.cerebro.run()
        
        # Extract results
        strategy_result = results[0]
        
        final_value = self.cerebro.broker.getvalue()
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Get analyzer results
        analyzers = {}
        for name, analyzer in strategy_result.analyzers.getitems():
            analyzers[name] = analyzer.get_analysis()
        
        # Compile results
        self.results = {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'sharpe_ratio': analyzers.get('sharpe', {}).get('sharperatio'),
            'max_drawdown': analyzers.get('drawdown', {}).get('max', {}).get('drawdown', 0),
            'returns': analyzers.get('returns', {}),
            'trade_analysis': analyzers.get('trades', {}),
            'strategy_name': strategy.name,
            'symbols': symbols,
            'start_date': start_date,
            'end_date': end_date,
            'duration_days': (end_date - start_date).days
        }
        
        return self.results
    
    def print_results(self):
        """Print backtest results."""
        if not self.results:
            print("No results to display. Run backtest first.")
            return
            
        results = self.results
        
        print("\n" + "="*50)
        print("BACKTEST RESULTS")
        print("="*50)
        print(f"Strategy: {results['strategy_name']}")
        print(f"Symbols: {', '.join(results['symbols'])}")
        print(f"Period: {results['start_date'].strftime('%Y-%m-%d')} to {results['end_date'].strftime('%Y-%m-%d')}")
        print(f"Duration: {results['duration_days']} days")
        print()
        print(f"Initial Capital: ${results['initial_capital']:,.2f}")
        print(f"Final Value: ${results['final_value']:,.2f}")
        print(f"Total Return: {results['total_return_pct']:.2f}%")
        print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
        
        if results['sharpe_ratio'] is not None:
            print(f"Sharpe Ratio: {results['sharpe_ratio']:.3f}")
        
        # Trade statistics
        trade_analysis = results.get('trade_analysis', {})
        if trade_analysis:
            total_trades = trade_analysis.get('total', {}).get('total', 0)
            won_trades = trade_analysis.get('won', {}).get('total', 0)
            lost_trades = trade_analysis.get('lost', {}).get('total', 0)
            
            print(f"\nTrade Statistics:")
            print(f"Total Trades: {total_trades}")
            print(f"Winning Trades: {won_trades}")
            print(f"Losing Trades: {lost_trades}")
            
            if total_trades > 0:
                win_rate = won_trades / total_trades * 100
                print(f"Win Rate: {win_rate:.1f}%")
        
        print("="*50)
    
    def plot_results(self):
        """Plot backtest results."""
        if self.cerebro is None:
            print("No backtest to plot. Run backtest first.")
            return
            
        try:
            self.cerebro.plot(style='candlestick')
        except Exception as e:
            print(f"Error plotting results: {e}")
    
    def save_results(self, filename: str):
        """Save results to JSON file."""
        if not self.results:
            print("No results to save.")
            return
            
        import json
        
        # Convert datetime objects to strings for JSON serialization
        serializable_results = self.results.copy()
        serializable_results['start_date'] = self.results['start_date'].isoformat()
        serializable_results['end_date'] = self.results['end_date'].isoformat()
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2)
            
        print(f"Results saved to {filename}")


def quick_backtest(
    strategy: BaseStrategy,
    symbols: List[str] = None,
    days: int = 365,
    initial_capital: float = 100000
) -> Dict[str, Any]:
    """
    Quick backtest helper function.
    
    Args:
        strategy: Strategy to test
        symbols: Symbols to test (defaults to strategy's required symbols)
        days: Number of days to backtest
        initial_capital: Initial capital
        
    Returns:
        Backtest results
    """
    from scizor.data.providers import YahooFinanceProvider
    
    if symbols is None:
        symbols = strategy.get_required_symbols()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    data_provider = YahooFinanceProvider()
    engine = BacktestEngine(initial_capital)
    
    return engine.run_backtest(
        strategy=strategy,
        data_provider=data_provider,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date
    )
