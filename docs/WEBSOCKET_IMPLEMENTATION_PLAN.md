# WebSocket Streaming Implementation Plan

## Overview

This document provides a detailed implementation plan for the WebSocket streaming component, the final piece needed to complete Phase 1 of the Schwab Autotrader system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebSocket Streaming Architecture              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Schwab WebSocket API                                            │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────┐                                             │
│  │  WebSocket       │                                             │
│  │  Connection      │◄─── Heartbeat (30s)                        │
│  │  Manager         │◄─── Auto-reconnect                         │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │  Message         │                                             │
│  │  Parser          │◄─── Format: JSON                           │
│  │                  │◄─── Types: Quote, Trade, Level2            │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │  Tick            │                                             │
│  │  Converter       │◄─── Schwab → Tick format                   │
│  │                  │◄─── Validation                             │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │  Stream          │                                             │
│  │  Processor       │◄─── 10K+ ticks/sec                         │
│  │  (Existing)      │◄─── OHLCV, Volume Profile                  │
│  └─────────────────┘                                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. WebSocket Connection Manager

```python
# src/data/websocket_client.py

import asyncio
import websockets
import json
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone
import logging

from ..auth.auth_service import get_auth_service
from ..utils.logger import get_logger
from .stream_processor import StreamProcessor, Tick, TickType

logger = get_logger(__name__)

class SchwabWebSocketClient:
    """
    Manages WebSocket connection to Schwab streaming API.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Heartbeat management
    - Message queuing during disconnections
    - Integration with Stream Processor
    """
    
    # Schwab WebSocket endpoints
    WS_URL = "wss://stream.schwabapi.com/v1/stream"
    
    # Connection parameters
    HEARTBEAT_INTERVAL = 30  # seconds
    RECONNECT_MAX_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 1  # seconds
    
    def __init__(self, stream_processor: StreamProcessor):
        self.stream_processor = stream_processor
        self.auth_service = None
        self.connection = None
        self.subscriptions: Dict[str, List[str]] = {}
        self._running = False
        self._heartbeat_task = None
        self._reconnect_attempts = 0
        self._message_queue = asyncio.Queue(maxsize=10000)
        
    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        
    async def disconnect(self):
        """Gracefully disconnect WebSocket."""
        
    async def subscribe(self, symbols: List[str], 
                       data_types: List[str] = ["QUOTE", "TRADE"]):
        """Subscribe to real-time data for symbols."""
        
    async def _handle_message(self, message: str):
        """Process incoming WebSocket messages."""
        
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to keep connection alive."""
        
    async def _reconnect(self):
        """Handle reconnection with exponential backoff."""
```

### 2. Message Parser

```python
# src/data/websocket_parser.py

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from .stream_processor import Tick, TickType

class MessageType(str, Enum):
    """Schwab WebSocket message types."""
    HEARTBEAT = "HEARTBEAT"
    RESPONSE = "RESPONSE"
    SNAPSHOT = "SNAPSHOT"
    UPDATE = "UPDATE"
    ERROR = "ERROR"

@dataclass
class ParsedMessage:
    """Parsed WebSocket message."""
    message_type: MessageType
    service: Optional[str]
    command: Optional[str]
    content: Dict[str, Any]
    timestamp: datetime

class SchwabMessageParser:
    """
    Parses Schwab WebSocket messages into internal format.
    
    Handles:
    - Quote updates (bid/ask/last)
    - Trade notifications
    - Level 2 data (if subscribed)
    - System messages
    """
    
    def parse(self, raw_message: str) -> ParsedMessage:
        """Parse raw WebSocket message."""
        
    def to_tick(self, parsed: ParsedMessage) -> Optional[Tick]:
        """Convert parsed message to Tick object."""
        
    def extract_quotes(self, content: Dict) -> List[Tick]:
        """Extract quote ticks from message content."""
        
    def extract_trades(self, content: Dict) -> List[Tick]:
        """Extract trade ticks from message content."""
```

### 3. Streaming Service Integration

```python
# src/data/streaming_service.py

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from .websocket_client import SchwabWebSocketClient
from .websocket_parser import SchwabMessageParser
from .stream_processor import StreamProcessor, create_stream_processor
from ..utils.logger import get_logger

logger = get_logger(__name__)

class StreamingService:
    """
    High-level streaming service coordinating WebSocket and Stream Processor.
    
    Features:
    - Manages WebSocket lifecycle
    - Routes parsed ticks to Stream Processor
    - Monitors streaming health
    - Provides unified interface
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.stream_processor = None
        self.websocket_client = None
        self.parser = SchwabMessageParser()
        self._running = False
        self._stats = {
            'messages_received': 0,
            'ticks_processed': 0,
            'errors': 0,
            'start_time': None
        }
        
    async def initialize(self):
        """Initialize streaming components."""
        # Create Stream Processor
        self.stream_processor = await create_stream_processor(
            redis_url=redis_url,
            save_to_db=True,
            timeframes=[1, 5, 15]
        )
        
        # Create WebSocket client
        self.websocket_client = SchwabWebSocketClient(
            stream_processor=self.stream_processor
        )
        
    async def start_streaming(self, symbols: List[str]):
        """Start streaming for specified symbols."""
        
    async def stop_streaming(self):
        """Stop all streaming."""
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get streaming statistics."""
```

