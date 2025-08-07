"""
Error analysis utilities for SCIZOR data collection.
Categorizes and analyzes IBKR and other collection errors.
"""

import re
from typing import Dict, Optional, Tuple
from datetime import datetime


class ErrorAnalyzer:
    """Analyze and categorize data collection errors."""
    
    # IBKR Error Code Categories
    IBKR_ERROR_CATEGORIES = {
        # Security Definition Errors
        200: "no_security_definition",
        162: "historical_data_query_error", 
        321: "error_validating_request",
        10167: "requested_market_data_not_subscribed",
        
        # Connection Errors  
        1100: "connectivity_lost",
        1101: "connectivity_restored", 
        1102: "connectivity_lost_data_maintained",
        2103: "market_data_farm_disconnected",
        2104: "market_data_farm_connected",
        2105: "historical_data_farm_disconnected",
        2106: "historical_data_farm_connected",
        
        # Rate Limiting / Pacing
        162: "pacing_violation",
        420: "unsupported_request",
        10018: "request_market_data_sending_error",
        10090: "part_of_requested_market_data_not_subscribed",
        
        # Data Quality Issues
        354: "requested_halted",
        10089: "request_market_data_not_allowed",
        10168: "market_data_request_has_been_halted",
        
        # Authentication/Permission Errors
        10147: "order_size_does_not_conform",
        10148: "invalid_client_id",
        504: "not_connected",
        
        # System/Server Errors
        502: "couldn_connect_to_server", 
        503: "could_not_connect_socket",
        1300: "socket_exception_occurred"
    }
    
    # Error Type Categories
    ERROR_TYPES = {
        "no_security_definition": "SECURITY_NOT_FOUND",
        "historical_data_query_error": "DATA_QUERY_ERROR", 
        "connectivity_lost": "CONNECTION_ERROR",
        "connectivity_restored": "CONNECTION_RESTORED",
        "pacing_violation": "RATE_LIMIT",
        "requested_halted": "MARKET_HALTED",
        "not_connected": "CONNECTION_ERROR",
        "couldn_connect_to_server": "CONNECTION_ERROR",
        "socket_exception_occurred": "CONNECTION_ERROR"
    }
    
    @classmethod
    def analyze_error(cls, error_code: Optional[int] = None, 
                     error_message: Optional[str] = None,
                     request_id: Optional[int] = None) -> Dict:
        """
        Analyze an error and return categorized information.
        
        Args:
            error_code: IBKR error code
            error_message: Error message text
            request_id: IBKR request ID
            
        Returns:
            Dict with error analysis details
        """
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "error_code": error_code,
            "error_message": error_message,
            "request_id": request_id,
            "error_category": None,
            "error_type": None,
            "severity": "unknown",
            "is_retryable": False,
            "suggested_action": None,
            "raw_details": {
                "error_code": error_code,
                "error_message": error_message,
                "request_id": request_id
            }
        }
        
        # Categorize by error code
        if error_code:
            analysis["error_category"] = cls.IBKR_ERROR_CATEGORIES.get(
                error_code, "unknown_error_code"
            )
            analysis["error_type"] = cls.ERROR_TYPES.get(
                analysis["error_category"], "UNKNOWN"
            )
            
        # Analyze error message if available
        if error_message:
            analysis.update(cls._analyze_error_message(error_message))
            
        # Determine severity and retry logic
        analysis.update(cls._determine_severity_and_retry(error_code, error_message))
        
        return analysis
    
    @classmethod
    def _analyze_error_message(cls, error_message: str) -> Dict:
        """Extract information from error message text."""
        message_lower = error_message.lower()
        details = {
            "message_keywords": [],
            "extracted_symbols": [],
            "contains_symbol_reference": False
        }
        
        # Common error patterns
        patterns = {
            "no_security_definition": r"no security definition.*found",
            "connection_lost": r"connectivity.*lost",
            "pacing_violation": r"pacing|too many|rate limit",
            "halted": r"halted|suspended",
            "not_subscribed": r"not subscribed|market data",
            "timeout": r"timeout|timed out",
            "invalid_symbol": r"invalid.*symbol|symbol.*invalid"
        }
        
        # Check for patterns
        for pattern_name, pattern in patterns.items():
            if re.search(pattern, message_lower):
                details["message_keywords"].append(pattern_name)
                
        # Extract symbol references (simple pattern)
        symbol_pattern = r"\b[A-Z]{1,5}\b"
        potential_symbols = re.findall(symbol_pattern, error_message)
        if potential_symbols:
            details["extracted_symbols"] = potential_symbols
            details["contains_symbol_reference"] = True
            
        return details
    
    @classmethod 
    def _determine_severity_and_retry(cls, error_code: Optional[int], 
                                    error_message: Optional[str]) -> Dict:
        """Determine error severity and if retry should be attempted."""
        severity_info = {
            "severity": "medium",
            "is_retryable": False,
            "suggested_action": "log_and_continue",
            "retry_delay_seconds": None
        }
        
        if not error_code:
            return severity_info
            
        # Critical errors - should stop collection
        critical_errors = [504, 502, 503, 1300]
        if error_code in critical_errors:
            severity_info.update({
                "severity": "critical",
                "is_retryable": False,
                "suggested_action": "stop_collection_and_alert"
            })
        # High severity - may need intervention
        elif error_code in [200, 321, 10167]:
            severity_info.update({
                "severity": "high", 
                "is_retryable": False,
                "suggested_action": "deactivate_symbol"
            })
        # Medium severity - retryable with backoff
        elif error_code in [162, 420, 10018]:
            severity_info.update({
                "severity": "medium",
                "is_retryable": True, 
                "suggested_action": "retry_with_backoff",
                "retry_delay_seconds": 30
            })
        # Low severity - connection issues, often self-resolving
        elif error_code in [1100, 1102, 2103, 2105]:
            severity_info.update({
                "severity": "low",
                "is_retryable": True,
                "suggested_action": "retry_after_delay", 
                "retry_delay_seconds": 10
            })
            
        return severity_info
    
    @classmethod
    def format_error_summary(cls, analysis: Dict) -> str:
        """Format error analysis into a readable summary."""
        error_code = analysis.get("error_code", "N/A")
        error_type = analysis.get("error_type", "UNKNOWN")
        severity = analysis.get("severity", "unknown")
        category = analysis.get("error_category", "unknown")
        
        summary = f"[{severity.upper()}] {error_type}"
        if error_code != "N/A":
            summary += f" (Code: {error_code})"
        if category != "unknown":
            summary += f" | {category}"
            
        return summary
    
    @classmethod
    def get_common_error_patterns(cls) -> Dict[str, Dict]:
        """Return common error patterns for debugging."""
        return {
            "security_not_found": {
                "codes": [200],
                "description": "Symbol not found in IBKR database",
                "common_causes": [
                    "Symbol delisted or merged",
                    "Incorrect symbol format", 
                    "Wrong exchange specified",
                    "Symbol suspended"
                ],
                "solutions": [
                    "Verify symbol is still active",
                    "Check correct exchange format",
                    "Update symbol database",
                    "Deactivate problematic symbols"
                ]
            },
            "connection_issues": {
                "codes": [1100, 1102, 502, 503, 504],
                "description": "IBKR connectivity problems",
                "common_causes": [
                    "TWS/Gateway disconnected",
                    "Network connectivity issues",
                    "IBKR server maintenance",
                    "Firewall blocking connection"
                ],
                "solutions": [
                    "Check TWS/Gateway status",
                    "Verify network connection",
                    "Restart IBKR connection",
                    "Implement retry logic"
                ]
            },
            "rate_limiting": {
                "codes": [162, 420, 10018],
                "description": "Request rate exceeded",
                "common_causes": [
                    "Too many concurrent requests",
                    "Pacing violation",
                    "Historical data limits exceeded"
                ],
                "solutions": [
                    "Implement request pacing",
                    "Reduce concurrent requests",
                    "Add delays between requests",
                    "Stagger collection times"
                ]
            }
        }
