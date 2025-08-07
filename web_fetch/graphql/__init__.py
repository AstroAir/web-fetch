"""
GraphQL support for web_fetch.

This module provides specialized GraphQL query support with schema validation,
response parsing, and advanced GraphQL features.
"""

from .builder import MutationBuilder, QueryBuilder, SubscriptionBuilder
from .client import GraphQLClient, GraphQLConfig
from .models import (
    GraphQLError,
    GraphQLMutation,
    GraphQLQuery,
    GraphQLResult,
    GraphQLSchema,
    GraphQLSubscription,
    GraphQLVariable,
)
from .validator import GraphQLValidator

__all__ = [
    # Client
    "GraphQLClient",
    "GraphQLConfig",
    # Models
    "GraphQLQuery",
    "GraphQLMutation",
    "GraphQLSubscription",
    "GraphQLVariable",
    "GraphQLResult",
    "GraphQLError",
    "GraphQLSchema",
    # Builders
    "QueryBuilder",
    "MutationBuilder",
    "SubscriptionBuilder",
    # Validator
    "GraphQLValidator",
]
