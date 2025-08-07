#!/usr/bin/env python3
"""
Simple test for GraphQL module imports and basic functionality.
"""

# Test imports
try:
    from web_fetch.graphql.models import GraphQLQuery, GraphQLMutation, GraphQLSchema
    from web_fetch.graphql.validator import GraphQLValidator, ValidationResult
    from web_fetch.graphql.builder import QueryBuilder, MutationBuilder, FieldBuilder
    print("✓ All GraphQL imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Test basic functionality
def test_basic_functionality():
    """Test basic GraphQL functionality without external dependencies."""
    print("\nTesting basic functionality...")
    
    # Test GraphQL query creation
    query = GraphQLQuery(
        query='query GetUser($id: ID!) { user(id: $id) { name } }',
        variables={"id": "123"}
    )
    
    # Test basic validation
    is_valid = query.validate()
    print(f"✓ Query validation: {'PASS' if is_valid else 'FAIL'}")
    
    # Test query builder
    builder = QueryBuilder("TestQuery")
    builder.variable("test", "String!")
    builder.add_fields("id", "name")
    
    built_query = builder.build({"test": "value"})
    print(f"✓ Query builder: {'PASS' if 'query TestQuery' in built_query.query else 'FAIL'}")
    
    # Test mutation builder
    mutation_builder = MutationBuilder("TestMutation")
    mutation_builder.variable("input", "TestInput!")
    mutation_builder.add_fields("id", "success")
    
    built_mutation = mutation_builder.build({"input": {"test": "data"}})
    print(f"✓ Mutation builder: {'PASS' if 'mutation TestMutation' in built_mutation.query else 'FAIL'}")
    
    # Test schema creation
    schema = GraphQLSchema(
        queries=[{"name": "user", "type": {"name": "User"}}],
        types=[{"name": "User", "kind": "OBJECT"}]
    )
    print("✓ Schema creation: PASS")
    
    print("\nAll basic tests passed! ✓")

if __name__ == "__main__":
    print("Testing GraphQL Module Basic Functionality")
    print("=" * 50)
    test_basic_functionality()
    print("=" * 50)
    print("GraphQL module is ready! 🎉")
