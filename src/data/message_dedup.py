"""
Message deduplication system using Bloom filters for efficient duplicate detection.

This module provides a memory-efficient way to detect duplicate messages in the
WebSocket stream using Bloom filters with automatic rotation.
"""

import asyncio
import hashlib
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Set
from dataclasses import dataclass
import mmh3  # murmurhash3 for better hash distribution

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BloomFilterStats:
    """Statistics for Bloom filter performance."""
    items_added: int = 0
    possible_duplicates: int = 0
    false_positive_estimate: float = 0.0
    memory_usage_bytes: int = 0
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class BloomFilter:
    """
    Space-efficient probabilistic data structure for duplicate detection.
    
    Features:
    - Configurable false positive rate
    - Multiple hash functions for better distribution
    - Memory-efficient bit array storage
    """
    
    def __init__(self, expected_items: int, false_positive_rate: float = 0.001):
        """
        Initialize Bloom filter.
        
        Args:
            expected_items: Expected number of items to store
            false_positive_rate: Desired false positive rate (default 0.1%)
        """
        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        
        # Calculate optimal size and hash functions
        self.size = self._calculate_size(expected_items, false_positive_rate)
        self.num_hashes = self._calculate_hash_count(self.size, expected_items)
        
        # Initialize bit array
        self.bit_array = bytearray(math.ceil(self.size / 8))
        self.items_added = 0
        
        logger.debug(
            f"Bloom filter initialized: size={self.size} bits, "
            f"hashes={self.num_hashes}, expected_items={expected_items}"
        )
    
    @staticmethod
    def _calculate_size(n: int, p: float) -> int:
        """Calculate optimal bit array size."""
        if n <= 0:
            return 1024  # Minimum size
        m = -n * math.log(p) / (math.log(2) ** 2)
        return max(int(m), 1024)
    
    @staticmethod
    def _calculate_hash_count(m: int, n: int) -> int:
        """Calculate optimal number of hash functions."""
        if n <= 0:
            return 1
        k = (m / n) * math.log(2)
        return max(int(k), 1)
    
    def _get_hash_positions(self, item: str) -> List[int]:
        """Get bit positions for an item using multiple hash functions."""
        positions = []
        
        # Use MurmurHash3 with different seeds for independent hashes
        for i in range(self.num_hashes):
            # Create hash with seed
            hash_value = mmh3.hash(item, seed=i, signed=False)
            position = hash_value % self.size
            positions.append(position)
        
        return positions
    
    def add(self, item: str) -> bool:
        """
        Add item to the filter.
        
        Returns:
            True if item was possibly already present (might be false positive)
        """
        positions = self._get_hash_positions(item)
        already_present = True
        
        for pos in positions:
            byte_index = pos // 8
            bit_index = pos % 8
            
            if not (self.bit_array[byte_index] & (1 << bit_index)):
                already_present = False
                self.bit_array[byte_index] |= (1 << bit_index)
        
        if not already_present:
            self.items_added += 1
        
        return already_present
    
    def contains(self, item: str) -> bool:
        """Check if item might be in the filter (can have false positives)."""
        positions = self._get_hash_positions(item)
        
        for pos in positions:
            byte_index = pos // 8
            bit_index = pos % 8
            
            if not (self.bit_array[byte_index] & (1 << bit_index)):
                return False
        
        return True
    
    def get_false_positive_probability(self) -> float:
        """Calculate current false positive probability."""
        if self.items_added == 0:
            return 0.0
        
        # Formula: (1 - e^(-k*n/m))^k
        ratio = -self.num_hashes * self.items_added / self.size
        return math.pow(1 - math.exp(ratio), self.num_hashes)
    
    def get_memory_usage(self) -> int:
        """Get memory usage in bytes."""
        return len(self.bit_array)


