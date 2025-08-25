"""
IBKR contract creation utilities for ASX stocks
Moved from asx_contracts.py to provide clean contract creation without hard-coded symbols
"""

from ibapi.contract import Contract
import structlog

logger = structlog.get_logger(__name__)


def create_asx_stock_contract(symbol: str) -> Contract:
    """
    Create properly formatted ASX stock contract for IBKR API
    
    Args:
        symbol: Stock symbol (e.g., "BHP", "CBA")
        
    Returns:
        Contract object configured for ASX stock
    """
    contract = Contract()
    contract.symbol = symbol.upper().strip()
    contract.secType = "STK"
    contract.currency = "AUD"
    contract.exchange = "ASX"
    contract.primaryExchange = "ASX"
    return contract


def create_contract_from_details(symbol: str, con_id: int, exchange: str = "ASX", 
                                currency: str = "AUD") -> Contract:
    """
    Create contract from contract details data
    
    Args:
        symbol: Stock symbol
        con_id: IBKR contract ID
        exchange: Exchange name
        currency: Currency code
        
    Returns:
        Contract object configured with provided details
    """
    contract = Contract()
    contract.symbol = symbol.upper().strip()
    contract.conId = con_id
    contract.secType = "STK" 
    contract.currency = currency
    contract.exchange = exchange
    contract.primaryExchange = exchange
    return contract