#!/usr/bin/env python3
"""Validate the worked examples in the prose against the schemas.

The specification and README contain JSON examples that implementers copy. This
script extracts every fenced ```json block from SPECIFICATION.md and README.md,
identifies the ones that are complete top-level documents, and validates each
against the matching schema:

    session document  -> telemetry-session.json
    standalone event  -> telemetry-event.json
    manifest          -> manifest.json

Fragments (a bare event object, a single turn, a one-field snippet) are not
top-level documents and cannot be validated against a top-level schema. They are
counted and listed rather than validated.

Usage:
    uv run --with jsonschema python tests/check_examples.py
    # or: pip install jsonschema && python tests/check_examples.py
"""

import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    print("ERROR: jsonschema package required. Install with: pip install jsonschema")
    sys.exit(1)

REPO = Path(__file__).resolve().parent.parent
SOURCES = [REPO / "SPECIFICATION.md", REPO / "README.md"]
FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def load_validators():
    """Build a validator per schema, sharing one registry so $refs resolve."""
    registry = Registry()
    schemas = {}
    for name in ("telemetry-session.json", "telemetry-event.json", "manifest.json"):
        schema = json.loads((REPO / name).read_text())
        schemas[name] = schema
        registry = registry.with_resource(
            schema.get("$id", name), Resource.from_contents(schema)
        )
    return {
        name: Draft202012Validator(schema, registry=registry)
        for name, schema in schemas.items()
    }


def strip_comments(block):
    """Drop leading // comment lines (used to label manifest examples)."""
    lines = block.splitlines()
    while lines and lines[0].lstrip().startswith("//"):
        lines.pop(0)
    return "\n".join(lines)


def classify(doc):
    """Return the schema a complete document validates against, or None for a fragment."""
    if not isinstance(doc, dict):
        return None
    if doc.get("document_type") == "session":
        return "telemetry-session.json"
    if doc.get("document_type") == "event" or isinstance(doc.get("event"), dict):
        return "telemetry-event.json"
    if {"roles", "operator", "id", "schema_version"} <= doc.keys():
        return "manifest.json"
    if "session_id" in doc and "started_at" in doc and "events" in doc:
        return "telemetry-session.json"
    return None


def iter_blocks():
    """Yield (source_name, line_number, raw_block) for every json fence."""
    for src in SOURCES:
        if not src.exists():
            continue
        text = src.read_text()
        for m in FENCE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            yield src.name, line, m.group(1)


def main():
    validators = load_validators()
    checked = failed = fragments = 0
    by_schema = {}

    for source, line, raw in iter_blocks():
        loc = f"{source}:{line}"
        try:
            doc = json.loads(strip_comments(raw))
        except json.JSONDecodeError:
            # A non-JSON or intentionally-elided block (e.g. truncated keys);
            # treat as a fragment rather than a failure.
            fragments += 1
            continue

        schema_name = classify(doc)
        if schema_name is None:
            fragments += 1
            continue

        checked += 1
        by_schema[schema_name] = by_schema.get(schema_name, 0) + 1
        errors = sorted(validators[schema_name].iter_errors(doc), key=lambda e: e.path)
        if errors:
            failed += 1
            print(f"  FAIL  {loc}  (against {schema_name})")
            for e in errors[:3]:
                path = "/".join(str(p) for p in e.path) or "(root)"
                print(f"        {path}: {e.message}")
        else:
            print(f"  PASS  {loc}  ({schema_name})")

    print()
    print("=" * 60)
    breakdown = ", ".join(f"{n} {s}" for s, n in sorted(by_schema.items()))
    print(f"Validated {checked} complete examples" + (f" ({breakdown})" if breakdown else ""))
    print(f"Skipped {fragments} fragments (not top-level documents)")
    print(f"SUMMARY: {checked - failed}/{checked} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
