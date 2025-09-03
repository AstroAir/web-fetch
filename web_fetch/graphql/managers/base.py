"""
Base infrastructure for GraphQL managers.

This module provides the base classes and configuration models that all
GraphQL managers inherit from, ensuring consistent patterns and interfaces.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GraphQLManagerConfig(BaseModel):
    """Base configuration for GraphQL managers."""

    enabled: bool = Field(default=True, description="Whether this manager is enabled")
    timeout: float = Field(default=30.0, ge=1.0, description="Operation timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    class Config:
        """Pydantic configuration."""
        extra = "forbid"
        validate_assignment = True


class BaseGraphQLManager(ABC):
    """
    Abstract base class for all GraphQL managers.

    Provides common functionality and patterns used across all GraphQL managers:
    - Async context management
    - Configuration handling
    - Lifecycle management
    - Error handling patterns
    - Logging integration

    All GraphQL managers should inherit from this class to ensure consistency
    and proper resource management.
    """

    def __init__(self, config: Optional[GraphQLManagerConfig] = None):
        """
        Initialize the manager.

        Args:
            config: Manager configuration
        """
        self.config = config or GraphQLManagerConfig()
        self._initialized = False
        self._closed = False
        self._lock = asyncio.Lock()

        # Setup logging
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    @property
    def is_closed(self) -> bool:
        """Check if manager is closed."""
        return self._closed

    async def initialize(self) -> None:
        """
        Initialize the manager.

        This method should be called before using the manager.
        It's safe to call multiple times.
        """
        if self._initialized or self._closed:
            return

        async with self._lock:
            if self._initialized or self._closed:
                return

            try:
                await self._initialize_impl()
                self._initialized = True
                self._logger.debug(f"{self.__class__.__name__} initialized")
            except Exception as e:
                self._logger.error(f"Failed to initialize {self.__class__.__name__}: {e}")
                raise

    async def close(self) -> None:
        """
        Close the manager and cleanup resources.

        This method should be called when the manager is no longer needed.
        It's safe to call multiple times.
        """
        if self._closed:
            return

        async with self._lock:
            if self._closed:
                return

            try:
                await self._close_impl()
                self._closed = True
                self._logger.debug(f"{self.__class__.__name__} closed")
            except Exception as e:
                self._logger.error(f"Error closing {self.__class__.__name__}: {e}")
                # Don't re-raise to ensure cleanup continues

    async def __aenter__(self) -> BaseGraphQLManager:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    @abstractmethod
    async def _initialize_impl(self) -> None:
        """
        Implementation-specific initialization logic.

        Subclasses must implement this method to perform their
        specific initialization tasks.
        """
        pass

    @abstractmethod
    async def _close_impl(self) -> None:
        """
        Implementation-specific cleanup logic.

        Subclasses must implement this method to perform their
        specific cleanup tasks.
        """
        pass

    def _ensure_initialized(self) -> None:
        """
        Ensure the manager is initialized.

        Raises:
            RuntimeError: If manager is not initialized or is closed
        """
        if self._closed:
            raise RuntimeError(f"{self.__class__.__name__} is closed")
        if not self._initialized:
            raise RuntimeError(f"{self.__class__.__name__} is not initialized")

    def _ensure_not_closed(self) -> None:
        """
        Ensure the manager is not closed.

        Raises:
            RuntimeError: If manager is closed
        """
        if self._closed:
            raise RuntimeError(f"{self.__class__.__name__} is closed")


class ManagerFactory:
    """
    Factory for creating and managing GraphQL managers.

    Provides dependency injection, lifecycle management, and configuration
    for all GraphQL managers in a coordinated way.
    """

    def __init__(self):
        """Initialize the factory."""
        self._managers: Dict[str, BaseGraphQLManager] = {}
        self._dependencies: Dict[str, list[str]] = {}
        self._initialization_order: list[str] = []
        self._initialized = False
        self._closed = False

    def register_manager(
        self,
        name: str,
        manager: BaseGraphQLManager,
        dependencies: Optional[list[str]] = None
    ) -> None:
        """
        Register a manager with the factory.

        Args:
            name: Manager name
            manager: Manager instance
            dependencies: List of manager names this manager depends on
        """
        if self._initialized:
            raise RuntimeError("Cannot register managers after initialization")

        self._managers[name] = manager
        self._dependencies[name] = dependencies or []
        self._compute_initialization_order()

    def get_manager(self, name: str) -> Optional[BaseGraphQLManager]:
        """
        Get a manager by name.

        Args:
            name: Manager name

        Returns:
            Manager instance or None if not found
        """
        return self._managers.get(name)

    def get_typed_manager(self, name: str, manager_type: type) -> Optional[Any]:
        """
        Get a manager by name with type checking.

        Args:
            name: Manager name
            manager_type: Expected manager type

        Returns:
            Typed manager instance or None if not found or wrong type
        """
        manager = self._managers.get(name)
        if manager and isinstance(manager, manager_type):
            return manager
        return None

    def _compute_initialization_order(self) -> None:
        """Compute the correct initialization order based on dependencies."""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        order = []

        def visit(name: str) -> None:
            if name in temp_visited:
                raise RuntimeError(f"Circular dependency detected involving {name}")
            if name in visited:
                return

            temp_visited.add(name)
            for dep in self._dependencies.get(name, []):
                if dep not in self._managers:
                    raise RuntimeError(f"Dependency {dep} not found for manager {name}")
                visit(dep)

            temp_visited.remove(name)
            visited.add(name)
            order.append(name)

        for name in self._managers:
            if name not in visited:
                visit(name)

        self._initialization_order = order

    async def initialize_all(self) -> None:
        """Initialize all registered managers in dependency order."""
        if self._initialized:
            return

        try:
            for name in self._initialization_order:
                manager = self._managers[name]
                await manager.initialize()

            self._initialized = True
            logger.debug(f"Initialized {len(self._managers)} managers")

        except Exception as e:
            logger.error(f"Failed to initialize managers: {e}")
            # Cleanup any partially initialized managers
            await self._cleanup_partial_initialization()
            raise

    async def close_all(self) -> None:
        """Close all registered managers in reverse dependency order."""
        if self._closed:
            return

        # Close in reverse order
        for name in reversed(self._initialization_order):
            manager = self._managers[name]
            try:
                await manager.close()
            except Exception as e:
                logger.error(f"Error closing manager {name}: {e}")
                # Continue closing other managers

        self._closed = True
        logger.debug(f"Closed {len(self._managers)} managers")

    async def _cleanup_partial_initialization(self) -> None:
        """Cleanup managers that were partially initialized."""
        for name in self._initialization_order:
            manager = self._managers[name]
            if manager.is_initialized:
                try:
                    await manager.close()
                except Exception as e:
                    logger.error(f"Error during cleanup of manager {name}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all managers.

        Returns:
            Dictionary with manager status information
        """
        return {
            "factory_initialized": self._initialized,
            "factory_closed": self._closed,
            "manager_count": len(self._managers),
            "initialization_order": self._initialization_order,
            "managers": {
                name: {
                    "initialized": manager.is_initialized,
                    "closed": manager.is_closed,
                    "type": manager.__class__.__name__,
                }
                for name, manager in self._managers.items()
            }
        }

    async def __aenter__(self) -> ManagerFactory:
        """Async context manager entry."""
        await self.initialize_all()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close_all()
