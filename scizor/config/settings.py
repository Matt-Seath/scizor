"""
Configuration management for Scizor trading system.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class CommissionSettings:
    rate: float = 0.001
    per_share: bool = False


@dataclass
class RiskSettings:
    max_position_size: float = 0.1
    stop_loss: float = 0.02
    take_profit: float = 0.06
    max_drawdown: float = 0.15


@dataclass
class TradingSettings:
    initial_capital: float = 100000
    commission: CommissionSettings = field(default_factory=CommissionSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)


@dataclass
class DataSettings:
    default_provider: str = "yahoo"
    cache_duration: int = 3600
    yahoo: Dict[str, Any] = field(default_factory=lambda: {
        "auto_adjust": True,
        "back_adjust": False
    })


@dataclass
class IBSettings:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    timeout: int = 30
    paper_trading: bool = True


@dataclass
class LoggingSettings:
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
    file: str = "logs/scizor.log"
    rotation: str = "1 day"
    retention: str = "30 days"


@dataclass
class MonitoringSettings:
    enable_dashboard: bool = False
    dashboard_port: int = 8000
    enable_slack_notifications: bool = False
    slack_webhook_url: str = ""


@dataclass
class StrategySettings:
    lookback_period: int = 20
    rebalance_frequency: str = "daily"


@dataclass
class Settings:
    trading: TradingSettings = field(default_factory=TradingSettings)
    data: DataSettings = field(default_factory=DataSettings)
    interactive_brokers: IBSettings = field(default_factory=IBSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)

    @classmethod
    def load_from_file(cls, config_path: str = None) -> 'Settings':
        """Load settings from YAML file."""
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"
        
        if not os.path.exists(config_path):
            print(f"Config file not found at {config_path}, using defaults")
            return cls()
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return cls._from_dict(config_data)
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'Settings':
        """Create Settings instance from dictionary."""
        settings = cls()
        
        if 'trading' in data:
            trading_data = data['trading']
            settings.trading = TradingSettings(
                initial_capital=trading_data.get('initial_capital', 100000),
                commission=CommissionSettings(**trading_data.get('commission', {})),
                risk=RiskSettings(**trading_data.get('risk', {}))
            )
        
        if 'data' in data:
            data_config = data['data']
            settings.data = DataSettings(
                default_provider=data_config.get('default_provider', 'yahoo'),
                cache_duration=data_config.get('cache_duration', 3600),
                yahoo=data_config.get('yahoo', settings.data.yahoo)
            )
        
        if 'interactive_brokers' in data:
            ib_data = data['interactive_brokers']
            settings.interactive_brokers = IBSettings(**ib_data)
        
        if 'logging' in data:
            logging_data = data['logging']
            settings.logging = LoggingSettings(**logging_data)
        
        if 'monitoring' in data:
            monitoring_data = data['monitoring']
            settings.monitoring = MonitoringSettings(**monitoring_data)
        
        if 'strategy' in data:
            strategy_data = data['strategy']
            settings.strategy = StrategySettings(**strategy_data)
        
        return settings
    
    def override_with_env(self):
        """Override settings with environment variables."""
        # Interactive Brokers settings
        if os.getenv('IB_HOST'):
            self.interactive_brokers.host = os.getenv('IB_HOST')
        if os.getenv('IB_PORT'):
            self.interactive_brokers.port = int(os.getenv('IB_PORT'))
        if os.getenv('IB_CLIENT_ID'):
            self.interactive_brokers.client_id = int(os.getenv('IB_CLIENT_ID'))
        
        # Slack webhook
        if os.getenv('SLACK_WEBHOOK_URL'):
            self.monitoring.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            
        return self


def get_settings(config_path: str = None) -> Settings:
    """
    Get application settings with environment variable overrides.
    
    Args:
        config_path: Path to config file (optional)
        
    Returns:
        Settings instance
    """
    settings = Settings.load_from_file(config_path)
    settings.override_with_env()
    return settings
