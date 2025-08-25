#!/usr/bin/env python3
"""
Populate contract details table by validating and inserting contracts from JSON file.
This script reads contract data from app/data/seeds/contracts.json, validates each 
contract against IBKR TWS API, and populates the database with comprehensive contract details.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from app.config.database import async_engine, AsyncSessionLocal
from app.config.settings import settings
from app.data.models.market import ContractDetail
from examples.client import IBKRManager
from ibapi.contract import Contract
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
logger = logging.getLogger(__name__)


class ContractUpdater:
    """Updates contract details by validating contracts from JSON file."""
    
    def __init__(self, json_file: str = "app/data/seeds/contracts.json"):
        self.json_file = json_file
        self.ibkr_manager = None
        self.session = None
        self.valid_contracts = []
        self.invalid_contracts = []
        self.existing_symbols = set()
        
    async def __aenter__(self):
        """Async context manager entry."""
        # Initialize database session
        self.session = AsyncSessionLocal()
        
        # Initialize IBKR connection using settings
        port = settings.ibkr_paper_port if settings.ibkr_paper_trading else settings.ibkr_live_port
        self.ibkr_manager = IBKRManager(
            host=settings.ibkr_host,
            port=port,
            client_id=settings.ibkr_client_id
        )
        
        # Connect with timeout from settings
        connected = await self.ibkr_manager.connect(timeout=settings.ibkr_connection_timeout)
        if not connected:
            raise ConnectionError("Failed to connect to IBKR TWS API")
            
        logger.info("Successfully connected to IBKR TWS API")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.ibkr_manager:
            await self.ibkr_manager.disconnect()
        if self.session:
            await self.session.close()
    
    def load_contracts_from_json(self) -> List[Dict]:
        """Load contract data from JSON file."""
        try:
            with open(self.json_file, 'r') as f:
                contracts = json.load(f)
            logger.debug(f"Loaded {len(contracts)} contracts from {self.json_file}")
            return contracts
        except FileNotFoundError:
            logger.error(f"Contract file {self.json_file} not found")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in contract file: {e}")
            return []
    
    def save_contracts_to_json(self, contracts: List[Dict]):
        """Save contract data back to JSON file."""
        try:
            with open(self.json_file, 'w') as f:
                json.dump(contracts, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving contract file: {e}")
    
    async def get_existing_symbols(self) -> set:
        """Get existing contract symbols from database."""
        try:
            result = await self.session.execute(select(ContractDetail.symbol))
            symbols = {row[0] for row in result}
            logger.debug(f"Found {len(symbols)} existing contracts in database")
            return symbols
        except Exception as e:
            logger.error(f"Database error fetching existing symbols: {e}")
            return set()
    
    def create_ibkr_contract(self, contract_data: Dict) -> Contract:
        """Create IBKR Contract object from JSON data."""
        contract = Contract()
        contract.symbol = contract_data["symbol"]
        contract.secType = contract_data["sec_type"]
        contract.currency = contract_data["currency"]
        contract.exchange = contract_data["exchange"]
        contract.primaryExchange = contract_data["primary_exchange"]
        return contract
    
    async def validate_contract_with_ibkr(self, contract_data: Dict) -> Optional[Dict]:
        """Validate contract against IBKR API and return enriched contract data."""
        try:
            logger.debug(f"Validating contract for {contract_data['symbol']}")
            
            ibkr_contract = self.create_ibkr_contract(contract_data)
            details = await self.ibkr_manager.get_contract_details(ibkr_contract)
            
            if details and len(details) > 0:
                detail = details[0]
                contract_detail = detail.contract
                
                
                enriched_data = {
                    "symbol": contract_data["symbol"],
                    "con_id": contract_detail.conId,
                    "sec_type": contract_data["sec_type"],
                    "currency": contract_data["currency"],
                    "exchange": contract_data["exchange"],
                    "primary_exchange": contract_data.get("primary_exchange"),
                    "local_symbol": contract_detail.localSymbol,
                    "trading_class": contract_detail.tradingClass,
                    
                    "long_name": getattr(detail, 'longName', None),
                    "market_name": getattr(detail, 'marketName', None),
                    
                    "industry": getattr(detail, 'industry', None),
                    "category": getattr(detail, 'category', None),
                    "subcategory": getattr(detail, 'subcategory', None),
                    
                    "min_tick": getattr(detail, 'minTick', None),
                    "price_magnifier": getattr(detail, 'priceMagnifier', 1),
                    "md_size_multiplier": getattr(detail, 'mdSizeMultiplier', 1),
                    
                    "market_rule_ids": getattr(detail, 'marketRuleIds', None),
                    "order_types": getattr(detail, 'orderTypes', None),
                    "valid_exchanges": getattr(detail, 'validExchanges', None),
                    
                    "trading_hours": getattr(detail, 'tradingHours', None),
                    "liquid_hours": getattr(detail, 'liquidHours', None),
                    "time_zone_id": getattr(detail, 'timeZoneId', None),
                    
                    "sec_id_list": json.dumps([str(sec_id) for sec_id in getattr(detail, 'secIdList', [])]),
                    "stock_type": getattr(detail, 'stockType', None),
                    "cusip": getattr(detail, 'cusip', None),
                    
                    "contract_month": contract_detail.lastTradeDateOrContractMonth or None,
                    "last_trading_day": None,
                    "real_expiration_date": getattr(detail, 'realExpirationDate', None),
                    "last_trade_time": getattr(detail, 'lastTradeTime', None),
                    
                    "bond_type": getattr(detail, 'bondType', None),
                    "coupon_type": getattr(detail, 'couponType', None),
                    "coupon": getattr(detail, 'coupon', None),
                    "callable": getattr(detail, 'callable', False),
                    "putable": getattr(detail, 'putable', False),
                    "convertible": getattr(detail, 'convertible', False),
                    "maturity": getattr(detail, 'maturity', None),
                    "issue_date": getattr(detail, 'issueDate', None),
                    "ratings": getattr(detail, 'ratings', None),
                    
                    "next_option_date": getattr(detail, 'nextOptionDate', None),
                    "next_option_type": getattr(detail, 'nextOptionType', None),
                    "next_option_partial": getattr(detail, 'nextOptionPartial', False),
                    
                    "under_con_id": getattr(detail, 'underConId', None),
                    "under_symbol": getattr(detail, 'underSymbol', None),
                    "under_sec_type": getattr(detail, 'underSecType', None),
                    
                    "agg_group": getattr(detail, 'aggGroup', None),
                    "ev_rule": getattr(detail, 'evRule', None),
                    "ev_multiplier": getattr(detail, 'evMultiplier', None),
                    "desc_append": getattr(detail, 'descAppend', None),
                    "notes": getattr(detail, 'notes', None)
                }
                
                logger.debug(f"Successfully validated {contract_data['symbol']} (ConID: {contract_detail.conId})")
                self.valid_contracts.append(contract_data["symbol"])
                return enriched_data
            else:
                logger.debug(f"No contract details found for {contract_data['symbol']}")
                self.invalid_contracts.append(contract_data["symbol"])
                return None
                
        except Exception as e:
            logger.warning(f"Failed to validate {contract_data['symbol']}: {e}")
            self.invalid_contracts.append(contract_data["symbol"])
            return None
    
    async def insert_contract_to_db(self, contract_data: Dict) -> bool:
        """Insert validated contract data into database."""
        try:
            contract_detail = ContractDetail(
                symbol=contract_data["symbol"],
                con_id=contract_data["con_id"],
                sec_type=contract_data["sec_type"],
                currency=contract_data["currency"],
                exchange=contract_data["exchange"],
                primary_exchange=contract_data.get("primary_exchange"),
                local_symbol=contract_data.get("local_symbol"),
                trading_class=contract_data.get("trading_class"),
                
                long_name=contract_data.get("long_name"),
                market_name=contract_data.get("market_name"),
                
                industry=contract_data.get("industry"),
                category=contract_data.get("category"),
                subcategory=contract_data.get("subcategory"),
                
                min_tick=contract_data.get("min_tick"),
                price_magnifier=contract_data.get("price_magnifier"),
                md_size_multiplier=contract_data.get("md_size_multiplier"),
                
                market_rule_ids=contract_data.get("market_rule_ids"),
                order_types=contract_data.get("order_types"),
                valid_exchanges=contract_data.get("valid_exchanges"),
                
                trading_hours=contract_data.get("trading_hours"),
                liquid_hours=contract_data.get("liquid_hours"),
                time_zone_id=contract_data.get("time_zone_id"),
                
                sec_id_list=contract_data.get("sec_id_list"),
                stock_type=contract_data.get("stock_type"),
                cusip=contract_data.get("cusip"),
                
                contract_month=contract_data.get("contract_month"),
                last_trading_day=contract_data.get("last_trading_day"),
                real_expiration_date=contract_data.get("real_expiration_date"),
                last_trade_time=contract_data.get("last_trade_time"),
                
                bond_type=contract_data.get("bond_type"),
                coupon_type=contract_data.get("coupon_type"),
                coupon=contract_data.get("coupon"),
                callable=contract_data.get("callable", False),
                putable=contract_data.get("putable", False),
                convertible=contract_data.get("convertible", False),
                maturity=contract_data.get("maturity"),
                issue_date=contract_data.get("issue_date"),
                ratings=contract_data.get("ratings"),
                
                next_option_date=contract_data.get("next_option_date"),
                next_option_type=contract_data.get("next_option_type"),
                next_option_partial=contract_data.get("next_option_partial", False),
                
                under_con_id=contract_data.get("under_con_id"),
                under_symbol=contract_data.get("under_symbol"),
                under_sec_type=contract_data.get("under_sec_type"),
                
                agg_group=contract_data.get("agg_group"),
                ev_rule=contract_data.get("ev_rule"),
                ev_multiplier=contract_data.get("ev_multiplier"),
                desc_append=contract_data.get("desc_append"),
                notes=contract_data.get("notes")
            )
            
            self.session.add(contract_detail)
            await self.session.commit()
            logger.debug(f"Inserted {contract_data['symbol']} into database")
            return True
            
        except IntegrityError as e:
            await self.session.rollback()
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"{contract_data['symbol']} already exists in database")
            else:
                logger.error(f"Database integrity error for {contract_data['symbol']}: {e}")
            return False
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Database error for {contract_data['symbol']}: {e}")
            return False
    
    async def process_contracts(self, keep_invalid: bool = False):
        """Main processing logic - load, validate, and update contracts."""
        self.existing_symbols = await self.get_existing_symbols()
        json_contracts = self.load_contracts_from_json()
        
        if not json_contracts:
            logger.error("No contracts found in JSON file")
            return
        
        logger.info(f"Processing {len(json_contracts)} contracts ({len(self.existing_symbols)} already in database)")
        
        updated_contracts = []
        new_contracts_added = 0
        
        for i, contract_data in enumerate(json_contracts, 1):
            symbol = contract_data.get("symbol")
            logger.debug(f"[{i}/{len(json_contracts)}] Processing {symbol}")
            
            if symbol in self.existing_symbols:
                logger.debug(f"Skipping {symbol} - already exists in database")
                updated_contracts.append(contract_data)
                continue
            
            validated_contract = await self.validate_contract_with_ibkr(contract_data)
            
            if validated_contract:
                success = await self.insert_contract_to_db(validated_contract)
                if success:
                    logger.info(f"Added {symbol} (ConID: {validated_contract['con_id']})")
                    new_contracts_added += 1
                updated_contracts.append(contract_data)
            else:
                if keep_invalid:
                    logger.debug(f"Keeping invalid contract {symbol} in JSON file (--keep-invalid flag set)")
                    updated_contracts.append(contract_data)
                else:
                    logger.warning(f"Removing invalid contract {symbol} from JSON file")
            
            await asyncio.sleep(2)
        
        self.save_contracts_to_json(updated_contracts)
        
        total_processed = len(json_contracts)
        existing_skipped = len(json_contracts) - len(self.valid_contracts) - len(self.invalid_contracts)
        
        logger.info(f"Complete: {new_contracts_added} new contracts added, {existing_skipped} skipped (already exist)")
        
        if self.invalid_contracts:
            if keep_invalid:
                logger.info(f"Kept {len(self.invalid_contracts)} invalid contracts in JSON file")
            else:
                logger.warning(f"Removed {len(self.invalid_contracts)} invalid contracts: {', '.join(self.invalid_contracts)}")


async def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate contract details from JSON file')
    parser.add_argument('--json-file', type=str, default='app/data/seeds/contracts.json',
                       help='JSON file containing contract data (default: app/data/seeds/contracts.json)')
    parser.add_argument('--live-trading', action='store_true',
                       help='Override settings to use live trading port instead of paper trading')
    parser.add_argument('--keep-invalid', action='store_true',
                       help='Keep invalid contracts in JSON file instead of removing them')
    args = parser.parse_args()
    
    # Override to live trading if requested
    original_paper_trading = settings.ibkr_paper_trading
    if args.live_trading:
        settings.ibkr_paper_trading = False
        logger.info(f"Overriding to live trading (port {settings.ibkr_live_port})")
    else:
        port = settings.ibkr_paper_port if settings.ibkr_paper_trading else settings.ibkr_live_port
        mode = "paper trading" if settings.ibkr_paper_trading else "live trading"
        logger.info(f"Using {mode} connection (port {port})")
    
    try:
        updater = ContractUpdater(json_file=args.json_file)
        
        async with updater:
            await updater.process_contracts(keep_invalid=args.keep_invalid)
            
    except KeyboardInterrupt:
        logger.info("❌ Process interrupted by user")
        sys.exit(1)
    except ConnectionError as e:
        logger.error(f"❌ Connection error: {e}")
        logger.error("Please ensure TWS is running and API is enabled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())