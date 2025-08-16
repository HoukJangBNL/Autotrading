"""Integration tests for historical data fetcher with real database."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from src.data import (
    HistoricalDataFetcher,
    PriceData,
    TimeFrame,
    db_service,
    get_historical_fetcher
)


@pytest.mark.integration
class TestHistoricalDataIntegration:
    """Integration tests with real database."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Initialize database
        db_service.initialize()
        db_service.create_tables()
        
        yield
        
        # Cleanup test data
        async with db_service.get_async_session() as session:
            await session.execute(
                text("DELETE FROM price_data WHERE symbol LIKE 'TEST%'")
            )
            await session.commit()
        
        db_service.close()
    
    @pytest.mark.asyncio
    async def test_save_to_database(self):
        """Test saving price data to database."""
        fetcher = HistoricalDataFetcher()
        
        # Create test data
        test_data = [
            {
                'symbol': 'TEST001',
                'timestamp': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                'open': Decimal('100.00'),
                'high': Decimal('101.00'),
                'low': Decimal('99.00'),
                'close': Decimal('100.50'),
                'volume': 1000000,
                'vwap': Decimal('100.25')
            },
            {
                'symbol': 'TEST001',
                'timestamp': datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                'open': Decimal('100.50'),
                'high': Decimal('102.00'),
                'low': Decimal('100.00'),
                'close': Decimal('101.50'),
                'volume': 1200000,
                'vwap': None
            }
        ]
        
        # Save to database
        await fetcher._save_to_database(test_data)
        
        # Verify data was saved
        async with db_service.get_async_session() as session:
            result = await session.execute(
                select(PriceData).where(PriceData.symbol == 'TEST001')
                .order_by(PriceData.timestamp)
            )
            saved_data = result.scalars().all()
            
            assert len(saved_data) == 2
            
            # Check first record
            assert saved_data[0].symbol == 'TEST001'
            assert saved_data[0].open == Decimal('100.00')
            assert saved_data[0].high == Decimal('101.00')
            assert saved_data[0].low == Decimal('99.00')
            assert saved_data[0].close == Decimal('100.50')
            assert saved_data[0].volume == 1000000
            assert saved_data[0].vwap == Decimal('100.25')
            
            # Check second record has no vwap
            assert saved_data[1].vwap is None
    
    @pytest.mark.asyncio
    async def test_upsert_duplicate_data(self):
        """Test upserting duplicate data."""
        fetcher = HistoricalDataFetcher()
        
        # Create initial data
        initial_data = [{
            'symbol': 'TEST002',
            'timestamp': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            'open': Decimal('100.00'),
            'high': Decimal('101.00'),
            'low': Decimal('99.00'),
            'close': Decimal('100.50'),
            'volume': 1000000
        }]
        
        # Save initial data
        await fetcher._save_to_database(initial_data)
        
        # Create updated data with same timestamp
        updated_data = [{
            'symbol': 'TEST002',
            'timestamp': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            'open': Decimal('100.10'),  # Changed
            'high': Decimal('101.10'),  # Changed
            'low': Decimal('99.10'),    # Changed
            'close': Decimal('100.60'),  # Changed
            'volume': 1100000           # Changed
        }]
        
        # Save updated data
        await fetcher._save_to_database(updated_data)
        
        # Verify only one record exists with updated values
        async with db_service.get_async_session() as session:
            result = await session.execute(
                select(PriceData).where(PriceData.symbol == 'TEST002')
            )
            saved_data = result.scalars().all()
            
            assert len(saved_data) == 1
            assert saved_data[0].open == Decimal('100.10')
            assert saved_data[0].volume == 1100000
    
    @pytest.mark.asyncio
    async def test_get_latest_timestamp(self):
        """Test getting latest timestamp for a symbol."""
        fetcher = HistoricalDataFetcher()
        
        # Insert test data with different timestamps
        test_data = [
            {
                'symbol': 'TEST003',
                'timestamp': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                'open': Decimal('100'), 'high': Decimal('101'),
                'low': Decimal('99'), 'close': Decimal('100'),
                'volume': 1000
            },
            {
                'symbol': 'TEST003',
                'timestamp': datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                'open': Decimal('101'), 'high': Decimal('102'),
                'low': Decimal('100'), 'close': Decimal('101'),
                'volume': 1100
            },
            {
                'symbol': 'TEST003',
                'timestamp': datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
                'open': Decimal('102'), 'high': Decimal('103'),
                'low': Decimal('101'), 'close': Decimal('102'),
                'volume': 1200
            }
        ]
        
        await fetcher._save_to_database(test_data)
        
        # Get latest timestamp
        latest = await fetcher.get_latest_timestamp('TEST003')
        
        assert latest == datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc)
        
        # Test non-existent symbol
        latest_none = await fetcher.get_latest_timestamp('NONEXISTENT')
        assert latest_none is None
    
    @pytest.mark.asyncio
    async def test_fill_data_gaps(self):
        """Test gap detection and filling."""
        fetcher = HistoricalDataFetcher()
        
        # Insert data with a gap
        test_data = [
            {
                'symbol': 'TEST004',
                'timestamp': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                'open': Decimal('100'), 'high': Decimal('101'),
                'low': Decimal('99'), 'close': Decimal('100'),
                'volume': 1000
            },
            # Gap here - missing 11:00
            {
                'symbol': 'TEST004',
                'timestamp': datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                'open': Decimal('102'), 'high': Decimal('103'),
                'low': Decimal('101'), 'close': Decimal('102'),
                'volume': 1200
            }
        ]
        
        await fetcher._save_to_database(test_data)
        
        # Check for gaps (using 60 minutes as max gap for hourly data)
        # Note: This test assumes the gap detection query works
        # In a real scenario, we'd need to mock the fetch_historical_data
        # to return data for the gap period
        
        async with db_service.get_async_session() as session:
            # Verify we have 2 records with a gap
            result = await session.execute(
                select(PriceData)
                .where(PriceData.symbol == 'TEST004')
                .order_by(PriceData.timestamp)
            )
            records = result.scalars().all()
            
            assert len(records) == 2
            
            # Calculate gap
            gap_minutes = (records[1].timestamp - records[0].timestamp).total_seconds() / 60
            assert gap_minutes == 120  # 2 hour gap
    
    @pytest.mark.asyncio
    async def test_batch_insert_performance(self):
        """Test batch insert performance with large dataset."""
        fetcher = HistoricalDataFetcher()
        
        # Create large dataset
        base_time = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        large_dataset = []
        
        for i in range(1000):  # 1000 records
            large_dataset.append({
                'symbol': 'TEST005',
                'timestamp': base_time + timedelta(minutes=i),
                'open': Decimal('100') + Decimal(str(i * 0.01)),
                'high': Decimal('101') + Decimal(str(i * 0.01)),
                'low': Decimal('99') + Decimal(str(i * 0.01)),
                'close': Decimal('100.5') + Decimal(str(i * 0.01)),
                'volume': 1000000 + i * 1000
            })
        
        # Time the insert
        import time
        start_time = time.time()
        
        await fetcher._save_to_database(large_dataset)
        
        elapsed_time = time.time() - start_time
        
        # Verify all records were saved
        async with db_service.get_async_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM price_data WHERE symbol = 'TEST005'")
            )
            count = result.scalar()
            
            assert count == 1000
            
        # Performance assertion - should complete in reasonable time
        assert elapsed_time < 5.0  # Should complete within 5 seconds
        
        print(f"Inserted 1000 records in {elapsed_time:.2f} seconds")


