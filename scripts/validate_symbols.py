#!/usr/bin/env python3
"""
Validate symbols against IBKR to identify missing or invalid symbols
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, project_root)

from shared.database.connection import init_db, AsyncSessionLocal
from shared.database.models import Symbol
from shared.ibkr.client import IBKRManager
from shared.ibkr.contracts import create_stock_contract
from sqlalchemy import select, update

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SymbolValidator:
    """Validates symbols against IBKR API to identify missing/invalid symbols."""
    
    def __init__(self):
        self.ibkr_manager = None
        self.invalid_symbols = []
        self.valid_symbols = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        await init_db()
        self.session = AsyncSessionLocal()
        self.ibkr_manager = IBKRManager(
            host="127.0.0.1",
            port=4002,  # Paper trading port
            client_id=99  # Different client ID for validation
        )
        await self.ibkr_manager.connect(timeout=30)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.ibkr_manager:
            await self.ibkr_manager.disconnect()
        if self.session:
            await self.session.close()
    
    async def validate_symbol(self, symbol: Symbol) -> bool:
        """Validate a single symbol against IBKR.
        
        Args:
            symbol: Symbol object to validate
            
        Returns:
            True if valid, False if invalid
        """
        try:
            # Create contract
            contract = create_stock_contract(
                symbol=symbol.symbol,
                exchange=symbol.exchange,
                currency=symbol.currency
            )
            
            # Request contract details (this validates the symbol exists)
            details = await self.ibkr_manager.get_contract_details(contract)
            
            if details and len(details) > 0:
                logger.info(f"✅ {symbol.symbol} ({symbol.exchange}) - Valid")
                self.valid_symbols.append(symbol.symbol)
                
                # Update last_verified timestamp
                await self.session.execute(
                    update(Symbol)
                    .where(Symbol.id == symbol.id)
                    .values(last_verified=datetime.utcnow(), updated_at=datetime.utcnow())
                )
                await self.session.commit()
                
                return True
            else:
                logger.warning(f"❌ {symbol.symbol} ({symbol.exchange}) - No contract details found")
                self.invalid_symbols.append(symbol.symbol)
                return False
                
        except Exception as e:
            logger.error(f"❌ {symbol.symbol} ({symbol.exchange}) - Error: {e}")
            self.invalid_symbols.append(symbol.symbol)
            return False
    
    async def validate_all_symbols(self, limit: int = None, force_revalidate: bool = False):
        """Validate all symbols in the database.
        
        Args:
            limit: Optional limit on number of symbols to validate
            force_revalidate: If True, skip the 90-day verification check
        """
        logger.info("🔍 Starting symbol validation...")
        
        # Calculate cutoff date for recent verification (90 days ago)
        verification_cutoff = datetime.utcnow() - timedelta(days=90)
        
        # Get all active symbols, optionally filtering by verification date
        if force_revalidate:
            # Skip recently verified symbols unless forced
            query = select(Symbol).where(Symbol.active == True).order_by(Symbol.priority)
        else:
            # Only validate symbols that haven't been verified in the last 90 days
            query = select(Symbol).where(
                (Symbol.active == True) & 
                ((Symbol.last_verified == None) | (Symbol.last_verified < verification_cutoff))
            ).order_by(Symbol.priority)
            
        if limit:
            query = query.limit(limit)
            
        result = await self.session.execute(query)
        symbols = result.scalars().all()
        
        # Count skipped symbols for reporting
        if not force_revalidate:
            skipped_query = select(Symbol).where(
                (Symbol.active == True) & 
                (Symbol.last_verified != None) & 
                (Symbol.last_verified >= verification_cutoff)
            )
            skipped_result = await self.session.execute(skipped_query)
            skipped_count = len(skipped_result.scalars().all())
            
            if skipped_count > 0:
                logger.info(f"⏭️  Skipping {skipped_count} symbols verified within the last 90 days")
        
        logger.info(f"📊 Found {len(symbols)} symbols to validate")
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"🔍 [{i}/{len(symbols)}] Validating {symbol.symbol} ({symbol.exchange})")
            
            is_valid = await self.validate_symbol(symbol)
            
            # Add delay to respect IBKR rate limits
            await asyncio.sleep(2)
        
        logger.info("✅ Symbol validation completed!")
        logger.info(f"📊 Results:")
        logger.info(f"   • Valid symbols: {len(self.valid_symbols)}")
        logger.info(f"   • Invalid symbols: {len(self.invalid_symbols)}")
        
        if self.invalid_symbols:
            logger.warning("❌ Invalid symbols found:")
            for symbol in self.invalid_symbols:
                logger.warning(f"   • {symbol}")
    
    async def deactivate_invalid_symbols(self):
        """Deactivate invalid symbols in the database."""
        if not self.invalid_symbols:
            logger.info("✅ No invalid symbols to deactivate")
            return
        
        logger.info(f"🔧 Deactivating {len(self.invalid_symbols)} invalid symbols...")
        
        # Update invalid symbols to be inactive
        await self.session.execute(
            update(Symbol)
            .where(Symbol.symbol.in_(self.invalid_symbols))
            .values(active=False, updated_at=datetime.utcnow())
        )
        
        await self.session.commit()
        logger.info("✅ Invalid symbols deactivated")
    
    async def remove_invalid_symbols(self):
        """Remove invalid symbols from the database completely."""
        if not self.invalid_symbols:
            logger.info("✅ No invalid symbols to remove")
            return
        
        logger.info(f"🗑️  Removing {len(self.invalid_symbols)} invalid symbols from database...")
        
        # Delete invalid symbols completely
        from sqlalchemy import delete
        await self.session.execute(
            delete(Symbol)
            .where(Symbol.symbol.in_(self.invalid_symbols))
        )
        
        await self.session.commit()
        logger.info("✅ Invalid symbols removed from database")


async def validate_single_symbol(validator, symbol_code):
    """Validate a single symbol by symbol code."""
    from sqlalchemy import select
    
    # Find the symbol in the database
    query = select(Symbol).where(Symbol.symbol == symbol_code.upper())
    result = await validator.session.execute(query)
    symbol = result.scalar_one_or_none()
    
    if not symbol:
        print(f"❌ Symbol {symbol_code} not found in database")
        return False
    
    print(f"🔍 Validating {symbol.symbol} ({symbol.exchange})")
    is_valid = await validator.validate_symbol(symbol)
    
    print("\n" + "="*60)
    print("🎯 SINGLE SYMBOL VALIDATION COMPLETE")
    print("="*60)
    if is_valid:
        print(f"✅ {symbol.symbol} is VALID")
    else:
        print(f"❌ {symbol.symbol} is INVALID")
    print("="*60)
    
    return is_valid


async def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate symbols against IBKR')
    parser.add_argument('--limit', type=int, help='Limit number of symbols to validate')
    parser.add_argument('--symbol', type=str, help='Validate a single specific symbol (e.g., DEG)')
    parser.add_argument('--deactivate', action='store_true', help='Deactivate invalid symbols instead of removing them')
    parser.add_argument('--remove', action='store_true', help='Remove invalid symbols from database (default behavior)')
    parser.add_argument('--keep', action='store_true', help='Keep invalid symbols in database (no changes)')
    parser.add_argument('--force-revalidate', action='store_true', help='Force revalidation of all symbols, ignoring last verification date')
    args = parser.parse_args()
    
    # Validate that we have either --limit or --symbol, not both
    if args.symbol and args.limit:
        print("❌ Cannot use both --symbol and --limit. Choose one option.")
        sys.exit(1)
    
    # Validate conflicting cleanup options
    cleanup_options = sum([args.deactivate, args.remove, args.keep])
    if cleanup_options > 1:
        print("❌ Cannot use multiple cleanup options. Choose one: --deactivate, --remove, or --keep")
        sys.exit(1)
    
    # Default behavior is to remove invalid symbols
    if cleanup_options == 0:
        args.remove = True
    
    if not args.symbol and not args.limit:
        # Default behavior - validate all symbols
        pass
    
    try:
        async with SymbolValidator() as validator:
            if args.symbol:
                # Validate single symbol
                await validate_single_symbol(validator, args.symbol)
                
                # For single symbol validation, ask user what to do with invalid symbol
                if validator.invalid_symbols and not args.keep:
                    print(f"\n⚠️  Symbol {args.symbol} is invalid.")
                    if args.remove:
                        await validator.remove_invalid_symbols()
                    elif args.deactivate:
                        await validator.deactivate_invalid_symbols()
            else:
                # Validate multiple symbols
                await validator.validate_all_symbols(limit=args.limit, force_revalidate=getattr(args, 'force_revalidate', False))
                
                # Handle cleanup of invalid symbols
                if validator.invalid_symbols:
                    if args.remove:
                        await validator.remove_invalid_symbols()
                    elif args.deactivate:
                        await validator.deactivate_invalid_symbols()
                    elif args.keep:
                        logger.info("⏭️  Keeping invalid symbols in database (no changes)")
                
                print("\n" + "="*60)
                print("🎯 SYMBOL VALIDATION COMPLETE")
                print("="*60)
                print(f"✅ Valid symbols: {len(validator.valid_symbols)}")
                print(f"❌ Invalid symbols: {len(validator.invalid_symbols)}")
                
                if validator.invalid_symbols:
                    print("\n❌ Invalid symbols found:")
                    for symbol in validator.invalid_symbols:
                        print(f"   • {symbol}")
                    
                    if args.remove:
                        print("\n🗑️  Invalid symbols have been removed from database")
                    elif args.deactivate:
                        print("\n� Invalid symbols have been deactivated")
                    elif args.keep:
                        print("\n💡 Invalid symbols kept in database (use --remove or --deactivate to clean up)")
                print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
