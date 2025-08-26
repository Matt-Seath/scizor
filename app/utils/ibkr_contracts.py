"""
IBKR contract creation utilities for stocks
Moved from asx_contracts.py to provide clean contract creation without hard-coded symbols
"""

from ibapi.contract import Contract
import structlog

logger = structlog.get_logger(__name__)


def create_stock_contract(symbol: str, exchange: str = "ASX", currency: str = "AUD") -> Contract:
    """
    Create properly formatted stock contract for IBKR API
    
    Args:
        symbol: Stock symbol (e.g., "BHP", "AAPL")
        exchange: Exchange code (e.g., "ASX", "NASDAQ", "NYSE")
        currency: Currency code (e.g., "AUD", "USD")
        
    Returns:
        Contract object configured for specified exchange
    """
    contract = Contract()
    contract.symbol = symbol.upper().strip()
    contract.secType = "STK"
    contract.currency = currency
    contract.exchange = exchange
    contract.primaryExchange = exchange
    return contract


# Backwards compatibility - can be removed later
def create_asx_stock_contract(symbol: str) -> Contract:
    """
    DEPRECATED: Use create_stock_contract() instead
    Backwards compatibility for existing code
    """
    return create_stock_contract(symbol, "ASX", "AUD")


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