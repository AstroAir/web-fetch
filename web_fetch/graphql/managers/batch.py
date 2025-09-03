"""
Batch management for GraphQL operations.

This module provides query batching, deduplication, and batch processing
for GraphQL clients, enabling efficient batch operations and request optimization.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from pydantic import Field

from ..models import GraphQLQuery, GraphQLResult
from .base import BaseGraphQLManager, GraphQLManagerConfig

logger = logging.getLogger(__name__)


class BatchManagerConfig(GraphQLManagerConfig):
    """Configuration for GraphQL batch manager."""
    
    # Batch settings
    batch_size: int = Field(default=10, ge=1, description="Maximum queries per batch")
    batch_timeout: float = Field(default=0.1, ge=0.01, description="Batch timeout in seconds")
    enable_batching: bool = Field(default=True, description="Enable query batching")
    
    # Deduplication settings
    enable_deduplication: bool = Field(default=True, description="Enable query deduplication")
    dedup_timeout: float = Field(default=5.0, ge=0.1, description="Deduplication timeout in seconds")
    max_pending_queries: int = Field(default=100, ge=1, description="Maximum pending deduplicated queries")
    
    # Processing settings
    auto_flush_interval: float = Field(default=0.05, ge=0.01, description="Auto-flush interval in seconds")
    enable_auto_flush: bool = Field(default=True, description="Enable automatic batch flushing")
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class GraphQLBatchManager(BaseGraphQLManager):
    """
    Batch manager for GraphQL operations.
    
    Manages query batching, deduplication, and batch processing,
    providing efficient batch operations and request optimization.
    
    Features:
    - Query batching with configurable batch size
    - Query deduplication to avoid duplicate requests
    - Automatic batch flushing
    - Batch timeout handling
    - Comprehensive batch metrics
    - Configurable batch and deduplication settings
    
    Examples:
        Basic usage:
        ```python
        config = BatchManagerConfig(batch_size=5, batch_timeout=0.2)
        async with GraphQLBatchManager(config) as batch_manager:
            # Add query to batch
            future = await batch_manager.add_query(query)
            result = await future
        ```
        
        With deduplication:
        ```python
        config = BatchManagerConfig(
            enable_deduplication=True,
            dedup_timeout=10.0
        )
        batch_manager = GraphQLBatchManager(config)
        ```
    """
    
    def __init__(
        self,
        config: Optional[BatchManagerConfig] = None,
        executor_callback: Optional[Any] = None,  # Callback to execute batches
    ):
        """
        Initialize batch manager.
        
        Args:
            config: Batch manager configuration
            executor_callback: Callback function to execute batches
        """
        super().__init__(config or BatchManagerConfig())
        self.executor_callback = executor_callback
        
        # Batch state
        self._batch_queue: List[GraphQLQuery] = []
        self._batch_futures: List[asyncio.Future[GraphQLResult]] = []
        self._batch_lock = asyncio.Lock()
        
        # Deduplication state
        self._pending_queries: Dict[str, asyncio.Future[GraphQLResult]] = {}
        self._dedup_lock = asyncio.Lock()
        
        # Processing tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "total_queries": 0,
            "batched_queries": 0,
            "deduplicated_queries": 0,
            "batches_executed": 0,
            "batch_timeouts": 0,
            "dedup_hits": 0,
            "dedup_misses": 0,
        }
    
    @property
    def batch_config(self) -> BatchManagerConfig:
        """Get typed batch configuration."""
        return self.config  # type: ignore
    
    async def _initialize_impl(self) -> None:
        """Initialize batch manager."""
        # Start auto-flush task
        if self.batch_config.enable_auto_flush:
            self._flush_task = asyncio.create_task(self._auto_flush_loop())
            self._logger.debug("Batch auto-flush task started")
        
        # Start cleanup task for deduplication
        if self.batch_config.enable_deduplication:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._logger.debug("Deduplication cleanup task started")
    
    async def _close_impl(self) -> None:
        """Close batch manager and cleanup resources."""
        # Stop tasks
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Flush any remaining batches
        await self._flush_batch()
        
        # Cancel pending queries
        for future in self._pending_queries.values():
            if not future.done():
                future.cancel()
        
        self._pending_queries.clear()
        self._batch_queue.clear()
        self._batch_futures.clear()
        
        self._logger.info(
            f"Batch manager closed. Final metrics: total_queries={self._stats['total_queries']}, "
            f"batches_executed={self._stats['batches_executed']}, "
            f"deduplicated_queries={self._stats['deduplicated_queries']}"
        )
    
    async def add_query(self, query: GraphQLQuery) -> asyncio.Future[GraphQLResult]:
        """
        Add query to batch or deduplication queue.
        
        Args:
            query: GraphQL query to add
            
        Returns:
            Future that will resolve to the query result
        """
        self._ensure_initialized()
        self._stats["total_queries"] += 1
        
        # Check for deduplication first
        if self.batch_config.enable_deduplication:
            dedup_key = self._generate_dedup_key(query)
            
            async with self._dedup_lock:
                if dedup_key in self._pending_queries:
                    # Query is already pending, return existing future
                    self._stats["dedup_hits"] += 1
                    self._stats["deduplicated_queries"] += 1
                    return self._pending_queries[dedup_key]
                
                # Create new future for this query
                future: asyncio.Future[GraphQLResult] = asyncio.Future()
                self._pending_queries[dedup_key] = future
                self._stats["dedup_misses"] += 1
        else:
            # No deduplication, create simple future
            future = asyncio.Future()
        
        # Add to batch queue
        if self.batch_config.enable_batching:
            await self._add_to_batch(query, future)
        else:
            # Execute immediately if batching is disabled
            await self._execute_single_query(query, future)
        
        return future
    
    async def _add_to_batch(self, query: GraphQLQuery, future: asyncio.Future[GraphQLResult]) -> None:
        """
        Add query to batch queue.
        
        Args:
            query: GraphQL query to add
            future: Future to resolve with result
        """
        async with self._batch_lock:
            self._batch_queue.append(query)
            self._batch_futures.append(future)
            self._stats["batched_queries"] += 1
            
            # Check if batch is full
            if len(self._batch_queue) >= self.batch_config.batch_size:
                await self._flush_batch()
    
    async def _flush_batch(self) -> None:
        """Flush current batch and execute queries."""
        async with self._batch_lock:
            if not self._batch_queue:
                return
            
            # Extract current batch
            batch_queries = self._batch_queue.copy()
            batch_futures = self._batch_futures.copy()
            
            # Clear queues
            self._batch_queue.clear()
            self._batch_futures.clear()
        
        # Execute batch
        try:
            if self.executor_callback:
                results = await self.executor_callback(batch_queries)
                
                # Resolve futures with results
                for future, result in zip(batch_futures, results):
                    if not future.done():
                        future.set_result(result)
                
                self._stats["batches_executed"] += 1
                self._logger.debug(f"Executed batch of {len(batch_queries)} queries")
            else:
                # No executor callback, resolve with error
                error_result = GraphQLResult(
                    success=False,
                    data=None,
                    errors=["No batch executor configured"],
                    extensions=None
                )
                
                for future in batch_futures:
                    if not future.done():
                        future.set_result(error_result)
        
        except Exception as e:
            # Handle batch execution error
            error_result = GraphQLResult(
                success=False,
                data=None,
                errors=[f"Batch execution failed: {str(e)}"],
                extensions=None
            )
            
            for future in batch_futures:
                if not future.done():
                    future.set_result(error_result)
            
            self._logger.error(f"Batch execution failed: {e}")
        
        finally:
            # Clean up deduplication entries
            await self._cleanup_dedup_entries(batch_queries)
    
    async def _execute_single_query(
        self, 
        query: GraphQLQuery, 
        future: asyncio.Future[GraphQLResult]
    ) -> None:
        """
        Execute single query immediately.
        
        Args:
            query: GraphQL query to execute
            future: Future to resolve with result
        """
        try:
            if self.executor_callback:
                results = await self.executor_callback([query])
                result = results[0] if results else GraphQLResult(
                    success=False,
                    data=None,
                    errors=["No result from executor"],
                    extensions=None
                )
            else:
                result = GraphQLResult(
                    success=False,
                    data=None,
                    errors=["No executor configured"],
                    extensions=None
                )
            
            if not future.done():
                future.set_result(result)
        
        except Exception as e:
            error_result = GraphQLResult(
                success=False,
                data=None,
                errors=[f"Query execution failed: {str(e)}"],
                extensions=None
            )
            
            if not future.done():
                future.set_result(error_result)
        
        finally:
            # Clean up deduplication entry
            await self._cleanup_dedup_entries([query])
    
    async def _auto_flush_loop(self) -> None:
        """Background loop for automatic batch flushing."""
        while not self._closed:
            try:
                await asyncio.sleep(self.batch_config.auto_flush_interval)
                
                # Check if batch has queries and timeout has passed
                if self._batch_queue:
                    await self._flush_batch()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in auto-flush loop: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired deduplication entries."""
        while not self._closed:
            try:
                await asyncio.sleep(self.batch_config.dedup_timeout / 2)
                await self._cleanup_expired_dedup()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired_dedup(self) -> None:
        """Clean up expired deduplication entries."""
        async with self._dedup_lock:
            expired_keys = []
            
            for key, future in self._pending_queries.items():
                if future.done():
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._pending_queries[key]
            
            if expired_keys:
                self._logger.debug(f"Cleaned up {len(expired_keys)} expired dedup entries")
    
    async def _cleanup_dedup_entries(self, queries: List[GraphQLQuery]) -> None:
        """
        Clean up deduplication entries for completed queries.
        
        Args:
            queries: List of completed queries
        """
        if not self.batch_config.enable_deduplication:
            return
        
        async with self._dedup_lock:
            for query in queries:
                dedup_key = self._generate_dedup_key(query)
                self._pending_queries.pop(dedup_key, None)
    
    def _generate_dedup_key(self, query: GraphQLQuery) -> str:
        """
        Generate deduplication key for query.
        
        Args:
            query: GraphQL query
            
        Returns:
            Deduplication key
        """
        import hashlib
        import json
        
        # Create deterministic key from query components
        key_data = {
            "query": query.query.strip(),
            "variables": query.variables,
            "operation_name": query.operation_name,
        }
        
        key_string = json.dumps(key_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def flush(self) -> None:
        """Manually flush current batch."""
        self._ensure_initialized()
        await self._flush_batch()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get batch manager metrics.
        
        Returns:
            Dictionary containing batch metrics
        """
        dedup_rate = 0.0
        if self._stats["total_queries"] > 0:
            dedup_rate = self._stats["deduplicated_queries"] / self._stats["total_queries"]
        
        batch_efficiency = 0.0
        if self._stats["batches_executed"] > 0:
            batch_efficiency = self._stats["batched_queries"] / self._stats["batches_executed"]
        
        return {
            "total_queries": self._stats["total_queries"],
            "batched_queries": self._stats["batched_queries"],
            "deduplicated_queries": self._stats["deduplicated_queries"],
            "batches_executed": self._stats["batches_executed"],
            "batch_timeouts": self._stats["batch_timeouts"],
            "dedup_hits": self._stats["dedup_hits"],
            "dedup_misses": self._stats["dedup_misses"],
            "deduplication_rate": dedup_rate,
            "batch_efficiency": batch_efficiency,
            "pending_queries": len(self._pending_queries),
            "queued_queries": len(self._batch_queue),
            "active_dedup_keys": len(self._pending_queries),
        }
