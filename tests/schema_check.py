"""A small JSON Schema subset validator, enough for the schemas in schemas/.

Supports: type, const, enum, pattern, minimum, properties, required,
additionalProperties (false), items, oneOf. Unknown keywords raise, so a schema
can never silently use a rule this checker ignores.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
_KNOWN = {"$schema", "$id", "title", "format", "type", "const", "enum", "pattern", "minimum",
          "properties", "required", "additionalProperties", "items", "oneOf"}
_TYPES = {"string": str, "boolean": bool, "array": list, "object": dict, "null": type(None)}


def load(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def _is(value: object, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


def errors(value: object, schema: dict, where: str = "$") -> list[str]:
    unknown = set(schema) - _KNOWN
    if unknown:
        raise ValueError(f"{where}: schema uses unsupported keywords {sorted(unknown)}")
    if "oneOf" in schema:
        matches = [s for s in schema["oneOf"] if not errors(value, s, where)]
        return [] if len(matches) == 1 else [f"{where}: matches {len(matches)} oneOf branches"]
    found: list[str] = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(_is(value, k) for k in kinds):
            return [f"{where}: expected {kinds}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        found.append(f"{where}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{where}: {value!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        found.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if "minimum" in schema and isinstance(value, int) and value < schema["minimum"]:
        found.append(f"{where}: below minimum")
    if isinstance(value, dict) and "properties" in schema:
        props = schema["properties"]
        for key in schema.get("required", ()):
            if key not in value:
                found.append(f"{where}: missing {key}")
        for key, item in value.items():
            if key in props:
                found += errors(item, props[key], f"{where}.{key}")
            elif schema.get("additionalProperties") is False:
                found.append(f"{where}: unexpected key {key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            found += errors(item, schema["items"], f"{where}[{index}]")
    return found
