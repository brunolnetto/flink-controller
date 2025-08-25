"""
Performance optimization components for Flink Job Controller.

This module provides caching, batching, and other performance optimizations
to eliminate bottlenecks and improve throughput.
"""

import asyncio
import time
from typing import Dict, List, Optional, Set, Callable, TypeVar, Generic, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict

from .types import JobId, SpecHash


T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


@dataclass
class CacheEntry(Generic[T]):
    """Generic cache entry with expiration and access tracking."""
    value: T
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() > self.ttl_seconds
    
    def touch(self) -> None:
        """Update access tracking."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1


class PerformanceCache(Generic[K, V]):
    """High-performance LRU cache with TTL and statistics."""
    
    def __init__(
        self, 
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        cleanup_interval: float = 60.0
    ):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        
        self._cache: Dict[K, CacheEntry[V]] = {}
        self._access_order: List[K] = []
        self._lock = threading.RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup()
    
    def _start_cleanup(self) -> None:
        """Start periodic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._remove_key(key)
    
    def get(self, key: K) -> Optional[V]:
        """Get value from cache with LRU update."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired():
                self._remove_key(key)
                self._misses += 1
                return None
            
            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            entry.touch()
            self._hits += 1
            return entry.value
    
    def put(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        """Put value in cache with optional TTL."""
        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                self._remove_key(key)
            
            # Create new entry
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                ttl_seconds=ttl or self._default_ttl
            )
            
            # Add to cache
            self._cache[key] = entry
            self._access_order.append(key)
            
            # Evict if over capacity
            while len(self._cache) > self._max_size:
                self._evict_lru()
    
    def _remove_key(self, key: K) -> None:
        """Remove key from cache and access order."""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._access_order:
            lru_key = self._access_order[0]
            self._remove_key(lru_key)
            self._evictions += 1
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 3),
                "evictions": self._evictions
            }
    
    def close(self) -> None:
        """Close cache and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()


