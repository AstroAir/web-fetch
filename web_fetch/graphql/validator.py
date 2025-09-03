"""
GraphQL query validator.

This module provides comprehensive GraphQL query validation against schemas,
including syntax validation, type checking, and variable validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from .models import (
    GraphQLError,
    GraphQLMutation,
    GraphQLOperationType,
    GraphQLQuery,
    GraphQLSchema,
    GraphQLSubscription,
)


@dataclass
class ValidationError:
    """Represents a validation error."""

    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    path: Optional[List[str]] = None
    error_type: str = "VALIDATION_ERROR"

    def __str__(self) -> str:
        """String representation of validation error."""
        location = ""
        if self.line is not None:
            location = f" at line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"

        path_str = ""
        if self.path:
            path_str = f" in {'.'.join(self.path)}"

        return f"{self.error_type}: {self.message}{location}{path_str}"


@dataclass
class ValidationResult:
    """Result of GraphQL validation."""

    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(self, message: str, **kwargs: Any) -> None:
        """Add validation error."""
        self.errors.append(ValidationError(message=message, **kwargs))
        self.is_valid = False

    def add_warning(self, message: str, **kwargs: Any) -> None:
        """Add validation warning."""
        self.warnings.append(
            ValidationError(message=message, error_type="WARNING", **kwargs)
        )


class GraphQLSyntaxValidator:
    """Validates GraphQL syntax."""

    # GraphQL syntax patterns
    OPERATION_PATTERN = re.compile(
        r"^\s*(query|mutation|subscription)\s+", re.IGNORECASE
    )
    FIELD_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
    VARIABLE_PATTERN = re.compile(r"\$[a-zA-Z_][a-zA-Z0-9_]*")
    ARGUMENT_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*")

    def validate_syntax(self, query_text: str) -> ValidationResult:
        """
        Validate GraphQL query syntax.

        Args:
            query_text: GraphQL query string

        Returns:
            ValidationResult with syntax validation results
        """
        result = ValidationResult(is_valid=True)

        if not query_text or not query_text.strip():
            result.add_error("Query cannot be empty")
            return result

        # Check for balanced braces
        self._validate_balanced_braces(query_text, result)

        # Check for balanced parentheses
        self._validate_balanced_parentheses(query_text, result)

        # Check for valid field syntax
        self._validate_field_syntax(query_text, result)

        # Check for valid variable syntax
        self._validate_variable_syntax(query_text, result)

        return result

    def _validate_balanced_braces(
        self, query_text: str, result: ValidationResult
    ) -> None:
        """Validate balanced braces."""
        brace_count = 0
        line_num = 1

        for i, char in enumerate(query_text):
            if char == "\n":
                line_num += 1
            elif char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count < 0:
                    result.add_error("Unexpected closing brace", line=line_num)
                    return

        if brace_count > 0:
            result.add_error(f"Missing {brace_count} closing brace(s)")
        elif brace_count < 0:
            result.add_error(f"Extra {abs(brace_count)} closing brace(s)")

    def _validate_balanced_parentheses(
        self, query_text: str, result: ValidationResult
    ) -> None:
        """Validate balanced parentheses."""
        paren_count = 0
        line_num = 1

        for i, char in enumerate(query_text):
            if char == "\n":
                line_num += 1
            elif char == "(":
                paren_count += 1
            elif char == ")":
                paren_count -= 1
                if paren_count < 0:
                    result.add_error("Unexpected closing parenthesis", line=line_num)
                    return

        if paren_count > 0:
            result.add_error(f"Missing {paren_count} closing parenthesis/parentheses")
        elif paren_count < 0:
            result.add_error(
                f"Extra {abs(paren_count)} closing parenthesis/parentheses"
            )

    def _validate_field_syntax(self, query_text: str, result: ValidationResult) -> None:
        """Validate field name syntax."""
        # Remove strings and comments to avoid false positives
        cleaned_text = self._remove_strings_and_comments(query_text)

        # Find potential field names (simplified heuristic)
        lines = cleaned_text.split("\n")
        for line_num, line in enumerate(lines, 1):
            # Skip operation definitions
            if self.OPERATION_PATTERN.match(line):
                continue

            # Look for invalid field patterns
            if re.search(r"\b\d+[a-zA-Z_]", line):
                result.add_error("Field names cannot start with numbers", line=line_num)

    def _validate_variable_syntax(
        self, query_text: str, result: ValidationResult
    ) -> None:
        """Validate variable syntax."""
        variables = self.VARIABLE_PATTERN.findall(query_text)

        for var in variables:
            if not re.match(r"^\$[a-zA-Z_][a-zA-Z0-9_]*$", var):
                result.add_error(f"Invalid variable name: {var}")

    def _remove_strings_and_comments(self, text: str) -> str:
        """Remove string literals and comments from GraphQL text."""
        # Simple implementation - removes content within quotes and # comments
        result = []
        in_string = False
        in_comment = False
        quote_char = None

        i = 0
        while i < len(text):
            char = text[i]

            if in_comment:
                if char == "\n":
                    in_comment = False
                    result.append(char)
                i += 1
                continue

            if in_string:
                if char == quote_char and (i == 0 or text[i - 1] != "\\"):
                    in_string = False
                    quote_char = None
                i += 1
                continue

            if char in ['"', "'"]:
                in_string = True
                quote_char = char
            elif char == "#":
                in_comment = True
            else:
                result.append(char)

            i += 1

        return "".join(result)


class GraphQLSchemaValidator:
    """Validates GraphQL queries against schema."""

    def __init__(self, schema: GraphQLSchema):
        """
        Initialize schema validator.

        Args:
            schema: GraphQL schema to validate against
        """
        self.schema = schema
        self._type_map = self._build_type_map()
        self._query_fields = self._build_field_map(schema.queries)
        self._mutation_fields = self._build_field_map(schema.mutations)
        self._subscription_fields = self._build_field_map(schema.subscriptions)

    def _build_type_map(self) -> Dict[str, Dict[str, Any]]:
        """Build a map of types for quick lookup."""
        type_map = {}
        for type_def in self.schema.types:
            type_map[type_def.get("name", "")] = type_def
        return type_map

    def _build_field_map(
        self, fields: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Build a map of fields for quick lookup."""
        field_map = {}
        for field in fields:
            field_map[field.get("name", "")] = field
        return field_map

    def validate_against_schema(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> ValidationResult:
        """
        Validate query against schema.

        Args:
            query: GraphQL query to validate

        Returns:
            ValidationResult with schema validation results
        """
        result = ValidationResult(is_valid=True)

        # Parse query to extract operation and fields (simplified)
        operation_type = query.operation_type
        query_fields = self._extract_fields_from_query(query.query)

        # Get appropriate field map based on operation type
        available_fields = {}
        if operation_type == GraphQLOperationType.QUERY:
            available_fields = self._query_fields
        elif operation_type == GraphQLOperationType.MUTATION:
            available_fields = self._mutation_fields
        elif operation_type == GraphQLOperationType.SUBSCRIPTION:
            available_fields = self._subscription_fields

        # Validate fields exist in schema
        for field_name in query_fields:
            if field_name not in available_fields:
                result.add_error(
                    f"Field '{field_name}' does not exist in {operation_type.value} type"
                )

        # Validate variables if present
        if query.variables:
            self._validate_variables(query, result)

        return result

    def _extract_fields_from_query(self, query_text: str) -> Set[str]:
        """
        Extract field names from GraphQL query (simplified parser).

        Args:
            query_text: GraphQL query string

        Returns:
            Set of field names found in query
        """
        fields = set()

        # Remove operation definition and focus on selection set
        lines = query_text.split("\n")
        in_selection = False

        for line in lines:
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith("#"):
                continue

            # Skip operation definition line
            if re.match(r"^\s*(query|mutation|subscription)", stripped, re.IGNORECASE):
                continue

            # Look for opening brace to start selection set
            if "{" in stripped:
                in_selection = True

            if in_selection:
                # Extract field names (simplified)
                field_matches = re.findall(
                    r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(|{|$)", stripped
                )
                for match in field_matches:
                    # Skip GraphQL keywords
                    if match.lower() not in [
                        "query",
                        "mutation",
                        "subscription",
                        "fragment",
                        "on",
                    ]:
                        fields.add(match)

        return fields

    def _validate_variables(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        result: ValidationResult,
    ) -> None:
        """Validate variables against schema types."""
        # Extract variable definitions from query (simplified)
        var_definitions = self._extract_variable_definitions(query.query)

        for var_name, var_value in query.variables.items():
            # Check if variable is defined in query
            if f"${var_name}" not in var_definitions:
                result.add_warning(f"Variable ${var_name} is not defined in query")
                continue

            # Basic type validation (can be extended)
            if var_value is None:
                continue  # Allow null values

            # Validate based on value type
            if isinstance(var_value, str) and len(var_value) > 10000:
                result.add_warning(f"Variable ${var_name} has very long string value")
            elif isinstance(var_value, (list, dict)) and len(str(var_value)) > 50000:
                result.add_warning(f"Variable ${var_name} has very large complex value")

    def _extract_variable_definitions(self, query_text: str) -> Set[str]:
        """Extract variable definitions from query."""
        variables = set()

        # Find variable definitions (simplified)
        var_matches = re.findall(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", query_text)
        for match in var_matches:
            variables.add(f"${match}")

        return variables


class GraphQLValidator:
    """
    Comprehensive GraphQL validator.

    Provides complete validation of GraphQL queries including:
    - Syntax validation
    - Schema validation
    - Variable validation
    - Security checks

    Examples:
        Basic validation:
        ```python
        schema = await client.introspect_schema()
        validator = GraphQLValidator(schema)

        query = GraphQLQuery(
            query="query GetUser($id: ID!) { user(id: $id) { name } }",
            variables={"id": "123"}
        )

        result = await validator.validate(query)
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error}")
        ```

        With custom validation rules:
        ```python
        validator = GraphQLValidator(schema)
        validator.max_query_depth = 10
        validator.max_query_complexity = 1000

        result = await validator.validate(query)
        ```
    """

    def __init__(self, schema: Optional[GraphQLSchema] = None):
        """
        Initialize GraphQL validator.

        Args:
            schema: Optional GraphQL schema for schema validation
        """
        self.schema = schema
        self.syntax_validator = GraphQLSyntaxValidator()
        self.schema_validator = GraphQLSchemaValidator(schema) if schema else None

        # Validation settings
        self.max_query_depth = 15
        self.max_query_complexity = 1000
        self.max_aliases = 100
        self.validate_syntax = True
        self.validate_schema = True
        self.validate_variables = True
        self.check_security = True

    async def validate(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> ValidationResult:
        """
        Validate GraphQL query comprehensively.

        Args:
            query: GraphQL query to validate

        Returns:
            ValidationResult with all validation results
        """
        result = ValidationResult(is_valid=True)

        # Basic query validation
        if not query.validate():
            result.add_error("Query failed basic validation")
            return result

        # Syntax validation
        if self.validate_syntax:
            syntax_result = self.syntax_validator.validate_syntax(query.query)
            result.errors.extend(syntax_result.errors)
            result.warnings.extend(syntax_result.warnings)
            if not syntax_result.is_valid:
                result.is_valid = False

        # Schema validation
        if self.validate_schema and self.schema_validator:
            schema_result = self.schema_validator.validate_against_schema(query)
            result.errors.extend(schema_result.errors)
            result.warnings.extend(schema_result.warnings)
            if not schema_result.is_valid:
                result.is_valid = False

        # Security validation
        if self.check_security:
            security_result = self._validate_security(query)
            result.errors.extend(security_result.errors)
            result.warnings.extend(security_result.warnings)
            if not security_result.is_valid:
                result.is_valid = False

        # Query complexity validation
        complexity_result = self._validate_complexity(query)
        result.errors.extend(complexity_result.errors)
        result.warnings.extend(complexity_result.warnings)
        if not complexity_result.is_valid:
            result.is_valid = False

        return result

    def _validate_security(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> ValidationResult:
        """Validate query for security issues."""
        result = ValidationResult(is_valid=True)

        query_text = query.query.lower()

        # Check for potential injection patterns
        suspicious_patterns = [
            r"union\s+select",
            r"drop\s+table",
            r"delete\s+from",
            r"insert\s+into",
            r"update\s+.*\s+set",
            r"exec\s*\(",
            r"script\s*>",
            r"javascript:",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, query_text):
                result.add_error(f"Suspicious pattern detected: {pattern}")

        # Check for excessively long queries
        if len(query.query) > 100000:  # 100KB limit
            result.add_error("Query exceeds maximum size limit")

        # Check for too many aliases
        alias_count = len(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\s*:", query.query))
        if alias_count > self.max_aliases:
            result.add_error(f"Too many aliases: {alias_count} > {self.max_aliases}")

        return result

    def _validate_complexity(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> ValidationResult:
        """Validate query complexity."""
        result = ValidationResult(is_valid=True)

        # Calculate query depth (simplified)
        depth = self._calculate_query_depth(query.query)
        if depth > self.max_query_depth:
            result.add_error(
                f"Query depth {depth} exceeds limit {self.max_query_depth}"
            )

        # Calculate query complexity (simplified scoring)
        complexity = self._calculate_query_complexity(query.query)
        if complexity > self.max_query_complexity:
            result.add_error(
                f"Query complexity {complexity} exceeds limit {self.max_query_complexity}"
            )

        return result

    def _calculate_query_depth(self, query_text: str) -> int:
        """Calculate maximum nesting depth of query."""
        max_depth = 0
        current_depth = 0

        for char in query_text:
            if char == "{":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == "}":
                current_depth -= 1

        return max_depth

    def _calculate_query_complexity(self, query_text: str) -> int:
        """Calculate advanced query complexity score with detailed analysis."""
        complexity = 0

        # Base field complexity
        field_count = len(
            re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?:\{|$|\()", query_text)
        )
        complexity += field_count

        # Fragment complexity (higher weight for inline fragments)
        fragment_spread_count = len(re.findall(r"\.\.\.\s*[a-zA-Z_]", query_text))
        inline_fragment_count = len(re.findall(r"\.\.\.\s*on\s+", query_text))
        complexity += fragment_spread_count * 2 + inline_fragment_count * 3

        # Variable complexity
        variable_count = len(re.findall(r"\$[a-zA-Z_][a-zA-Z0-9_]*", query_text))
        complexity += variable_count

        # Argument complexity (weighted by type)
        simple_args = len(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*[^{\[{]", query_text))
        complex_args = len(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*[{\[]", query_text))
        complexity += simple_args + complex_args * 3

        # Directive complexity
        directive_count = len(re.findall(r"@[a-zA-Z_][a-zA-Z0-9_]*", query_text))
        complexity += directive_count * 2

        # Nested query complexity (exponential growth for deep nesting)
        depth = self._calculate_query_depth(query_text)
        if depth > 5:
            complexity += (depth - 5) ** 2

        # List field complexity (pagination patterns)
        list_patterns = len(re.findall(r"(first|last|limit|offset|take|skip)\s*:", query_text))
        complexity += list_patterns * 2

        return complexity

    def analyze_query_complexity(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> Dict[str, Any]:
        """
        Perform detailed query complexity analysis.

        Args:
            query: GraphQL query to analyze

        Returns:
            Detailed complexity analysis report
        """
        query_text = query.query

        analysis = {
            "total_complexity": self._calculate_query_complexity(query_text),
            "depth": self._calculate_query_depth(query_text),
            "field_count": len(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?:\{|$|\()", query_text)),
            "fragment_count": len(re.findall(r"\.\.\.", query_text)),
            "variable_count": len(re.findall(r"\$[a-zA-Z_][a-zA-Z0-9_]*", query_text)),
            "directive_count": len(re.findall(r"@[a-zA-Z_][a-zA-Z0-9_]*", query_text)),
            "optimization_hints": self._generate_optimization_hints(query_text),
            "performance_score": self._calculate_performance_score(query_text),
        }

        return analysis

    def _generate_optimization_hints(self, query_text: str) -> List[str]:
        """Generate optimization hints for the query."""
        hints = []

        # Check for excessive nesting
        depth = self._calculate_query_depth(query_text)
        if depth > 10:
            hints.append("Consider reducing query depth - very deep nesting can impact performance")
        elif depth > 7:
            hints.append("Query depth is high - consider using fragments to reduce complexity")

        # Check for missing pagination
        if re.search(r"\b(users|posts|comments|items|list)\b", query_text, re.IGNORECASE):
            if not re.search(r"\b(first|last|limit|offset|take|skip)\b", query_text):
                hints.append("Consider adding pagination to list fields to improve performance")

        # Check for excessive field selection
        field_count = len(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?:\{|$|\()", query_text))
        if field_count > 50:
            hints.append("Large number of fields selected - consider using fragments or selecting only needed fields")

        # Check for potential N+1 problems
        if re.search(r"\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\{", query_text):
            hints.append("Deep nested selections detected - ensure proper data loading strategies are in place")

        # Check for missing field aliases in complex queries
        alias_count = len(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*\s*:", query_text))
        if field_count > 20 and alias_count == 0:
            hints.append("Consider using field aliases for better query organization in complex queries")

        return hints

    def _calculate_performance_score(self, query_text: str) -> float:
        """Calculate a performance score (0-100, higher is better)."""
        complexity = self._calculate_query_complexity(query_text)
        depth = self._calculate_query_depth(query_text)

        # Base score
        score = 100.0

        # Penalize high complexity
        if complexity > self.max_query_complexity:
            score -= min(50, (complexity - self.max_query_complexity) * 2)
        elif complexity > self.max_query_complexity * 0.7:
            score -= (complexity - self.max_query_complexity * 0.7) * 0.5

        # Penalize high depth
        if depth > self.max_query_depth:
            score -= min(30, (depth - self.max_query_depth) * 5)
        elif depth > self.max_query_depth * 0.7:
            score -= (depth - self.max_query_depth * 0.7) * 2

        # Bonus for good practices
        if re.search(r"\b(first|last|limit)\b", query_text):
            score += 5  # Pagination bonus
        if re.search(r"fragment\s+", query_text):
            score += 3  # Fragment usage bonus

        return max(0.0, min(100.0, score))

    def update_schema(self, schema: GraphQLSchema) -> None:
        """Update the schema used for validation."""
        self.schema = schema
        self.schema_validator = GraphQLSchemaValidator(schema)

    def get_validation_rules(self) -> Dict[str, Any]:
        """Get current validation rules and settings."""
        return {
            "max_query_depth": self.max_query_depth,
            "max_query_complexity": self.max_query_complexity,
            "max_aliases": self.max_aliases,
            "validate_syntax": self.validate_syntax,
            "validate_schema": self.validate_schema,
            "validate_variables": self.validate_variables,
            "check_security": self.check_security,
            "schema_available": self.schema is not None,
        }
