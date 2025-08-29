#!/bin/bash

echo "═══════════════════════════════════════════════════════════════"
echo "     🛑 STOPPING AUTOTRADING SERVICES"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stop processes from PID file if exists
if [ -f ".pids" ]; then
    echo "📄 Reading PIDs from .pids file..."
    while IFS= read -r pid; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "   Stopping process $pid..."
            kill $pid 2>/dev/null
        fi
    done < .pids
    rm .pids
    echo -e "${GREEN}✓${NC} Stopped processes from PID file"
fi

# Kill any remaining uvicorn processes
echo "🔍 Looking for uvicorn processes..."
if pgrep -f "uvicorn" > /dev/null; then
    pkill -f "uvicorn"
    echo -e "${GREEN}✓${NC} Stopped uvicorn processes"
else
    echo "   No uvicorn processes found"
fi

# Kill any remaining npm/node processes for our app
echo "🔍 Looking for frontend processes..."
if pgrep -f "craco start" > /dev/null; then
    pkill -f "craco start"
    echo -e "${GREEN}✓${NC} Stopped frontend processes"
else
    echo "   No frontend processes found"
fi

# Kill processes on specific ports
echo "🔍 Checking ports..."

# Check port 8182 (backend)
if lsof -i :8182 > /dev/null 2>&1; then
    echo "   Killing processes on port 8182..."
    lsof -ti:8182 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓${NC} Cleared port 8182"
else
    echo "   Port 8182 is already free"
fi

# Check port 3000 (frontend)
if lsof -i :3000 > /dev/null 2>&1; then
    echo "   Killing processes on port 3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓${NC} Cleared port 3000"
else
    echo "   Port 3000 is already free"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}     ✅ ALL SERVICES STOPPED${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "To restart services, run: ./start_services.sh"
echo ""