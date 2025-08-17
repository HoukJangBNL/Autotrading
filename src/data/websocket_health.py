"""
WebSocket health monitoring and alerting system.

This module provides comprehensive health monitoring for WebSocket connections
with configurable alerts and automatic issue detection.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics

from ..utils.logger import get_logger
from ..config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: float
    threshold_warning: float
    threshold_critical: float
    unit: str = ""
    
    @property
    def status(self) -> HealthStatus:
        """Get status based on thresholds."""
        if self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.HEALTHY


@dataclass
class HealthAlert:
    """Health alert information."""
    timestamp: datetime
    severity: AlertSeverity
    metric_name: str
    message: str
    value: Any
    threshold: Any
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class ConnectionHealthStats:
    """Comprehensive connection health statistics."""
    status: HealthStatus
    uptime_seconds: float
    message_rate_per_second: float
    error_rate: float
    reconnect_count: int
    last_heartbeat_age_seconds: float
    latency_ms: float
    subscription_count: int
    duplicate_rate: float
    memory_usage_mb: float
    alerts: List[HealthAlert] = field(default_factory=list)


class WebSocketHealthMonitor:
    """
    Comprehensive health monitoring for WebSocket connections.
    
    Features:
    - Real-time health metrics tracking
    - Configurable thresholds and alerts
    - Historical metric tracking
    - Automatic issue detection
    - Alert callbacks for integration
    """
    
    def __init__(
        self,
        connection_id: str,
        check_interval: int = 10,  # seconds
        history_size: int = 100,
        alert_callback: Optional[Callable[[HealthAlert], None]] = None
    ):
        """
        Initialize health monitor.
        
        Args:
            connection_id: Connection identifier
            check_interval: Seconds between health checks
            history_size: Number of historical data points to keep
            alert_callback: Optional callback for alerts
        """
        self.connection_id = connection_id
        self.check_interval = check_interval
        self.history_size = history_size
        self.alert_callback = alert_callback
        
        # Metrics tracking
        self.metrics_history: Dict[str, deque] = {
            'message_rate': deque(maxlen=history_size),
            'error_rate': deque(maxlen=history_size),
            'latency': deque(maxlen=history_size),
            'heartbeat_age': deque(maxlen=history_size),
            'duplicate_rate': deque(maxlen=history_size),
            'memory_usage': deque(maxlen=history_size)
        }
        
        # Current metrics
        self.connection_start_time = datetime.now(timezone.utc)
        self.last_message_time = datetime.now(timezone.utc)
        self.last_heartbeat_time = datetime.now(timezone.utc)
        self.message_count = 0
        self.error_count = 0
        self.reconnect_count = 0
        self.duplicate_count = 0
        self.subscription_count = 0
        
        # Latency tracking
        self.latency_samples = deque(maxlen=100)
        
        # Active alerts
        self.active_alerts: Dict[str, HealthAlert] = {}
        
        # Thresholds
        self.thresholds = {
            'message_rate_min': {'warning': 0.1, 'critical': 0.01},  # msgs/sec
            'error_rate_max': {'warning': 0.05, 'critical': 0.1},  # 5%, 10%
            'latency_max_ms': {'warning': 1000, 'critical': 5000},  # milliseconds
            'heartbeat_stale_sec': {'warning': 60, 'critical': 120},  # seconds
            'reconnect_rate_hour': {'warning': 5, 'critical': 10},  # per hour
            'duplicate_rate_max': {'warning': 0.01, 'critical': 0.05},  # 1%, 5%
            'memory_usage_mb': {'warning': 500, 'critical': 1000}  # megabytes
        }
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"Health monitor initialized for connection {connection_id}")
    
    async def start(self):
        """Start health monitoring."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitoring started for {self.connection_id}")
    
    async def stop(self):
        """Stop health monitoring."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Health monitoring stopped for {self.connection_id}")
    
    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Perform health check
                health_stats = await self.check_health()
                
                # Check for issues and generate alerts
                self._check_thresholds(health_stats)
                
                # Log health status if not healthy
                if health_stats.status != HealthStatus.HEALTHY:
                    logger.warning(
                        f"Connection {self.connection_id} health: {health_stats.status} - "
                        f"Alerts: {len(health_stats.alerts)}"
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
    
    def record_message(self):
        """Record a received message."""
        self.message_count += 1
        self.last_message_time = datetime.now(timezone.utc)
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
    
    def record_heartbeat(self):
        """Record a heartbeat."""
        self.last_heartbeat_time = datetime.now(timezone.utc)
    
    def record_reconnect(self):
        """Record a reconnection."""
        self.reconnect_count += 1
    
    def record_duplicate(self):
        """Record a duplicate message."""
        self.duplicate_count += 1
    
    def record_latency(self, latency_ms: float):
        """Record message latency."""
        self.latency_samples.append(latency_ms)
    
    def update_subscription_count(self, count: int):
        """Update subscription count."""
        self.subscription_count = count
    
    def record_memory_usage(self, usage_mb: float):
        """Record memory usage."""
        self.metrics_history['memory_usage'].append(usage_mb)
    
    async def check_health(self) -> ConnectionHealthStats:
        """
        Perform comprehensive health check.
        
        Returns:
            Current health statistics
        """
        now = datetime.now(timezone.utc)
        
        # Calculate uptime
        uptime = (now - self.connection_start_time).total_seconds()
        
        # Calculate message rate
        time_window = min(60, uptime)  # Use 60 second window or total uptime
        message_rate = self.message_count / max(time_window, 1)
        self.metrics_history['message_rate'].append(message_rate)
        
        # Calculate error rate
        error_rate = self.error_count / max(self.message_count, 1)
        self.metrics_history['error_rate'].append(error_rate)
        
        # Calculate heartbeat age
        heartbeat_age = (now - self.last_heartbeat_time).total_seconds()
        self.metrics_history['heartbeat_age'].append(heartbeat_age)
        
        # Calculate average latency
        avg_latency = 0
        if self.latency_samples:
            avg_latency = statistics.mean(self.latency_samples)
        self.metrics_history['latency'].append(avg_latency)
        
        # Calculate duplicate rate
        duplicate_rate = self.duplicate_count / max(self.message_count, 1)
        self.metrics_history['duplicate_rate'].append(duplicate_rate)
        
        # Get memory usage (simplified - in production would use psutil)
        memory_usage = 100  # Placeholder
        
        # Determine overall health status
        status = self._calculate_overall_status({
            'message_rate': message_rate,
            'error_rate': error_rate,
            'heartbeat_age': heartbeat_age,
            'latency': avg_latency,
            'reconnect_count': self.reconnect_count
        })
        
        # Get active alerts
        active_alerts = list(self.active_alerts.values())
        
        return ConnectionHealthStats(
            status=status,
            uptime_seconds=uptime,
            message_rate_per_second=message_rate,
            error_rate=error_rate,
            reconnect_count=self.reconnect_count,
            last_heartbeat_age_seconds=heartbeat_age,
            latency_ms=avg_latency,
            subscription_count=self.subscription_count,
            duplicate_rate=duplicate_rate,
            memory_usage_mb=memory_usage,
            alerts=active_alerts
        )
    
    def _calculate_overall_status(self, metrics: Dict[str, float]) -> HealthStatus:
        """Calculate overall health status from metrics."""
        critical_count = 0
        unhealthy_count = 0
        
        # Check message rate
        if metrics['message_rate'] < self.thresholds['message_rate_min']['critical']:
            critical_count += 1
        elif metrics['message_rate'] < self.thresholds['message_rate_min']['warning']:
            unhealthy_count += 1
        
        # Check error rate
        if metrics['error_rate'] > self.thresholds['error_rate_max']['critical']:
            critical_count += 1
        elif metrics['error_rate'] > self.thresholds['error_rate_max']['warning']:
            unhealthy_count += 1
        
        # Check heartbeat staleness
        if metrics['heartbeat_age'] > self.thresholds['heartbeat_stale_sec']['critical']:
            critical_count += 1
        elif metrics['heartbeat_age'] > self.thresholds['heartbeat_stale_sec']['warning']:
            unhealthy_count += 1
        
        # Check latency
        if metrics['latency'] > self.thresholds['latency_max_ms']['critical']:
            critical_count += 1
        elif metrics['latency'] > self.thresholds['latency_max_ms']['warning']:
            unhealthy_count += 1
        
        # Determine status
        if critical_count > 0:
            return HealthStatus.CRITICAL
        elif unhealthy_count >= 2:
            return HealthStatus.UNHEALTHY
        elif unhealthy_count > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _check_thresholds(self, stats: ConnectionHealthStats):
        """Check thresholds and generate/resolve alerts."""
        # Check message rate
        self._check_metric(
            'message_rate_low',
            stats.message_rate_per_second,
            self.thresholds['message_rate_min']['warning'],
            self.thresholds['message_rate_min']['critical'],
            f"Message rate too low: {stats.message_rate_per_second:.2f} msgs/sec",
            reverse=True
        )
        
        # Check error rate
        self._check_metric(
            'error_rate_high',
            stats.error_rate,
            self.thresholds['error_rate_max']['warning'],
            self.thresholds['error_rate_max']['critical'],
            f"Error rate too high: {stats.error_rate:.1%}"
        )
        
        # Check heartbeat staleness
        self._check_metric(
            'heartbeat_stale',
            stats.last_heartbeat_age_seconds,
            self.thresholds['heartbeat_stale_sec']['warning'],
            self.thresholds['heartbeat_stale_sec']['critical'],
            f"Heartbeat is stale: {stats.last_heartbeat_age_seconds:.0f} seconds old"
        )
        
        # Check latency
        self._check_metric(
            'latency_high',
            stats.latency_ms,
            self.thresholds['latency_max_ms']['warning'],
            self.thresholds['latency_max_ms']['critical'],
            f"Latency too high: {stats.latency_ms:.0f}ms"
        )
        
        # Check duplicate rate
        self._check_metric(
            'duplicate_rate_high',
            stats.duplicate_rate,
            self.thresholds['duplicate_rate_max']['warning'],
            self.thresholds['duplicate_rate_max']['critical'],
            f"Duplicate rate too high: {stats.duplicate_rate:.1%}"
        )
    
    def _check_metric(
        self,
        alert_key: str,
        value: float,
        warning_threshold: float,
        critical_threshold: float,
        message: str,
        reverse: bool = False
    ):
        """Check a metric against thresholds and manage alerts."""
        # Determine if threshold is breached
        if reverse:
            # For metrics where lower is worse (like message rate)
            breached_critical = value < critical_threshold
            breached_warning = value < warning_threshold
        else:
            # For metrics where higher is worse (like error rate)
            breached_critical = value > critical_threshold
            breached_warning = value > warning_threshold
        
        if breached_critical:
            severity = AlertSeverity.CRITICAL
            threshold = critical_threshold
        elif breached_warning:
            severity = AlertSeverity.WARNING
            threshold = warning_threshold
        else:
            # Metric is healthy - resolve any existing alert
            if alert_key in self.active_alerts:
                alert = self.active_alerts[alert_key]
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                del self.active_alerts[alert_key]
                
                logger.info(f"Alert resolved: {alert_key}")
            return
        
        # Create or update alert
        if alert_key not in self.active_alerts:
            alert = HealthAlert(
                timestamp=datetime.now(timezone.utc),
                severity=severity,
                metric_name=alert_key,
                message=message,
                value=value,
                threshold=threshold
            )
            
            self.active_alerts[alert_key] = alert
            
            # Trigger callback
            if self.alert_callback:
                self.alert_callback(alert)
            
            logger.warning(f"Health alert: {alert_key} - {message}")
        else:
            # Update existing alert if severity increased
            existing_alert = self.active_alerts[alert_key]
            if severity.value > existing_alert.severity.value:
                existing_alert.severity = severity
                existing_alert.message = message
                existing_alert.value = value
                
                if self.alert_callback:
                    self.alert_callback(existing_alert)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of recent metrics."""
        summary = {}
        
        for metric_name, history in self.metrics_history.items():
            if history:
                summary[metric_name] = {
                    'current': history[-1],
                    'average': statistics.mean(history),
                    'min': min(history),
                    'max': max(history),
                    'samples': len(history)
                }
        
        return summary
    
    def get_alert_history(self, include_resolved: bool = True) -> List[HealthAlert]:
        """Get alert history."""
        alerts = list(self.active_alerts.values())
        
        if include_resolved:
            # In production, would load from persistent storage
            pass
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)