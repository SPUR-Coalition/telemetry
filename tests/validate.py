#!/usr/bin/env python3
"""
Conformance test runner for Content Telemetry Specification v0.1.

Validates JSON test fixtures against telemetry-session.json, telemetry-event.json,
telemetry-event-batch.json, manifest.json, and application-layer conformance rules
that JSON Schema cannot express. Fixtures whose filename starts with "manifest-"
are validated against manifest.json; all others dispatch on the document_type
discriminator (section 7.1): "event" validates as a standalone event envelope,
"event_batch" as an event batch envelope, and "session" or absent as a session
document.

Usage:
    pip install jsonschema
    python validate.py
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from jsonschema import Draft202012Validator, ValidationError
    from referencing import Registry, Resource
except ImportError:
    print("ERROR: jsonschema package required. Install with: pip install jsonschema")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Application-layer conformance checks
#
# These rules are specified in the Content Telemetry Specification but cannot be
# expressed in JSON Schema alone. They are checked programmatically here.
#
# 1. Privacy level field gating (section 5.5):
#    - At "minimal" level: query_text, response_text, query_intent, topics,
#      model_id, ad_rendered, response_mode, and response_type MUST NOT be
#      present. Only response_tokens and content_urls are allowed.
#    - At "intent" level: query_text and response_text MUST NOT be present.
#
# 2. content_url or content_id requirement (section 5.7.5):
#    Every content event MUST include at least one of content_url or
#    content_id. Not enforced by JSON Schema (both are optional individually).
#
# 3. session_id or ctx_token requirement (sections 5.7.5, 7.1):
#    A standalone event or event batch envelope MUST carry either session_id
#    or ctx_token. Not enforced by JSON Schema (both are optional on the
#    envelope).
#
# 4. Manifest rejection rules (section 8.7):
#    Duplicate keys[].id values, and domains entries that are not the
#    manifest's own host or a subdomain of it (section 8.6). JSON Schema
#    cannot compare values across array items or against the manifest's id.
#
# Not checked here: agent_id at Grounding/Citation conformance (section
# 5.7) depends on the emitter's declared conformance level, which fixtures do
# not carry, so it is out of scope for the fixture suite.
# ---------------------------------------------------------------------------

# Files in invalid/ that pass JSON Schema but fail application-layer rules.
# Map of filename -> description of the conformance violation.
APPLICATION_LAYER_VIOLATIONS = {
    "privacy-violation-query-at-minimal.json": (
        "Turn at minimal privacy includes query_text. "
        "Violates section 5.5: query_text MUST NOT be present at minimal level."
    ),
    "privacy-violation-ad-rendered-at-minimal.json": (
        "Turn at minimal privacy includes ad_rendered. "
        "Violates section 5.5: platform metadata not available at minimal level."
    ),
    "privacy-violation-query-at-intent.json": (
        "Turn at intent privacy includes query_text. "
        "Violates section 5.5: query_text MUST NOT be present at intent level."
    ),
    "content-event-missing-identifier.json": (
        "content_grounded event has neither content_url nor content_id. "
        "Violates section 5.7.5: every content event MUST carry at least one."
    ),
    "standalone-missing-session-and-ctx-token.json": (
        "Standalone event envelope has neither session_id nor ctx_token. "
        "Violates section 5.7.5: an event MUST carry one at Grounding+ (section 7.1)."
    ),
    "batch-missing-session-and-ctx-token.json": (
        "Event batch envelope has neither session_id nor ctx_token. "
        "Violates section 5.7.5: an event MUST carry one at Grounding+ (section 7.1)."
    ),
    "manifest-duplicate-key-id.json": (
        "Manifest carries two keys sharing the same id. "
        "Violates section 8.7: consumers reject a manifest with duplicate keys[].id."
    ),
    "manifest-foreign-domain.json": (
        "Manifest at example.com claims othersite.com in domains. "
        "Violates section 8.6: every entry MUST be the manifest's own host or a "
        "subdomain of it. Consumers reject the manifest as malformed (section 8.7)."
    ),
}

# Event types that carry content and therefore require an identifier
# (content_url or content_id) under section 5.7.5. turn_started and
# turn_completed are turn events, not content events, and are exempt.
CONTENT_EVENT_TYPES = {
    "content_retrieved", "content_grounded", "content_cited",
    "content_presented", "content_engaged",
}

# Fields that MUST NOT appear at each privacy level (section 5.5).
# "minimal" strips everything except token counts (query_tokens, response_tokens) and content_urls.
# "intent" strips query_text and response_text.
PRIVACY_FORBIDDEN_FIELDS = {
    "minimal": {
        "query_text", "response_text", "query_intent", "topics",
        "response_type", "response_mode", "model_id", "ad_rendered",
    },
    "intent": {
        "query_text", "response_text",
    },
}


def load_schema(schema_path):
    """Load and return the JSON Schema and a validator instance."""
    with open(schema_path) as f:
        schema = json.load(f)
    # Build a registry so that $ref pointers resolve when validating
    # sub-schemas (e.g. TelemetryEvent) extracted from the root.
    schema_id = schema.get("$id", "")
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(schema_id, resource)

    # Load the standalone event envelope schema if present.
    event_schema_path = schema_path.parent / "telemetry-event.json"
    if event_schema_path.exists():
        with open(event_schema_path) as f:
            event_schema = json.load(f)
        event_schema_id = event_schema.get("$id", "")
        event_resource = Resource.from_contents(event_schema)
        registry = registry.with_resource(event_schema_id, event_resource)
    else:
        event_schema = None

    # Load the event batch envelope schema if present.
    batch_schema_path = schema_path.parent / "telemetry-event-batch.json"
    if batch_schema_path.exists():
        with open(batch_schema_path) as f:
            batch_schema = json.load(f)
        batch_schema_id = batch_schema.get("$id", "")
        batch_resource = Resource.from_contents(batch_schema)
        registry = registry.with_resource(batch_schema_id, batch_resource)
    else:
        batch_schema = None

    # Load the manifest schema if present. Manifest fixtures are identified
    # by a "manifest-" filename prefix and validated against this schema
    # rather than the session/event schemas.
    manifest_schema_path = schema_path.parent / "manifest.json"
    if manifest_schema_path.exists():
        with open(manifest_schema_path) as f:
            manifest_schema = json.load(f)
        manifest_schema_id = manifest_schema.get("$id", "")
        manifest_resource = Resource.from_contents(manifest_schema)
        registry = registry.with_resource(manifest_schema_id, manifest_resource)
        manifest_validator = Draft202012Validator(manifest_schema, registry=registry)
    else:
        manifest_validator = None

    validator = Draft202012Validator(schema, registry=registry)
    return schema, event_schema, batch_schema, validator, manifest_validator, registry


def load_test_file(path):
    """Load a JSON test file."""
    with open(path) as f:
        return json.load(f)


def is_standalone_event(data):
    """Check if the test file is a standalone event envelope (document_type 'event').

    Dispatch follows the document_type discriminator (section 7.1). A document
    without document_type is treated as a session - the consumer rule for
    pre-0.1 documents - even when an 'event' key is present.
    """
    return data.get("document_type") == "event"


def is_event_batch(data):
    """Check if the test file is an event batch envelope (document_type 'event_batch')."""
    return data.get("document_type") == "event_batch"


def is_manifest_fixture(path):
    """Check if the test file is a manifest fixture (filename starts with 'manifest-')."""
    return path.name.startswith("manifest-")


def validate_standalone_event(data, session_schema, event_schema, registry):
    """Validate a standalone event against the event envelope schema.

    If the event envelope schema (telemetry-event.json) is available,
    validates the full envelope. Otherwise falls back to validating
    just the event body against the TelemetryEvent definition.
    """
    if event_schema is not None:
        validator = Draft202012Validator(event_schema, registry=registry)
        errors = list(validator.iter_errors(data))
    else:
        schema_id = session_schema.get("$id", "")
        wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
        validator = Draft202012Validator(wrapper, registry=registry)
        errors = list(validator.iter_errors(data["event"]))
    return errors


def validate_event_batch(data, session_schema, batch_schema, registry):
    """Validate an event batch against the batch envelope schema.

    If the batch envelope schema (telemetry-event-batch.json) is available,
    validates the full envelope. Otherwise falls back to validating each
    event body against the TelemetryEvent definition.
    """
    if batch_schema is not None:
        validator = Draft202012Validator(batch_schema, registry=registry)
        return list(validator.iter_errors(data))
    schema_id = session_schema.get("$id", "")
    wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
    validator = Draft202012Validator(wrapper, registry=registry)
    errors = []
    for event in data.get("events", []):
        errors.extend(validator.iter_errors(event))
    return errors


def check_privacy_conformance(data):
    """
    Check application-layer privacy conformance rules.

    Returns a list of violation descriptions, empty if conforming.
    """
    violations = []
    events = data.get("events", [])

    for event in events:
        turn = event.get("turn")
        if turn is None:
            continue

        privacy = turn.get("privacy_level")
        if privacy is None:
            continue

        forbidden = PRIVACY_FORBIDDEN_FIELDS.get(privacy, set())
        for field in forbidden:
            if field in turn and turn[field] is not None:
                violations.append(
                    f"Field '{field}' present on turn with privacy_level '{privacy}'"
                )

    return violations


def _iter_events(data):
    """Yield the content/turn events in a document, whether it is a session
    (events list) or a standalone envelope (single event under 'event')."""
    if is_standalone_event(data):
        event = data.get("event")
        if isinstance(event, dict):
            yield event
    else:
        yield from data.get("events", [])


def check_content_identifier(data):
    """
    Check that every content event carries content_url or content_id
    (section 5.7.5). Returns a list of violation descriptions.
    """
    violations = []
    for event in _iter_events(data):
        if event.get("type") not in CONTENT_EVENT_TYPES:
            continue
        if not event.get("content_url") and not event.get("content_id"):
            violations.append(
                f"Content event '{event.get('type')}' carries neither "
                "content_url nor content_id"
            )
    return violations


def check_session_or_ctx_token(data):
    """
    Check that a standalone event or event batch envelope carries session_id
    or ctx_token (sections 5.7.5, 7.1). The rule applies at Grounding
    conformance and above; Retrieval-level content_retrieved events are
    exempt. Session documents always satisfy this: session_id is required at
    the top level by the schema. Returns a list of violations.
    """
    if is_standalone_event(data):
        kind = "Standalone event"
        types = {(data.get("event") or {}).get("type")}
    elif is_event_batch(data):
        kind = "Event batch"
        types = {e.get("type") for e in data.get("events", [])}
    else:
        return []
    if types <= {"content_retrieved"}:
        return []  # Retrieval level - below the Grounding+ threshold for this rule
    if not data.get("session_id") and not data.get("ctx_token"):
        return [f"{kind} envelope carries neither session_id nor ctx_token"]
    return []


def check_application_layer(data):
    """Run every application-layer conformance rule and return all violations."""
    return (
        check_privacy_conformance(data)
        + check_content_identifier(data)
        + check_session_or_ctx_token(data)
    )


def check_manifest_application_layer(data):
    """
    Check the manifest rejection rules of section 8.7 that JSON Schema cannot
    express: duplicate keys[].id values, and domains entries that are not the
    manifest's own host or a subdomain of it (section 8.6).
    Returns a list of violation descriptions.
    """
    violations = []

    seen = set()
    for key in data.get("keys", []):
        kid = key.get("id")
        if kid in seen:
            violations.append(f"Duplicate keys[].id '{kid}'")
        seen.add(kid)

    host = urlparse(data.get("id", "")).hostname
    if host:
        for entry in data.get("domains", []):
            bare = entry[2:] if entry.startswith("*.") else entry
            if bare != host and not bare.endswith("." + host):
                violations.append(
                    f"domains entry '{entry}' is not the manifest host "
                    f"'{host}' or a subdomain of it"
                )

    return violations


def run_tests():
    """Run all conformance tests and return (passed, failed, results)."""
    tests_dir = Path(__file__).parent
    schema_path = tests_dir.parent / "telemetry-session.json"
    valid_dir = tests_dir / "valid"
    invalid_dir = tests_dir / "invalid"

    schema, event_schema, batch_schema, session_validator, manifest_validator, registry = load_schema(schema_path)

    results = []
    passed = 0
    failed = 0

    # --- Valid tests: must pass JSON Schema ---
    print("=" * 60)
    print("VALID tests (must pass JSON Schema validation)")
    print("=" * 60)

    for path in sorted(valid_dir.glob("*.json")):
        data = load_test_file(path)
        name = path.name
        desc = data.get("_test_description", "")

        if is_manifest_fixture(path):
            if manifest_validator is None:
                print(f"  FAIL  {name}")
                print("        manifest.json schema not found alongside telemetry-session.json")
                failed += 1
                results.append((name, False, "manifest schema missing"))
                continue
            errors = list(manifest_validator.iter_errors(data))
        elif is_event_batch(data):
            # Event batches validate against the batch envelope schema
            errors = validate_event_batch(data, schema, batch_schema, registry)
        elif is_standalone_event(data):
            # Standalone events validate against event envelope schema
            errors = validate_standalone_event(data, schema, event_schema, registry)
        else:
            errors = list(session_validator.iter_errors(data))

        # Valid fixtures must also satisfy the application-layer rules that
        # schema validation cannot express (sections 5.7.5 and 8.7).
        app_violations = (
            check_manifest_application_layer(data)
            if is_manifest_fixture(path)
            else check_application_layer(data)
        )

        if not errors and not app_violations:
            print(f"  PASS  {name}")
            passed += 1
            results.append((name, True, None))
        elif errors:
            msg = "; ".join(e.message for e in errors[:3])
            print(f"  FAIL  {name}")
            print(f"        {msg}")
            failed += 1
            results.append((name, False, msg))
        else:
            msg = "; ".join(app_violations[:3])
            print(f"  FAIL  {name}")
            print(f"        Application-layer violation: {msg}")
            failed += 1
            results.append((name, False, msg))

    print()

    # --- Invalid tests: must fail JSON Schema OR application-layer ---
    print("=" * 60)
    print("INVALID tests (must fail validation)")
    print("=" * 60)

    for path in sorted(invalid_dir.glob("*.json")):
        data = load_test_file(path)
        name = path.name
        desc = data.get("_test_description", "")

        is_app_layer = name in APPLICATION_LAYER_VIOLATIONS

        if is_manifest_fixture(path):
            if manifest_validator is None:
                print(f"  FAIL  {name}")
                print("        manifest.json schema not found alongside telemetry-session.json")
                failed += 1
                results.append((name, False, "manifest schema missing"))
                continue
            schema_errors = list(manifest_validator.iter_errors(data))
        elif is_event_batch(data):
            schema_errors = validate_event_batch(data, schema, batch_schema, registry)
        elif is_standalone_event(data):
            schema_errors = validate_standalone_event(data, schema, event_schema, registry)
        else:
            schema_errors = list(session_validator.iter_errors(data))

        if schema_errors:
            # Failed JSON Schema - good
            msg = schema_errors[0].message
            print(f"  PASS  {name}")
            print(f"        Schema error: {msg}")
            passed += 1
            results.append((name, True, None))

        elif is_app_layer:
            # Passes JSON Schema but should fail conformance
            conformance_violations = (
                check_manifest_application_layer(data)
                if is_manifest_fixture(path)
                else check_application_layer(data)
            )
            if conformance_violations:
                print(f"  PASS  {name}  [application-layer]")
                print(f"        {APPLICATION_LAYER_VIOLATIONS[name]}")
                passed += 1
                results.append((name, True, None))
            else:
                print(f"  FAIL  {name}")
                print(f"        Expected application-layer violation but none found")
                failed += 1
                results.append((name, False, "Expected conformance violation"))

        else:
            # Should have failed schema but didn't
            print(f"  FAIL  {name}")
            print(f"        Expected schema validation error but file validated OK")
            failed += 1
            results.append((name, False, "Expected schema error"))

    # --- Summary ---
    total = passed + failed
    print()
    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} passed, {failed}/{total} failed")
    print("=" * 60)

    return passed, failed, results


if __name__ == "__main__":
    passed, failed, results = run_tests()
    sys.exit(0 if failed == 0 else 1)
