"""
Trading calendar utilities for US stock market.

Handles trading days calculation excluding weekends and US market holidays.
"""

from datetime import datetime, timedelta
from typing import List, Set
import holidays


class TradingCalendar:
    """US stock market trading calendar."""
    
    # Trading hours in minutes
    REGULAR_TRADING_MINUTES = 390  # 9:30 AM - 4:00 PM ET
    EXTENDED_TRADING_MINUTES = 960  # 4:00 AM - 8:00 PM ET
    
    # Conservative estimate of actual trading minutes per day
    # Not all minutes have trades, especially for low-volume stocks
    EFFECTIVE_TRADING_RATIO = 0.6  # 60% of minutes have actual trades
    
    def __init__(self):
        # US market holidays
        self.us_holidays = holidays.US(years=range(2020, 2030))
        # Add market-specific holidays
        self._add_market_holidays()
    
    def _add_market_holidays(self):
        """Add market-specific holidays not in standard US holidays."""
        # Good Friday (market closed)
        # Day after Thanksgiving (half day, but we'll treat as closed for simplicity)
        pass  # holidays.US already includes most market holidays
    
    def get_trading_days(self, start_date: datetime, end_date: datetime) -> int:
        """
        Calculate number of trading days between two dates.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Number of trading days (excluding weekends and holidays)
        """
        trading_days = 0
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            # Check if it's a weekday (0=Monday, 4=Friday)
            if current_date.weekday() < 5:
                # Check if it's not a holiday
                if current_date not in self.us_holidays:
                    trading_days += 1
            
            current_date += timedelta(days=1)
        
        return trading_days
    
    def get_expected_minute_bars(
        self, 
        start_date: datetime, 
        end_date: datetime,
        include_extended_hours: bool = True,
        apply_effectiveness_ratio: bool = True
    ) -> int:
        """
        Calculate expected number of minute bars for a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            include_extended_hours: Include pre/post market hours
            apply_effectiveness_ratio: Apply ratio for actual trading activity
            
        Returns:
            Expected number of minute bars
        """
        trading_days = self.get_trading_days(start_date, end_date)
        
        if include_extended_hours:
            minutes_per_day = self.EXTENDED_TRADING_MINUTES
        else:
            minutes_per_day = self.REGULAR_TRADING_MINUTES
        
        expected_bars = trading_days * minutes_per_day
        
        if apply_effectiveness_ratio:
            # Apply effectiveness ratio for more realistic expectations
            expected_bars = int(expected_bars * self.EFFECTIVE_TRADING_RATIO)
        
        return expected_bars
    
    def get_minimum_required_bars(
        self,
        trading_days: int,
        min_coverage_ratio: float = 0.3
    ) -> int:
        """
        Calculate minimum required minute bars for data validity.
        
        Args:
            trading_days: Number of trading days
            min_coverage_ratio: Minimum ratio of expected bars (default 30%)
            
        Returns:
            Minimum number of minute bars required
        """
        # Use regular hours only for minimum calculation
        expected_bars = trading_days * self.REGULAR_TRADING_MINUTES
        return int(expected_bars * min_coverage_ratio)
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if a specific date is a trading day."""
        date_only = date.date()
        
        # Check if it's a weekday
        if date_only.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's a holiday
        if date_only in self.us_holidays:
            return False
        
        return True
    
    def next_trading_day(self, date: datetime) -> datetime:
        """Get the next trading day after the given date."""
        next_day = date + timedelta(days=1)
        
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        
        return next_day
    
    def previous_trading_day(self, date: datetime) -> datetime:
        """Get the previous trading day before the given date."""
        prev_day = date - timedelta(days=1)
        
        while not self.is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
        
        return prev_day


# Singleton instance
trading_calendar = TradingCalendar()