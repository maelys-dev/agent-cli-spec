# SPDX-License-Identifier: MPL-2.0
"""A small JSON Schema validator for the schemas of this repository.

Standard library only, so that the conformance kit runs anywhere python3
runs. It covers the subset the schemas use: type (including a list of
types), const, enum, required, properties, additionalProperties (boolean or
schema), patternProperties, items, minItems, minimum, maximum, pattern,
oneOf, anyOf, allOf, and $ref to a definition of the same document
(`#/definitions/NAME`). Anything else in a schema is ignored, deliberately:
this is a checker of the contract, not a general validator.
"""
from __future__ import annotations

import re
from typing import Any

TYPES = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


class Issue:
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"{self.path or '$'}: {self.message}"


def validate(value: Any, schema: dict, root: dict | None = None, path: str = "") -> list[Issue]:
    """Every violation of `schema` by `value`, deepest first is not guaranteed."""
    root = root if root is not None else schema
    issues: list[Issue] = []
    if "$ref" in schema:
        target = schema["$ref"]
        if not target.startswith("#/"):
            raise ValueError(f"unsupported $ref: {target}")
        resolved: Any = root
        for part in target[2:].split("/"):
            resolved = resolved[part]
        return validate(value, resolved, root, path)
    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(TYPES[name](value) for name in allowed):
            issues.append(Issue(path, f"expected {' or '.join(allowed)}, got {type(value).__name__}"))
            return issues
    if "const" in schema and value != schema["const"]:
        issues.append(Issue(path, f"expected {schema['const']!r}, got {value!r}"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(Issue(path, f"expected one of {schema['enum']}, got {value!r}"))
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        issues.append(Issue(path, f"{value!r} does not match {schema['pattern']}"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(Issue(path, f"{value} is below {schema['minimum']}"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(Issue(path, f"{value} is above {schema['maximum']}"))
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                issues.append(Issue(path, f"missing member {name!r}"))
        properties = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        additional = schema.get("additionalProperties", True)
        for name, member in value.items():
            child = f"{path}.{name}" if path else name
            if name in properties:
                issues.extend(validate(member, properties[name], root, child))
                continue
            matched = [pattern for pattern in patterns if re.search(pattern, name)]
            if matched:
                for pattern in matched:
                    issues.extend(validate(member, patterns[pattern], root, child))
                continue
            if additional is False:
                issues.append(Issue(child, "member not allowed by the contract"))
            elif isinstance(additional, dict):
                issues.extend(validate(member, additional, root, child))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            issues.append(Issue(path, f"expected at least {schema['minItems']} items"))
        if "items" in schema:
            for index, item in enumerate(value):
                issues.extend(validate(item, schema["items"], root, f"{path}[{index}]"))
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            results = [validate(value, option, root, path) for option in schema[keyword]]
            passing = [result for result in results if not result]
            if keyword == "oneOf" and len(passing) != 1 or keyword == "anyOf" and not passing:
                # report the closest alternative: the one with the fewest issues
                closest = min(results, key=len)
                issues.append(Issue(path, f"no {keyword} alternative matched"))
                issues.extend(closest)
    for option in schema.get("allOf", []):
        issues.extend(validate(value, option, root, path))
    return issues
