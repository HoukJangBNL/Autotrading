"""Smart Gap Filler for efficient historical data synchronization."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
import pytz
from src.data.historical_data_collector import HistoricalDataCollector
from src.utils.logger import get_logger
from src.models.market_data import Candle1Min, MiningStatus

logger = get_logger(__name__)

# EST timezone for market hours
EST = pytz.timezone('US/Eastern')


class SmartGapFiller(HistoricalDataCollector):
    """Intelligent gap detection and filling with rate limit compliance."""
    
    def __init__(self, client=None):
        """Initialize the smart gap filler."""
        super().__init__(client)
        # Rate limit: 120 requests/minute = 2/second
        # Adding small buffer for safety
        self.rate_limit_delay = 0.51  # seconds between API calls
        
    async def analyze_gaps(self) -> Dict[str, Tuple[str, datetime, int]]:
        """
        Analyze gaps between latest data in DB and current time.
        
        Returns:
            Dict mapping symbol to (symbol, last_date, gap_days)
        """
        gap_data = {}
        current_time = datetime.now(pytz.UTC)
        
        with Session(self.engine) as session:
            # Get latest timestamp for each active symbol
            result = session.execute(
                select(
                    MiningStatus.symbol,
                    MiningStatus.last_date,
                    MiningStatus.is_active
                ).where(MiningStatus.is_active == True)
            ).all()
            
            for symbol, last_date, is_active in result:
                if last_date:
                    # Calculate gap in days
                    gap = current_time - last_date
                    gap_days = gap.days
                    
                    # Only consider gaps during market days
                    # (rough estimate, can be refined)
                    if gap_days > 0:
                        gap_data[symbol] = (symbol, last_date, gap_days)
                        logger.debug(f"{symbol}: Last data {last_date}, gap {gap_days} days")
                else:
                    # No data at all for this symbol
                    gap_data[symbol] = (symbol, None, 60)  # Default to 60 days
                    logger.debug(f"{symbol}: No data found, will collect 60 days")
                    
        logger.info(f"Analyzed {len(gap_data)} symbols for gaps")
        return gap_data
    
    async def categorize_symbols(self, gap_data: Dict) -> Dict[str, List[Tuple[str, int]]]:
        """
        Categorize symbols by gap size for prioritized processing.
        
        Args:
            gap_data: Dict of symbol -> (symbol, last_date, gap_days)
            
        Returns:
            Dict with 'no_gap', 'small_gap', 'large_gap' lists
        """
        categorized = {
            'no_gap': [],      # < 1 day (up to date)
            'small_gap': [],   # 1-2 days (high priority)
            'large_gap': []    # 2+ days (lower priority)
        }
        
        for symbol, (_, last_date, gap_days) in gap_data.items():
            if gap_days < 1:
                categorized['no_gap'].append((symbol, gap_days))
            elif gap_days <= 2:
                categorized['small_gap'].append((symbol, gap_days))
            else:
                categorized['large_gap'].append((symbol, gap_days))
        
        # Sort by gap size within each category
        categorized['small_gap'].sort(key=lambda x: x[1])
        categorized['large_gap'].sort(key=lambda x: x[1])
        
        logger.info(f"Categorized: {len(categorized['no_gap'])} up-to-date, "
                   f"{len(categorized['small_gap'])} small gaps, "
                   f"{len(categorized['large_gap'])} large gaps")
        
        return categorized
    
    async def fill_gaps_sequential(self, symbols_by_gap: Dict) -> List[Dict]:
        """
        Fill gaps sequentially with rate limit compliance.
        
        Args:
            symbols_by_gap: Categorized symbols from categorize_symbols()
            
        Returns:
            List of collection results
        """
        results = []
        
        # Combine symbols prioritizing small gaps first
        all_symbols = symbols_by_gap['small_gap'] + symbols_by_gap['large_gap']
        
        if not all_symbols:
            logger.info("No gaps to fill - all symbols up to date!")
            return results
        
        logger.info(f"Starting sequential gap filling for {len(all_symbols)} symbols")
        start_time = datetime.now()
        
        for i, (symbol, gap_days) in enumerate(all_symbols):
            symbol_start = time.time()
            
            try:
                # Collect historical data for the gap period
                result = await self.collect_historical_data(
                    symbol=symbol,
                    days_back=min(gap_days + 1, 60),  # Cap at 60 days
                    operation="smart_gap_fill"
                )
                
                # Progress display
                elapsed = time.time() - symbol_start
                status = "✅" if result['success'] else "❌"
                print(f"[{i+1}/{len(all_symbols)}] {symbol}: "
                      f"{result.get('candles_added', 0):,} candles "
                      f"({elapsed:.1f}s) {status}")
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                results.append({
                    'symbol': symbol,
                    'success': False,
                    'error': str(e),
                    'candles_added': 0
                })
            
            # Rate limit compliance (skip delay after last symbol)
            if i < len(all_symbols) - 1:
                await asyncio.sleep(self.rate_limit_delay)
        
        # Summary statistics
        total_time = (datetime.now() - start_time).total_seconds()
        total_candles = sum(r.get('candles_added', 0) for r in results)
        success_count = sum(1 for r in results if r.get('success', False))
        
        logger.info(f"Gap filling completed: {success_count}/{len(all_symbols)} successful, "
                   f"{total_candles:,} candles in {total_time:.1f}s")
        
        return results
    
    async def get_gap_summary(self) -> Dict:
        """Get summary of current gaps in the database."""
        gap_data = await self.analyze_gaps()
        categorized = await self.categorize_symbols(gap_data)
        
        # Calculate statistics
        total_gaps = len(gap_data)
        total_gap_days = sum(gap_days for _, _, gap_days in gap_data.values())
        avg_gap = total_gap_days / total_gaps if total_gaps > 0 else 0
        
        return {
            'total_symbols': total_gaps,
            'up_to_date': len(categorized['no_gap']),
            'small_gaps': len(categorized['small_gap']),
            'large_gaps': len(categorized['large_gap']),
            'total_gap_days': total_gap_days,
            'average_gap_days': round(avg_gap, 1),
            'estimated_time_seconds': len(categorized['small_gap'] + categorized['large_gap']) * 0.51
        }
    
    async def fill_specific_symbols(self, symbols: List[str], days_back: int = None) -> List[Dict]:
        """
        Fill gaps for specific symbols only.
        
        Args:
            symbols: List of symbols to process
            days_back: Override days to collect (default: auto-detect gap)
            
        Returns:
            List of collection results
        """
        results = []
        
        for i, symbol in enumerate(symbols):
            # Determine days to collect
            if days_back is None:
                gap_data = await self.analyze_gaps()
                if symbol in gap_data:
                    _, _, gap_days = gap_data[symbol]
                    days = min(gap_days + 1, 60)
                else:
                    days = 60  # Default if symbol not found
            else:
                days = days_back
            
            # Collect data
            result = await self.collect_historical_data(
                symbol=symbol,
                days_back=days,
                operation="smart_gap_fill"
            )
            results.append(result)
            
            # Rate limit
            if i < len(symbols) - 1:
                await asyncio.sleep(self.rate_limit_delay)
        
        return results