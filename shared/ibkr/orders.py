"""Order utilities for IBKR API."""

from typing import Optional

from ibapi.order import Order


def create_market_order(action: str, quantity: int, account: Optional[str] = None) -> Order:
    """Create a market order."""
    order = Order()
    order.action = action.upper()  # BUY or SELL
    order.orderType = "MKT"
    order.totalQuantity = quantity
    order.tif = "DAY"
    
    if account:
        order.account = account
        
    return order


def create_limit_order(action: str, quantity: int, limit_price: float, 
                      account: Optional[str] = None, tif: str = "DAY") -> Order:
    """Create a limit order."""
    order = Order()
    order.action = action.upper()  # BUY or SELL
    order.orderType = "LMT"
    order.totalQuantity = quantity
    order.lmtPrice = limit_price
    order.tif = tif.upper()
    
    if account:
        order.account = account
        
    return order


def create_stop_order(action: str, quantity: int, stop_price: float,
                     account: Optional[str] = None, tif: str = "DAY") -> Order:
    """Create a stop order."""
    order = Order()
    order.action = action.upper()  # BUY or SELL
    order.orderType = "STP"
    order.totalQuantity = quantity
    order.auxPrice = stop_price
    order.tif = tif.upper()
    
    if account:
        order.account = account
        
    return order


def create_stop_limit_order(action: str, quantity: int, stop_price: float, 
                           limit_price: float, account: Optional[str] = None, 
                           tif: str = "DAY") -> Order:
    """Create a stop-limit order."""
    order = Order()
    order.action = action.upper()  # BUY or SELL
    order.orderType = "STP LMT"
    order.totalQuantity = quantity
    order.auxPrice = stop_price
    order.lmtPrice = limit_price
    order.tif = tif.upper()
    
    if account:
        order.account = account
        
    return order


def create_trailing_stop_order(action: str, quantity: int, trailing_percent: float,
                              account: Optional[str] = None, tif: str = "DAY") -> Order:
    """Create a trailing stop order."""
    order = Order()
    order.action = action.upper()  # BUY or SELL
    order.orderType = "TRAIL"
    order.totalQuantity = quantity
    order.trailingPercent = trailing_percent
    order.tif = tif.upper()
    
    if account:
        order.account = account
        
    return order


def create_bracket_order(parent_order_id: int, action: str, quantity: int, 
                        limit_price: float, take_profit_price: float, 
                        stop_loss_price: float, account: Optional[str] = None) -> tuple[Order, Order, Order]:
    """Create a bracket order (parent + take profit + stop loss)."""
    
    # Parent order
    parent = create_limit_order(action, quantity, limit_price, account)
    parent.orderId = parent_order_id
    parent.transmit = False
    
    # Take profit order
    take_profit_action = "SELL" if action.upper() == "BUY" else "BUY"
    take_profit = create_limit_order(take_profit_action, quantity, take_profit_price, account)
    take_profit.orderId = parent_order_id + 1
    take_profit.parentId = parent_order_id
    take_profit.transmit = False
    
    # Stop loss order
    stop_loss = create_stop_order(take_profit_action, quantity, stop_loss_price, account)
    stop_loss.orderId = parent_order_id + 2
    stop_loss.parentId = parent_order_id
    stop_loss.transmit = True  # This will transmit all three orders
    
    return parent, take_profit, stop_loss


def create_oca_order(action: str, quantity: int, limit_price: float, 
                    oca_group: str, account: Optional[str] = None) -> Order:
    """Create an OCA (One-Cancels-All) order."""
    order = create_limit_order(action, quantity, limit_price, account)
    order.ocaGroup = oca_group
    order.ocaType = 1  # Cancel on fill with block
    
    return order


def add_conditions_to_order(order: Order, conditions: list) -> Order:
    """Add conditions to an order."""
    order.conditions = conditions
    order.conditionsIgnoreRth = True
    order.conditionsCancelOrder = False
    
    return order


