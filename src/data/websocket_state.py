"""
WebSocket connection state manager with persistence and recovery capabilities.

This module provides state synchronization for WebSocket connections to enable
recovery after crashes or disconnections while maintaining message continuity.
"""

import asyncio
import json
import pickle
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import aiofiles
import redis.asyncio as redis

from ..utils.logger import get_logger
from ..config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ConnectionMetrics:
    """Metrics for connection health monitoring."""
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    messages_received: int = 0
    messages_sent: int = 0
    reconnect_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'messages_received': self.messages_received,
            'messages_sent': self.messages_sent,
            'reconnect_count': self.reconnect_count,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionMetrics':
        """Create from dictionary."""
        return cls(
            connected_at=datetime.fromisoformat(data['connected_at']) if data.get('connected_at') else None,
            last_heartbeat=datetime.fromisoformat(data['last_heartbeat']) if data.get('last_heartbeat') else None,
            messages_received=data.get('messages_received', 0),
            messages_sent=data.get('messages_sent', 0),
            reconnect_count=data.get('reconnect_count', 0),
            last_error=data.get('last_error'),
            last_error_time=datetime.fromisoformat(data['last_error_time']) if data.get('last_error_time') else None
        )


@dataclass
class WebSocketState:
    """Complete WebSocket connection state."""
    connection_id: str
    account_id: str
    subscriptions: Dict[str, Set[str]] = field(default_factory=dict)  # service -> symbols
    pending_subscriptions: List[Dict[str, Any]] = field(default_factory=list)
    last_message_id: int = 0
    last_sequence_numbers: Dict[str, int] = field(default_factory=dict)  # symbol -> sequence
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    checkpoint_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'connection_id': self.connection_id,
            'account_id': self.account_id,
            'subscriptions': {k: list(v) for k, v in self.subscriptions.items()},
            'pending_subscriptions': self.pending_subscriptions,
            'last_message_id': self.last_message_id,
            'last_sequence_numbers': self.last_sequence_numbers,
            'metrics': self.metrics.to_dict(),
            'checkpoint_time': self.checkpoint_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketState':
        """Create from dictionary."""
        subscriptions = {k: set(v) for k, v in data.get('subscriptions', {}).items()}
        return cls(
            connection_id=data['connection_id'],
            account_id=data['account_id'],
            subscriptions=subscriptions,
            pending_subscriptions=data.get('pending_subscriptions', []),
            last_message_id=data.get('last_message_id', 0),
            last_sequence_numbers=data.get('last_sequence_numbers', {}),
            metrics=ConnectionMetrics.from_dict(data.get('metrics', {})),
            checkpoint_time=datetime.fromisoformat(data['checkpoint_time'])
        )


class StateStorage(Enum):
    """Storage backend options."""
    FILE = "file"
    REDIS = "redis"
    MEMORY = "memory"


