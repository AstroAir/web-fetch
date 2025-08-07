"""
Comprehensive tests for the GraphQL module.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.graphql import (
    GraphQLClient,
    GraphQLConfig,
    GraphQLQuery,
    GraphQLMutation,
    GraphQLSubscription,
    GraphQLVariable,
    GraphQLResult,
    GraphQLError,
    GraphQLSchema,
    QueryBuilder,
    MutationBuilder,
    SubscriptionBuilder,
    GraphQLValidator,
)


class TestGraphQLModels:
    """Test GraphQL model classes."""

    def test_graphql_variable_creation(self):
        """Test GraphQL variable creation."""
        variable = GraphQLVariable(
            name="userId",
            type="ID!",
            value="123"
        )
        
        assert variable.name == "userId"
        assert variable.type == "ID!"
        assert variable.value == "123"

    def test_graphql_query_creation(self):
        """Test GraphQL query creation."""
        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { name email } }",
            variables={"id": "123"},
            operation_name="GetUser"
        )
        
        assert query.query.startswith("query GetUser")
        assert query.variables["id"] == "123"
        assert query.operation_name == "GetUser"

    def test_graphql_mutation_creation(self):
        """Test GraphQL mutation creation."""
        mutation = GraphQLMutation(
            query="mutation CreateUser($input: UserInput!) { createUser(input: $input) { id name } }",
            variables={"input": {"name": "John", "email": "john@example.com"}},
            operation_name="CreateUser"
        )
        
        assert mutation.query.startswith("mutation CreateUser")
        assert mutation.variables["input"]["name"] == "John"
        assert mutation.operation_name == "CreateUser"

    def test_graphql_subscription_creation(self):
        """Test GraphQL subscription creation."""
        subscription = GraphQLSubscription(
            query="subscription OnCommentAdded($postId: ID!) { commentAdded(postId: $postId) { id content author } }",
            variables={"postId": "post123"},
            operation_name="OnCommentAdded"
        )
        
        assert subscription.query.startswith("subscription OnCommentAdded")
        assert subscription.variables["postId"] == "post123"
        assert subscription.operation_name == "OnCommentAdded"

    def test_graphql_result_success(self):
        """Test successful GraphQL result."""
        result = GraphQLResult(
            data={"user": {"id": "123", "name": "John"}},
            errors=None,
            extensions={"tracing": {"version": 1}}
        )
        
        assert result.data["user"]["name"] == "John"
        assert result.errors is None
        assert result.extensions["tracing"]["version"] == 1
        assert result.is_success is True

    def test_graphql_result_with_errors(self):
        """Test GraphQL result with errors."""
        errors = [
            GraphQLError(
                message="User not found",
                locations=[{"line": 2, "column": 3}],
                path=["user"]
            )
        ]
        
        result = GraphQLResult(
            data=None,
            errors=errors
        )
        
        assert result.data is None
        assert len(result.errors) == 1
        assert result.errors[0].message == "User not found"
        assert result.is_success is False

    def test_graphql_schema_creation(self):
        """Test GraphQL schema creation."""
        schema_sdl = """
        type User {
            id: ID!
            name: String!
            email: String!
        }
        
        type Query {
            user(id: ID!): User
            users: [User!]!
        }
        """
        
        schema = GraphQLSchema(
            sdl=schema_sdl,
            types=["User", "Query"],
            queries=["user", "users"]
        )
        
        assert "type User" in schema.sdl
        assert "User" in schema.types
        assert "user" in schema.queries


class TestQueryBuilder:
    """Test GraphQL query builder."""

    def test_simple_query_building(self):
        """Test building simple query."""
        builder = QueryBuilder()
        
        query = (builder
                .query("GetUser")
                .field("user", {"id": "$userId"})
                .field("id")
                .field("name")
                .field("email")
                .variable("userId", "ID!", "123")
                .build())
        
        assert isinstance(query, GraphQLQuery)
        assert "query GetUser" in query.query
        assert "user(id: $userId)" in query.query
        assert query.variables["userId"] == "123"

    def test_nested_query_building(self):
        """Test building nested query."""
        builder = QueryBuilder()
        
        query = (builder
                .query("GetUserWithPosts")
                .field("user", {"id": "$userId"})
                .field("id")
                .field("name")
                .nested_field("posts")
                .field("id")
                .field("title")
                .field("content")
                .end_nested()
                .variable("userId", "ID!", "123")
                .build())
        
        assert "posts {" in query.query
        assert "title" in query.query
        assert "content" in query.query

    def test_query_with_fragments(self):
        """Test building query with fragments."""
        builder = QueryBuilder()
        
        fragment = "fragment UserInfo on User { id name email }"
        
        query = (builder
                .query("GetUsers")
                .fragment(fragment)
                .field("users")
                .spread("UserInfo")
                .build())
        
        assert "fragment UserInfo" in query.query
        assert "...UserInfo" in query.query

    def test_query_with_aliases(self):
        """Test building query with field aliases."""
        builder = QueryBuilder()
        
        query = (builder
                .query("GetUserData")
                .alias("currentUser", "user", {"id": "$userId"})
                .field("id")
                .field("name")
                .variable("userId", "ID!", "123")
                .build())
        
        assert "currentUser: user(id: $userId)" in query.query

    def test_query_with_directives(self):
        """Test building query with directives."""
        builder = QueryBuilder()
        
        query = (builder
                .query("GetUserConditional")
                .field("user", {"id": "$userId"})
                .field("id")
                .field("name")
                .field("email", directives=["@include(if: $includeEmail)"])
                .variable("userId", "ID!", "123")
                .variable("includeEmail", "Boolean!", True)
                .build())
        
        assert "@include(if: $includeEmail)" in query.query
        assert query.variables["includeEmail"] is True


class TestMutationBuilder:
    """Test GraphQL mutation builder."""

    def test_simple_mutation_building(self):
        """Test building simple mutation."""
        builder = MutationBuilder()
        
        mutation = (builder
                   .mutation("CreateUser")
                   .field("createUser", {"input": "$userInput"})
                   .field("id")
                   .field("name")
                   .field("email")
                   .variable("userInput", "UserInput!", {
                       "name": "John",
                       "email": "john@example.com"
                   })
                   .build())
        
        assert isinstance(mutation, GraphQLMutation)
        assert "mutation CreateUser" in mutation.query
        assert "createUser(input: $userInput)" in mutation.query
        assert mutation.variables["userInput"]["name"] == "John"

    def test_mutation_with_multiple_operations(self):
        """Test building mutation with multiple operations."""
        builder = MutationBuilder()
        
        mutation = (builder
                   .mutation("UpdateUserAndPost")
                   .field("updateUser", {"id": "$userId", "input": "$userInput"})
                   .field("id")
                   .field("name")
                   .field("updatePost", {"id": "$postId", "input": "$postInput"})
                   .field("id")
                   .field("title")
                   .variable("userId", "ID!", "123")
                   .variable("userInput", "UserInput!", {"name": "Updated Name"})
                   .variable("postId", "ID!", "456")
                   .variable("postInput", "PostInput!", {"title": "Updated Title"})
                   .build())
        
        assert "updateUser" in mutation.query
        assert "updatePost" in mutation.query
        assert len(mutation.variables) == 4


class TestSubscriptionBuilder:
    """Test GraphQL subscription builder."""

    def test_simple_subscription_building(self):
        """Test building simple subscription."""
        builder = SubscriptionBuilder()
        
        subscription = (builder
                       .subscription("OnCommentAdded")
                       .field("commentAdded", {"postId": "$postId"})
                       .field("id")
                       .field("content")
                       .field("author")
                       .field("name")
                       .variable("postId", "ID!", "post123")
                       .build())
        
        assert isinstance(subscription, GraphQLSubscription)
        assert "subscription OnCommentAdded" in subscription.query
        assert "commentAdded(postId: $postId)" in subscription.query
        assert subscription.variables["postId"] == "post123"

    def test_subscription_with_filters(self):
        """Test building subscription with filters."""
        builder = SubscriptionBuilder()
        
        subscription = (builder
                       .subscription("OnUserStatusChanged")
                       .field("userStatusChanged", {
                           "userId": "$userId",
                           "statuses": "$allowedStatuses"
                       })
                       .field("id")
                       .field("status")
                       .field("timestamp")
                       .variable("userId", "ID!", "user123")
                       .variable("allowedStatuses", "[UserStatus!]!", ["ONLINE", "OFFLINE"])
                       .build())
        
        assert "userStatusChanged" in subscription.query
        assert subscription.variables["allowedStatuses"] == ["ONLINE", "OFFLINE"]


class TestGraphQLValidator:
    """Test GraphQL validator."""

    def test_validate_simple_query(self):
        """Test validating simple query."""
        validator = GraphQLValidator()
        
        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { name email } }",
            variables={"id": "123"}
        )
        
        result = validator.validate_query(query)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_query_syntax_error(self):
        """Test validating query with syntax error."""
        validator = GraphQLValidator()
        
        # Missing closing brace
        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { name email }",
            variables={"id": "123"}
        )
        
        result = validator.validate_query(query)
        
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_query_missing_variables(self):
        """Test validating query with missing variables."""
        validator = GraphQLValidator()
        
        query = GraphQLQuery(
            query="query GetUser($id: ID!, $includeEmail: Boolean!) { user(id: $id) { name email @include(if: $includeEmail) } }",
            variables={"id": "123"}  # Missing includeEmail variable
        )
        
        result = validator.validate_query(query)
        
        assert result.is_valid is False
        assert any("includeEmail" in error for error in result.errors)

    def test_validate_mutation(self):
        """Test validating mutation."""
        validator = GraphQLValidator()
        
        mutation = GraphQLMutation(
            query="mutation CreateUser($input: UserInput!) { createUser(input: $input) { id name } }",
            variables={"input": {"name": "John", "email": "john@example.com"}}
        )
        
        result = validator.validate_mutation(mutation)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_subscription(self):
        """Test validating subscription."""
        validator = GraphQLValidator()
        
        subscription = GraphQLSubscription(
            query="subscription OnCommentAdded($postId: ID!) { commentAdded(postId: $postId) { id content } }",
            variables={"postId": "post123"}
        )
        
        result = validator.validate_subscription(subscription)
        
        assert result.is_valid is True
        assert len(result.errors) == 0


class TestGraphQLClient:
    """Test GraphQL client."""

    def test_client_creation(self):
        """Test GraphQL client creation."""
        config = GraphQLConfig(
            endpoint="https://api.example.com/graphql",
            headers={"Authorization": "Bearer token123"}
        )
        
        client = GraphQLClient(config)
        
        assert client.config == config
        assert client.config.endpoint == "https://api.example.com/graphql"

    @pytest.mark.asyncio
    async def test_client_execute_query(self):
        """Test executing GraphQL query."""
        config = GraphQLConfig(endpoint="https://api.example.com/graphql")
        client = GraphQLClient(config)
        
        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { id name email } }",
            variables={"id": "123"}
        )
        
        mock_response_data = {
            "data": {
                "user": {
                    "id": "123",
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await client.execute_query(query)
            
            assert isinstance(result, GraphQLResult)
            assert result.is_success is True
            assert result.data["user"]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_client_execute_mutation(self):
        """Test executing GraphQL mutation."""
        config = GraphQLConfig(endpoint="https://api.example.com/graphql")
        client = GraphQLClient(config)
        
        mutation = GraphQLMutation(
            query="mutation CreateUser($input: UserInput!) { createUser(input: $input) { id name } }",
            variables={"input": {"name": "Jane", "email": "jane@example.com"}}
        )
        
        mock_response_data = {
            "data": {
                "createUser": {
                    "id": "456",
                    "name": "Jane"
                }
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await client.execute_mutation(mutation)
            
            assert result.is_success is True
            assert result.data["createUser"]["id"] == "456"

    @pytest.mark.asyncio
    async def test_client_execute_with_errors(self):
        """Test executing GraphQL operation with errors."""
        config = GraphQLConfig(endpoint="https://api.example.com/graphql")
        client = GraphQLClient(config)
        
        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { id name } }",
            variables={"id": "nonexistent"}
        )
        
        mock_response_data = {
            "data": None,
            "errors": [
                {
                    "message": "User not found",
                    "locations": [{"line": 1, "column": 25}],
                    "path": ["user"]
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await client.execute_query(query)
            
            assert result.is_success is False
            assert len(result.errors) == 1
            assert result.errors[0].message == "User not found"

    @pytest.mark.asyncio
    async def test_client_with_authentication(self):
        """Test GraphQL client with authentication."""
        config = GraphQLConfig(
            endpoint="https://api.example.com/graphql",
            headers={"Authorization": "Bearer secret-token"}
        )
        
        client = GraphQLClient(config)
        
        query = GraphQLQuery(
            query="query GetCurrentUser { me { id name } }"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"data": {"me": {"id": "current", "name": "Current User"}}}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            await client.execute_query(query)
            
            # Verify that authorization header was sent
            call_args = mock_post.call_args
            headers = call_args[1]['headers']
            assert headers['Authorization'] == 'Bearer secret-token'
