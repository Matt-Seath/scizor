#!/usr/bin/env python3
"""
Test the backtester with real WES data
"""
import asyncio
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
sys.path.append('.')

from shared.database.connection import get_db
from sqlalchemy import text

async def test_backtester_with_wes():
    """Test the backtester using real WES data"""
    
    print("🧪 Testing Backtester with WES Data")
    print("=" * 50)
    
    # 1. Fetch WES data from database
    print("📊 Fetching WES data from database...")
    async for session in get_db():
        query = text("""
            SELECT m.timestamp, m.open, m.high, m.low, m.close, m.volume 
            FROM market_data m
            JOIN symbols s ON m.symbol_id = s.id
            WHERE s.symbol = :symbol 
            ORDER BY m.timestamp ASC
        """)
        result = await session.execute(query, {'symbol': 'WES'})
        rows = result.fetchall()
        break  # Only need one session
    
    if not rows:
        print("❌ No WES data found in database")
        return
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Convert Decimal columns to float for pandas compatibility
    numeric_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_columns:
        df[col] = df[col].astype(float)
    
    print(f"✅ Loaded {len(df)} records from {df.index[0].date()} to {df.index[-1].date()}")
    print(f"📈 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # 2. Simple Moving Average Strategy Test
    print("\n🔄 Testing Simple Moving Average Crossover Strategy...")
    
    # Calculate moving averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    # Generate signals
    df['signal'] = 0
    df.loc[df.index[20:], 'signal'] = np.where(df['sma_20'][20:] > df['sma_50'][20:], 1, 0)
    df['position'] = df['signal'].diff()
    
    # Calculate returns
    df['market_return'] = df['close'].pct_change()
    df['strategy_return'] = df['market_return'] * df['signal'].shift(1)
    
    # Performance metrics (skip NaN values)
    strategy_returns = df['strategy_return'].dropna()
    market_returns = df['market_return'].dropna()
    
    total_return = (1 + strategy_returns).prod() - 1
    market_return = (1 + market_returns).prod() - 1
    volatility = strategy_returns.std() * (252 ** 0.5)  # Annualized
    
    # Count trades
    buy_signals = len(df[df['position'] == 1])
    sell_signals = len(df[df['position'] == -1])
    
    print(f"📊 Strategy Performance:")
    print(f"   Total Return: {total_return:.2%}")
    print(f"   Market Return: {market_return:.2%}")
    print(f"   Excess Return: {(total_return - market_return):.2%}")
    print(f"   Volatility: {volatility:.2%}")
    print(f"   Buy Signals: {buy_signals}")
    print(f"   Sell Signals: {sell_signals}")
    
    # Show recent signals
    recent_signals = df[df['position'] != 0].tail(5)
    if not recent_signals.empty:
        print(f"\n🔔 Recent Signals:")
        for idx, row in recent_signals.iterrows():
            signal_type = "BUY" if row['position'] == 1 else "SELL"
            print(f"   {idx.date()}: {signal_type} at ${row['close']:.2f}")
    
    # 3. Current Position
    current_position = df['signal'].iloc[-1]
    current_price = df['close'].iloc[-1]
    current_sma_20 = df['sma_20'].iloc[-1]
    current_sma_50 = df['sma_50'].iloc[-1]
    
    print(f"\n📍 Current Status:")
    print(f"   Date: {df.index[-1].date()}")
    print(f"   Price: ${current_price:.2f}")
    print(f"   SMA 20: ${current_sma_20:.2f}")
    print(f"   SMA 50: ${current_sma_50:.2f}")
    print(f"   Position: {'LONG' if current_position == 1 else 'CASH'}")
    
    print("\n✅ Backtester test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_backtester_with_wes())
