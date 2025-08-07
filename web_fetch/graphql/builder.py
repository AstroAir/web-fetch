"""
GraphQL query builders.

This module provides fluent interfaces for building GraphQL queries, mutations,
and subscriptions programmatically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .models import (
    GraphQLMutation,
    GraphQLOperationType,
    GraphQLQuery,
    GraphQLSubscription,
    GraphQLVariable,
)


class FieldBuilder:
    """Builder for GraphQL fields."""

    def __init__(
        self,
        name: str,
        parent: Optional[
            Union["QueryBuilder", "FieldBuilder", "FragmentBuilder"]
        ] = None,
    ):
        """
        Initialize field builder.

        Args:
            name: Field name
            parent: Parent builder (QueryBuilder, FieldBuilder, or FragmentBuilder)
        """
        self.name = name
        self.parent = parent
        self.arguments: Dict[str, Any] = {}
        self.alias: Optional[str] = None
        self.sub_fields: List[FieldBuilder] = []
        self.directives: List[Dict[str, Any]] = []

    def arg(self, name: str, value: Any) -> FieldBuilder:
        """
        Add argument to field.

        Args:
            name: Argument name
            value: Argument value

        Returns:
            Self for chaining
        """
        self.arguments[name] = value
        return self

    def args(self, **kwargs: Any) -> FieldBuilder:
        """
        Add multiple arguments to field.

        Args:
            **kwargs: Arguments as keyword arguments

        Returns:
            Self for chaining
        """
        self.arguments.update(kwargs)
        return self

    def as_alias(self, alias: str) -> FieldBuilder:
        """
        Set field alias.

        Args:
            alias: Field alias

        Returns:
            Self for chaining
        """
        self.alias = alias
        return self

    def field(self, name: str) -> FieldBuilder:
        """
        Add sub-field.

        Args:
            name: Sub-field name

        Returns:
            FieldBuilder for the sub-field
        """
        sub_field = FieldBuilder(name, parent=self)
        self.sub_fields.append(sub_field)
        return sub_field

    def add_fields(self, *names: str) -> FieldBuilder:
        """
        Add multiple simple sub-fields.

        Args:
            *names: Field names

        Returns:
            Self for chaining
        """
        for name in names:
            self.sub_fields.append(FieldBuilder(name, parent=self))
        return self

    def end(self) -> Union["QueryBuilder", "FieldBuilder", "FragmentBuilder"]:
        """
        Return to parent builder.

        Returns:
            Parent builder (QueryBuilder, FieldBuilder, or FragmentBuilder)
        """
        if self.parent is None:
            raise ValueError("Cannot call end() on root field builder")
        return self.parent

    def directive(self, name: str, **args: Any) -> FieldBuilder:
        """
        Add directive to field.

        Args:
            name: Directive name
            **args: Directive arguments

        Returns:
            Self for chaining
        """
        self.directives.append({"name": name, "args": args})
        return self

    def to_string(self, indent: int = 0) -> str:
        """
        Convert field to GraphQL string.

        Args:
            indent: Indentation level

        Returns:
            GraphQL field string
        """
        spaces = "  " * indent
        result = spaces

        # Add alias if present
        if self.alias:
            result += f"{self.alias}: "

        # Add field name
        result += self.name

        # Add arguments if present
        if self.arguments:
            args_str = ", ".join(
                [
                    f"{key}: {self._format_value(value)}"
                    for key, value in self.arguments.items()
                ]
            )
            result += f"({args_str})"

        # Add directives if present
        for directive in self.directives:
            result += f" @{directive['name']}"
            if directive["args"]:
                args_str = ", ".join(
                    [
                        f"{key}: {self._format_value(value)}"
                        for key, value in directive["args"].items()
                    ]
                )
                result += f"({args_str})"

        # Add sub-fields if present
        if self.sub_fields:
            result += " {\n"
            for sub_field in self.sub_fields:
                result += sub_field.to_string(indent + 1) + "\n"
            result += spaces + "}"

        return result

    def _format_value(self, value: Any) -> str:
        """Format value for GraphQL."""
        if isinstance(value, str):
            # Check if it's a variable reference
            if value.startswith("$"):
                return value
            # Otherwise, quote it
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            items = [self._format_value(item) for item in value]
            return f"[{', '.join(items)}]"
        elif isinstance(value, dict):
            items = [f"{key}: {self._format_value(val)}" for key, val in value.items()]
            return f"{{{', '.join(items)}}}"
        elif value is None:
            return "null"
        else:
            return str(value)


class QueryBuilder:
    """
    Fluent interface for building GraphQL queries.

    The QueryBuilder provides a programmatic way to construct GraphQL queries
    with proper syntax and structure validation.

    Examples:
        Simple query:
        ```python
        query = (QueryBuilder()
            .field("user")
                .arg("id", "$userId")
                .field("name")
                .field("email")
                .field("profile")
                    .field("avatar")
                    .field("bio")
            .build()
        )
        ```

        Query with variables:
        ```python
        query = (QueryBuilder("GetUserProfile")
            .variable("userId", "ID!")
            .variable("includeProfile", "Boolean", False)
            .field("user")
                .arg("id", "$userId")
                .add_fields("name", "email")
                .field("profile")
                    .directive("include", if_="$includeProfile")
                    .add_fields("avatar", "bio")
            .build()
        )
        ```

        Complex query with fragments:
        ```python
        query = (QueryBuilder()
            .fragment("UserInfo", "User")
                .add_fields("id", "name", "email")
            .field("viewer")
                .fragment_spread("UserInfo")
            .field("users")
                .arg("first", 10)
                .fragment_spread("UserInfo")
            .build()
        )
        ```
    """

    def __init__(self, operation_name: Optional[str] = None):
        """
        Initialize query builder.

        Args:
            operation_name: Optional operation name
        """
        self.operation_name = operation_name
        self.variables: List[GraphQLVariable] = []
        self.fields: List[FieldBuilder] = []
        self.fragments: List[Dict[str, Any]] = []
        self.directives: List[Dict[str, Any]] = []

    def variable(
        self,
        name: str,
        type_: str,
        default_value: Optional[Any] = None,
        description: Optional[str] = None,
    ) -> QueryBuilder:
        """
        Add variable to query.

        Args:
            name: Variable name (without $)
            type_: GraphQL type (e.g., "String!", "Int", "[ID!]!")
            default_value: Default value
            description: Variable description

        Returns:
            Self for chaining
        """
        self.variables.append(
            GraphQLVariable(
                name=name,
                type=type_,
                value=default_value,  # This will be set at execution time
                default_value=default_value,
                description=description,
            )
        )
        return self

    def field(self, name: str) -> FieldBuilder:
        """
        Add field to query.

        Args:
            name: Field name

        Returns:
            FieldBuilder for the field
        """
        field_builder = FieldBuilder(name, parent=self)
        self.fields.append(field_builder)
        return field_builder

    def add_fields(self, *names: str) -> QueryBuilder:
        """
        Add multiple simple fields to query.

        Args:
            *names: Field names

        Returns:
            Self for chaining
        """
        for name in names:
            self.fields.append(FieldBuilder(name, parent=self))
        return self

    def fragment(self, name: str, on_type: str) -> FragmentBuilder:
        """
        Define a fragment.

        Args:
            name: Fragment name
            on_type: Type the fragment applies to

        Returns:
            FragmentBuilder for the fragment
        """
        fragment_builder = FragmentBuilder(name, on_type, self)
        return fragment_builder

    def fragment_spread(self, name: str) -> QueryBuilder:
        """
        Add fragment spread to query.

        Args:
            name: Fragment name

        Returns:
            Self for chaining
        """
        # Add as a special field that represents fragment spread
        field_builder = FieldBuilder(f"...{name}")
        self.fields.append(field_builder)
        return self

    def directive(self, name: str, **args: Any) -> QueryBuilder:
        """
        Add directive to query.

        Args:
            name: Directive name
            **args: Directive arguments

        Returns:
            Self for chaining
        """
        self.directives.append({"name": name, "args": args})
        return self

    def build(self, variables: Optional[Dict[str, Any]] = None) -> GraphQLQuery:
        """
        Build the GraphQL query.

        Args:
            variables: Variable values

        Returns:
            GraphQLQuery object
        """
        query_string = self._build_query_string()

        # Merge provided variables with defaults
        final_variables = {}
        for var in self.variables:
            if variables and var.name in variables:
                final_variables[var.name] = variables[var.name]
            elif var.default_value is not None:
                final_variables[var.name] = var.default_value

        return GraphQLQuery(
            query=query_string,
            variables=final_variables,
            operation_name=self.operation_name,
            operation_type=GraphQLOperationType.QUERY,
        )

    def _build_query_string(self) -> str:
        """Build the query string."""
        lines = []

        # Add operation definition
        operation_line = "query"
        if self.operation_name:
            operation_line += f" {self.operation_name}"

        # Add variables
        if self.variables:
            var_defs = []
            for var in self.variables:
                var_def = f"${var.name}: {var.type}"
                if var.default_value is not None:
                    var_def += f" = {self._format_default_value(var.default_value)}"
                var_defs.append(var_def)
            operation_line += f"({', '.join(var_defs)})"

        # Add directives
        for directive in self.directives:
            operation_line += f" @{directive['name']}"
            if directive["args"]:
                args_str = ", ".join(
                    [
                        f"{key}: {self._format_default_value(value)}"
                        for key, value in directive["args"].items()
                    ]
                )
                operation_line += f"({args_str})"

        operation_line += " {"
        lines.append(operation_line)

        # Add fields
        for field in self.fields:
            lines.append(field.to_string(1))

        lines.append("}")

        # Add fragments
        for fragment in self.fragments:
            lines.append("")
            lines.append(f"fragment {fragment['name']} on {fragment['on_type']} {{")
            for field in fragment["fields"]:
                lines.append(field.to_string(1))
            lines.append("}")

        return "\n".join(lines)

    def _format_default_value(self, value: Any) -> str:
        """Format default value for GraphQL."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return "null"
        else:
            return str(value)


