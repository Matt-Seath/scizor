from typing import List, Dict
from ibapi.contract import Contract
import structlog

logger = structlog.get_logger(__name__)


def create_asx_stock_contract(symbol: str) -> Contract:
    """Create properly formatted ASX stock contract"""
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.currency = "AUD"
    contract.exchange = "ASX"
    contract.primaryExchange = "ASX"
    return contract


def get_asx200_symbols() -> List[str]:
    """
    Get ASX200 constituent symbols.
    NOTE: This is a subset for development. Production should use full ASX200 list
    updated from official ASX source quarterly.
    """
    # Top 50 most liquid ASX200 stocks for development/testing
    return [
        "BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG", "TLS", "WOW",
        "NCM", "RIO", "TCL", "GMG", "STO", "COL", "ALL", "REA", "XRO", "CPU",
        "IAG", "QBE", "ASX", "JHX", "COH", "SHL", "APT", "CAR", "LLC", "TPM",
        "WTC", "RMD", "PME", "AMP", "ORG", "AGL", "CTD", "SGP", "ALD", "CWN",
        "BOQ", "HVN", "ING", "DXS", "SKI", "NAN", "FPH", "IPL", "TWE", "ALU"
    ]


def get_asx200_major_contracts() -> Dict[str, Contract]:
    """Get pre-built contracts for major ASX200 stocks"""
    major_symbols = [
        "BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG", "TLS", "WOW"
    ]
    
    contracts = {}
    for symbol in major_symbols:
        contracts[symbol] = create_asx_stock_contract(symbol)
    
    logger.info("Created ASX major stock contracts", count=len(contracts))
    return contracts


def get_market_cap_tiers() -> Dict[str, List[str]]:
    """
    Categorize ASX200 stocks by market cap for strategy allocation
    """
    return {
        "large_cap": [
            "BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG"
        ],
        "mid_cap": [
            "TLS", "WOW", "NCM", "RIO", "TCL", "GMG", "STO", "COL",
            "ALL", "REA", "XRO", "CPU", "IAG", "QBE", "ASX", "JHX"
        ],
        "small_cap": [
            "COH", "SHL", "APT", "CAR", "LLC", "TPM", "WTC", "RMD",
            "PME", "AMP", "ORG", "AGL", "CTD", "SGP", "ALD", "CWN",
            "BOQ", "HVN", "ING", "DXS", "SKI", "NAN", "FPH", "IPL",
            "TWE", "ALU"
        ]
    }


def validate_asx_symbol(symbol: str) -> bool:
    """Validate if symbol is in our ASX200 list"""
    return symbol.upper() in get_asx200_symbols()


def get_liquid_stocks(count: int = 20) -> List[str]:
    """Get most liquid ASX stocks for intraday strategies"""
    liquid_stocks = [
        "BHP", "CBA", "CSL", "ANZ", "WBC", "NAB", "WES", "MQG", 
        "TLS", "WOW", "NCM", "RIO", "TCL", "GMG", "STO", "COL",
        "ALL", "REA", "XRO", "CPU"
    ]
    return liquid_stocks[:count]