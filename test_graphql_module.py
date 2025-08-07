#!/usr/bin/env python3
"""
Test script for GraphQL module functionality.
"""

import asyncio
from web_fetch.graphql import (
    GraphQLQuery,
    GraphQLMutation,
    GraphQLValidator,
    QueryBuilder,
    MutationBuilder,
    GraphQLSchema,
    GraphQLConfig,
    GraphQLClient,
)


async def test_validator() -> None:
    """Test the GraphQL validator."""
    print("Testing GraphQL Validator...")
    
    # Create a simple schema
    schema = GraphQLSchema(
        queries=[
            {"name": "user", "type": {"name": "User"}},
            {"name": "users", "type": {"name": "[User]"}},
        ],
        mutations=[
            {"name": "createUser", "type": {"name": "User"}},
        ],
        types=[
            {
                "name": "User",
                "kind": "OBJECT",
                "fields": [
                    {"name": "id", "type": {"name": "ID"}},
                    {"name": "name", "type": {"name": "String"}},
                    {"name": "email", "type": {"name": "String"}},
                ]
            }
        ]
    )
    
    # Create validator
    validator = GraphQLValidator(schema)
    
    # Test valid query
    valid_query = GraphQLQuery(
        query='''
            query GetUser($id: ID!) {
                user(id: $id) {
                    name
                    email
                }
            }
        ''',
        variables={"id": "123"}
    )
    
    result = await validator.validate(valid_query)
    print(f"Valid query validation: {'PASS' if result.is_valid else 'FAIL'}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  Error: {error}")
    
    # Test invalid query (syntax error)
    invalid_query = GraphQLQuery(
        query='''
            query GetUser($id: ID!) {
                user(id: $id) {
                    name
                    email
                }
            }
        ''',  # Missing closing brace
        variables={"id": "123"}
    )
    
    result = await validator.validate(invalid_query)
    print(f"Invalid query validation: {'PASS' if not result.is_valid else 'FAIL'}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  Error: {error}")


def test_query_builder() -> None:
    """Test the GraphQL query builder."""
    print("\nTesting GraphQL Query Builder...")
    
    # Build a simple query first
    builder = QueryBuilder("GetUser")
    builder.variable("userId", "ID!")
    
    # Add fields using add_fields method
    builder.add_fields("id", "name", "email")
    
    query = builder.build({"userId": "123"})
    
    print("Generated Query:")
    print(query.query)
    print(f"Variables: {query.variables}")
    
    # Test that the query structure is correct
    assert "query GetUser" in query.query
    assert "$userId: ID!" in query.query
    assert query.variables["userId"] == "123"
    print("Query Builder: PASS")


def test_mutation_builder() -> None:
    """Test the GraphQL mutation builder."""
    print("\nTesting GraphQL Mutation Builder...")
    
    # Build a mutation
    builder = MutationBuilder("CreateUser")
    builder.variable("input", "CreateUserInput!")
    
    # Add the mutation field
    create_user_field = builder.field("createUser")
    create_user_field.arg("input", "$input")
    create_user_field.add_fields("id", "name", "email")
    
    mutation = builder.build({"input": {"name": "John Doe", "email": "john@example.com"}})
    
    print("Generated Mutation:")
    print(mutation.query)
    print(f"Variables: {mutation.variables}")
    
    # Test that the mutation structure is correct
    assert "mutation CreateUser" in mutation.query
    assert "$input: CreateUserInput!" in mutation.query
    assert "createUser(input: $input)" in mutation.query
    assert mutation.variables["input"]["name"] == "John Doe"
    print("Mutation Builder: PASS")


async def main() -> None:
    """Run all tests."""
    print("Testing GraphQL Module Components...")
    print("=" * 50)
    
    await test_validator()
    test_query_builder()
    test_mutation_builder()
    
    print("\n" + "=" * 50)
    print("All GraphQL module tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