class FragmentBuilder:
    """Builder for GraphQL fragments."""

    def __init__(self, name: str, on_type: str, parent: QueryBuilder):
        """
        Initialize fragment builder.

        Args:
            name: Fragment name
            on_type: Type the fragment applies to
            parent: Parent query builder
        """
        self.name = name
        self.on_type = on_type
        self.parent = parent
        self.fields: List[FieldBuilder] = []

    def field(self, name: str) -> FieldBuilder:
        """
        Add field to fragment.

        Args:
            name: Field name

        Returns:
            FieldBuilder for the field
        """
        field_builder = FieldBuilder(name, parent=self)
        self.fields.append(field_builder)
        return field_builder

    def add_fields(self, *names: str) -> FragmentBuilder:
        """
        Add multiple simple fields to fragment.

        Args:
            *names: Field names

        Returns:
            Self for chaining
        """
        for name in names:
            self.fields.append(FieldBuilder(name, parent=self))
        return self

    def end_fragment(self) -> QueryBuilder:
        """
        Complete fragment definition and return to parent builder.

        Returns:
            Parent QueryBuilder
        """
        self.parent.fragments.append(
            {"name": self.name, "on_type": self.on_type, "fields": self.fields}
        )
        return self.parent


class MutationBuilder(QueryBuilder):
    """
    Fluent interface for building GraphQL mutations.

    Similar to QueryBuilder but for mutations.

    Examples:
        Simple mutation:
        ```python
        mutation = (MutationBuilder("CreateUser")
            .variable("input", "CreateUserInput!")
            .field("createUser")
                .arg("input", "$input")
                .add_fields("id", "name", "email")
            .build()
        )
        ```

        Complex mutation with error handling:
        ```python
        mutation = (MutationBuilder()
            .field("updateProfile")
                .arg("id", "$userId")
                .arg("data", "$profileData")
                .field("user")
                    .add_fields("id", "name", "email")
                .field("errors")
                    .add_fields("field", "message")
            .build()
        )
        ```
    """

    def build(self, variables: Optional[Dict[str, Any]] = None) -> GraphQLMutation:
        """
        Build the GraphQL mutation.

        Args:
            variables: Variable values

        Returns:
            GraphQLMutation object
        """
        query_string = self._build_mutation_string()

        # Merge provided variables with defaults
        final_variables = {}
        for var in self.variables:
            if variables and var.name in variables:
                final_variables[var.name] = variables[var.name]
            elif var.default_value is not None:
                final_variables[var.name] = var.default_value

        return GraphQLMutation(
            query=query_string,
            variables=final_variables,
            operation_name=self.operation_name,
        )

    def _build_mutation_string(self) -> str:
        """Build the mutation string."""
        lines = []

        # Add operation definition
        operation_line = "mutation"
        if self.operation_name:
            operation_line += f" {self.operation_name}"

        # Add variables
        if self.variables:
            var_defs = []
            for var in self.variables:
                var_def = f"${var.name}: {var.type}"
                if var.default_value is not None:
                    var_def += f" = {self._format_default_value(var.default_value)}"
                var_defs.append(var_def)
            operation_line += f"({', '.join(var_defs)})"

        # Add directives
        for directive in self.directives:
            operation_line += f" @{directive['name']}"
            if directive["args"]:
                args_str = ", ".join(
                    [
                        f"{key}: {self._format_default_value(value)}"
                        for key, value in directive["args"].items()
                    ]
                )
                operation_line += f"({args_str})"

        operation_line += " {"
        lines.append(operation_line)

        # Add fields
        for field in self.fields:
            lines.append(field.to_string(1))

        lines.append("}")

        # Add fragments
        for fragment in self.fragments:
            lines.append("")
            lines.append(f"fragment {fragment['name']} on {fragment['on_type']} {{")
            for field in fragment["fields"]:
                lines.append(field.to_string(1))
            lines.append("}")

        return "\n".join(lines)


