"""Tests for rate limiter and circuit breaker."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.broker.rate_limiter import (
    TokenBucket,
    RateLimiter,
    SlidingWindowLimiter,
    CircuitBreaker,
    CircuitState,
    AdaptiveRateLimiter
)


class TestTokenBucket:
    """Test token bucket implementation."""
    
    @pytest.mark.asyncio
    async def test_token_bucket_basic(self):
        """Test basic token bucket functionality."""
        # 2 tokens per second, capacity 5
        bucket = TokenBucket(rate=2, capacity=5, refill_period=1.0)
        
        # Should start at full capacity
        wait_time = await bucket.acquire(3)
        assert wait_time == 0  # No wait needed
        
        # Should have 2 tokens left
        wait_time = await bucket.acquire(2)
        assert wait_time == 0  # No wait needed
        
        # Should need to wait for more tokens
        start = time.monotonic()
        wait_time = await bucket.acquire(2)
        elapsed = time.monotonic() - start
        
        assert wait_time > 0
        assert elapsed >= 0.5  # Need 1 token, rate is 2/sec, so 0.5s wait
    
    @pytest.mark.asyncio
    async def test_token_bucket_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(rate=10, capacity=10, refill_period=1.0)
        
        # Consume all tokens
        await bucket.acquire(10)
        
        # Wait for refill
        await asyncio.sleep(0.5)
        
        # Should have ~5 tokens refilled
        wait_time = await bucket.acquire(5)
        assert wait_time < 0.1  # Small wait or no wait
    
    def test_token_bucket_try_acquire(self):
        """Test non-blocking token acquisition."""
        bucket = TokenBucket(rate=1, capacity=2, refill_period=1.0)
        
        # Should succeed
        assert bucket.try_acquire(1) is True
        assert bucket.try_acquire(1) is True
        
        # Should fail
        assert bucket.try_acquire(1) is False
    
    @pytest.mark.asyncio
    async def test_token_bucket_overcapacity_request(self):
        """Test requesting more tokens than capacity."""
        bucket = TokenBucket(rate=1, capacity=5, refill_period=1.0)
        
        with pytest.raises(ValueError, match="Cannot acquire 10 tokens"):
            await bucket.acquire(10)


class TestRateLimiter:
    """Test rate limiter with various strategies."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_token_bucket(self):
        """Test rate limiter with token bucket strategy."""
        limiter = RateLimiter(rate=10, period=1.0, burst=5, strategy="token_bucket")
        
        # Should allow burst
        for _ in range(5):
            await limiter.acquire()
        
        # Next request should wait
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        assert elapsed > 0  # Should have waited
        assert limiter.total_requests == 6
    
    def test_rate_limiter_try_acquire(self):
        """Test non-blocking rate limiter."""
        limiter = RateLimiter(rate=5, period=1.0, burst=2, strategy="token_bucket")
        
        # Should succeed for burst
        assert limiter.try_acquire() is True
        assert limiter.try_acquire() is True
        
        # Should fail
        assert limiter.try_acquire() is False
        assert limiter.rejected_requests == 1
    
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter(rate=10, period=1.0)
        
        # Make some requests
        limiter.try_acquire()
        limiter.try_acquire()
        limiter.rejected_requests = 1
        limiter.total_wait_time = 2.5
        
        stats = limiter.get_stats()
        
        assert stats['total_requests'] == 2
        assert stats['rejected_requests'] == 1
        assert stats['average_wait_time'] == 1.25
        assert stats['strategy'] == 'token_bucket'
    
    @pytest.mark.asyncio
    async def test_sliding_window_limiter(self):
        """Test sliding window rate limiter."""
        limiter = RateLimiter(rate=3, period=1.0, strategy="sliding_window")
        
        # Should allow 3 requests
        for _ in range(3):
            await limiter.acquire()
        
        # 4th request should wait
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        assert elapsed >= 0.9  # Should wait about 1 second


