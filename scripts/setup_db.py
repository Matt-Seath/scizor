#!/usr/bin/env python3
"""
Database setup script for ASX200 Trading System
Creates all tables and performs initial database setup
"""

import sys
import os
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

def create_database():
    """Create the database and all tables"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Build database URL from environment variables
        postgres_user = os.getenv('POSTGRES_USER', 'postgres')
        postgres_password = os.getenv('POSTGRES_PASSWORD', 'password')
        postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        postgres_port = os.getenv('POSTGRES_PORT', '5432')
        postgres_db = os.getenv('POSTGRES_DB', 'asx_trading')
        
        database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        logger.info("Setting up database", url=database_url.replace(postgres_password, "***"))
        
        # Create engine
        engine = create_engine(database_url)
        
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
        postgres_db = os.getenv('POSTGRES_DB', 'asx_trading')
        
        database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as session:
            # Add a few test ASX200 stocks
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
    print("🚀 Starting ASX200 Trading System Database Setup")
    print("=" * 50)
    
    # Step 1: Create database and tables
    print("1. Creating database schema...")
    if not create_database():
        print("❌ Database creation failed")
        sys.exit(1)
    
    # Step 2: Seed test data
    print("\n2. Seeding test data...")
    if not seed_test_data():
        print("❌ Test data seeding failed")
        sys.exit(1)
    
    print("\n✅ Database setup completed successfully!")
    print("\nNext steps:")
    print("- Test IB Gateway connection")
    print("- Run data collection for ASX200 stocks")
    print("- Validate data quality")

if __name__ == "__main__":
    main()