class SubscriptionBuilder(QueryBuilder):
    """
    Fluent interface for building GraphQL subscriptions.

    Similar to QueryBuilder but for subscriptions.

    Examples:
        Simple subscription:
        ```python
        subscription = (SubscriptionBuilder("MessageAdded")
            .variable("channelId", "ID!")
            .field("messageAdded")
                .arg("channelId", "$channelId")
                .add_fields("id", "content", "user { name }")
            .build()
        )
        ```
    """

    def build(self, variables: Optional[Dict[str, Any]] = None) -> GraphQLSubscription:
        """
        Build the GraphQL subscription.

        Args:
            variables: Variable values

        Returns:
            GraphQLSubscription object
        """
        query_string = self._build_subscription_string()

        # Merge provided variables with defaults
        final_variables = {}
        for var in self.variables:
            if variables and var.name in variables:
                final_variables[var.name] = variables[var.name]
            elif var.default_value is not None:
                final_variables[var.name] = var.default_value

        return GraphQLSubscription(
            query=query_string,
            variables=final_variables,
            operation_name=self.operation_name,
        )

    def _build_subscription_string(self) -> str:
        """Build the subscription string."""
        lines = []

        # Add operation definition
        operation_line = "subscription"
        if self.operation_name:
            operation_line += f" {self.operation_name}"

        # Add variables
        if self.variables:
            var_defs = []
            for var in self.variables:
                var_def = f"${var.name}: {var.type}"
                if var.default_value is not None:
                    var_def += f" = {self._format_default_value(var.default_value)}"
                var_defs.append(var_def)
            operation_line += f"({', '.join(var_defs)})"

        # Add directives
        for directive in self.directives:
            operation_line += f" @{directive['name']}"
            if directive["args"]:
                args_str = ", ".join(
                    [
                        f"{key}: {self._format_default_value(value)}"
                        for key, value in directive["args"].items()
                    ]
                )
                operation_line += f"({args_str})"

        operation_line += " {"
        lines.append(operation_line)

        # Add fields
        for field in self.fields:
            lines.append(field.to_string(1))

        lines.append("}")

        # Add fragments
        for fragment in self.fragments:
            lines.append("")
            lines.append(f"fragment {fragment['name']} on {fragment['on_type']} {{")
            for field in fragment["fields"]:
                lines.append(field.to_string(1))
            lines.append("}")

        return "\n".join(lines)
