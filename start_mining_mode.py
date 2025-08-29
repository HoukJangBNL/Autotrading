#!/usr/bin/env python3
"""Start the application in Mining Mode."""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

def print_banner():
    """Print the mining mode banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     🔷 AUTOTRADING SYSTEM - DATA MINING MODE 🔷             ║
    ║                                                              ║
    ║     Mining 11,609 US Market Symbols                         ║
    ║     2 Months of 1-Minute Bar Data                           ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def main():
    """Main entry point for mining mode."""
    print_banner()
    
    print("\n📊 Mining Mode Features:")
    print("  ✓ Full market data collection (11,609 symbols)")
    print("  ✓ Smart gap detection and filling")
    print("  ✓ Failed symbol tracking and retry logic")
    print("  ✓ Real-time progress monitoring")
    print("  ✓ Performance optimization with caching")
    print("  ✓ Web dashboard at http://localhost:3000/mining")
    
    print("\n🚀 Starting services...")
    
    # Check Redis
    import redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("  ✓ Redis is running")
    except:
        print("  ❌ Redis is not running. Please start Redis first:")
        print("     brew services start redis")
        sys.exit(1)
    
    # Check PostgreSQL
    try:
        from sqlalchemy import create_engine
        engine = create_engine("postgresql://houkjang@localhost/autotrading")
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        print("  ✓ PostgreSQL is running")
    except Exception as e:
        print(f"  ❌ PostgreSQL is not running: {e}")
        print("     brew services start postgresql@16")
        sys.exit(1)
    
    print("\n📡 Starting Backend API...")
    print("  Access API docs at: http://localhost:8000/api/docs")
    print("  Mining endpoints:")
    print("    POST /api/mining/start - Start mining")
    print("    POST /api/mining/control - Control mining (pause/resume/stop)")
    print("    GET  /api/mining/status - Get current status")
    print("    GET  /api/mining/progress - Get detailed progress")
    print("    GET  /api/mining/statistics - Get statistics")
    
    print("\n💻 Starting Frontend...")
    print("  Access dashboard at: http://localhost:3000")
    print("  Mining dashboard at: http://localhost:3000/mining")
    
    print("\n" + "=" * 60)
    print("Instructions:")
    print("1. In terminal 1: uvicorn src.api.main:app --reload")
    print("2. In terminal 2: cd frontend && npm start")
    print("3. Open browser to http://localhost:3000")
    print("4. Navigate to Data Mining in the menu")
    print("5. Click 'Start Mining' and configure settings")
    print("=" * 60)
    
    print("\n⚙️ Mining Modes:")
    print("  • Full Mode: Collect all symbols from scratch")
    print("  • Gaps Only: Fill missing data in existing symbols")
    print("  • New Only: Collect only symbols without any data")
    print("  • Phases: Incremental collection (Core → S&P100 → NASDAQ100)")
    
    print("\n📈 Recommended Settings:")
    print("  • Start with 'Phases' mode for testing")
    print("  • Days Back: 60 (2 months)")
    print("  • Batch Size: 50")
    print("  • Concurrent Limit: 10")
    
    print("\n⚠️ Important Notes:")
    print("  • Mining 11,609 symbols will take several hours")
    print("  • Failed symbols are tracked and can be retried")
    print("  • Progress is saved and can resume after interruption")
    print("  • Monitor rate limits in the dashboard")
    
    print("\nPress Ctrl+C to exit")
    
    try:
        # Keep the script running
        while True:
            input()
    except KeyboardInterrupt:
        print("\n\n👋 Mining mode stopped. Goodbye!")

if __name__ == "__main__":
    main()