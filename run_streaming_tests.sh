#!/bin/bash
# Phase 3 Streaming Test Script

echo "========================================="
echo "Phase 3: Real-time Streaming Test Suite"
echo "========================================="

# Check Redis
echo -e "\n1. Checking Redis connectivity..."
if redis-cli -a redis123 ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not running. Please start Redis with: redis-server --requirepass redis123"
    exit 1
fi

# Check if API server is running
echo -e "\n2. Checking API server..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API server is running"
else
    echo "❌ API server is not running"
    echo "Please start it with: uvicorn src.api.main:app --reload"
fi

# Run mock streaming test (limited time)
echo -e "\n3. Running mock streaming test (10 seconds)..."
timeout 10 python test_streaming_mock.py || true

# Check test files exist
echo -e "\n4. Checking test files..."
for file in test_streaming_mock.py test_websocket_simple.py test_streaming_integration.py; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done

echo -e "\n========================================="
echo "Test Environment Status Complete"
echo "========================================="