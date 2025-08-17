#!/usr/bin/env python3
"""
Launch script for Schwab Auto Trading System GUI.
Run this to start the GUI application for discovery mode testing.
"""

import sys
import os
import logging
from pathlib import Path

# Add src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "logs" / "gui.log", mode='a')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for GUI application."""
    try:
        # Create logs directory if it doesn't exist
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        logger.info("Starting Schwab Auto Trading GUI...")
        
        # Import and run GUI
        from gui.main_window import main as gui_main
        
        # Set environment variables for development
        os.environ.setdefault('QT_LOGGING_RULES', '*.debug=false')
        
        logger.info("GUI application starting...")
        return gui_main()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        return 1
        
    except Exception as e:
        logger.error(f"GUI startup error: {e}")
        print(f"Error starting GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())