class BatchProcessor(Generic[T]):
    """High-performance batch processor for database operations."""
    
    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        max_pending: int = 1000
    ):
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_pending = max_pending
        
        self._pending: List[T] = []
        self._processors: Dict[str, Callable[[List[T]], None]] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self._batches_processed = 0
        self._items_processed = 0
        self._flush_task: Optional[asyncio.Task] = None
        
        self._start_flush_loop()
    
    def _start_flush_loop(self) -> None:
        """Start periodic flush task."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def _flush_loop(self) -> None:
        """Periodic flush of pending items."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Batch flush error: {e}")
    
    def register_processor(self, name: str, processor: Callable[[List[T]], None]) -> None:
        """Register a batch processor function."""
        self._processors[name] = processor
    
    async def add_item(self, item: T) -> None:
        """Add item to batch queue."""
        async with self._lock:
            self._pending.append(item)
            
            # Force flush if batch is full or too many pending
            if len(self._pending) >= self._batch_size or len(self._pending) >= self._max_pending:
                await self._flush_batch()
    
    async def flush(self) -> None:
        """Flush all pending items."""
        async with self._lock:
            if self._pending:
                await self._flush_batch()
    
    async def _flush_batch(self) -> None:
        """Internal batch flush implementation."""
        if not self._pending:
            return
        
        batch = self._pending.copy()
        self._pending.clear()
        
        # Process batch with all registered processors
        for name, processor in self._processors.items():
            try:
                # Run processor in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    await loop.run_in_executor(executor, processor, batch)
            except Exception as e:
                print(f"Batch processor {name} error: {e}")
        
        # Update statistics
        self._batches_processed += 1
        self._items_processed += len(batch)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get batch processing statistics."""
        return {
            "pending_items": len(self._pending),
            "batches_processed": self._batches_processed,
            "items_processed": self._items_processed,
            "registered_processors": len(self._processors)
        }
    
    async def close(self) -> None:
        """Close batch processor and flush remaining items."""
        if self._flush_task:
            self._flush_task.cancel()
        
        await self.flush()


@dataclass
class PerformanceMetrics:
    """Performance metrics tracking."""
    operation_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    operation_durations: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cache_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def record_operation(self, operation: str, duration: float, success: bool = True) -> None:
        """Record operation metrics."""
        self.operation_counts[operation] += 1
        self.operation_durations[operation].append(duration)
        
        if not success:
            self.error_counts[operation] += 1
    
    def get_average_duration(self, operation: str) -> float:
        """Get average duration for operation."""
        durations = self.operation_durations.get(operation, [])
        return sum(durations) / len(durations) if durations else 0.0
    
    def get_error_rate(self, operation: str) -> float:
        """Get error rate for operation."""
        total = self.operation_counts.get(operation, 0)
        errors = self.error_counts.get(operation, 0)
        return errors / total if total > 0 else 0.0


class PerformanceOptimizer:
    """Central performance optimization coordinator."""
    
    def __init__(self):
        # Caches for different data types
        self.job_spec_cache = PerformanceCache[JobId, dict](
            max_size=500, 
            default_ttl=300.0  # 5 minutes
        )
        
        self.job_status_cache = PerformanceCache[JobId, dict](
            max_size=1000,
            default_ttl=30.0   # 30 seconds
        )
        
        self.cluster_info_cache = PerformanceCache[str, dict](
            max_size=10,
            default_ttl=60.0   # 1 minute
        )
        
        # Batch processors
        self.spec_batch_processor = BatchProcessor[Tuple[JobId, dict]](
            batch_size=50,
            flush_interval=2.0
        )
        
        self.metrics_batch_processor = BatchProcessor[dict](
            batch_size=100,
            flush_interval=5.0
        )
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
        
        # Connection pooling
        self._connection_pools: Dict[str, List] = defaultdict(list)
        self._pool_lock = asyncio.Lock()
    
    def setup_database_batching(
        self,
        spec_saver: Callable[[List[Tuple[JobId, dict]]], None],
        metrics_recorder: Callable[[List[dict]], None]
    ) -> None:
        """Setup batch processing for database operations."""
        self.spec_batch_processor.register_processor("save_specs", spec_saver)
        self.metrics_batch_processor.register_processor("record_metrics", metrics_recorder)
    
    async def cache_job_spec(self, job_id: JobId, spec_dict: dict) -> None:
        """Cache job specification."""
        self.job_spec_cache.put(job_id, spec_dict)
    
    def get_cached_job_spec(self, job_id: JobId) -> Optional[dict]:
        """Get cached job specification."""
        return self.job_spec_cache.get(job_id)
    
    async def cache_job_status(self, job_id: JobId, status_dict: dict) -> None:
        """Cache job status."""
        self.job_status_cache.put(job_id, status_dict, ttl=30.0)
    
    def get_cached_job_status(self, job_id: JobId) -> Optional[dict]:
        """Get cached job status."""
        return self.job_status_cache.get(job_id)
    
    async def cache_cluster_info(self, cluster_id: str, info_dict: dict) -> None:
        """Cache cluster information."""
        self.cluster_info_cache.put(cluster_id, info_dict, ttl=60.0)
    
    def get_cached_cluster_info(self, cluster_id: str) -> Optional[dict]:
        """Get cached cluster information."""
        return self.cluster_info_cache.get(cluster_id)
    
    async def batch_save_spec(self, job_id: JobId, spec_dict: dict) -> None:
        """Add spec to batch save queue."""
        await self.spec_batch_processor.add_item((job_id, spec_dict))
    
    async def batch_record_metrics(self, metrics_dict: dict) -> None:
        """Add metrics to batch recording queue."""
        await self.metrics_batch_processor.add_item(metrics_dict)
    
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        return TimingContext(self.metrics, operation_name)
    
    def get_performance_summary(self) -> dict:
        """Get comprehensive performance summary."""
        return {
            "caches": {
                "job_specs": self.job_spec_cache.get_statistics(),
                "job_status": self.job_status_cache.get_statistics(),
                "cluster_info": self.cluster_info_cache.get_statistics()
            },
            "batch_processors": {
                "spec_processor": self.spec_batch_processor.get_statistics(),
                "metrics_processor": self.metrics_batch_processor.get_statistics()
            },
            "operations": {
                operation: {
                    "count": self.metrics.operation_counts[operation],
                    "avg_duration": self.metrics.get_average_duration(operation),
                    "error_rate": self.metrics.get_error_rate(operation)
                }
                for operation in self.metrics.operation_counts.keys()
            }
        }
    
    async def close(self) -> None:
        """Close all performance components."""
        self.job_spec_cache.close()
        self.job_status_cache.close()
        self.cluster_info_cache.close()
        
        await self.spec_batch_processor.close()
        await self.metrics_batch_processor.close()


class TimingContext:
    """Context manager for operation timing."""
    
    def __init__(self, metrics: PerformanceMetrics, operation_name: str):
        self.metrics = metrics
        self.operation_name = operation_name
        self.start_time = 0.0
        self.success = True
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.success = exc_type is None
        self.metrics.record_operation(self.operation_name, duration, self.success)
    
    def mark_error(self):
        """Mark operation as failed."""
        self.success = False


class ConnectionPool:
    """Generic connection pool for resource optimization."""
    
    def __init__(
        self,
        connection_factory: Callable[[], T],
        max_connections: int = 10,
        idle_timeout: float = 300.0
    ):
        self._factory = connection_factory
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout
        
        self._available: List[Tuple[T, datetime]] = []
        self._in_use: Set[T] = set()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> T:
        """Acquire connection from pool."""
        async with self._lock:
            # Try to get available connection
            now = datetime.now(timezone.utc)
            while self._available:
                conn, created_at = self._available.pop(0)
                
                # Check if connection is still valid (not timed out)
                if (now - created_at).total_seconds() < self._idle_timeout:
                    self._in_use.add(conn)
                    return conn
            
            # Create new connection if under limit
            if len(self._in_use) < self._max_connections:
                conn = self._factory()
                self._in_use.add(conn)
                return conn
            
            # Pool exhausted - this would normally wait or raise error
            raise RuntimeError("Connection pool exhausted")
    
    async def release(self, connection: T) -> None:
        """Release connection back to pool."""
        async with self._lock:
            if connection in self._in_use:
                self._in_use.remove(connection)
                self._available.append((connection, datetime.now(timezone.utc)))
    
    def get_statistics(self) -> dict:
        """Get pool statistics."""
        return {
            "available": len(self._available),
            "in_use": len(self._in_use),
            "max_connections": self._max_connections
        }