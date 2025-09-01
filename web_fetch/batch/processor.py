"""
Batch processor for executing batch requests.

This module handles the actual execution of batch requests with
concurrency control, progress tracking, and error handling.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Callable, Dict, List, Optional, Set

from ..models import FetchConfig, FetchRequest, FetchResult
from ..core_fetcher import WebFetcher
from .models import BatchConfig, BatchRequest, BatchResult, BatchStatus

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Processor for executing batch requests."""

    def __init__(self, config: BatchConfig):
        """
        Initialize batch processor.

        Args:
            config: Batch configuration
        """
        self.config = config
        self._active_batches: Dict[str, asyncio.Task] = {}
        self._paused_batches: Set[str] = set()
        self._cancelled_batches: Set[str] = set()

    async def process_batch(
        self, batch_request: BatchRequest, progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """
        Process a batch request.

        Args:
            batch_request: Batch request to process
            progress_callback: Optional progress callback

        Returns:
            Batch result
        """
        batch_id = batch_request.id

        # Create result
        result = BatchResult(
            id=batch_id,
            status=BatchStatus.RUNNING,
            started_at=time.time(),
            total_requests=len(batch_request.requests),
        )

        try:
            # Create fetcher configuration
            fetch_config = FetchConfig(
                total_timeout=batch_request.timeout,
                max_concurrent_requests=batch_request.max_concurrent,
                max_retries=3 if batch_request.retry_failed else 0,
            )

            # Process requests with concurrency control
            async with WebFetcher(fetch_config) as fetcher:
                semaphore = asyncio.Semaphore(batch_request.max_concurrent)

                # Create tasks for all requests
                tasks = []
                for i, request in enumerate(batch_request.requests):
                    task = asyncio.create_task(
                        self._process_single_request(
                            fetcher,
                            request,
                            semaphore,
                            batch_id,
                            i,
                            progress_callback,
                            result,
                        )
                    )
                    tasks.append(task)

                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)

            # Finalize result
            result.status = BatchStatus.COMPLETED
            result.completed_at = time.time()
            result.total_time = result.completed_at - (result.started_at or 0.0)

            logger.info(
                f"Batch {batch_id} completed: {result.successful_requests}/{result.total_requests} successful"
            )

        except Exception as e:
            result.status = BatchStatus.FAILED
            result.completed_at = time.time()
            result.errors.append(str(e))
            logger.error(f"Batch {batch_id} failed: {e}")

        return result

    async def cancel_batch(self, batch_id: str) -> None:
        """
        Cancel a running batch.

        Args:
            batch_id: Batch ID to cancel
        """
        self._cancelled_batches.add(batch_id)

        if batch_id in self._active_batches:
            task = self._active_batches[batch_id]
            task.cancel()
            del self._active_batches[batch_id]

        logger.info(f"Cancelled batch {batch_id}")

    async def pause_batch(self, batch_id: str) -> None:
        """
        Pause a running batch.

        Args:
            batch_id: Batch ID to pause
        """
        self._paused_batches.add(batch_id)
        logger.info(f"Paused batch {batch_id}")

    async def resume_batch(self, batch_id: str) -> None:
        """
        Resume a paused batch.

        Args:
            batch_id: Batch ID to resume
        """
        self._paused_batches.discard(batch_id)
        logger.info(f"Resumed batch {batch_id}")

    async def _process_single_request(
        self,
        fetcher: WebFetcher,
        request: FetchRequest,
        semaphore: asyncio.Semaphore,
        batch_id: str,
        request_index: int,
        progress_callback: Optional[Callable],
        batch_result: BatchResult,
    ) -> None:
        """Process a single request within a batch."""
        async with semaphore:
            # Check for cancellation
            if batch_id in self._cancelled_batches:
                return

            # Wait while paused
            while batch_id in self._paused_batches:
                await asyncio.sleep(0.1)
                if batch_id in self._cancelled_batches:
                    return

            try:
                # Execute request
                result = await fetcher.fetch_single(request)

                # Add to batch result
                batch_result.add_result(result)

                # Call progress callback
                if progress_callback:
                    progress_data = {
                        "completed": batch_result.successful_requests
                        + batch_result.failed_requests,
                        "failed": batch_result.failed_requests,
                        "current_url": (
                            str(request.url) if hasattr(request, "url") else None
                        ),
                    }
                    progress_callback(progress_data)

                logger.debug(f"Completed request {request_index} in batch {batch_id}")

            except Exception as e:
                # Handle request error
                logger.error(
                    f"Error in request {request_index} of batch {batch_id}: {e}"
                )
                batch_result.failed_requests += 1
                batch_result.errors.append(f"Request {request_index}: {str(e)}")


