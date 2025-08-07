"""
GraphQL models and data structures.

This module defines the data models and types used for GraphQL operations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl

from ..exceptions import WebFetchError


class GraphQLError(WebFetchError):
    """GraphQL-specific error."""
    pass


class GraphQLOperationType(str, Enum):
    """GraphQL operation types."""
    
    QUERY = "query"
    MUTATION = "mutation"
    SUBSCRIPTION = "subscription"


@dataclass
class GraphQLVariable:
    """GraphQL variable definition."""
    
    name: str
    type: str
    value: Any
    default_value: Optional[Any] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": self.type,
            "value": self.value,
            "defaultValue": self.default_value,
            "description": self.description
        }


@dataclass
class GraphQLQuery:
    """GraphQL query definition."""
    
    query: str
    variables: Dict[str, Any] = field(default_factory=dict)
    operation_name: Optional[str] = None
    operation_type: GraphQLOperationType = GraphQLOperationType.QUERY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "query": self.query,
            "variables": self.variables
        }
        
        if self.operation_name:
            result["operationName"] = self.operation_name
        
        return result
    
    def validate(self) -> bool:
        """Basic validation of the query."""
        if not self.query or not self.query.strip():
            return False
        
        # Check for basic GraphQL syntax
        query_lower = self.query.lower().strip()
        if self.operation_type == GraphQLOperationType.QUERY:
            return "query" in query_lower or "{" in query_lower
        elif self.operation_type == GraphQLOperationType.MUTATION:
            return "mutation" in query_lower
        else:  # SUBSCRIPTION
            return "subscription" in query_lower


@dataclass
class GraphQLMutation(GraphQLQuery):
    """GraphQL mutation definition."""
    
    operation_type: GraphQLOperationType = field(default=GraphQLOperationType.MUTATION, init=False)


@dataclass
class GraphQLSubscription(GraphQLQuery):
    """GraphQL subscription definition."""
    
    operation_type: GraphQLOperationType = field(default=GraphQLOperationType.SUBSCRIPTION, init=False)


@dataclass
class GraphQLResult:
    """Result of GraphQL operation."""
    
    success: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    extensions: Optional[Dict[str, Any]] = None
    response_time: Optional[float] = None
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    raw_response: Optional[str] = None
    
    @property
    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0
    
    @property
    def error_messages(self) -> List[str]:
        """Get list of error messages."""
        return [error.get("message", "Unknown error") for error in self.errors]
    
    def get_data(self, path: Optional[str] = None) -> Any:
        """
        Get data from result with optional path.
        
        Args:
            path: Dot-separated path to data (e.g., "user.profile.name")
            
        Returns:
            Data at the specified path or full data if no path
        """
        if not self.data:
            return None
        
        if not path:
            return self.data
        
        current = self.data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class GraphQLSchema(BaseModel):
    """GraphQL schema information."""
    
    types: List[Dict[str, Any]] = Field(default_factory=list, description="Schema types")
    queries: List[Dict[str, Any]] = Field(default_factory=list, description="Available queries")
    mutations: List[Dict[str, Any]] = Field(default_factory=list, description="Available mutations")
    subscriptions: List[Dict[str, Any]] = Field(default_factory=list, description="Available subscriptions")
    directives: List[Dict[str, Any]] = Field(default_factory=list, description="Schema directives")
    
    def get_type(self, name: str) -> Optional[Dict[str, Any]]:
        """Get type definition by name."""
        for type_def in self.types:
            if type_def.get("name") == name:
                return type_def
        return None
    
    def get_query(self, name: str) -> Optional[Dict[str, Any]]:
        """Get query definition by name."""
        for query in self.queries:
            if query.get("name") == name:
                return query
        return None
    
    def get_mutation(self, name: str) -> Optional[Dict[str, Any]]:
        """Get mutation definition by name."""
        for mutation in self.mutations:
            if mutation.get("name") == name:
                return mutation
        return None


class GraphQLConfig(BaseModel):
    """Configuration for GraphQL client."""
    
    # Endpoint settings
    endpoint: HttpUrl = Field(description="GraphQL endpoint URL")
    subscription_endpoint: Optional[HttpUrl] = Field(default=None, description="WebSocket endpoint for subscriptions")
    
    # Request settings
    timeout: float = Field(default=30.0, ge=1.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    
    # Headers
    headers: Dict[str, str] = Field(default_factory=dict, description="Default headers for requests")
    
    # Schema settings
    introspection_enabled: bool = Field(default=True, description="Enable schema introspection")
    schema_cache_ttl: int = Field(default=3600, ge=0, description="Schema cache TTL in seconds")
    
    # Validation settings
    validate_queries: bool = Field(default=True, description="Validate queries before sending")
    validate_variables: bool = Field(default=True, description="Validate variables against schema")
    
    # Error handling
    raise_on_errors: bool = Field(default=False, description="Raise exception on GraphQL errors")
    include_extensions: bool = Field(default=True, description="Include extensions in response")
    
    # Performance settings
    enable_query_batching: bool = Field(default=False, description="Enable query batching")
    max_batch_size: int = Field(default=10, ge=1, description="Maximum queries per batch")
    
    # Caching
    enable_response_caching: bool = Field(default=False, description="Enable response caching")
    cache_ttl: int = Field(default=300, ge=0, description="Response cache TTL in seconds")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
