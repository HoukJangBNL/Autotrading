"""
Charles Schwab Automated Trading System

A comprehensive automated trading system using the Charles Schwab API
with real-time streaming, multiple trading strategies, and risk management.
"""

__version__ = "0.1.0"
__author__ = "Trading System Team"

# Configure default logging
import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())