class StreamingBatchProcessor(BatchProcessor):
    """Batch processor with streaming capabilities."""

    async def process_batch_streaming(
        self,
        batch_request: BatchRequest,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
    ) -> BatchResult:
        """
        Process batch with streaming results.

        Args:
            batch_request: Batch request to process
            progress_callback: Optional progress callback
            result_callback: Optional callback for individual results

        Returns:
            Batch result
        """
        batch_id = batch_request.id

        result = BatchResult(
            id=batch_id,
            status=BatchStatus.RUNNING,
            started_at=time.time(),
            total_requests=len(batch_request.requests),
        )

        try:
            fetch_config = FetchConfig(
                total_timeout=batch_request.timeout,
                max_concurrent_requests=batch_request.max_concurrent,
            )

            async with WebFetcher(fetch_config) as fetcher:
                semaphore = asyncio.Semaphore(batch_request.max_concurrent)

                # Process requests and stream results
                async for request_result in self._stream_requests(
                    fetcher, batch_request.requests, semaphore, batch_id
                ):
                    # Add to batch result
                    result.add_result(request_result)

                    # Call result callback
                    if result_callback:
                        await result_callback(request_result)

                    # Call progress callback
                    if progress_callback:
                        progress_data = {
                            "completed": result.successful_requests
                            + result.failed_requests,
                            "failed": result.failed_requests,
                            "current_url": (
                                str(request_result.url) if request_result.url else None
                            ),
                        }
                        progress_callback(progress_data)

            result.status = BatchStatus.COMPLETED
            result.completed_at = time.time()
            result.total_time = result.completed_at - (result.started_at or 0.0)

        except Exception as e:
            result.status = BatchStatus.FAILED
            result.completed_at = time.time()
            result.errors.append(str(e))

        return result

    async def _stream_requests(self, fetcher: WebFetcher, requests: List[FetchRequest], semaphore: asyncio.Semaphore, batch_id: str) -> AsyncGenerator[FetchResult, None]:
        """Stream individual request results as they complete."""
        # Create queue for results
        result_queue: asyncio.Queue = asyncio.Queue()

        # Create tasks
        async def process_request(request: FetchRequest, index: int) -> None:
            async with semaphore:
                if batch_id in self._cancelled_batches:
                    return

                try:
                    result = await fetcher.fetch_single(request)
                    await result_queue.put(result)
                except Exception as e:
                    # Create error result
                    from ..models import FetchResult

                    error_result = FetchResult(
                        url=getattr(request, "url", "unknown"),
                        status_code=0,
                        error=str(e),
                    )
                    await result_queue.put(error_result)

        # Start all tasks
        tasks = [
            asyncio.create_task(process_request(req, i))
            for i, req in enumerate(requests)
        ]

        # Yield results as they complete
        completed = 0
        while completed < len(requests):
            try:
                result = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                yield result
                completed += 1
            except asyncio.TimeoutError:
                # Check if all tasks are done
                if all(task.done() for task in tasks):
                    break

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)


class PersistentBatchProcessor(BatchProcessor):
    """Batch processor with result persistence."""

    def __init__(self, config: BatchConfig, storage_path: str = "batch_results"):
        """
        Initialize persistent batch processor.

        Args:
            config: Batch configuration
            storage_path: Path for storing results
        """
        super().__init__(config)
        self.storage_path = storage_path

    async def process_batch(
        self, batch_request: BatchRequest, progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """Process batch with result persistence."""
        result = await super().process_batch(batch_request, progress_callback)

        # Persist result if configured
        if self.config.persist_results:
            await self._persist_result(result)

        return result

    async def _persist_result(self, result: BatchResult) -> None:
        """Persist batch result to storage."""
        import json
        from pathlib import Path

        try:
            storage_dir = Path(self.storage_path)
            storage_dir.mkdir(parents=True, exist_ok=True)

            result_file = storage_dir / f"batch_{result.id}.json"

            # Convert result to dict for JSON serialization
            result_data = {
                "id": result.id,
                "status": result.status.value,
                "total_requests": result.total_requests,
                "successful_requests": result.successful_requests,
                "failed_requests": result.failed_requests,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "total_time": result.total_time,
                "success_rate": result.success_rate,
                "errors": result.errors,
                "failed_urls": result.failed_urls,
            }

            with open(result_file, "w") as f:
                json.dump(result_data, f, indent=2)

            logger.info(f"Persisted result for batch {result.id}")

        except Exception as e:
            logger.error(f"Failed to persist result for batch {result.id}: {e}")
