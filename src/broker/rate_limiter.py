"""Rate limiting and circuit breaker implementations for API protection."""

import asyncio
import time
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any, Dict
import statistics

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TokenBucket:
    """
    Token bucket rate limiter implementation.
    
    Allows burst traffic while maintaining average rate limit.
    """
    
    def __init__(self, rate: float, capacity: int, refill_period: float = 1.0):
        """
        Initialize token bucket.
        
        Args:
            rate: Number of tokens to add per refill period
            capacity: Maximum number of tokens in bucket
            refill_period: Time period in seconds for token refill
        """
        self.rate = rate
        self.capacity = capacity
        self.refill_period = refill_period
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            Time waited in seconds
            
        Raises:
            ValueError: If requesting more tokens than capacity
        """
        if tokens > self.capacity:
            raise ValueError(f"Cannot acquire {tokens} tokens, capacity is {self.capacity}")
        
        async with self._lock:
            wait_time = 0.0
            
            # Refill tokens based on time elapsed
            now = time.monotonic()
            elapsed = now - self.last_refill
            tokens_to_add = (elapsed / self.refill_period) * self.rate
            
            if tokens_to_add > 0:
                self.tokens = min(self.capacity, self.tokens + tokens_to_add)
                self.last_refill = now
            
            # Wait if not enough tokens
            if tokens > self.tokens:
                tokens_needed = tokens - self.tokens
                wait_time = (tokens_needed / self.rate) * self.refill_period
                
                logger.debug(
                    f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens "
                    f"(current: {self.tokens:.1f}/{self.capacity})"
                )
                
                await asyncio.sleep(wait_time)
                
                # Refill after waiting
                now = time.monotonic()
                elapsed = now - self.last_refill
                tokens_to_add = (elapsed / self.refill_period) * self.rate
                self.tokens = min(self.capacity, self.tokens + tokens_to_add)
                self.last_refill = now
            
            # Consume tokens
            self.tokens -= tokens
            
            return wait_time
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False otherwise
        """
        # Refill tokens
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = (elapsed / self.refill_period) * self.rate
        
        if tokens_to_add > 0:
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
        
        # Check if enough tokens
        if tokens <= self.tokens:
            self.tokens -= tokens
            return True
        
        return False


class RateLimiter:
    """
    Rate limiter with multiple strategies.
    
    Supports token bucket and sliding window algorithms.
    """
    
    def __init__(
        self,
        rate: int = 120,
        period: float = 60.0,
        burst: Optional[int] = None,
        strategy: str = "token_bucket"
    ):
        """
        Initialize rate limiter.
        
        Args:
            rate: Number of requests allowed per period
            period: Time period in seconds
            burst: Burst capacity (defaults to rate * 0.25)
            strategy: Rate limiting strategy ("token_bucket" or "sliding_window")
        """
        self.rate = rate
        self.period = period
        self.burst = burst or int(rate * 0.25)
        self.strategy = strategy
        
        if strategy == "token_bucket":
            # Token bucket with tokens refilled per second
            tokens_per_second = rate / period
            self.limiter = TokenBucket(
                rate=tokens_per_second,
                capacity=self.burst,
                refill_period=1.0
            )
        elif strategy == "sliding_window":
            self.limiter = SlidingWindowLimiter(rate, period)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Statistics
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.rejected_requests = 0
    
    async def acquire(self):
        """Acquire permission to make a request."""
        start = time.monotonic()
        
        if self.strategy == "token_bucket":
            wait_time = await self.limiter.acquire()
        else:
            wait_time = await self.limiter.acquire()
        
        self.total_requests += 1
        self.total_wait_time += wait_time
        
        if wait_time > 0:
            logger.info(f"Rate limited: waited {wait_time:.2f}s")
    
    def try_acquire(self) -> bool:
        """Try to acquire permission without waiting."""
        if self.strategy == "token_bucket":
            success = self.limiter.try_acquire()
        else:
            success = self.limiter.try_acquire()
        
        if success:
            self.total_requests += 1
        else:
            self.rejected_requests += 1
        
        return success
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'rejected_requests': self.rejected_requests,
            'total_wait_time': self.total_wait_time,
            'average_wait_time': avg_wait,
            'strategy': self.strategy
        }


