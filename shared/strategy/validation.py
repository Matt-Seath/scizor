"""
Strategy validation utilities.

This module provides validation for strategy configurations and implementations.
"""

import inspect
from typing import List, Dict, Any, Type, Optional
from datetime import datetime
import pandas as pd

from .base import BaseStrategy, StrategyConfig, StrategySignal


class ValidationError(Exception):
    """Raised when strategy validation fails."""
    pass


class StrategyValidator:
    """
    Validates strategy implementations and configurations.
    
    Ensures strategies properly implement required methods and have valid configurations.
    """
    
    @staticmethod
    def validate_strategy_class(strategy_class: Type[BaseStrategy]) -> List[str]:
        """
        Validate a strategy class implementation.
        
        Args:
            strategy_class: Strategy class to validate
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Check if it inherits from BaseStrategy
        if not issubclass(strategy_class, BaseStrategy):
            issues.append("Strategy must inherit from BaseStrategy")
            return issues
        
        # Check required methods are implemented
        required_methods = ['initialize', 'generate_signals', 'update_state']
        
        for method_name in required_methods:
            if not hasattr(strategy_class, method_name):
                issues.append(f"Missing required method: {method_name}")
                continue
            
            method = getattr(strategy_class, method_name)
            if getattr(method, '__isabstractmethod__', False):
                issues.append(f"Method {method_name} is not implemented (still abstract)")
        
        # Check method signatures
        try:
            # Check initialize method
            init_sig = inspect.signature(strategy_class.initialize)
            init_params = list(init_sig.parameters.keys())
            expected_init = ['self', 'symbols', 'start_date', 'end_date']
            if init_params != expected_init:
                issues.append(f"initialize method signature should be {expected_init}, got {init_params}")
            
            # Check generate_signals method
            signals_sig = inspect.signature(strategy_class.generate_signals)
            signals_params = list(signals_sig.parameters.keys())
            expected_signals = ['self', 'data', 'timestamp', 'portfolio_state']
            if signals_params != expected_signals:
                issues.append(f"generate_signals method signature should be {expected_signals}, got {signals_params}")
            
            # Check update_state method
            update_sig = inspect.signature(strategy_class.update_state)
            update_params = list(update_sig.parameters.keys())
            expected_update = ['self', 'data', 'timestamp', 'portfolio_state']
            if update_params != expected_update:
                issues.append(f"update_state method signature should be {expected_update}, got {update_params}")
                
        except Exception as e:
            issues.append(f"Error checking method signatures: {str(e)}")
        
        return issues
    
    @staticmethod
    def validate_strategy_config(config: StrategyConfig) -> List[str]:
        """
        Validate strategy configuration.
        
        Args:
            config: Strategy configuration to validate
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Basic validation
        if not config.name or len(config.name.strip()) == 0:
            issues.append("Strategy name cannot be empty")
        
        if config.max_position_size <= 0:
            issues.append("max_position_size must be positive")
        
        if config.max_positions <= 0:
            issues.append("max_positions must be positive")
        
        if config.risk_per_trade <= 0 or config.risk_per_trade > 1:
            issues.append("risk_per_trade must be between 0 and 1")
        
        if config.lookback_period <= 0:
            issues.append("lookback_period must be positive")
        
        # Risk management validation
        if config.stop_loss_pct is not None:
            if config.stop_loss_pct <= 0 or config.stop_loss_pct >= 1:
                issues.append("stop_loss_pct must be between 0 and 1")
        
        if config.take_profit_pct is not None:
            if config.take_profit_pct <= 0:
                issues.append("take_profit_pct must be positive")
        
        # Rebalance frequency validation
        valid_frequencies = ['daily', 'weekly', 'monthly', 'quarterly']
        if config.rebalance_frequency not in valid_frequencies:
            issues.append(f"rebalance_frequency must be one of {valid_frequencies}")
        
        return issues
    
    @staticmethod
    def validate_strategy_signals(signals: List[StrategySignal]) -> List[str]:
        """
        Validate a list of strategy signals.
        
        Args:
            signals: List of signals to validate
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        for i, signal in enumerate(signals):
            signal_issues = StrategyValidator.validate_signal(signal)
            for issue in signal_issues:
                issues.append(f"Signal {i}: {issue}")
        
        return issues
    
    @staticmethod
    def validate_signal(signal: StrategySignal) -> List[str]:
        """
        Validate a single strategy signal.
        
        Args:
            signal: Signal to validate
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Basic validation
        if not signal.symbol or len(signal.symbol.strip()) == 0:
            issues.append("Signal symbol cannot be empty")
        
        if signal.price <= 0:
            issues.append("Signal price must be positive")
        
        if signal.confidence < 0 or signal.confidence > 1:
            issues.append("Signal confidence must be between 0 and 1")
        
        if signal.quantity is not None and signal.quantity <= 0:
            issues.append("Signal quantity must be positive")
        
        # Order type specific validation
        if signal.order_type.value == "LIMIT" and signal.limit_price is None:
            issues.append("LIMIT orders require limit_price")
        
        if signal.order_type.value in ["STOP", "STOP_LIMIT"] and signal.stop_price is None:
            issues.append("STOP orders require stop_price")
        
        if signal.order_type.value == "STOP_LIMIT":
            if signal.limit_price is None:
                issues.append("STOP_LIMIT orders require limit_price")
            if signal.stop_price is None:
                issues.append("STOP_LIMIT orders require stop_price")
        
        # Price validation for order types
        if signal.limit_price is not None and signal.limit_price <= 0:
            issues.append("limit_price must be positive")
        
        if signal.stop_price is not None and signal.stop_price <= 0:
            issues.append("stop_price must be positive")
        
        return issues
    
    @staticmethod
    def validate_data_format(data: Dict[str, pd.DataFrame]) -> List[str]:
        """
        Validate market data format for strategy consumption.
        
        Args:
            data: Dictionary of symbol -> DataFrame with market data
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        if not data:
            issues.append("Data dictionary cannot be empty")
            return issues
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        for symbol, df in data.items():
            if not isinstance(df, pd.DataFrame):
                issues.append(f"{symbol}: Data must be a pandas DataFrame")
                continue
            
            if df.empty:
                issues.append(f"{symbol}: DataFrame cannot be empty")
                continue
            
            # Check required columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                issues.append(f"{symbol}: Missing required columns: {missing_columns}")
            
            # Check data types
            for col in required_columns:
                if col in df.columns:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        issues.append(f"{symbol}: Column {col} must be numeric")
            
            # Check for negative prices
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                if col in df.columns and (df[col] <= 0).any():
                    issues.append(f"{symbol}: Column {col} contains non-positive values")
            
            # Check for negative volume
            if 'volume' in df.columns and (df['volume'] < 0).any():
                issues.append(f"{symbol}: Volume contains negative values")
            
            # Check OHLC relationship
            if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
                # High should be >= Open, Close
                if (df['high'] < df['open']).any() or (df['high'] < df['close']).any():
                    issues.append(f"{symbol}: High price is less than Open or Close")
                
                # Low should be <= Open, Close
                if (df['low'] > df['open']).any() or (df['low'] > df['close']).any():
                    issues.append(f"{symbol}: Low price is greater than Open or Close")
        
        return issues
    
    @staticmethod
    def validate_strategy_instance(strategy: BaseStrategy, 
                                 test_data: Optional[Dict[str, pd.DataFrame]] = None) -> List[str]:
        """
        Validate a strategy instance by running basic tests.
        
        Args:
            strategy: Strategy instance to validate
            test_data: Optional test data for validation
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Validate configuration
        config_issues = StrategyValidator.validate_strategy_config(strategy.config)
        issues.extend(config_issues)
        
        # If test data provided, run basic functionality tests
        if test_data is not None:
            data_issues = StrategyValidator.validate_data_format(test_data)
            if data_issues:
                issues.extend(data_issues)
                return issues  # Don't proceed if data is invalid
            
            try:
                # Test initialization
                symbols = list(test_data.keys())
                start_date = datetime(2023, 1, 1)
                end_date = datetime(2023, 12, 31)
                
                strategy.initialize(symbols, start_date, end_date)
                
                if not strategy.is_initialized:
                    issues.append("Strategy did not set is_initialized to True after initialization")
                
                # Test signal generation
                portfolio_state = {'cash': 100000, 'positions': {}, 'total_value': 100000}
                timestamp = datetime(2023, 6, 1)
                
                signals = strategy.generate_signals(test_data, timestamp, portfolio_state)
                
                if not isinstance(signals, list):
                    issues.append("generate_signals must return a list")
                else:
                    signal_issues = StrategyValidator.validate_strategy_signals(signals)
                    issues.extend(signal_issues)
                
                # Test state update
                strategy.update_state(test_data, timestamp, portfolio_state)
                
                if strategy.last_update is None:
                    issues.append("Strategy should update last_update timestamp in update_state")
                
            except Exception as e:
                issues.append(f"Error during strategy testing: {str(e)}")
        
        return issues
    
    @staticmethod
    def run_comprehensive_validation(strategy_class: Type[BaseStrategy], 
                                   config: StrategyConfig,
                                   test_data: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, Any]:
        """
        Run comprehensive validation on a strategy.
        
        Args:
            strategy_class: Strategy class to validate
            config: Configuration to use
            test_data: Optional test data
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'is_valid': True,
            'class_issues': [],
            'config_issues': [],
            'instance_issues': [],
            'total_issues': 0
        }
        
        # Validate class
        class_issues = StrategyValidator.validate_strategy_class(strategy_class)
        results['class_issues'] = class_issues
        
        # Validate config
        config_issues = StrategyValidator.validate_strategy_config(config)
        results['config_issues'] = config_issues
        
        # If class is valid, test instance
        if not class_issues:
            try:
                strategy = strategy_class(config)
                instance_issues = StrategyValidator.validate_strategy_instance(strategy, test_data)
                results['instance_issues'] = instance_issues
            except Exception as e:
                results['instance_issues'] = [f"Failed to create strategy instance: {str(e)}"]
        
        # Calculate totals
        total_issues = len(class_issues) + len(config_issues) + len(results['instance_issues'])
        results['total_issues'] = total_issues
        results['is_valid'] = total_issues == 0
        
        return results
