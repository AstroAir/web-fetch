"""
Batch manager for coordinating batch operations.

This module provides centralized management of batch requests with
priority scheduling, resource management, and progress tracking.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from uuid import uuid4

from .models import (
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchStatus,
    BatchMetrics,
    BatchProgress,
    BatchPriority,
)
from .scheduler import BatchScheduler
from .processor import BatchProcessor
from ..exceptions import WebFetchError

logger = logging.getLogger(__name__)


class BatchManager:
    """Centralized batch operations manager."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        Initialize batch manager.
        
        Args:
            config: Batch configuration
        """
        self.config = config or BatchConfig()
        self.scheduler = BatchScheduler(self.config)
        self.processor = BatchProcessor(self.config)
        
        # State tracking
        self._batches: Dict[str, BatchRequest] = {}
        self._results: Dict[str, BatchResult] = {}
        self._progress: Dict[str, BatchProgress] = {}
        self._running_batches: Set[str] = set()
        
        # Metrics
        self._metrics = BatchMetrics()
        self._start_time = time.time()
        
        # Control
        self._shutdown = False
        self._manager_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the batch manager."""
        if self._manager_task is not None:
            return
        
        logger.info("Starting batch manager")
        self._shutdown = False
        self._manager_task = asyncio.create_task(self._manager_loop())
    
    async def stop(self) -> None:
        """Stop the batch manager."""
        if self._manager_task is None:
            return
        
        logger.info("Stopping batch manager")
        self._shutdown = True
        
        # Cancel running batches
        for batch_id in list(self._running_batches):
            await self.cancel_batch(batch_id)
        
        # Cancel manager task
        if self._manager_task:
            self._manager_task.cancel()
            try:
                await self._manager_task
            except asyncio.CancelledError:
                pass
            self._manager_task = None
    
    async def submit_batch(self, batch_request: BatchRequest) -> str:
        """
        Submit a batch request for processing.
        
        Args:
            batch_request: Batch request to submit
            
        Returns:
            Batch ID
            
        Raises:
            WebFetchError: If batch cannot be submitted
        """
        # Validate batch
        if not batch_request.requests:
            raise WebFetchError("Batch request must contain at least one request")
        
        # Check dependencies
        for dep_id in batch_request.depends_on:
            if dep_id not in self._results:
                raise WebFetchError(f"Dependency batch {dep_id} not found")
            if not self._results[dep_id].is_complete:
                raise WebFetchError(f"Dependency batch {dep_id} not complete")
        
        # Store batch
        batch_id = batch_request.id
        self._batches[batch_id] = batch_request
        
        # Create result and progress tracking
        self._results[batch_id] = BatchResult(
            id=batch_id,
            status=BatchStatus.PENDING,
            total_requests=len(batch_request.requests)
        )
        
        self._progress[batch_id] = BatchProgress(
            batch_id=batch_id,
            total_requests=len(batch_request.requests),
            completed_requests=0,
            failed_requests=0
        )
        
        # Add to scheduler
        await self.scheduler.add_batch(batch_request)
        
        # Update metrics
        self._metrics.queued_batches += 1
        
        logger.info(f"Submitted batch {batch_id} with {len(batch_request.requests)} requests")
        return batch_id
    
    async def get_batch_status(self, batch_id: str) -> Optional[BatchStatus]:
        """
        Get status of a batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            Batch status or None if not found
        """
        result = self._results.get(batch_id)
        return result.status if result else None
    
    async def get_batch_result(self, batch_id: str) -> Optional[BatchResult]:
        """
        Get result of a batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            Batch result or None if not found
        """
        return self._results.get(batch_id)
    
    async def get_batch_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """
        Get progress of a batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            Batch progress or None if not found
        """
        progress = self._progress.get(batch_id)
        if progress:
            progress.estimate_completion()
        return progress
    
    async def cancel_batch(self, batch_id: str) -> bool:
        """
        Cancel a batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            True if cancelled, False if not found or already complete
        """
        result = self._results.get(batch_id)
        if not result or result.is_complete:
            return False
        
        # Update status
        result.status = BatchStatus.CANCELLED
        result.completed_at = time.time()
        
        # Remove from running batches
        self._running_batches.discard(batch_id)
        
        # Cancel in processor
        await self.processor.cancel_batch(batch_id)
        
        logger.info(f"Cancelled batch {batch_id}")
        return True
    
    async def pause_batch(self, batch_id: str) -> bool:
        """
        Pause a batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            True if paused, False if not found or not running
        """
        result = self._results.get(batch_id)
        if not result or result.status != BatchStatus.RUNNING:
            return False
        
        result.status = BatchStatus.PAUSED
        await self.processor.pause_batch(batch_id)
        
        logger.info(f"Paused batch {batch_id}")
        return True
    
    async def resume_batch(self, batch_id: str) -> bool:
        """
        Resume a paused batch.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            True if resumed, False if not found or not paused
        """
        result = self._results.get(batch_id)
        if not result or result.status != BatchStatus.PAUSED:
            return False
        
        result.status = BatchStatus.RUNNING
        await self.processor.resume_batch(batch_id)
        
        logger.info(f"Resumed batch {batch_id}")
        return True
    
    def get_metrics(self) -> BatchMetrics:
        """
        Get current metrics.
        
        Returns:
            Current batch metrics
        """
        # Update uptime
        self._metrics.uptime_seconds = time.time() - self._start_time
        self._metrics.last_updated = time.time()
        
        # Update running batches count
        self._metrics.running_batches = len(self._running_batches)
        
        return self._metrics
    
    def list_batches(self, status: Optional[BatchStatus] = None) -> List[str]:
        """
        List batch IDs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of batch IDs
        """
        if status is None:
            return list(self._batches.keys())
        
        return [
            batch_id for batch_id, result in self._results.items()
            if result.status == status
        ]
    
    async def _manager_loop(self) -> None:
        """Main manager loop."""
        logger.info("Batch manager loop started")
        
        try:
            while not self._shutdown:
                # Process next batch from scheduler
                next_batch = await self.scheduler.get_next_batch()
                
                if next_batch and len(self._running_batches) < self.config.max_concurrent_batches:
                    await self._start_batch(next_batch)
                
                # Clean up completed batches
                await self._cleanup_completed_batches()
                
                # Update metrics
                self._update_metrics()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            logger.info("Batch manager loop cancelled")
        except Exception as e:
            logger.error(f"Error in batch manager loop: {e}")
        
        logger.info("Batch manager loop stopped")
    
    async def _start_batch(self, batch_request: BatchRequest) -> None:
        """Start processing a batch."""
        batch_id = batch_request.id
        
        # Update status
        result = self._results[batch_id]
        result.status = BatchStatus.RUNNING
        result.started_at = time.time()
        
        # Add to running batches
        self._running_batches.add(batch_id)
        
        # Update metrics
        self._metrics.queued_batches -= 1
        self._metrics.running_batches += 1
        
        # Start processing
        asyncio.create_task(self._process_batch(batch_request))
        
        logger.info(f"Started processing batch {batch_id}")
    
    async def _process_batch(self, batch_request: BatchRequest) -> None:
        """Process a batch request."""
        batch_id = batch_request.id
        
        try:
            # Process with processor
            result = await self.processor.process_batch(
                batch_request,
                progress_callback=lambda progress: self._update_progress(batch_id, progress)
            )
            
            # Update final result
            self._results[batch_id] = result
            result.completed_at = time.time()
            result.total_time = result.completed_at - (result.started_at or result.completed_at)
            
            # Call completion callback
            if batch_request.completion_callback:
                try:
                    await batch_request.completion_callback(result)
                except Exception as e:
                    logger.error(f"Error in completion callback for batch {batch_id}: {e}")
            
            logger.info(f"Completed batch {batch_id} with {result.success_rate:.1%} success rate")
        
        except Exception as e:
            # Handle batch failure
            result = self._results[batch_id]
            result.status = BatchStatus.FAILED
            result.completed_at = time.time()
            result.errors.append(str(e))
            
            # Call error callback
            if batch_request.error_callback:
                try:
                    await batch_request.error_callback(e)
                except Exception as callback_error:
                    logger.error(f"Error in error callback for batch {batch_id}: {callback_error}")
            
            logger.error(f"Failed to process batch {batch_id}: {e}")
        
        finally:
            # Remove from running batches
            self._running_batches.discard(batch_id)
    
    def _update_progress(self, batch_id: str, progress_data: dict) -> None:
        """Update progress for a batch."""
        progress = self._progress.get(batch_id)
        if progress:
            progress.completed_requests = progress_data.get('completed', 0)
            progress.failed_requests = progress_data.get('failed', 0)
            progress.current_request = progress_data.get('current_url')
            progress.estimate_completion()
    
    async def _cleanup_completed_batches(self) -> None:
        """Clean up completed batches."""
        # This could implement cleanup logic like removing old results
        # For now, we'll keep all results in memory
        pass
    
    def _update_metrics(self) -> None:
        """Update metrics."""
        # Count completed and failed batches
        completed = sum(1 for r in self._results.values() if r.status == BatchStatus.COMPLETED)
        failed = sum(1 for r in self._results.values() if r.status == BatchStatus.FAILED)
        
        self._metrics.completed_batches = completed
        self._metrics.failed_batches = failed
        
        # Calculate totals
        total_requests = sum(r.total_requests for r in self._results.values())
        successful_requests = sum(r.successful_requests for r in self._results.values())
        
        self._metrics.total_requests_processed = total_requests
        self._metrics.successful_requests = successful_requests
        self._metrics.failed_requests = total_requests - successful_requests
