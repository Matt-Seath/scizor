#!/usr/bin/env python3
"""
Database setup script for Scizor Trading System
Creates all tables and performs initial database setup
"""

import sys
import os
import argparse
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import structlog
import os

from app.config.database import Base
from app.data.models.market import DailyPrice, IntradayPrice
from app.data.models.signals import Signal
from app.data.models.portfolio import Position, Order, RiskMetric, PerformanceMetric

logger = structlog.get_logger(__name__)

def create_database(nuke=False):
    """Create the database and all tables"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Build database URL from environment variables
        postgres_user = os.getenv('POSTGRES_USER', 'postgres')
        postgres_password = os.getenv('POSTGRES_PASSWORD', 'password')
        postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        postgres_port = os.getenv('POSTGRES_PORT', '5432')
        postgres_db = os.getenv('POSTGRES_DB', 'scizor_db')
        
        database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        logger.info("Setting up database", url=database_url.replace(postgres_password, "***"))
        
        # Create engine
        engine = create_engine(database_url)
        
        if nuke:
            # Drop all tables first (clean slate)
            logger.info("🔥 NUKING: Dropping all existing tables and indexes...")
            with engine.connect() as conn:
                # Drop all indexes first
                result = conn.execute(text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND indexname NOT LIKE 'pg_%'
                """))
                indexes = [row[0] for row in result.fetchall()]
                for index in indexes:
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index}"))
                        logger.info(f"Dropped index: {index}")
                    except Exception as e:
                        logger.warning(f"Could not drop index {index}: {e}")
                
                conn.commit()
            
            # Now drop all tables
            Base.metadata.drop_all(bind=engine)
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            # Check if tables exist
            tables = [
                'daily_prices',
                'intraday_prices', 
                'signals',
                'positions',
                'orders',
                'risk_metrics',
                'performance_metrics'
            ]
            
            for table in tables:
                result = conn.execute(text(f"SELECT tablename FROM pg_tables WHERE tablename='{table}';"))
                if result.fetchone():
                    logger.info("Table created successfully", table=table)
                else:
                    logger.error("Table creation failed", table=table)
                    return False
        
        logger.info("✅ Database setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("❌ Database setup failed", error=str(e))
        return False

def seed_test_data():
    """Seed database with test data"""
    try:
        from datetime import datetime, timedelta
        import pandas as pd
        
        # Build database URL from environment variables
        postgres_user = os.getenv('POSTGRES_USER', 'postgres')
        postgres_password = os.getenv('POSTGRES_PASSWORD', 'password')
        postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        postgres_port = os.getenv('POSTGRES_PORT', '5432')
        postgres_db = os.getenv('POSTGRES_DB', 'scizor_db')
        
        database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as session:
            # Add a few test stocks
            test_symbols = ['BHP', 'CBA', 'CSL', 'ANZ', 'WBC']
            base_date = datetime.now().date() - timedelta(days=30)
            
            logger.info("Seeding test market data...")
            
            for symbol in test_symbols:
                for i in range(30):  # 30 days of data
                    date = base_date + timedelta(days=i)
                    
                    # Skip weekends
                    if date.weekday() >= 5:
                        continue
                    
                    # Generate realistic price data
                    base_price = 50.0 + (hash(symbol) % 100)  # Different base price per symbol
                    daily_change = (hash(f"{symbol}{date}") % 21 - 10) / 100  # -10% to +10%
                    
                    price = base_price * (1 + daily_change)
                    volume = 1000000 + (hash(f"{symbol}{date}volume") % 2000000)
                    
                    daily_price = DailyPrice(
                        symbol=symbol,
                        date=date,
                        open=price * 0.99,
                        high=price * 1.02,
                        low=price * 0.98,
                        close=price,
                        volume=volume,
                        adj_close=price
                    )
                    
                    session.add(daily_price)
            
            session.commit()
            logger.info("✅ Test data seeded successfully")
            
            # Verify data
            count = session.query(DailyPrice).count()
            logger.info("Database contains records", count=count)
            
        return True
        
    except Exception as e:
        logger.error("❌ Test data seeding failed", error=str(e))
        return False

def main():
    """Main setup function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scizor Trading System Database Setup')
    parser.add_argument('--nuke', action='store_true', 
                       help='Drop all existing tables before creating new ones')
    parser.add_argument('--no-seed', action='store_true',
                       help='Skip seeding test data')
    args = parser.parse_args()
    
    if args.nuke:
        print("🔥 NUKE MODE: Will drop all existing tables first!")
    
    print("🚀 Starting Scizor Trading System Database Setup")
    print("=" * 50)
    
    # Step 1: Create database and tables
    print("1. Creating database schema...")
    if not create_database(nuke=args.nuke):
        print("❌ Database creation failed")
        sys.exit(1)
    
    # Step 2: Seed test data (unless --no-seed is specified)
    if not args.no_seed:
        print("\n2. Seeding test data...")
        if not seed_test_data():
            print("❌ Test data seeding failed")
            sys.exit(1)
    else:
        print("\n2. Skipping test data seeding (--no-seed specified)")
    
    print("\n✅ Database setup completed successfully!")
    print("\nNext steps:")
    print("- Test IB Gateway connection")
    print("- Run data collection for stocks")
    print("- Validate data quality")

if __name__ == "__main__":
    main()