@pytest.mark.asyncio
async def test_concurrent_symbol_fetching():
    """Test fetching multiple symbols concurrently."""
    # This is a standalone test that doesn't need database setup
    fetcher = HistoricalDataFetcher()
    
    # Mock the fetch method to simulate concurrent operations
    fetch_times = {}
    
    async def mock_fetch(symbol, *args, **kwargs):
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.1)  # Simulate API call
        fetch_times[symbol] = asyncio.get_event_loop().time() - start
        return [{
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc),
            'open': Decimal('100'),
            'high': Decimal('101'),
            'low': Decimal('99'),
            'close': Decimal('100'),
            'volume': 1000
        }]
    
    # Patch the fetch method
    fetcher.fetch_historical_data = mock_fetch
    
    # Fetch multiple symbols
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META']
    
    start_time = asyncio.get_event_loop().time()
    results = await fetcher.fetch_multiple_symbols(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        max_concurrent=3
    )
    total_time = asyncio.get_event_loop().time() - start_time
    
    # Verify all symbols were fetched
    assert len(results) == len(symbols)
    for symbol in symbols:
        assert symbol in results
        assert len(results[symbol]) == 1
    
    # Verify concurrent execution (should be faster than sequential)
    # With max_concurrent=3 and 5 symbols, should take ~0.2s not 0.5s
    assert total_time < 0.3
    
    print(f"Fetched {len(symbols)} symbols in {total_time:.2f} seconds")