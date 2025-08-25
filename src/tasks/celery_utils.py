"""Utilities for Celery async task execution."""

import asyncio
from typing import Any, Callable, Coroutine
from functools import wraps

from ..utils.logger import get_logger

logger = get_logger(__name__)


def run_async_in_celery(func: Callable[..., Coroutine]) -> Callable[..., Any]:
    """
    Decorator to run async functions in Celery tasks.
    
    This creates a new event loop for each task execution,
    ensuring no conflicts with existing loops.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async function
            result = loop.run_until_complete(func(*args, **kwargs))
            return result
        except Exception as e:
            logger.error(f"Error in async task: {e}")
            raise
        finally:
            # Clean up the event loop
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                # Run the loop one more time to clean up
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            
            # Close the loop
            loop.close()
            
            # Reset the event loop for the thread
            asyncio.set_event_loop(None)
    
    return wrapper