### 4. Integration Points

#### Stream Processor Integration

```python
# Integration with existing Stream Processor
async def route_to_processor(self, tick: Tick):
    """Route tick to Stream Processor with error handling."""
    try:
        success = await self.stream_processor.add_tick(tick)
        if success:
            self._stats['ticks_processed'] += 1
        else:
            logger.warning(f"Failed to process tick: {tick}")
            self._stats['errors'] += 1
    except Exception as e:
        logger.error(f"Error routing tick: {e}")
        self._stats['errors'] += 1
```

#### Authentication Integration

```python
# WebSocket authentication using existing auth service
async def _authenticate_websocket(self):
    """Authenticate WebSocket connection."""
    if not self.auth_service:
        self.auth_service = get_auth_service()
        await self.auth_service.initialize()
    
    # Get access token
    token = await self.auth_service.get_access_token()
    
    # Include in WebSocket headers
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "SchwabAutotrader/1.0"
    }
    
    return headers
```

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_websocket_client.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
import websockets

class TestWebSocketClient:
    """Test WebSocket connection management."""
    
    @pytest.mark.asyncio
    async def test_connection_establishment(self):
        """Test successful connection."""
        
    @pytest.mark.asyncio
    async def test_reconnection_logic(self):
        """Test automatic reconnection."""
        
    @pytest.mark.asyncio
    async def test_heartbeat_management(self):
        """Test heartbeat sending."""
```

### 2. Integration Tests

```python
# tests/test_streaming_integration.py

class TestStreamingIntegration:
    """Test full streaming pipeline."""
    
    @pytest.mark.asyncio
    async def test_message_flow(self):
        """Test message flow from WebSocket to Stream Processor."""
        
    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test system recovery from errors."""
```

### 3. Performance Tests

```python
# tests/benchmark_streaming.py

async def benchmark_throughput():
    """Measure streaming throughput."""
    # Simulate high-volume message flow
    # Measure processing latency
    # Check memory usage
```

## Implementation Timeline

### Day 1 - Morning (4 hours)
1. **WebSocket Connection Manager** (2 hours)
   - Basic connection establishment
   - Authentication integration
   - Heartbeat implementation

2. **Message Parser** (2 hours)
   - Parse Schwab message format
   - Convert to Tick objects
   - Handle different message types

### Day 1 - Afternoon (4 hours)
3. **Streaming Service** (2 hours)
   - Coordinate components
   - Implement error handling
   - Add monitoring

4. **Testing & Validation** (2 hours)
   - Unit tests for all components
   - Integration tests
   - Performance validation

## Risk Mitigation

### Connection Reliability
- **Risk**: WebSocket disconnections
- **Mitigation**: 
  - Automatic reconnection with exponential backoff
  - Message queuing during disconnections
  - Fallback to REST API for critical data

### Message Volume
- **Risk**: High message volume overwhelming system
- **Mitigation**:
  - Queue-based architecture (10K capacity)
  - Selective symbol subscription
  - Message filtering options

### Data Integrity
- **Risk**: Missing or corrupted messages
- **Mitigation**:
  - Message sequence tracking
  - Data validation in parser
  - Reconciliation with REST API

## Performance Targets

- Connection establishment: < 1 second
- Message parsing: < 1ms per message
- End-to-end latency: < 10ms (WebSocket → Stream Processor)
- Throughput: 10,000+ messages/second
- Memory usage: < 500MB for 100 symbol subscriptions

## Success Criteria

1. **Functional Requirements**
   - [ ] Stable WebSocket connection maintained
   - [ ] All message types parsed correctly
   - [ ] Ticks routed to Stream Processor
   - [ ] Automatic reconnection working

2. **Performance Requirements**
   - [ ] Meet latency targets
   - [ ] Handle target throughput
   - [ ] Stable memory usage

3. **Integration Requirements**
   - [ ] Seamless auth integration
   - [ ] Clean Stream Processor integration
   - [ ] Monitoring and health checks

## Next Steps After Implementation

1. **Production Testing**
   - Extended stability testing (24+ hours)
   - Peak volume testing (market open)
   - Failure scenario validation

2. **Optimization**
   - Message batching optimization
   - Subscription management
   - Resource usage tuning

3. **Documentation**
   - API documentation
   - Operational runbook
   - Troubleshooting guide