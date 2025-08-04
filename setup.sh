#!/bin/bash

# Scizor Stock Data Collection Setup Script

set -e  # Exit on any error

echo "🚀 Setting up Scizor Stock Data Collection System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3.8+ is installed
check_python() {
    print_status "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        print_status "Found Python $PYTHON_VERSION"
        
        # Check if version is 3.8 or higher
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)'; then
            print_success "Python version is compatible"
        else
            print_error "Python 3.8 or higher is required. Current version: $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    
    print_success "Virtual environment created and activated"
}

# Install requirements
install_requirements() {
    print_status "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Dependencies installed successfully"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
}

# Initialize database
init_database() {
    print_status "Initializing database..."
    
    python -m scizor.database init
    
    print_success "Database initialized with sample data"
}

# Create systemd service (Linux only)
create_service() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_status "Creating systemd service..."
        
        SERVICE_FILE="/etc/systemd/system/scizor-scheduler.service"
        WORKING_DIR=$(pwd)
        
        cat > scizor-scheduler.service << EOF
[Unit]
Description=Scizor Stock Data Collection Scheduler
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKING_DIR
Environment=PATH=$WORKING_DIR/venv/bin
ExecStart=$WORKING_DIR/venv/bin/python -m scizor.database.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        print_warning "To install the systemd service, run:"
        print_warning "  sudo cp scizor-scheduler.service /etc/systemd/system/"
        print_warning "  sudo systemctl daemon-reload"
        print_warning "  sudo systemctl enable scizor-scheduler"
        print_warning "  sudo systemctl start scizor-scheduler"
        
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "Creating launchd plist for macOS..."
        
        PLIST_FILE="$HOME/Library/LaunchAgents/com.scizor.scheduler.plist"
        WORKING_DIR=$(pwd)
        
        cat > com.scizor.scheduler.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.scizor.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>$WORKING_DIR/venv/bin/python</string>
        <string>-m</string>
        <string>scizor.database.scheduler</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$WORKING_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$WORKING_DIR/logs/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>$WORKING_DIR/logs/scheduler.error.log</string>
</dict>
</plist>
EOF

        mkdir -p logs
        
        print_warning "To install the launchd service, run:"
        print_warning "  cp com.scizor.scheduler.plist ~/Library/LaunchAgents/"
        print_warning "  launchctl load ~/Library/LaunchAgents/com.scizor.scheduler.plist"
    fi
}

# Create example configuration
create_config() {
    print_status "Creating example configuration..."
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_success "Created .env file from template"
        print_warning "Please edit .env file to configure your settings"
    else
        print_warning ".env file already exists"
    fi
}

# Display usage information
show_usage() {
    echo
    print_success "🎉 Setup completed successfully!"
    echo
    echo "Quick Start Commands:"
    echo "  # Activate virtual environment"
    echo "  source venv/bin/activate"
    echo
    echo "  # Add stock symbols to track"
    echo "  python -m scizor.database add AAPL GOOGL MSFT TSLA"
    echo
    echo "  # Update all symbols with 30 days of data"
    echo "  python -m scizor.database backfill AAPL GOOGL MSFT TSLA --days 30"
    echo
    echo "  # Show database summary"
    echo "  python -m scizor.database summary"
    echo
    echo "  # Run real-time updates (every 15 minutes)"
    echo "  python -m scizor.database realtime --interval 15"
    echo
    echo "  # Start automated scheduler"
    echo "  python -m scizor.database.scheduler"
    echo
    echo "Configuration:"
    echo "  - Edit config/config.yaml for main settings"
    echo "  - Edit .env for sensitive credentials"
    echo
    echo "Logs will be stored in: logs/"
    echo "Database file: scizor_data.db"
    echo
}

# Main setup process
main() {
    echo "=================================================================================="
    echo "                     SCIZOR STOCK DATA COLLECTION SETUP"
    echo "=================================================================================="
    echo
    
    check_python
    create_venv
    install_requirements
    init_database
    create_config
    create_service
    show_usage
}

# Run main function
main
