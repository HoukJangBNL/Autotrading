"""Main entry point for the Schwab automated trading system."""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional

import click

from .config import settings
from .config.constants import TradingMode
from .utils.logger import setup_logging, get_logger


logger = get_logger(__name__)


class TradingSystem:
    """Main trading system orchestrator."""
    
    def __init__(self, mode: Optional[TradingMode] = None):
        self.mode = mode
        self.running = False
        self._tasks = []
        
        # Components will be initialized in setup
        self.auth_manager = None
        self.broker = None
        self.data_service = None
        self.trading_engine = None
        self.gui = None
    
    async def setup(self):
        """Initialize all system components."""
        logger.info("Initializing trading system...")
        
        # TODO: Initialize components
        # self.auth_manager = OAuthManager(...)
        # self.broker = SchwabBroker(self.auth_manager)
        # self.data_service = DatabaseService(...)
        # self.trading_engine = TradingEngine(...)
        
        logger.info("Trading system initialized successfully")
    
    async def start(self):
        """Start the trading system."""
        self.running = True
        logger.info(f"Starting trading system in {self.mode or 'full'} mode")
        
        try:
            await self.setup()
            
            # Start components based on mode
            if self.mode == TradingMode.DISCOVERY:
                await self.run_discovery_mode()
            elif self.mode == TradingMode.SELECTION:
                await self.run_selection_mode()
            elif self.mode == TradingMode.TRADING:
                await self.run_trading_mode()
            else:
                # Run all modes in sequence
                await self.run_full_cycle()
                
        except Exception as e:
            logger.error(f"Error starting trading system: {e}", exc_info=True)
            await self.shutdown()
            raise
    
    async def run_discovery_mode(self):
        """Run discovery mode to find trading candidates."""
        logger.info("Running discovery mode...")
        # TODO: Implement discovery logic
        await asyncio.sleep(1)  # Placeholder
    
    async def run_selection_mode(self):
        """Run selection mode to optimize strategies."""
        logger.info("Running selection mode...")
        # TODO: Implement selection logic
        await asyncio.sleep(1)  # Placeholder
    
    async def run_trading_mode(self):
        """Run trading mode for live trading."""
        logger.info("Running trading mode...")
        # TODO: Implement trading logic
        while self.running:
            await asyncio.sleep(1)  # Main trading loop
    
    async def run_full_cycle(self):
        """Run all modes in proper sequence."""
        current_time = datetime.now()
        
        # Schedule modes based on market hours
        # TODO: Implement proper scheduling
        await self.run_discovery_mode()
        await self.run_selection_mode()
        await self.run_trading_mode()
    
    async def shutdown(self):
        """Gracefully shutdown the system."""
        logger.info("Shutting down trading system...")
        self.running = False
        
        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # TODO: Cleanup components
        logger.info("Trading system shutdown complete")


def signal_handler(system: TradingSystem):
    """Handle shutdown signals."""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(system.shutdown())
    
    return handler


@click.command()
@click.option(
    '--mode', 
    type=click.Choice(['discovery', 'selection', 'trading']),
    help='Run specific mode only'
)
@click.option(
    '--config', 
    type=click.Path(exists=True),
    help='Path to configuration file'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Enable debug logging'
)
def main(mode: Optional[str], config: Optional[str], debug: bool):
    """Schwab Automated Trading System"""
    
    # Setup logging
    setup_logging()
    
    if debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Log startup
    logger.info("=" * 60)
    logger.info("Schwab Automated Trading System Starting")
    logger.info(f"Environment: {settings.system.environment}")
    logger.info(f"Mode: {mode or 'full'}")
    logger.info("=" * 60)
    
    # Validate configuration
    if not settings.schwab.api_key or not settings.schwab.app_secret:
        logger.error("Schwab API credentials not configured!")
        sys.exit(1)
    
    # Create trading system
    trading_mode = TradingMode(mode) if mode else None
    system = TradingSystem(mode=trading_mode)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(system))
    signal.signal(signal.SIGTERM, signal_handler(system))
    
    # Run the system
    try:
        asyncio.run(system.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Trading system stopped")


if __name__ == "__main__":
    main()