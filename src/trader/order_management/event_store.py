"""
Event Store Configuration for Order Management System.

This module provides event store setup and configuration for persistent 
event sourcing with optimized performance and reliability.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID
import logging

from eventsourcing.application import Application
from eventsourcing.persistence import (
    EventStore, AggregateRecorder, ApplicationRecorder,
    Tracking, IntegrityError
)
from eventsourcing.sqlite import (
    SQLiteAggregateRecorder, SQLiteApplicationRecorder,
    SQLiteDatastore, SQLiteInfrastructure
)
from eventsourcing.postgres import (
    PostgresAggregateRecorder, PostgresApplicationRecorder,
    PostgresDatastore, PostgresInfrastructure
)

from .event_sourced_order import OrderAggregate
from ...utils.logger import get_logger

logger = get_logger(__name__)


class OrderEventStore:
    """
    Specialized event store for Order aggregates with optimized persistence.
    
    Provides configuration for SQLite and PostgreSQL backends with
    performance optimization and connection pooling.
    """
    
    def __init__(
        self,
        db_type: str = "sqlite",
        db_path: Optional[str] = None,
        connection_string: Optional[str] = None,
        pool_size: int = 10,
        **kwargs
    ):
        """
        Initialize event store.
        
        Args:
            db_type: Database type ('sqlite' or 'postgres')
            db_path: SQLite database file path
            connection_string: PostgreSQL connection string
            pool_size: Connection pool size for PostgreSQL
            **kwargs: Additional configuration
        """
        self.db_type = db_type.lower()
        self.db_path = db_path
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.config = kwargs
        
        # Initialize infrastructure
        self.infrastructure = self._create_infrastructure()
        self.aggregate_recorder = self._create_aggregate_recorder()
        self.application_recorder = self._create_application_recorder()
        
        # Create event store
        self.event_store = EventStore(
            aggregate_recorder=self.aggregate_recorder,
            application_recorder=self.application_recorder
        )
        
        logger.info(f"Order event store initialized with {db_type} backend")
    
    def _create_infrastructure(self):
        """Create database infrastructure based on type."""
        if self.db_type == "sqlite":
            return self._create_sqlite_infrastructure()
        elif self.db_type == "postgres":
            return self._create_postgres_infrastructure()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _create_sqlite_infrastructure(self) -> SQLiteInfrastructure:
        """Create SQLite infrastructure with optimized settings."""
        
        # Default to in-memory for testing, file for production
        if self.db_path is None:
            if os.getenv("ENVIRONMENT") == "test":
                db_path = ":memory:"
            else:
                # Create data directory if it doesn't exist
                data_dir = Path("data")
                data_dir.mkdir(exist_ok=True)
                db_path = str(data_dir / "orders_events.db")
        else:
            db_path = self.db_path
        
        # Create datastore with optimized settings
        datastore = SQLiteDatastore(
            db_path,
            # Performance optimizations
            lock_timeout=30.0,
            pragma={
                "journal_mode": "WAL",  # Write-Ahead Logging for better concurrency
                "synchronous": "NORMAL",  # Balance between performance and safety
                "cache_size": -64000,  # 64MB cache
                "temp_store": "MEMORY",  # Use memory for temporary storage
                "mmap_size": 268435456,  # 256MB memory-mapped I/O
                "busy_timeout": 30000,  # 30 second busy timeout
            }
        )
        
        infrastructure = SQLiteInfrastructure(datastore=datastore)
        
        # Create tables if they don't exist
        self._ensure_tables_exist(datastore)
        
        return infrastructure
    
    def _create_postgres_infrastructure(self) -> PostgresInfrastructure:
        """Create PostgreSQL infrastructure with connection pooling."""
        
        if not self.connection_string:
            # Build connection string from environment variables
            self.connection_string = self._build_postgres_connection_string()
        
        # Create datastore with connection pooling
        datastore = PostgresDatastore(
            self.connection_string,
            pool_size=self.pool_size,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections every hour
        )
        
        infrastructure = PostgresInfrastructure(datastore=datastore)
        
        # Create tables if they don't exist
        self._ensure_postgres_tables_exist(datastore)
        
        return infrastructure
    
    def _build_postgres_connection_string(self) -> str:
        """Build PostgreSQL connection string from environment variables."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "autotrading")
        username = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    def _ensure_tables_exist(self, datastore: SQLiteDatastore):
        """Ensure SQLite tables exist with proper schema."""
        try:
            with datastore.transaction() as conn:
                # Create events table with optimized schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        originator_id TEXT NOT NULL,
                        originator_version INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        state BLOB NOT NULL,
                        timestamp REAL NOT NULL,
                        PRIMARY KEY (originator_id, originator_version)
                    )
                """)
                
                # Create snapshots table for performance
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        originator_id TEXT NOT NULL,
                        originator_version INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        state BLOB NOT NULL,
                        timestamp REAL NOT NULL,
                        PRIMARY KEY (originator_id, originator_version)
                    )
                """)
                
                # Create application tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tracking (
                        application_name TEXT NOT NULL,
                        notification_id INTEGER NOT NULL,
                        PRIMARY KEY (application_name, notification_id)
                    )
                """)
                
                # Create indices for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_originator_id 
                    ON events (originator_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                    ON events (timestamp)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_topic 
                    ON events (topic)
                """)
                
                logger.info("SQLite event store tables created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create SQLite tables: {e}")
            raise
    
    def _ensure_postgres_tables_exist(self, datastore: PostgresDatastore):
        """Ensure PostgreSQL tables exist with proper schema."""
        try:
            with datastore.transaction() as conn:
                # Create events table with optimized schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        originator_id UUID NOT NULL,
                        originator_version INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        state BYTEA NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        PRIMARY KEY (originator_id, originator_version)
                    )
                """)
                
                # Create snapshots table for performance
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        originator_id UUID NOT NULL,
                        originator_version INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        state BYTEA NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        PRIMARY KEY (originator_id, originator_version)
                    )
                """)
                
                # Create application tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tracking (
                        application_name TEXT NOT NULL,
                        notification_id BIGINT NOT NULL,
                        PRIMARY KEY (application_name, notification_id)
                    )
                """)
                
                # Create indices for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_originator_id 
                    ON events (originator_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                    ON events (timestamp)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_topic 
                    ON events (topic)
                """)
                
                # Create partial indices for active orders
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_active_orders 
                    ON events (originator_id, timestamp) 
                    WHERE topic LIKE '%OrderCreated%' OR topic LIKE '%OrderValidated%' 
                    OR topic LIKE '%OrderSubmitted%' OR topic LIKE '%OrderAcknowledged%'
                """)
                
                logger.info("PostgreSQL event store tables created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL tables: {e}")
            raise
    
    def _create_aggregate_recorder(self) -> AggregateRecorder:
        """Create aggregate recorder based on database type."""
        if self.db_type == "sqlite":
            return SQLiteAggregateRecorder(
                datastore=self.infrastructure.datastore,
                events_table_name="events",
                snapshots_table_name="snapshots"
            )
        elif self.db_type == "postgres":
            return PostgresAggregateRecorder(
                datastore=self.infrastructure.datastore,
                events_table_name="events",
                snapshots_table_name="snapshots"
            )
    
    def _create_application_recorder(self) -> ApplicationRecorder:
        """Create application recorder based on database type."""
        if self.db_type == "sqlite":
            return SQLiteApplicationRecorder(
                datastore=self.infrastructure.datastore,
                tracking_table_name="tracking"
            )
        elif self.db_type == "postgres":
            return PostgresApplicationRecorder(
                datastore=self.infrastructure.datastore,
                tracking_table_name="tracking"
            )
    
    def get_order_events(self, order_id: UUID) -> list:
        """
        Get all events for a specific order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            List of events for the order
        """
        try:
            events = list(self.aggregate_recorder.select_events(
                originator_id=order_id
            ))
            return events
        except Exception as e:
            logger.error(f"Failed to get events for order {order_id}: {e}")
            return []
    
    def get_order_events_after_version(self, order_id: UUID, version: int) -> list:
        """
        Get order events after a specific version.
        
        Args:
            order_id: Order identifier
            version: Minimum version to retrieve
            
        Returns:
            List of events after the specified version
        """
        try:
            events = list(self.aggregate_recorder.select_events(
                originator_id=order_id,
                gt=version
            ))
            return events
        except Exception as e:
            logger.error(f"Failed to get events for order {order_id} after version {version}: {e}")
            return []
    
    def create_snapshot(self, order: OrderAggregate) -> bool:
        """
        Create a snapshot of an order aggregate for performance.
        
        Args:
            order: Order aggregate to snapshot
            
        Returns:
            True if snapshot created successfully
        """
        try:
            # Create snapshot every 10 events to optimize loading
            if order.version > 0 and order.version % 10 == 0:
                self.aggregate_recorder.insert_snapshot(
                    originator_id=order.id,
                    originator_version=order.version,
                    topic=f"{OrderAggregate.__name__}.Snapshot",
                    state=order.__dict__
                )
                logger.debug(f"Created snapshot for order {order.id} at version {order.version}")
                return True
        except Exception as e:
            logger.error(f"Failed to create snapshot for order {order.id}: {e}")
        
        return False
    
    def get_event_store_statistics(self) -> Dict[str, Any]:
        """
        Get event store statistics for monitoring.
        
        Returns:
            Dictionary with event store statistics
        """
        try:
            stats = {
                "db_type": self.db_type,
                "total_events": 0,
                "total_snapshots": 0,
                "unique_aggregates": 0,
                "latest_event_timestamp": None
            }
            
            if self.db_type == "sqlite":
                with self.infrastructure.datastore.transaction() as conn:
                    # Count total events
                    result = conn.execute("SELECT COUNT(*) FROM events").fetchone()
                    stats["total_events"] = result[0] if result else 0
                    
                    # Count total snapshots
                    result = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()
                    stats["total_snapshots"] = result[0] if result else 0
                    
                    # Count unique aggregates
                    result = conn.execute("SELECT COUNT(DISTINCT originator_id) FROM events").fetchone()
                    stats["unique_aggregates"] = result[0] if result else 0
                    
                    # Get latest event timestamp
                    result = conn.execute("SELECT MAX(timestamp) FROM events").fetchone()
                    if result and result[0]:
                        stats["latest_event_timestamp"] = result[0]
            
            elif self.db_type == "postgres":
                with self.infrastructure.datastore.transaction() as conn:
                    # Count total events
                    result = conn.execute("SELECT COUNT(*) FROM events").fetchone()
                    stats["total_events"] = result[0] if result else 0
                    
                    # Count total snapshots
                    result = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()
                    stats["total_snapshots"] = result[0] if result else 0
                    
                    # Count unique aggregates
                    result = conn.execute("SELECT COUNT(DISTINCT originator_id) FROM events").fetchone()
                    stats["unique_aggregates"] = result[0] if result else 0
                    
                    # Get latest event timestamp
                    result = conn.execute("SELECT MAX(timestamp) FROM events").fetchone()
                    if result and result[0]:
                        stats["latest_event_timestamp"] = result[0].isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get event store statistics: {e}")
            return {
                "db_type": self.db_type,
                "error": str(e)
            }
    
    def close(self):
        """Close event store connections."""
        try:
            if hasattr(self.infrastructure.datastore, 'close'):
                self.infrastructure.datastore.close()
            logger.info("Event store connections closed")
        except Exception as e:
            logger.error(f"Error closing event store: {e}")


class OrderEventStoreFactory:
    """
    Factory for creating properly configured order event stores.
    
    Handles environment-specific configuration and provides
    sensible defaults for different deployment scenarios.
    """
    
    @staticmethod
    def create_event_store(
        environment: str = "development",
        **kwargs
    ) -> OrderEventStore:
        """
        Create event store based on environment.
        
        Args:
            environment: Target environment (development, test, production)
            **kwargs: Additional configuration overrides
            
        Returns:
            Configured OrderEventStore instance
        """
        if environment == "test":
            return OrderEventStoreFactory.create_test_store(**kwargs)
        elif environment == "development":
            return OrderEventStoreFactory.create_development_store(**kwargs)
        elif environment == "production":
            return OrderEventStoreFactory.create_production_store(**kwargs)
        else:
            raise ValueError(f"Unknown environment: {environment}")
    
    @staticmethod
    def create_test_store(**kwargs) -> OrderEventStore:
        """Create in-memory event store for testing."""
        config = {
            "db_type": "sqlite",
            "db_path": ":memory:",
            **kwargs
        }
        return OrderEventStore(**config)
    
    @staticmethod
    def create_development_store(**kwargs) -> OrderEventStore:
        """Create file-based SQLite event store for development."""
        config = {
            "db_type": "sqlite",
            "db_path": "data/orders_events_dev.db",
            **kwargs
        }
        return OrderEventStore(**config)
    
    @staticmethod
    def create_production_store(**kwargs) -> OrderEventStore:
        """Create PostgreSQL event store for production."""
        
        # Check if PostgreSQL is available, fallback to SQLite
        if os.getenv("POSTGRES_HOST") or kwargs.get("connection_string"):
            config = {
                "db_type": "postgres",
                "pool_size": 20,
                **kwargs
            }
        else:
            logger.warning("PostgreSQL not configured, using SQLite for production")
            config = {
                "db_type": "sqlite",
                "db_path": "data/orders_events_prod.db",
                **kwargs
            }
        
        return OrderEventStore(**config)