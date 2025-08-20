#!/bin/bash

# SESAME Web API Service Manager
# This script manages the SESAME web app as a background service

# Configuration
APP_NAME="sesame-webapi"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/sesame_webapi.pid"
LOG_FILE="$APP_DIR/sesame_webapi.log"
PYTHON_CMD="python3"
MAIN_SCRIPT="$APP_DIR/main.py"
PORT=${SESAME_PORT:-8000}
HOST=${SESAME_HOST:-"0.0.0.0"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== SESAME Web API Service Manager ===${NC}"
}

# Function to check if service is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is dead
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to get service status
get_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        local uptime=$(ps -o etime= -p "$pid" 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✓ Service is RUNNING${NC}"
        echo "  PID: $pid"
        echo "  Uptime: $uptime"
        echo "  Port: $PORT"
        echo "  Log: $LOG_FILE"
        
        # Check if the API is responding
        if command -v curl > /dev/null 2>&1; then
            if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
                echo -e "  API: ${GREEN}✓ Responding${NC}"
            else
                echo -e "  API: ${YELLOW}⚠ Not responding${NC}"
            fi
        fi
    else
        echo -e "${RED}✗ Service is STOPPED${NC}"
    fi
}

# Function to start the service
start_service() {
    print_header
    print_status "Starting SESAME Web API service..."
    
    if is_running; then
        print_warning "Service is already running!"
        get_status
        return 1
    fi
    
    # Check if required files exist
    if [ ! -f "$MAIN_SCRIPT" ]; then
        print_error "Main script not found: $MAIN_SCRIPT"
        return 1
    fi
    
    if [ ! -f "$APP_DIR/.env" ]; then
        print_warning ".env file not found. Please create it from env.example"
        print_status "Creating .env from env.example..."
        if [ -f "$APP_DIR/env.example" ]; then
            cp "$APP_DIR/env.example" "$APP_DIR/.env"
            print_warning "Please edit $APP_DIR/.env with your device credentials"
        else
            print_error "env.example not found!"
            return 1
        fi
    fi
    
    # Check if Python dependencies are installed
    if [ ! -f "$APP_DIR/requirements.txt" ]; then
        print_error "requirements.txt not found!"
        return 1
    fi
    
    # Start the service in background
    print_status "Starting service on $HOST:$PORT..."
    cd "$APP_DIR"
    
    # Start the Python process in background
    nohup $PYTHON_CMD "$MAIN_SCRIPT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # Save PID to file
    echo $pid > "$PID_FILE"
    
    # Wait a moment to check if it started successfully
    sleep 2
    
    if is_running; then
        print_status "Service started successfully!"
        get_status
        print_status "Logs: tail -f $LOG_FILE"
        print_status "API: http://localhost:$PORT"
        print_status "Docs: http://localhost:$PORT/docs"
    else
        print_error "Failed to start service!"
        print_status "Check logs: tail -f $LOG_FILE"
        return 1
    fi
}

# Function to stop the service
stop_service() {
    print_header
    print_status "Stopping SESAME Web API service..."
    
    if ! is_running; then
        print_warning "Service is not running!"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    print_status "Stopping process $pid..."
    
    # Try graceful shutdown first
    kill "$pid" 2>/dev/null
    
    # Wait for graceful shutdown
    local count=0
    while [ $count -lt 10 ] && is_running; do
        sleep 1
        ((count++))
    done
    
    # Force kill if still running
    if is_running; then
        print_warning "Force killing process..."
        kill -9 "$pid" 2>/dev/null
        sleep 1
    fi
    
    # Clean up PID file
    rm -f "$PID_FILE"
    
    if ! is_running; then
        print_status "Service stopped successfully!"
    else
        print_error "Failed to stop service!"
        return 1
    fi
}

# Function to restart the service
restart_service() {
    print_header
    print_status "Restarting SESAME Web API service..."
    
    stop_service
    sleep 2
    start_service
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_status "Showing logs (Ctrl+C to exit):"
        tail -f "$LOG_FILE"
    else
        print_warning "No log file found: $LOG_FILE"
    fi
}

# Function to show recent logs
show_recent_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_status "Recent logs:"
        tail -n 50 "$LOG_FILE"
    else
        print_warning "No log file found: $LOG_FILE"
    fi
}

# Function to clean up
cleanup() {
    print_status "Cleaning up..."
    rm -f "$PID_FILE"
    print_status "Cleanup complete!"
}

# Function to show help
show_help() {
    print_header
    echo "Usage: $0 {start|stop|restart|status|logs|recent|cleanup|help}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the SESAME Web API service"
    echo "  stop      - Stop the SESAME Web API service"
    echo "  restart   - Restart the SESAME Web API service"
    echo "  status    - Show service status"
    echo "  logs      - Show live logs (tail -f)"
    echo "  recent    - Show recent logs (last 50 lines)"
    echo "  cleanup   - Clean up PID file"
    echo "  help      - Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  SESAME_PORT - Port to run on (default: 8000)"
    echo "  SESAME_HOST - Host to bind to (default: 0.0.0.0)"
    echo ""
    echo "Files:"
    echo "  PID file: $PID_FILE"
    echo "  Log file: $LOG_FILE"
    echo "  App dir:  $APP_DIR"
}

# Main script logic
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        print_header
        get_status
        ;;
    logs)
        show_logs
        ;;
    recent)
        show_recent_logs
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

exit 0
