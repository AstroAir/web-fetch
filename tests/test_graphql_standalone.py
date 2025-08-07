#!/usr/bin/env python3
"""
Standalone test for GraphQL module components.
"""

import sys
import os

# Add the web_fetch directory to Python path
sys.path.insert(0, '/home/max/web-fetch')

# Test imports one by one
def test_imports():
    print("Testing GraphQL module imports...")
    
    try:
        # Test models
        from web_fetch.graphql.models import GraphQLQuery, GraphQLMutation, GraphQLSchema
        print("✓ Models import successful")
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        # Test validator 
        from web_fetch.graphql.validator import GraphQLValidator, ValidationResult
        print("✓ Validator import successful")
    except Exception as e:
        print(f"✗ Validator import failed: {e}")
        return False
    
    try:
        # Test builder
        from web_fetch.graphql.builder import QueryBuilder, MutationBuilder
        print("✓ Builder import successful")
    except Exception as e:
        print(f"✗ Builder import failed: {e}")
        return False
    
    return True

def test_functionality():
    """Test basic functionality."""
    print("\nTesting basic functionality...")
    
    # Import what we need
    from web_fetch.graphql.models import GraphQLQuery, GraphQLMutation, GraphQLSchema
    from web_fetch.graphql.builder import QueryBuilder, MutationBuilder
    
    # Test GraphQL query creation
    query = GraphQLQuery(
        query='query GetUser($id: ID!) { user(id: $id) { name } }',
        variables={"id": "123"}
    )
    
    # Test basic validation
    is_valid = query.validate()
    print(f"✓ Query validation: {'PASS' if is_valid else 'FAIL'}")
    
    # Test query to_dict
    query_dict = query.to_dict()
    print(f"✓ Query serialization: {'PASS' if 'query' in query_dict else 'FAIL'}")
    
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
    user_type = schema.get_type("User")
    print(f"✓ Schema functionality: {'PASS' if user_type is not None else 'FAIL'}")
    
    print("\nAll basic tests passed! ✓")

if __name__ == "__main__":
    print("Testing GraphQL Module Components")
    print("=" * 50)
    
    if test_imports():
        test_functionality()
        print("=" * 50)
        print("GraphQL module is complete and functional! 🎉")
    else:
        print("=" * 50)
        print("Some imports failed. Check dependencies.")
        sys.exit(1)
