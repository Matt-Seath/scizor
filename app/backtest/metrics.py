import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import structlog

from app.backtest.engine import BacktestMetrics, BacktestTrade

logger = structlog.get_logger(__name__)


class PerformanceAnalyzer:
    """
    Advanced performance analysis for backtesting results
    Calculates comprehensive metrics for strategy evaluation
    """
    
    @staticmethod
    def calculate_advanced_metrics(trades: List[BacktestTrade], 
                                 portfolio_curve: pd.DataFrame,
                                 benchmark_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """
        Calculate comprehensive performance metrics
        
        Args:
            trades: List of completed trades
            portfolio_curve: DataFrame with date index and portfolio_value column
            benchmark_returns: Optional benchmark returns for comparison
            
        Returns:
            Dictionary of performance metrics
        """
        if trades is None or len(trades) == 0:
            return {}
        
        metrics = {}
        
        try:
            # Basic trade statistics
            metrics.update(PerformanceAnalyzer._calculate_trade_stats(trades))
            
            # Portfolio-level metrics
            metrics.update(PerformanceAnalyzer._calculate_portfolio_metrics(portfolio_curve))
            
            # Risk metrics
            metrics.update(PerformanceAnalyzer._calculate_risk_metrics(trades, portfolio_curve))
            
            # Time-based metrics
            metrics.update(PerformanceAnalyzer._calculate_time_metrics(trades))
            
            # Benchmark comparison (if available)
            if benchmark_returns is not None:
                metrics.update(PerformanceAnalyzer._calculate_benchmark_metrics(
                    portfolio_curve, benchmark_returns
                ))
            
            logger.info("Advanced metrics calculated", 
                       total_metrics=len(metrics),
                       total_trades=len(trades))
            
        except Exception as e:
            logger.error("Error calculating advanced metrics", error=str(e))
        
        return metrics
    
    @staticmethod
    def _calculate_trade_stats(trades: List[BacktestTrade]) -> Dict[str, float]:
        """Calculate trade-level statistics"""
        if not trades:
            return {}
        
        # Basic counts
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        break_even_trades = total_trades - winning_trades - losing_trades
        
        # P&L statistics
        total_pnl = sum(t.pnl for t in trades)
        gross_profits = sum(t.pnl for t in trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in trades if t.pnl < 0))
        
        # Return statistics
        returns = [t.return_pct for t in trades]
        positive_returns = [r for r in returns if r > 0]
        negative_returns = [r for r in returns if r < 0]
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'break_even_trades': break_even_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'loss_rate': losing_trades / total_trades if total_trades > 0 else 0,
            'profit_factor': gross_profits / gross_losses if gross_losses > 0 else float('inf'),
            'total_pnl': total_pnl,
            'avg_trade_pnl': total_pnl / total_trades if total_trades > 0 else 0,
            'avg_win': np.mean(positive_returns) if positive_returns else 0,
            'avg_loss': np.mean(negative_returns) if negative_returns else 0,
            'largest_win': max(returns) if returns else 0,
            'largest_loss': min(returns) if returns else 0,
            'avg_trade_return': np.mean(returns) if returns else 0,
            'median_trade_return': np.median(returns) if returns else 0,
            'std_trade_return': np.std(returns) if len(returns) > 1 else 0
        }
    
    @staticmethod
    def _calculate_portfolio_metrics(portfolio_curve: pd.DataFrame) -> Dict[str, float]:
        """Calculate portfolio-level performance metrics"""
        if portfolio_curve.empty:
            return {}
        
        # Ensure we have the right column name
        value_col = 'portfolio_value' if 'portfolio_value' in portfolio_curve.columns else portfolio_curve.columns[0]
        values = portfolio_curve[value_col]
        
        initial_value = values.iloc[0]
        final_value = values.iloc[-1]
        
        # Calculate daily returns
        daily_returns = values.pct_change().dropna()
        
        # Total return
        total_return = (final_value - initial_value) / initial_value
        
        # Annualized return
        trading_days = len(values)
        years = trading_days / 252  # Approximate trading days per year
        annual_return = ((1 + total_return) ** (1 / years)) - 1 if years > 0 else 0
        
        # Volatility
        annual_volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0
        
        # Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate = 0.02
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = daily_returns[daily_returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = (annual_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'daily_return_mean': daily_returns.mean() if len(daily_returns) > 0 else 0,
            'daily_return_std': daily_returns.std() if len(daily_returns) > 1 else 0,
            'final_portfolio_value': final_value
        }
    
    @staticmethod
    def _calculate_risk_metrics(trades: List[BacktestTrade], 
                              portfolio_curve: pd.DataFrame) -> Dict[str, float]:
        """Calculate risk-related metrics"""
        metrics = {}
        
        # Drawdown calculations
        if not portfolio_curve.empty:
            value_col = 'portfolio_value' if 'portfolio_value' in portfolio_curve.columns else portfolio_curve.columns[0]
            values = portfolio_curve[value_col]
            
            # Calculate drawdowns
            peak = values.expanding().max()
            drawdown = (values - peak) / peak
            
            metrics['max_drawdown'] = abs(drawdown.min())
            metrics['avg_drawdown'] = abs(drawdown[drawdown < 0].mean()) if len(drawdown[drawdown < 0]) > 0 else 0
            
            # Drawdown duration
            in_drawdown = drawdown < -0.01  # More than 1% drawdown
            if in_drawdown.any():
                drawdown_periods = []
                current_period = 0
                
                for in_dd in in_drawdown:
                    if in_dd:
                        current_period += 1
                    else:
                        if current_period > 0:
                            drawdown_periods.append(current_period)
                        current_period = 0
                
                if current_period > 0:
                    drawdown_periods.append(current_period)
                
                metrics['max_drawdown_duration'] = max(drawdown_periods) if drawdown_periods else 0
                metrics['avg_drawdown_duration'] = np.mean(drawdown_periods) if drawdown_periods else 0
            else:
                metrics['max_drawdown_duration'] = 0
                metrics['avg_drawdown_duration'] = 0
        
        # Trade-level risk metrics
        if trades:
            returns = [t.return_pct for t in trades]
            negative_returns = [r for r in returns if r < 0]
            
            # Value at Risk (95% confidence)
            if len(returns) >= 20:  # Need sufficient sample size
                var_95 = np.percentile(returns, 5)  # 5th percentile
                var_99 = np.percentile(returns, 1)  # 1st percentile
                metrics['var_95'] = var_95
                metrics['var_99'] = var_99
            
            # Expected shortfall (Conditional VaR)
            if len(negative_returns) >= 5:
                expected_shortfall = np.mean(sorted(negative_returns)[:int(len(negative_returns) * 0.05)])
                metrics['expected_shortfall'] = expected_shortfall
            
            # Maximum consecutive losses
            consecutive_losses = 0
            max_consecutive_losses = 0
            
            for trade in trades:
                if trade.pnl < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0
            
            metrics['max_consecutive_losses'] = max_consecutive_losses
        
        return metrics
    
    @staticmethod
    def _calculate_time_metrics(trades: List[BacktestTrade]) -> Dict[str, float]:
        """Calculate time-based metrics"""
        if not trades:
            return {}
        
        # Holding period statistics
        holding_days = [t.holding_days for t in trades]
        
        # Monthly/weekly analysis
        trades_by_month = {}
        trades_by_weekday = {}
        
        for trade in trades:
            month = trade.entry_date.month
            weekday = trade.entry_date.weekday()
            
            if month not in trades_by_month:
                trades_by_month[month] = []
            trades_by_month[month].append(trade.return_pct)
            
            if weekday not in trades_by_weekday:
                trades_by_weekday[weekday] = []
            trades_by_weekday[weekday].append(trade.return_pct)
        
        # Best/worst months
        monthly_returns = {month: np.mean(returns) for month, returns in trades_by_month.items()}
        best_month = max(monthly_returns, key=monthly_returns.get) if monthly_returns else 0
        worst_month = min(monthly_returns, key=monthly_returns.get) if monthly_returns else 0
        
        return {
            'avg_holding_days': np.mean(holding_days),
            'median_holding_days': np.median(holding_days),
            'min_holding_days': min(holding_days),
            'max_holding_days': max(holding_days),
            'best_month': best_month,
            'worst_month': worst_month,
            'best_month_return': monthly_returns.get(best_month, 0),
            'worst_month_return': monthly_returns.get(worst_month, 0)
        }
    
    @staticmethod
    def _calculate_benchmark_metrics(portfolio_curve: pd.DataFrame, 
                                   benchmark_returns: pd.Series) -> Dict[str, float]:
        """Calculate metrics relative to benchmark"""
        try:
            value_col = 'portfolio_value' if 'portfolio_value' in portfolio_curve.columns else portfolio_curve.columns[0]
            portfolio_returns = portfolio_curve[value_col].pct_change().dropna()
            
            # Align dates
            common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
            if len(common_dates) < 10:  # Need sufficient overlap
                return {}
            
            portfolio_aligned = portfolio_returns.loc[common_dates]
            benchmark_aligned = benchmark_returns.loc[common_dates]
            
            # Alpha and Beta
            if len(portfolio_aligned) > 1 and len(benchmark_aligned) > 1:
                covariance = np.cov(portfolio_aligned, benchmark_aligned)[0, 1]
                benchmark_variance = np.var(benchmark_aligned)
                
                beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
                
                portfolio_mean = portfolio_aligned.mean() * 252  # Annualized
                benchmark_mean = benchmark_aligned.mean() * 252  # Annualized
                risk_free_rate = 0.02
                
                alpha = (portfolio_mean - risk_free_rate) - beta * (benchmark_mean - risk_free_rate)
                
                # Information ratio
                excess_returns = portfolio_aligned - benchmark_aligned
                tracking_error = excess_returns.std() * np.sqrt(252)
                information_ratio = (excess_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0
                
                # Correlation
                correlation = np.corrcoef(portfolio_aligned, benchmark_aligned)[0, 1]
                
                return {
                    'alpha': alpha,
                    'beta': beta,
                    'information_ratio': information_ratio,
                    'tracking_error': tracking_error,
                    'correlation_with_benchmark': correlation
                }
        
        except Exception as e:
            logger.error("Error calculating benchmark metrics", error=str(e))
        
        return {}


class StrategyComparison:
    """Compare performance across multiple strategies"""
    
    @staticmethod
    def compare_strategies(strategy_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Compare multiple strategy results
        
        Args:
            strategy_results: Dict of strategy_name -> metrics dict
            
        Returns:
            DataFrame with comparison metrics
        """
        if not strategy_results:
            return pd.DataFrame()
        
        # Key metrics for comparison
        comparison_metrics = [
            'total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown',
            'win_rate', 'profit_factor', 'total_trades', 'avg_holding_days'
        ]
        
        comparison_data = {}
        
        for strategy_name, metrics in strategy_results.items():
            comparison_data[strategy_name] = {
                metric: metrics.get(metric, 0) for metric in comparison_metrics
            }
        
        df = pd.DataFrame(comparison_data).T
        
        # Add ranking columns
        for metric in comparison_metrics:
            if metric in ['max_drawdown']:  # Lower is better
                df[f'{metric}_rank'] = df[metric].rank(ascending=True)
            else:  # Higher is better
                df[f'{metric}_rank'] = df[metric].rank(ascending=False)
        
        # Calculate overall score (average of ranks)
        rank_columns = [col for col in df.columns if col.endswith('_rank')]
        df['overall_rank'] = df[rank_columns].mean(axis=1)
        
        return df.sort_values('overall_rank')


class ReportGenerator:
    """Generate comprehensive backtest reports"""
    
    @staticmethod
    def generate_summary_report(strategy_name: str, metrics: Dict[str, float], 
                              trades: List[BacktestTrade]) -> str:
        """Generate a summary report for a strategy"""
        
        report = f"""
        BACKTEST SUMMARY REPORT
        =======================
        
        Strategy: {strategy_name}
        Analysis Period: {trades[0].entry_date.strftime('%Y-%m-%d') if trades else 'N/A'} to {trades[-1].exit_date.strftime('%Y-%m-%d') if trades else 'N/A'}
        
        PERFORMANCE METRICS
        -------------------
        Total Return: {metrics.get('total_return', 0):.2%}
        Annual Return: {metrics.get('annual_return', 0):.2%}
        Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}
        Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}
        Maximum Drawdown: {metrics.get('max_drawdown', 0):.2%}
        
        TRADE STATISTICS
        ----------------
        Total Trades: {metrics.get('total_trades', 0)}
        Win Rate: {metrics.get('win_rate', 0):.2%}
        Profit Factor: {metrics.get('profit_factor', 0):.2f}
        Average Trade Return: {metrics.get('avg_trade_return', 0):.2%}
        Average Holding Days: {metrics.get('avg_holding_days', 0):.1f}
        
        RISK METRICS
        ------------
        Annual Volatility: {metrics.get('annual_volatility', 0):.2%}
        VaR (95%): {metrics.get('var_95', 0):.2%}
        Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0)}
        Max Drawdown Duration: {metrics.get('max_drawdown_duration', 0)} days
        
        TRADE BREAKDOWN
        ---------------
        Winning Trades: {metrics.get('winning_trades', 0)}
        Losing Trades: {metrics.get('losing_trades', 0)}
        Largest Win: {metrics.get('largest_win', 0):.2%}
        Largest Loss: {metrics.get('largest_loss', 0):.2%}
        Average Win: {metrics.get('avg_win', 0):.2%}
        Average Loss: {metrics.get('avg_loss', 0):.2%}
        """
        
        return report