class MessageDeduplicator:
    """
    Message deduplication system with automatic Bloom filter rotation.
    
    Features:
    - Time-based filter rotation to prevent unbounded growth
    - Duplicate detection across multiple filters
    - Performance statistics tracking
    - Configurable retention period
    """
    
    def __init__(
        self,
        expected_messages_per_minute: int = 10000,
        false_positive_rate: float = 0.001,
        retention_minutes: int = 5,
        rotation_interval_minutes: int = 1
    ):
        """
        Initialize message deduplicator.
        
        Args:
            expected_messages_per_minute: Expected message rate
            false_positive_rate: Acceptable false positive rate
            retention_minutes: How long to remember messages
            rotation_interval_minutes: How often to rotate filters
        """
        self.expected_messages_per_minute = expected_messages_per_minute
        self.false_positive_rate = false_positive_rate
        self.retention_minutes = retention_minutes
        self.rotation_interval_minutes = rotation_interval_minutes
        
        # Calculate expected items per filter
        self.expected_items_per_filter = (
            expected_messages_per_minute * rotation_interval_minutes
        )
        
        # Active filters with rotation timestamps
        self.filters: List[Tuple[BloomFilter, datetime]] = []
        self.max_filters = math.ceil(retention_minutes / rotation_interval_minutes)
        
        # Statistics
        self.stats = {
            'total_messages': 0,
            'duplicates_detected': 0,
            'filters_rotated': 0,
            'current_false_positive_rate': 0.0
        }
        
        # Rotation task
        self._rotation_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Create initial filter
        self._create_new_filter()
        
        logger.info(
            f"Message deduplicator initialized: "
            f"retention={retention_minutes}min, "
            f"rotation={rotation_interval_minutes}min, "
            f"max_filters={self.max_filters}"
        )
    
    def _create_new_filter(self):
        """Create a new Bloom filter and add to rotation."""
        new_filter = BloomFilter(
            self.expected_items_per_filter,
            self.false_positive_rate
        )
        
        self.filters.append((new_filter, datetime.now(timezone.utc)))
        
        # Remove old filters if exceeding max
        while len(self.filters) > self.max_filters:
            old_filter, _ = self.filters.pop(0)
            logger.debug(
                f"Removed old filter with {old_filter.items_added} items"
            )
        
        self.stats['filters_rotated'] += 1
    
    async def start(self):
        """Start the deduplicator with automatic rotation."""
        self._running = True
        self._rotation_task = asyncio.create_task(self._rotation_loop())
        logger.info("Message deduplicator started")
    
    async def stop(self):
        """Stop the deduplicator."""
        self._running = False
        
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Message deduplicator stopped")
    
    async def _rotation_loop(self):
        """Background task to rotate filters periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.rotation_interval_minutes * 60)
                self._create_new_filter()
                self._update_statistics()
                
                logger.debug(
                    f"Filter rotated. Active filters: {len(self.filters)}, "
                    f"Total processed: {self.stats['total_messages']}"
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rotation loop: {e}")
    
    def _update_statistics(self):
        """Update deduplication statistics."""
        # Calculate combined false positive rate
        if self.filters:
            # Probability that an item is a false positive in any filter
            combined_rate = 1.0
            for bloom_filter, _ in self.filters:
                filter_rate = bloom_filter.get_false_positive_probability()
                combined_rate *= (1 - filter_rate)
            
            self.stats['current_false_positive_rate'] = 1 - combined_rate
    
    def create_message_id(self, message: dict) -> str:
        """
        Create a unique identifier for a message.
        
        Args:
            message: Message dictionary
            
        Returns:
            Unique message identifier
        """
        # Extract key fields for deduplication
        key_parts = []
        
        # Service and timestamp are always included
        if 'service' in message:
            key_parts.append(f"service:{message['service']}")
        
        if 'timestamp' in message:
            key_parts.append(f"ts:{message['timestamp']}")
        
        # Handle data messages
        if 'data' in message:
            for item in message.get('data', []):
                if 'content' in item:
                    for content in item.get('content', []):
                        # Include symbol and key price/trade data
                        symbol = content.get('key', content.get('symbol', ''))
                        if symbol:
                            key_parts.append(f"sym:{symbol}")
                        
                        # For trades, include sequence number if available
                        sequence = content.get('4', content.get('SEQUENCE'))
                        if sequence:
                            key_parts.append(f"seq:{sequence}")
                        
                        # For quotes, include price and size
                        for field in ['1', '2', '3', 'BID_PRICE', 'ASK_PRICE', 'LAST_PRICE']:
                            if field in content:
                                key_parts.append(f"{field}:{content[field]}")
        
        # Create hash of combined key
        combined_key = '|'.join(sorted(key_parts))
        return hashlib.sha256(combined_key.encode()).hexdigest()[:16]
    
    def is_duplicate(self, message: dict) -> bool:
        """
        Check if a message is a duplicate.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is likely a duplicate
        """
        self.stats['total_messages'] += 1
        
        # Create message ID
        message_id = self.create_message_id(message)
        
        # Check if message exists in any filter
        is_dup = False
        for bloom_filter, _ in self.filters:
            if bloom_filter.contains(message_id):
                is_dup = True
                break
        
        # Add to current (newest) filter
        if self.filters:
            current_filter = self.filters[-1][0]
            current_filter.add(message_id)
        
        if is_dup:
            self.stats['duplicates_detected'] += 1
            logger.debug(f"Duplicate message detected: {message_id}")
        
        return is_dup
    
    def get_statistics(self) -> dict:
        """Get deduplication statistics."""
        stats = self.stats.copy()
        
        # Add filter details
        stats['active_filters'] = len(self.filters)
        stats['total_memory_bytes'] = sum(
            f.get_memory_usage() for f, _ in self.filters
        )
        
        # Calculate duplicate rate
        if stats['total_messages'] > 0:
            stats['duplicate_rate'] = (
                stats['duplicates_detected'] / stats['total_messages']
            )
        else:
            stats['duplicate_rate'] = 0.0
        
        # Add per-filter stats
        stats['filters'] = []
        for bloom_filter, created_at in self.filters:
            filter_stats = {
                'created_at': created_at.isoformat(),
                'items_added': bloom_filter.items_added,
                'false_positive_rate': bloom_filter.get_false_positive_probability(),
                'memory_bytes': bloom_filter.get_memory_usage()
            }
            stats['filters'].append(filter_stats)
        
        return stats
    
    def reset_statistics(self):
        """Reset statistics counters."""
        self.stats['total_messages'] = 0
        self.stats['duplicates_detected'] = 0
        logger.info("Deduplication statistics reset")