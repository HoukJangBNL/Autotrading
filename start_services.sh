#!/bin/bash

echo "═══════════════════════════════════════════════════════════════"
echo "     🚀 AUTOTRADING SYSTEM - STARTING SERVICES 🚀"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8182
FRONTEND_PORT=3000

# Function to check if PostgreSQL is running
check_postgres() {
    # Try different methods to check PostgreSQL
    if command -v pg_isready &> /dev/null; then
        pg_isready -q
        return $?
    elif [ -S /tmp/.s.PGSQL.5432 ]; then
        # PostgreSQL socket exists
        return 0
    else
        # Check if PostgreSQL process is running
        pgrep -x postgres > /dev/null 2>&1
        return $?
    fi
}

# Check if Redis is running
echo "🔍 Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${YELLOW}⚠${NC} Redis is not running. Starting Redis..."
    brew services start redis
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis started successfully"
    else
        echo -e "${RED}✗${NC} Failed to start Redis"
        exit 1
    fi
fi

# Check if PostgreSQL is running
echo "🔍 Checking PostgreSQL..."
if check_postgres; then
    echo -e "${GREEN}✓${NC} PostgreSQL is running"
else
    echo -e "${YELLOW}⚠${NC} PostgreSQL is not running. Starting PostgreSQL..."
    brew services start postgresql@16
    sleep 3
    
    # Wait for PostgreSQL to start
    local max_attempts=10
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if check_postgres; then
            echo -e "${GREEN}✓${NC} PostgreSQL started successfully"
            break
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${RED}✗${NC} Failed to start PostgreSQL"
        exit 1
    fi
fi

# Kill any existing backend processes
echo "🔄 Cleaning up existing processes..."
pkill -f "uvicorn" 2>/dev/null
sleep 1

# Generate SSL certificates if they don't exist
if [ ! -f "config/cert.pem" ] || [ ! -f "config/key.pem" ]; then
    echo "🔐 Generating SSL certificates..."
    cd config
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" > /dev/null 2>&1
    cd ..
    echo -e "${GREEN}✓${NC} SSL certificates generated"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Backend
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "     📡 STARTING BACKEND (FastAPI)"
echo "═══════════════════════════════════════════════════════════════"

# Start backend with HTTPS on port 8182
nohup uvicorn src.api.main:app \
    --reload \
    --host 127.0.0.1 \
    --port $BACKEND_PORT \
    --ssl-keyfile config/key.pem \
    --ssl-certfile config/cert.pem \
    > logs/backend.log 2>&1 &

BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -k -s https://127.0.0.1:$BACKEND_PORT/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Backend is ready!"
        break
    fi
    sleep 1
    echo -n "."
done

# Check if backend is running
if ! curl -k -s https://127.0.0.1:$BACKEND_PORT/api/health > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Backend failed to start. Check logs/backend.log for details"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "     💻 STARTING FRONTEND (React)"
echo "═══════════════════════════════════════════════════════════════"

# Start Frontend
cd frontend
nohup npm start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "Frontend started with PID: $FRONTEND_PID"

# Wait for frontend to be ready (it takes longer)
echo "Waiting for frontend to be ready (this may take a minute)..."
for i in {1..90}; do
    if curl -k -s https://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Frontend is ready!"
        break
    fi
    sleep 2
    echo -n "."
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}     ✅ ALL SERVICES STARTED SUCCESSFULLY!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Access Points:"
echo "   • Frontend:      https://localhost:3000"
echo "   • Backend API:   https://127.0.0.1:8182"
echo "   • API Docs:      https://127.0.0.1:8182/api/docs"
echo "   • Mining Dashboard: https://localhost:3000/mining"
echo ""
echo "📁 Log Files:"
echo "   • Backend:  logs/backend.log"
echo "   • Frontend: logs/frontend.log"
echo ""
echo "🛑 To stop all services, run: ./stop_services.sh"
echo ""
echo "Process IDs saved to .pids file"
echo "$BACKEND_PID" > .pids
echo "$FRONTEND_PID" >> .pids

echo ""
echo "📝 To view logs in real-time, use:"
echo "   • Backend:  tail -f logs/backend.log"
echo "   • Frontend: tail -f logs/frontend.log"
echo ""
echo "Services are running in the background. You can close this terminal."