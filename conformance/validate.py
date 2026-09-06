# SPDX-License-Identifier: MPL-2.0
"""A small JSON Schema validator for the schemas of this repository.

Standard library only, so that the conformance kit runs anywhere python3
runs. It covers the subset the schemas use: type (including a list of
types), const, enum, required, properties, additionalProperties (boolean or
schema), patternProperties, items, minItems, maxItems, minLength, maxLength,
minimum, maximum, pattern, oneOf, anyOf, allOf, not, if/then/else, and local
$ref. Product schemas are inspected with unsupported_keywords before use:
unsupported assertions must be reported as unverified, never silently passed.
"""
from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import unquote

TYPES = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool)
    or isinstance(value, float) and math.isfinite(value) and value.is_integer(),
    "number": lambda value: isinstance(value, int) and not isinstance(value, bool)
    or isinstance(value, float) and math.isfinite(value),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}

ASSERTIONS = {"type", "const", "enum", "required", "properties", "additionalProperties", "patternProperties",
              "items", "minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum", "pattern",
              "oneOf", "anyOf", "allOf", "not", "if", "then", "else", "$ref"}
ANNOTATIONS = {"$schema", "$id", "$comment", "$defs", "definitions", "title", "description", "default",
               "examples", "deprecated", "readOnly", "writeOnly"}


def json_equal(left: Any, right: Any) -> bool:
    """JSON equality distinguishes booleans from numbers, including nested values."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    return left == right


def resolve_ref(target: str, root: dict) -> Any:
    if target == "#":
        return root
    if not target.startswith("#/"):
        raise ValueError(f"unsupported $ref: {target}")
    resolved = root
    for part in unquote(target[2:]).split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(resolved, list):
            if re.fullmatch(r"0|[1-9][0-9]*", part) is None:
                raise ValueError(f"invalid array index in $ref: {target}")
            resolved = resolved[int(part)]
        else:
            resolved = resolved[part]
    return resolved


def unsupported_keywords(schema: Any, path: str = "$") -> list[str]:
    """Inspect schema locations only, not names in properties or values in const."""
    if isinstance(schema, bool):
        return []
    if not isinstance(schema, dict):
        raise ValueError(f"{path}: a schema must be an object or boolean")
    unknown = [f"{path}.{key}" for key in schema if key not in ASSERTIONS | ANNOTATIONS]
    if "$schema" in schema and schema["$schema"].rstrip("#") != "https://json-schema.org/draft/2020-12/schema":
        unknown.append(f"{path}.$schema: unsupported dialect {schema['$schema']}")
    if "$id" in schema and path != "$":
        unknown.append(f"{path}.$id: embedded schema resources are not supported")
    if "$ref" in schema and not (schema["$ref"] == "#" or schema["$ref"].startswith("#/")):
        unknown.append(f"{path}.$ref: {schema['$ref']}")
    for key in ("properties", "patternProperties", "$defs", "definitions"):
        for name, child in schema.get(key, {}).items():
            unknown.extend(unsupported_keywords(child, f"{path}.{key}.{name}"))
    for key in ("items", "additionalProperties", "not", "if", "then", "else"):
        if key in schema:
            unknown.extend(unsupported_keywords(schema[key], f"{path}.{key}"))
    for key in ("oneOf", "anyOf", "allOf"):
        for index, child in enumerate(schema.get(key, [])):
            unknown.extend(unsupported_keywords(child, f"{path}.{key}[{index}]"))
    return unknown


class Issue:
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"{self.path or '$'}: {self.message}"


def validate(value: Any, schema: dict | bool, root: dict | None = None, path: str = "") -> list[Issue]:
    """Every violation of `schema` by `value`, deepest first is not guaranteed."""
    if isinstance(schema, bool):
        return [] if schema else [Issue(path, "false schema rejects every value")]
    root = root if root is not None else schema
    issues: list[Issue] = []
    if "$ref" in schema:
        issues.extend(validate(value, resolve_ref(schema["$ref"], root), root, path))
    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(TYPES[name](value) for name in allowed):
            issues.append(Issue(path, f"expected {' or '.join(allowed)}, got {type(value).__name__}"))
            return issues
    if "const" in schema and not json_equal(value, schema["const"]):
        issues.append(Issue(path, f"expected {schema['const']!r}, got {value!r}"))
    if "enum" in schema and not any(json_equal(value, member) for member in schema["enum"]):
        issues.append(Issue(path, f"expected one of {schema['enum']}, got {value!r}"))
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        issues.append(Issue(path, f"{value!r} does not match {schema['pattern']}"))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            issues.append(Issue(path, f"expected at least {schema['minLength']} characters"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            issues.append(Issue(path, f"expected at most {schema['maxLength']} characters"))
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
            matched = [pattern for pattern in patterns if re.search(pattern, name)]
            if matched:
                for pattern in matched:
                    issues.extend(validate(member, patterns[pattern], root, child))
                continue
            if name in properties:
                continue
            if additional is False:
                issues.append(Issue(child, "member not allowed by the contract"))
            elif isinstance(additional, dict):
                issues.extend(validate(member, additional, root, child))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            issues.append(Issue(path, f"expected at least {schema['minItems']} items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            issues.append(Issue(path, f"expected at most {schema['maxItems']} items"))
        if "items" in schema:
            for index, item in enumerate(value):
                issues.extend(validate(item, schema["items"], root, f"{path}[{index}]"))
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            results = [validate(value, option, root, path) for option in schema[keyword]]
            passing = [result for result in results if not result]
            if keyword == "oneOf" and len(passing) != 1 or keyword == "anyOf" and not passing:
                # report the closest alternative: the one with the fewest issues
                closest = min(results, key=len, default=[])
                issues.append(Issue(path, f"{len(passing)} {keyword} alternatives matched"))
                issues.extend(closest)
    for option in schema.get("allOf", []):
        issues.extend(validate(value, option, root, path))
    if "not" in schema and not validate(value, schema["not"], root, path):
        issues.append(Issue(path, "matched forbidden schema"))
    if "if" in schema:
        branch = "else" if validate(value, schema["if"], root, path) else "then"
        if branch in schema:
            issues.extend(validate(value, schema[branch], root, path))
    return issues
