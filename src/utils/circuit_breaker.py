"""
Circuit Breaker Pattern Implementation.

Provides circuit breaker functionality to prevent cascading failures
in distributed systems and protect against overloading failing services.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass

from .logger import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Blocking requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service is recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    failure_threshold: int = 5
    timeout_seconds: int = 60
    recovery_timeout_seconds: int = 30
    success_threshold: int = 3  # Successes needed in half-open to close
    max_half_open_requests: int = 3


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascading failures.
    
    The circuit breaker monitors the success/failure rate of operations
    and can temporarily block requests when the failure rate is too high.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        recovery_timeout: int = 30,
        name: str = "default"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening
            timeout: Time in seconds to wait before trying again
            recovery_timeout: Time in seconds for half-open state
            name: Name for logging/identification
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout_seconds=timeout,
            recovery_timeout_seconds=recovery_timeout
        )
        self.name = name
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.next_half_open_time: Optional[datetime] = None
        self.half_open_requests = 0
        
        # Statistics
        self.total_requests = 0
        self.total_successes = 0
        self.total_failures = 0
        self.times_opened = 0
        
        # Event handlers
        self.on_state_change: Optional[Callable] = None
        self.on_failure: Optional[Callable] = None
        self.on_success: Optional[Callable] = None
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        self._update_state()
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        self._update_state()
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        self._update_state()
        return self.state == CircuitBreakerState.HALF_OPEN
    
    def _update_state(self):
        """Update circuit breaker state based on current conditions."""
        now = datetime.now(timezone.utc)
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if timeout has elapsed
            if self.next_half_open_time and now >= self.next_half_open_time:
                self._transition_to_half_open()
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Check if recovery timeout has elapsed
            if (self.last_failure_time and 
                now - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout_seconds)):
                # If no new failures in recovery timeout, consider closing
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerException: If circuit breaker is open
        """
        if self.is_open:
            raise CircuitBreakerException(f"Circuit breaker '{self.name}' is open")
        
        # Check half-open request limit
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_requests >= self.config.max_half_open_requests:
                raise CircuitBreakerException(f"Circuit breaker '{self.name}' half-open request limit exceeded")
            self.half_open_requests += 1
        
        self.total_requests += 1
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self.record_success()
            return result
            
        except Exception as e:
            # Record failure
            await self.record_failure()
            raise e
    
    async def record_success(self):
        """Record a successful operation."""
        now = datetime.now(timezone.utc)
        
        self.success_count += 1
        self.total_successes += 1
        self.last_success_time = now
        self.failure_count = 0  # Reset failure count on success
        
        # In half-open state, check if we should close
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        # Trigger success callback
        if self.on_success:
            try:
                if asyncio.iscoroutinefunction(self.on_success):
                    await self.on_success(self)
                else:
                    self.on_success(self)
            except Exception as e:
                logger.error(f"Error in circuit breaker success callback: {e}")
        
        logger.debug(f"Circuit breaker '{self.name}' recorded success")
    
    async def record_failure(self):
        """Record a failed operation."""
        now = datetime.now(timezone.utc)
        
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = now
        self.success_count = 0  # Reset success count on failure
        
        # Check if we should open the circuit
        if (self.state in [CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN] and
            self.failure_count >= self.config.failure_threshold):
            self._transition_to_open()
        
        # Trigger failure callback
        if self.on_failure:
            try:
                if asyncio.iscoroutinefunction(self.on_failure):
                    await self.on_failure(self)
                else:
                    self.on_failure(self)
            except Exception as e:
                logger.error(f"Error in circuit breaker failure callback: {e}")
        
        logger.debug(f"Circuit breaker '{self.name}' recorded failure ({self.failure_count})")
    
    def _transition_to_open(self):
        """Transition to open state."""
        old_state = self.state
        self.state = CircuitBreakerState.OPEN
        self.times_opened += 1
        self.next_half_open_time = (
            datetime.now(timezone.utc) + 
            timedelta(seconds=self.config.timeout_seconds)
        )
        
        logger.warning(f"Circuit breaker '{self.name}' opened (failures: {self.failure_count})")
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_half_open(self):
        """Transition to half-open state."""
        old_state = self.state
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        self.half_open_requests = 0
        
        logger.info(f"Circuit breaker '{self.name}' half-opened")
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_closed(self):
        """Transition to closed state."""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.success_count = 0
        self.failure_count = 0
        self.half_open_requests = 0
        self.next_half_open_time = None
        
        logger.info(f"Circuit breaker '{self.name}' closed")
        self._notify_state_change(old_state, self.state)
    
    def _notify_state_change(self, old_state: CircuitBreakerState, new_state: CircuitBreakerState):
        """Notify state change handlers."""
        if self.on_state_change:
            try:
                self.on_state_change(self, old_state, new_state)
            except Exception as e:
                logger.error(f"Error in circuit breaker state change callback: {e}")
    
    async def reset(self):
        """Reset the circuit breaker to closed state."""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_requests = 0
        self.next_half_open_time = None
        
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self._notify_state_change(old_state, self.state)
    
    def get_statistics(self) -> dict:
        """Get circuit breaker statistics."""
        now = datetime.now(timezone.utc)
        
        stats = {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'total_requests': self.total_requests,
            'total_successes': self.total_successes,
            'total_failures': self.total_failures,
            'times_opened': self.times_opened,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None,
            'next_half_open_time': self.next_half_open_time.isoformat() if self.next_half_open_time else None,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'timeout_seconds': self.config.timeout_seconds,
                'recovery_timeout_seconds': self.config.recovery_timeout_seconds,
                'success_threshold': self.config.success_threshold,
                'max_half_open_requests': self.config.max_half_open_requests
            }
        }
        
        # Calculate success rate
        if self.total_requests > 0:
            stats['success_rate'] = self.total_successes / self.total_requests
        else:
            stats['success_rate'] = 0.0
        
        # Calculate time since last failure
        if self.last_failure_time:
            stats['seconds_since_last_failure'] = (now - self.last_failure_time).total_seconds()
        
        return stats
    
    def __str__(self) -> str:
        """String representation of circuit breaker."""
        return f"CircuitBreaker(name='{self.name}', state={self.state.value}, failures={self.failure_count})"
    
    def __repr__(self) -> str:
        """Detailed representation of circuit breaker."""
        return (f"CircuitBreaker(name='{self.name}', state={self.state.value}, "
                f"failures={self.failure_count}, successes={self.success_count}, "
                f"total_requests={self.total_requests})")


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
    
    def create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 60,
        recovery_timeout: int = 30
    ) -> CircuitBreaker:
        """Create a new circuit breaker."""
        if name in self.circuit_breakers:
            raise ValueError(f"Circuit breaker '{name}' already exists")
        
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout,
            recovery_timeout=recovery_timeout,
            name=name
        )
        
        self.circuit_breakers[name] = cb
        return cb
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    def get_all_statistics(self) -> dict:
        """Get statistics for all circuit breakers."""
        return {
            name: cb.get_statistics()
            for name, cb in self.circuit_breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            await cb.reset()
    
    def remove_circuit_breaker(self, name: str) -> bool:
        """Remove a circuit breaker."""
        if name in self.circuit_breakers:
            del self.circuit_breakers[name]
            return True
        return False


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()