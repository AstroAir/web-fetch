"""
GraphQL manager components for modular client architecture.

This module provides specialized managers that handle different aspects
of GraphQL operations, enabling better separation of concerns and maintainability.
"""

from .base import BaseGraphQLManager, GraphQLManagerConfig, ManagerFactory
from .session import GraphQLSessionManager, SessionManagerConfig
from .schema import GraphQLSchemaManager, SchemaManagerConfig
from .cache import GraphQLCacheManager, CacheManagerConfig
from .batch import GraphQLBatchManager, BatchManagerConfig
from .subscription import GraphQLSubscriptionManager, SubscriptionManagerConfig

__all__ = [
    # Base infrastructure
    "BaseGraphQLManager",
    "GraphQLManagerConfig",
    "ManagerFactory",
    # Session management
    "GraphQLSessionManager",
    "SessionManagerConfig",
    # Schema management
    "GraphQLSchemaManager",
    "SchemaManagerConfig",
    # Cache management
    "GraphQLCacheManager",
    "CacheManagerConfig",
    # Batch management
    "GraphQLBatchManager",
    "BatchManagerConfig",
    # Subscription management
    "GraphQLSubscriptionManager",
    "SubscriptionManagerConfig",
]
