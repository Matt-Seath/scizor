"""
Monitoring and metrics collection.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import json


class MetricsCollector:
    """Collects and manages trading metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        
        # Time series data
        self.portfolio_values = deque(maxlen=max_history)
        self.trade_history = deque(maxlen=max_history)
        self.signal_history = deque(maxlen=max_history)
        
        # Performance metrics
        self.daily_returns = deque(maxlen=max_history)
        self.sharpe_ratios = deque(maxlen=max_history)
        
        # Trade statistics
        self.trade_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_win': 0.0,
            'max_loss': 0.0
        }
        
    def record_portfolio_value(self, value: float, timestamp: datetime = None):
        """Record portfolio value at a point in time."""
        if timestamp is None:
            timestamp = datetime.now()
            
        self.portfolio_values.append({
            'timestamp': timestamp,
            'value': value
        })
        
        # Calculate daily return if we have previous data
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values[-2]['value']
            daily_return = (value - prev_value) / prev_value
            self.daily_returns.append({
                'timestamp': timestamp,
                'return': daily_return
            })
    
    def record_trade(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        pnl: float = 0.0,
        timestamp: datetime = None
    ):
        """Record a completed trade."""
        if timestamp is None:
            timestamp = datetime.now()
            
        trade = {
            'timestamp': timestamp,
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'pnl': pnl,
            'value': quantity * price
        }
        
        self.trade_history.append(trade)
        
        # Update trade statistics
        self.trade_stats['total_trades'] += 1
        self.trade_stats['total_pnl'] += pnl
        
        if pnl > 0:
            self.trade_stats['winning_trades'] += 1
            if pnl > self.trade_stats['max_win']:
                self.trade_stats['max_win'] = pnl
        elif pnl < 0:
            self.trade_stats['losing_trades'] += 1
            if pnl < self.trade_stats['max_loss']:
                self.trade_stats['max_loss'] = pnl
    
    def record_signal(
        self,
        symbol: str,
        action: str,
        confidence: float,
        strategy: str,
        metadata: Dict[str, Any] = None,
        timestamp: datetime = None
    ):
        """Record a trading signal."""
        if timestamp is None:
            timestamp = datetime.now()
            
        signal = {
            'timestamp': timestamp,
            'symbol': symbol,
            'action': action,
            'confidence': confidence,
            'strategy': strategy,
            'metadata': metadata or {}
        }
        
        self.signal_history.append(signal)
    
    def calculate_sharpe_ratio(self, window_days: int = 30) -> Optional[float]:
        """Calculate Sharpe ratio over a window period."""
        if len(self.daily_returns) < window_days:
            return None
            
        # Get recent returns
        recent_returns = list(self.daily_returns)[-window_days:]
        returns = [r['return'] for r in recent_returns]
        
        if not returns:
            return None
            
        # Calculate mean and std
        mean_return = sum(returns) / len(returns)
        if len(returns) > 1:
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_return = variance ** 0.5
        else:
            std_return = 0
            
        # Calculate annualized Sharpe ratio (assuming 252 trading days)
        if std_return > 0:
            sharpe = (mean_return * 252) / (std_return * (252 ** 0.5))
        else:
            sharpe = 0
            
        # Record Sharpe ratio
        self.sharpe_ratios.append({
            'timestamp': datetime.now(),
            'sharpe_ratio': sharpe,
            'window_days': window_days
        })
        
        return sharpe
    
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics over specified period."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Filter data by date
        recent_values = [
            v for v in self.portfolio_values 
            if v['timestamp'] >= cutoff_date
        ]
        
        recent_trades = [
            t for t in self.trade_history 
            if t['timestamp'] >= cutoff_date
        ]
        
        recent_returns = [
            r for r in self.daily_returns 
            if r['timestamp'] >= cutoff_date
        ]
        
        if not recent_values:
            return {}
        
        # Calculate metrics
        start_value = recent_values[0]['value']
        end_value = recent_values[-1]['value']
        total_return = (end_value - start_value) / start_value if start_value > 0 else 0
        
        # Trade metrics
        trade_count = len(recent_trades)
        winning_trades = sum(1 for t in recent_trades if t['pnl'] > 0)
        win_rate = winning_trades / trade_count if trade_count > 0 else 0
        
        # Return metrics
        if recent_returns:
            returns = [r['return'] for r in recent_returns]
            avg_daily_return = sum(returns) / len(returns)
            volatility = (sum((r - avg_daily_return) ** 2 for r in returns) / len(returns)) ** 0.5 if len(returns) > 1 else 0
        else:
            avg_daily_return = 0
            volatility = 0
            
        return {
            'period_days': days,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'avg_daily_return': avg_daily_return,
            'volatility': volatility,
            'sharpe_ratio': self.calculate_sharpe_ratio(min(days, len(recent_returns))),
            'trade_count': trade_count,
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': trade_count - winning_trades,
            'start_value': start_value,
            'end_value': end_value
        }
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """Get overall trade summary."""
        total_trades = self.trade_stats['total_trades']
        winning_trades = self.trade_stats['winning_trades']
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': self.trade_stats['losing_trades'],
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': self.trade_stats['total_pnl'],
            'avg_pnl_per_trade': self.trade_stats['total_pnl'] / total_trades if total_trades > 0 else 0,
            'max_win': self.trade_stats['max_win'],
            'max_loss': self.trade_stats['max_loss'],
            'profit_factor': abs(self.trade_stats['max_win'] / self.trade_stats['max_loss']) if self.trade_stats['max_loss'] < 0 else 0
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            'performance_7d': self.get_performance_metrics(7),
            'performance_30d': self.get_performance_metrics(30),
            'trade_summary': self.get_trade_summary(),
            'current_sharpe': self.calculate_sharpe_ratio(),
            'data_points': {
                'portfolio_values': len(self.portfolio_values),
                'trades': len(self.trade_history),
                'signals': len(self.signal_history)
            }
        }
    
    def export_data(self) -> Dict[str, Any]:
        """Export all collected data."""
        return {
            'portfolio_values': list(self.portfolio_values),
            'trade_history': list(self.trade_history),
            'signal_history': list(self.signal_history),
            'daily_returns': list(self.daily_returns),
            'trade_stats': self.trade_stats,
            'export_timestamp': datetime.now().isoformat()
        }
