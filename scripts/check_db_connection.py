#!/usr/bin/env python3
"""Check database connection."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import get_settings
from src.data import db_service


async def main():
    """Check database connection."""
    settings = get_settings()
    
    print("Database Configuration:")
    print(f"Database URL: {settings.database.database_url}")
    print(f"Redis URL: {settings.database.redis_url}")
    print(f"Environment: {settings.system.environment}")
    
    # Test database connection
    print("\nTesting database connection...")
    
    try:
        db_service.initialize()
        
        # Test sync connection
        with db_service.get_session() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1"))
            print("✅ Sync database connection successful")
            
        # Test async connection
        async with db_service.get_async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            print("✅ Async database connection successful")
            
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db_service.engine)
        tables = inspector.get_table_names()
        print(f"\nExisting tables: {tables}")
        
        if 'price_data' not in tables:
            print("\n⚠️  price_data table not found. Creating tables...")
            db_service.create_tables()
            print("✅ Tables created")
            
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db_service.close()


if __name__ == "__main__":
    asyncio.run(main())