class ConnectionStateManager:
    """
    Manages WebSocket connection state with persistence and recovery.
    
    Features:
    - State checkpointing to disk/Redis
    - Crash recovery with state restoration
    - Message sequence tracking
    - Connection health metrics
    """
    
    def __init__(
        self,
        connection_id: str,
        account_id: str,
        storage_backend: StateStorage = StateStorage.FILE,
        checkpoint_interval: int = 30,  # seconds
        state_dir: Optional[Path] = None,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize state manager.
        
        Args:
            connection_id: Unique connection identifier
            account_id: Account ID for this connection
            storage_backend: Storage backend to use
            checkpoint_interval: Seconds between state checkpoints
            state_dir: Directory for file-based storage
            redis_client: Redis client for Redis-based storage
        """
        self.connection_id = connection_id
        self.account_id = account_id
        self.storage_backend = storage_backend
        self.checkpoint_interval = checkpoint_interval
        
        # Storage setup
        if storage_backend == StateStorage.FILE:
            self.state_dir = state_dir or Path.home() / ".schwab_trader" / "websocket_state"
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = self.state_dir / f"ws_state_{connection_id}.json"
        elif storage_backend == StateStorage.REDIS:
            if not redis_client:
                raise ValueError("Redis client required for Redis storage backend")
            self.redis_client = redis_client
            self.redis_key = f"websocket:state:{connection_id}"
        
        # Current state
        self.state = WebSocketState(
            connection_id=connection_id,
            account_id=account_id
        )
        
        # Checkpoint task
        self._checkpoint_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"State manager initialized for connection {connection_id} using {storage_backend.value} backend")
    
    async def initialize(self) -> bool:
        """
        Initialize state manager and recover existing state if available.
        
        Returns:
            True if state was recovered, False if starting fresh
        """
        # Try to recover existing state
        recovered = await self.recover_state()
        
        # Start checkpoint task
        self._running = True
        self._checkpoint_task = asyncio.create_task(self._checkpoint_loop())
        
        if recovered:
            logger.info(f"Recovered state for connection {self.connection_id}")
        else:
            logger.info(f"Starting fresh state for connection {self.connection_id}")
        
        return recovered
    
    async def shutdown(self):
        """Shutdown state manager and save final state."""
        self._running = False
        
        # Cancel checkpoint task
        if self._checkpoint_task:
            self._checkpoint_task.cancel()
            try:
                await self._checkpoint_task
            except asyncio.CancelledError:
                pass
        
        # Save final state
        await self.checkpoint_state()
        logger.info(f"State manager shutdown for connection {self.connection_id}")
    
    async def checkpoint_state(self):
        """Save current state to storage."""
        try:
            self.state.checkpoint_time = datetime.now(timezone.utc)
            state_data = json.dumps(self.state.to_dict(), default=str)
            
            if self.storage_backend == StateStorage.FILE:
                async with aiofiles.open(self.state_file, 'w') as f:
                    await f.write(state_data)
                    
            elif self.storage_backend == StateStorage.REDIS:
                await self.redis_client.setex(
                    self.redis_key,
                    timedelta(days=7),  # Expire after 7 days
                    state_data
                )
            
            logger.debug(f"State checkpointed for connection {self.connection_id}")
            
        except Exception as e:
            logger.error(f"Error checkpointing state: {e}")
    
    async def recover_state(self) -> bool:
        """
        Recover state from storage if available.
        
        Returns:
            True if state was recovered, False otherwise
        """
        try:
            state_data = None
            
            if self.storage_backend == StateStorage.FILE:
                if self.state_file.exists():
                    async with aiofiles.open(self.state_file, 'r') as f:
                        state_data = await f.read()
                        
            elif self.storage_backend == StateStorage.REDIS:
                state_data = await self.redis_client.get(self.redis_key)
                if state_data:
                    state_data = state_data.decode('utf-8')
            
            if state_data:
                data = json.loads(state_data)
                self.state = WebSocketState.from_dict(data)
                
                # Validate recovered state
                if self._validate_recovered_state():
                    return True
                else:
                    logger.warning("Recovered state failed validation, starting fresh")
                    self.state = WebSocketState(self.connection_id, self.account_id)
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error recovering state: {e}")
            return False
    
    def _validate_recovered_state(self) -> bool:
        """Validate recovered state is recent and consistent."""
        # Check if checkpoint is recent (within last hour)
        age = datetime.now(timezone.utc) - self.state.checkpoint_time
        if age > timedelta(hours=1):
            logger.warning(f"Recovered state is {age.total_seconds() / 3600:.1f} hours old")
            return False
        
        # Additional validation could be added here
        return True
    
    async def _checkpoint_loop(self):
        """Background task to periodically checkpoint state."""
        while self._running:
            try:
                await asyncio.sleep(self.checkpoint_interval)
                await self.checkpoint_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in checkpoint loop: {e}")
    
    # State update methods
    
    def update_subscriptions(self, service: str, symbols: Set[str]):
        """Update subscription state."""
        self.state.subscriptions[service] = symbols
    
    def add_pending_subscription(self, subscription: Dict[str, Any]):
        """Add pending subscription."""
        self.state.pending_subscriptions.append(subscription)
    
    def clear_pending_subscriptions(self):
        """Clear pending subscriptions."""
        self.state.pending_subscriptions.clear()
    
    def update_message_id(self, message_id: int):
        """Update last message ID."""
        self.state.last_message_id = max(self.state.last_message_id, message_id)
    
    def update_sequence_number(self, symbol: str, sequence: int):
        """Update last sequence number for a symbol."""
        self.state.last_sequence_numbers[symbol] = sequence
    
    def get_next_message_id(self) -> int:
        """Get next message ID."""
        self.state.last_message_id += 1
        return self.state.last_message_id
    
    def should_process_message(self, symbol: str, sequence: Optional[int]) -> bool:
        """
        Check if a message should be processed based on sequence number.
        
        Returns:
            True if message should be processed, False if it's a duplicate
        """
        if sequence is None:
            return True
        
        last_sequence = self.state.last_sequence_numbers.get(symbol, -1)
        return sequence > last_sequence
    
    # Metrics methods
    
    def record_connection(self):
        """Record successful connection."""
        self.state.metrics.connected_at = datetime.now(timezone.utc)
        self.state.metrics.reconnect_count += 1
    
    def record_heartbeat(self):
        """Record heartbeat."""
        self.state.metrics.last_heartbeat = datetime.now(timezone.utc)
    
    def record_message_received(self):
        """Record received message."""
        self.state.metrics.messages_received += 1
    
    def record_message_sent(self):
        """Record sent message."""
        self.state.metrics.messages_sent += 1
    
    def record_error(self, error: str):
        """Record error."""
        self.state.metrics.last_error = error
        self.state.metrics.last_error_time = datetime.now(timezone.utc)
    
    def get_connection_health(self) -> Dict[str, Any]:
        """Get connection health metrics."""
        now = datetime.now(timezone.utc)
        metrics = self.state.metrics
        
        # Calculate uptime
        uptime = None
        if metrics.connected_at:
            uptime = (now - metrics.connected_at).total_seconds()
        
        # Check heartbeat staleness
        heartbeat_stale = False
        if metrics.last_heartbeat:
            heartbeat_age = (now - metrics.last_heartbeat).total_seconds()
            heartbeat_stale = heartbeat_age > 60  # Consider stale after 60 seconds
        
        return {
            'connection_id': self.connection_id,
            'account_id': self.account_id,
            'uptime_seconds': uptime,
            'messages_received': metrics.messages_received,
            'messages_sent': metrics.messages_sent,
            'reconnect_count': metrics.reconnect_count,
            'heartbeat_stale': heartbeat_stale,
            'last_error': metrics.last_error,
            'subscriptions_count': sum(len(symbols) for symbols in self.state.subscriptions.values())
        }