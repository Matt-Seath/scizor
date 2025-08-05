"""Contract utilities for IBKR API."""

from typing import Optional

from ibapi.contract import Contract


def create_stock_contract(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
    """Create a stock contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def create_forex_contract(symbol: str, currency: str = "USD") -> Contract:
    """Create a forex contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "CASH"
    contract.exchange = "IDEALPRO"
    contract.currency = currency
    return contract


def create_future_contract(symbol: str, exchange: str, last_trade_date: str, 
                          currency: str = "USD") -> Contract:
    """Create a future contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "FUT"
    contract.exchange = exchange
    contract.lastTradeDateOrContractMonth = last_trade_date
    contract.currency = currency
    return contract


def create_option_contract(symbol: str, exchange: str, last_trade_date: str,
                          strike: float, option_type: str, currency: str = "USD") -> Contract:
    """Create an option contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "OPT"
    contract.exchange = exchange
    contract.lastTradeDateOrContractMonth = last_trade_date
    contract.strike = strike
    contract.right = option_type  # "C" for call, "P" for put
    contract.currency = currency
    contract.multiplier = "100"
    return contract


def create_index_contract(symbol: str, exchange: str, currency: str = "USD") -> Contract:
    """Create an index contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "IND"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def create_bond_contract(symbol: str, exchange: str, currency: str = "USD") -> Contract:
    """Create a bond contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "BOND"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def create_crypto_contract(symbol: str, exchange: str = "PAXOS", currency: str = "USD") -> Contract:
    """Create a cryptocurrency contract."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "CRYPTO"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def contract_to_dict(contract: Contract) -> dict:
    """Convert contract to dictionary."""
    return {
        "symbol": contract.symbol,
        "secType": contract.secType,
        "exchange": contract.exchange,
        "currency": contract.currency,
        "conId": contract.conId,
        "localSymbol": contract.localSymbol,
        "tradingClass": contract.tradingClass,
        "multiplier": contract.multiplier,
        "lastTradeDateOrContractMonth": contract.lastTradeDateOrContractMonth,
        "strike": contract.strike,
        "right": contract.right,
    }


def dict_to_contract(data: dict) -> Contract:
    """Convert dictionary to contract."""
    contract = Contract()
    
    # Required fields
    contract.symbol = data.get("symbol", "")
    contract.secType = data.get("secType", "STK")
    contract.exchange = data.get("exchange", "SMART")
    contract.currency = data.get("currency", "USD")
    
    # Optional fields
    if "conId" in data and data["conId"]:
        contract.conId = data["conId"]
    if "localSymbol" in data and data["localSymbol"]:
        contract.localSymbol = data["localSymbol"]
    if "tradingClass" in data and data["tradingClass"]:
        contract.tradingClass = data["tradingClass"]
    if "multiplier" in data and data["multiplier"]:
        contract.multiplier = data["multiplier"]
    if "lastTradeDateOrContractMonth" in data and data["lastTradeDateOrContractMonth"]:
        contract.lastTradeDateOrContractMonth = data["lastTradeDateOrContractMonth"]
    if "strike" in data and data["strike"]:
        contract.strike = data["strike"]
    if "right" in data and data["right"]:
        contract.right = data["right"]
        
    return contract


def get_contract_description(contract: Contract) -> str:
    """Get a human-readable description of the contract."""
    if contract.secType == "STK":
        return f"{contract.symbol} Stock ({contract.exchange})"
    elif contract.secType == "OPT":
        return f"{contract.symbol} {contract.right} {contract.strike} {contract.lastTradeDateOrContractMonth}"
    elif contract.secType == "FUT":
        return f"{contract.symbol} Future {contract.lastTradeDateOrContractMonth}"
    elif contract.secType == "CASH":
        return f"{contract.symbol}.{contract.currency} Forex"
    elif contract.secType == "IND":
        return f"{contract.symbol} Index"
    elif contract.secType == "BOND":
        return f"{contract.symbol} Bond"
    elif contract.secType == "CRYPTO":
        return f"{contract.symbol} Crypto"
    else:
        return f"{contract.symbol} {contract.secType}"
