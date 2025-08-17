# Stream Processor Coverage Gap Analysis

## Current Coverage: 83.30% (384/461 statements)

## Detailed Gap Analysis

### 1. **Property Edge Cases** (7 lines)
- Line 119: OHLCV timezone handling edge case
- Lines 201, 204: VolumeProfile cache invalidation
- Lines 228-230, 235-237: Value Area Low/High property getters

**Risk**: Low - These are defensive coding paths
**Recommendation**: Add edge case tests for empty volume profiles

### 2. **Startup/Shutdown Edge Cases** (2 lines)
- Lines 486-487: Warning when processor already running

**Risk**: Low - Defensive check
**Recommendation**: Test double-start scenario

### 3. **Queue Management** (9 lines)
- Lines 547-548: Redis publish in add_tick
- Lines 552-556: Queue full handling and tick dropping

**Risk**: Medium - Important for high-volume scenarios
**Test Needed**: Overflow test with full queue

### 4. **Error Handling Paths** (16 lines)
- Lines 575, 578-579: Timeout and error in tick processing
- Lines 616-619: Health monitor error recording
- Lines 626-629: Database save errors
- Lines 642-643: Redis publish errors for bars
- Lines 649-653: General bar processing errors

**Risk**: Medium - Error recovery important
**Test Needed**: Mock various error conditions

### 5. **Health Monitoring Logic** (36 lines)
- Lines 661-693: Extended health monitoring logic
  - Status updates based on latency
  - Health callback execution
  - Redis health publishing
  
- Lines 696, 700-707: Stale stream detection

**Risk**: Medium - Monitoring accuracy
**Test Needed**: Long-running health scenarios

### 6. **Data Access Methods** (17 lines)
- Lines 748-749: get_poc when no profile exists
- Lines 753-756: get_value_area when no profile
- Lines 764, 773: is_healthy for missing monitors
- Lines 788-794: get_recent_bars for missing timeframe

**Risk**: Low - Defensive null checks
**Test Needed**: Access methods with missing data

### 7. **Factory Function Error** (3 lines)
- Lines 826-828: Redis connection error handling

**Risk**: Low - Graceful degradation
**Test Needed**: Factory with failed Redis

### 8. **Utility Edge Case** (1 line)
- Line 859: Empty tick list in gap detection

**Risk**: Low - Edge case
**Test Needed**: detect_tick_gaps with <2 ticks

## Priority Recommendations

### High Priority (Implement First)
1. **Queue Overflow Test** - Critical for production
   ```python
   async def test_queue_overflow():
       # Fill queue to capacity
       # Verify tick dropping behavior
       # Check health metrics update
   ```

2. **Error Injection Tests** - Resilience validation
   ```python
   async def test_database_save_error():
       # Mock database error
       # Verify error handling
       # Check processing continues
   ```

### Medium Priority
3. **Health Monitoring Scenarios**
   ```python
   async def test_extended_health_monitoring():
       # Test latency-based status changes
       # Test stale stream detection
       # Test health callback errors
   ```

4. **Redis Connection Failures**
   ```python
   async def test_redis_publish_failures():
       # Mock Redis errors
       # Verify graceful degradation
       # Check error logging
   ```

### Low Priority (Nice to Have)
5. **Edge Case Properties**
   ```python
   def test_empty_volume_profile_properties():
       # Test POC/VAL/VAH with no data
       # Test cache behavior
   ```

6. **Defensive Null Checks**
   ```python
   def test_missing_data_access():
       # Test access methods with missing symbols
       # Test missing timeframes
   ```

## Coverage Improvement Strategy

### Quick Wins (Add 5-10% coverage)
1. Test empty/edge cases for properties
2. Add defensive null check tests
3. Test double-start scenario

### Significant Gains (Add 10-15% coverage)
1. Comprehensive error injection suite
2. Extended health monitoring tests
3. Queue overflow scenarios

### Target Coverage
- Current: 83.30%
- Achievable: 95%+
- Recommended: 90% (good balance)

## Testing Best Practices Applied

1. **Risk-Based Testing**: Focus on high-risk areas first
2. **Edge Case Coverage**: Systematic edge case identification
3. **Error Path Testing**: Comprehensive error injection
4. **Performance Awareness**: Consider high-volume scenarios
5. **Maintainability**: Clear test structure and naming

## Next Steps

1. Implement high-priority tests (2-3 hours)
2. Add medium-priority tests (1-2 hours)
3. Consider property-based testing for edge cases
4. Set up mutation testing to validate test quality
5. Add performance benchmarks for critical paths