#!/bin/bash

# SCIZOR Trading System Startup Script
echo "🚀 Starting SCIZOR Trading System..."

# Make sure we're in the project directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start Docker services (PostgreSQL and Redis)
echo "🐳 Starting database services..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for database services..."
sleep 10

# Start microservices in the background
echo "🚀 Starting microservices..."

# Data Farmer
echo "Starting Data Farmer service..."
python -m uvicorn services.data-farmer.main:app --host 0.0.0.0 --port 8001 --reload &
DATA_FARMER_PID=$!

sleep 5

# Backtester
echo "Starting Backtester service..."
python -m uvicorn services.backtester.main:app --host 0.0.0.0 --port 8002 --reload &
BACKTESTER_PID=$!

sleep 5

# Algo Trader
echo "Starting Algo Trader service..."
python -m uvicorn services.algo-trader.main:app --host 0.0.0.0 --port 8003 --reload &
ALGO_TRADER_PID=$!

sleep 5

echo "✅ SCIZOR Trading System is running!"
echo ""
echo "📊 Service URLs:"
echo "  Data Farmer:  http://localhost:8001"
echo "  Backtester:   http://localhost:8002"
echo "  Algo Trader:  http://localhost:8003"
echo ""
echo "📖 API Documentation:"
echo "  Data Farmer:  http://localhost:8001/docs"
echo "  Backtester:   http://localhost:8002/docs"
echo "  Algo Trader:  http://localhost:8003/docs"
echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping SCIZOR services..."
    kill $DATA_FARMER_PID 2>/dev/null
    kill $BACKTESTER_PID 2>/dev/null
    kill $ALGO_TRADER_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Wait for services to run
wait