class TestCircuitBreaker:
    """Test circuit breaker implementation."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # Should allow requests
        assert breaker.can_request() is True
        assert breaker.state == CircuitState.CLOSED
        
        # Successful request
        async def success():
            return "success"
        
        result = await breaker(success)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_on_failures(self):
        """Test circuit breaker opens after failures."""
        breaker = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)
        
        # Failing function
        async def fail():
            raise ValueError("Failed")
        
        # Should open after 3 failures
        for i in range(3):
            with pytest.raises(ValueError):
                await breaker(fail)
        
        assert breaker.state == CircuitState.OPEN
        assert not breaker.can_request()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            expected_exception=ValueError
        )
        
        # Open the circuit
        async def fail():
            raise ValueError("Failed")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker(fail)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half-open
        assert breaker.can_request() is True
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Successful request should close circuit
        async def success():
            return "success"
        
        await breaker(success)
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker reopens on half-open failure."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            expected_exception=ValueError
        )
        
        # Open the circuit
        async def fail():
            raise ValueError("Failed")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker(fail)
        
        # Wait for recovery
        await asyncio.sleep(0.2)
        
        # Fail during half-open
        with pytest.raises(ValueError):
            await breaker(fail)
        
        assert breaker.state == CircuitState.OPEN
    
    def test_circuit_breaker_manual_operations(self):
        """Test manual circuit breaker operations."""
        breaker = CircuitBreaker()
        
        # Record failures manually
        for _ in range(5):
            breaker.record_failure()
        
        assert breaker.state == CircuitState.OPEN
        
        # Reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_stats(self):
        """Test circuit breaker statistics."""
        breaker = CircuitBreaker()
        
        # Generate some activity
        breaker.total_requests = 100
        breaker.total_failures = 10
        breaker.total_rejections = 5
        
        stats = breaker.get_stats()
        
        assert stats['total_requests'] == 100
        assert stats['total_failures'] == 10
        assert stats['total_rejections'] == 5
        assert stats['success_rate'] == 0.9
        assert stats['state'] == 'closed'


class TestAdaptiveRateLimiter:
    """Test adaptive rate limiter."""
    
    @pytest.mark.asyncio
    async def test_adaptive_rate_limiter_basic(self):
        """Test basic adaptive rate limiter functionality."""
        limiter = AdaptiveRateLimiter(
            base_rate=100,
            period=60.0,
            adjustment_interval=0.1  # Quick adjustment for testing
        )
        
        # Should start at base rate
        assert limiter.current_rate == 100
        
        # Make request
        await limiter.acquire()
        
        # Record slow response times
        for _ in range(20):
            limiter.record_response_time(3.0)  # Slow responses
        
        # Wait for adjustment
        await asyncio.sleep(0.2)
        await limiter.acquire()
        
        # Rate should be reduced
        assert limiter.current_rate < 100
    
    @pytest.mark.asyncio
    async def test_adaptive_rate_increase(self):
        """Test adaptive rate increase on fast responses."""
        limiter = AdaptiveRateLimiter(
            base_rate=100,
            period=60.0,
            adjustment_interval=0.1
        )
        
        # Record fast response times
        for _ in range(20):
            limiter.record_response_time(0.1)  # Fast responses
        
        # Trigger adjustment
        await asyncio.sleep(0.2)
        await limiter.acquire()
        
        # Rate should be increased
        assert limiter.current_rate > 100
    
    @pytest.mark.asyncio
    async def test_adaptive_rate_limits(self):
        """Test adaptive rate limiter respects min/max limits."""
        limiter = AdaptiveRateLimiter(
            base_rate=100,
            period=60.0,
            min_rate=50,
            max_rate=150,
            adjustment_interval=0.1
        )
        
        # Record very slow responses
        for _ in range(100):
            limiter.record_response_time(10.0)
        
        # Trigger multiple adjustments
        for _ in range(5):
            await asyncio.sleep(0.2)
            await limiter.acquire()
        
        # Should not go below minimum
        assert limiter.current_rate >= 50
        
        # Reset and test maximum
        limiter.current_rate = 100
        limiter.response_times.clear()
        
        # Record very fast responses
        for _ in range(100):
            limiter.record_response_time(0.01)
        
        # Trigger multiple adjustments
        for _ in range(5):
            await asyncio.sleep(0.2)
            await limiter.acquire()
        
        # Should not exceed maximum
        assert limiter.current_rate <= 150