class SlidingWindowLimiter:
    """Sliding window rate limiter implementation."""
    
    def __init__(self, rate: int, period: float):
        """
        Initialize sliding window limiter.
        
        Args:
            rate: Number of requests allowed per period
            period: Time period in seconds
        """
        self.rate = rate
        self.period = period
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """Acquire permission to make a request."""
        async with self._lock:
            now = time.monotonic()
            wait_time = 0.0
            
            # Remove old requests outside the window
            cutoff = now - self.period
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check if we can make a request
            if len(self.requests) >= self.rate:
                # Need to wait until the oldest request expires
                oldest = self.requests[0]
                wait_time = (oldest + self.period) - now
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.monotonic()
                    
                    # Remove expired requests again
                    cutoff = now - self.period
                    while self.requests and self.requests[0] < cutoff:
                        self.requests.popleft()
            
            # Add new request
            self.requests.append(now)
            
            return wait_time
    
    def try_acquire(self) -> bool:
        """Try to acquire permission without waiting."""
        now = time.monotonic()
        
        # Remove old requests
        cutoff = now - self.period
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
        
        # Check if we can make a request
        if len(self.requests) < self.rate:
            self.requests.append(now)
            return True
        
        return False


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by failing fast when errors occur.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type = Exception,
        success_threshold: int = 1
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures to open circuit
            recovery_timeout: Time in seconds before attempting recovery
            expected_exception: Exception type to catch
            success_threshold: Successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        
        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        self.total_rejections = 0
        self.state_changes = []
        
        self._lock = asyncio.Lock()
    
    async def __call__(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            if not self.can_request():
                self.total_rejections += 1
                raise Exception(f"Circuit breaker is {self.state.value}")
            
            self.total_requests += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
            
        except self.expected_exception as e:
            await self._record_failure()
            raise
    
    def can_request(self) -> bool:
        """Check if requests are allowed."""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)):
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
            
        # HALF_OPEN - allow one request to test
        return True
    
    def record_success(self):
        """Record a successful request."""
        asyncio.create_task(self._record_success())
    
    def record_failure(self):
        """Record a failed request."""
        asyncio.create_task(self._record_failure())
    
    async def _record_success(self):
        """Record success with state management."""
        async with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info("Circuit breaker closed after successful recovery")
    
    async def _record_failure(self):
        """Record failure with state management."""
        async with self._lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        f"Circuit breaker opened after {self.failure_count} failures"
                    )
                    
            elif self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test
                self._transition_to(CircuitState.OPEN)
                logger.warning("Circuit breaker reopened after recovery test failed")
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to new state."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.last_state_change = datetime.now()
            
            if new_state == CircuitState.CLOSED:
                self.failure_count = 0
                self.success_count = 0
                
            elif new_state == CircuitState.HALF_OPEN:
                self.success_count = 0
            
            # Record state change
            self.state_changes.append({
                'from': old_state.value,
                'to': new_state.value,
                'time': self.last_state_change,
                'failures': self.failure_count
            })
            
            logger.info(f"Circuit breaker: {old_state.value} -> {new_state.value}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        success_rate = (
            (self.total_requests - self.total_failures) / self.total_requests 
            if self.total_requests > 0 else 0
        )
        
        return {
            'state': self.state.value,
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'total_rejections': self.total_rejections,
            'success_rate': success_rate,
            'failure_count': self.failure_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_state_change': self.last_state_change.isoformat(),
            'state_changes': len(self.state_changes)
        }
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker reset to closed state")


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on response times.
    
    Reduces rate when response times increase, indicating server load.
    """
    
    def __init__(
        self,
        base_rate: int = 120,
        period: float = 60.0,
        min_rate: int = 30,
        max_rate: int = 300,
        adjustment_interval: float = 300.0  # 5 minutes
    ):
        """
        Initialize adaptive rate limiter.
        
        Args:
            base_rate: Base request rate
            period: Time period in seconds
            min_rate: Minimum allowed rate
            max_rate: Maximum allowed rate
            adjustment_interval: How often to adjust rate
        """
        self.base_rate = base_rate
        self.period = period
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.adjustment_interval = adjustment_interval
        
        self.current_rate = base_rate
        self.rate_limiter = RateLimiter(base_rate, period)
        
        # Response time tracking
        self.response_times = deque(maxlen=100)
        self.last_adjustment = time.monotonic()
        
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request."""
        await self.rate_limiter.acquire()
        
        # Check if we need to adjust rate
        async with self._lock:
            now = time.monotonic()
            if now - self.last_adjustment > self.adjustment_interval:
                await self._adjust_rate()
                self.last_adjustment = now
    
    def record_response_time(self, response_time: float):
        """Record response time for adaptive adjustment."""
        self.response_times.append(response_time)
    
    async def _adjust_rate(self):
        """Adjust rate based on response times."""
        if len(self.response_times) < 10:
            return  # Not enough data
        
        # Calculate statistics
        avg_time = statistics.mean(self.response_times)
        p95_time = statistics.quantiles(self.response_times, n=20)[18]  # 95th percentile
        
        # Adjust rate based on response times
        # If p95 > 2 seconds, reduce rate
        # If p95 < 0.5 seconds, increase rate
        if p95_time > 2.0:
            # Reduce rate by 20%
            new_rate = int(self.current_rate * 0.8)
            
        elif p95_time < 0.5 and avg_time < 0.3:
            # Increase rate by 10%
            new_rate = int(self.current_rate * 1.1)
            
        else:
            # No change
            return
        
        # Apply limits
        new_rate = max(self.min_rate, min(self.max_rate, new_rate))
        
        if new_rate != self.current_rate:
            logger.info(
                f"Adjusting rate: {self.current_rate} -> {new_rate} "
                f"(avg: {avg_time:.2f}s, p95: {p95_time:.2f}s)"
            )
            
            self.current_rate = new_rate
            self.rate_limiter = RateLimiter(new_rate, self.period)