def set_good_after_time(order: Order, good_after_time: str) -> Order:
    """Set good after time for an order."""
    order.goodAfterTime = good_after_time
    return order


def set_good_till_date(order: Order, good_till_date: str) -> Order:
    """Set good till date for an order."""
    order.goodTillDate = good_till_date
    return order


def set_outside_regular_hours(order: Order, outside_rth: bool = True) -> Order:
    """Allow order to be filled outside regular trading hours."""
    order.outsideRth = outside_rth
    return order


def set_hidden_order(order: Order, hidden: bool = True) -> Order:
    """Make order hidden from the market."""
    order.hidden = hidden
    return order


def set_all_or_none(order: Order, all_or_none: bool = True) -> Order:
    """Set all-or-none condition."""
    order.allOrNone = all_or_none
    return order


def set_minimum_quantity(order: Order, min_qty: int) -> Order:
    """Set minimum quantity for order execution."""
    order.minQty = min_qty
    return order


def set_display_size(order: Order, display_size: int) -> Order:
    """Set display size for iceberg orders."""
    order.displaySize = display_size
    return order


def order_to_dict(order: Order) -> dict:
    """Convert order to dictionary."""
    return {
        "orderId": order.orderId,
        "action": order.action,
        "orderType": order.orderType,
        "totalQuantity": order.totalQuantity,
        "lmtPrice": order.lmtPrice,
        "auxPrice": order.auxPrice,
        "tif": order.tif,
        "account": order.account,
        "parentId": order.parentId,
        "ocaGroup": order.ocaGroup,
        "ocaType": order.ocaType,
        "transmit": order.transmit,
        "hidden": order.hidden,
        "outsideRth": order.outsideRth,
        "allOrNone": order.allOrNone,
        "minQty": order.minQty,
        "displaySize": order.displaySize,
        "trailingPercent": order.trailingPercent,
        "goodAfterTime": order.goodAfterTime,
        "goodTillDate": order.goodTillDate,
    }


def dict_to_order(data: dict) -> Order:
    """Convert dictionary to order."""
    order = Order()
    
    # Required fields
    order.action = data.get("action", "BUY")
    order.orderType = data.get("orderType", "MKT")
    order.totalQuantity = data.get("totalQuantity", 0)
    
    # Optional fields
    if "orderId" in data and data["orderId"]:
        order.orderId = data["orderId"]
    if "lmtPrice" in data and data["lmtPrice"]:
        order.lmtPrice = data["lmtPrice"]
    if "auxPrice" in data and data["auxPrice"]:
        order.auxPrice = data["auxPrice"]
    if "tif" in data and data["tif"]:
        order.tif = data["tif"]
    if "account" in data and data["account"]:
        order.account = data["account"]
    if "parentId" in data and data["parentId"]:
        order.parentId = data["parentId"]
    if "ocaGroup" in data and data["ocaGroup"]:
        order.ocaGroup = data["ocaGroup"]
    if "ocaType" in data and data["ocaType"]:
        order.ocaType = data["ocaType"]
    if "transmit" in data:
        order.transmit = data["transmit"]
    if "hidden" in data:
        order.hidden = data["hidden"]
    if "outsideRth" in data:
        order.outsideRth = data["outsideRth"]
    if "allOrNone" in data:
        order.allOrNone = data["allOrNone"]
    if "minQty" in data and data["minQty"]:
        order.minQty = data["minQty"]
    if "displaySize" in data and data["displaySize"]:
        order.displaySize = data["displaySize"]
    if "trailingPercent" in data and data["trailingPercent"]:
        order.trailingPercent = data["trailingPercent"]
    if "goodAfterTime" in data and data["goodAfterTime"]:
        order.goodAfterTime = data["goodAfterTime"]
    if "goodTillDate" in data and data["goodTillDate"]:
        order.goodTillDate = data["goodTillDate"]
        
    return order
