#!/usr/bin/env python3
"""
Conformance test runner for Content Telemetry Specification v1.

Validates JSON test fixtures against telemetry-session.json, telemetry-event.json,
telemetry-event-batch.json, manifest.json, and application-layer conformance rules
that JSON Schema cannot express. Fixtures whose filename starts with "manifest-"
are validated against manifest.json; all others dispatch on the document_type
discriminator (section 7.1): "event" validates as a standalone event envelope,
"event_batch" as an event batch envelope, and "session" or absent as a session
document.

Usage:
    pip install "jsonschema[format-nongpl]"
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
    print('ERROR: jsonschema package required. Install with: pip install "jsonschema[format-nongpl]"')
    sys.exit(1)

# Format assertions (uuid, date-time, uri) are annotation-only unless a
# FormatChecker is attached to the validator. Every validator constructed in
# this suite MUST pass format_checker=FORMAT_CHECKER; guard at startup so a
# missing optional dependency (rfc3339-validator) hard-errors instead of
# silently downgrading every format assertion to a no-op.
FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER
_missing_formats = {"uuid", "date-time"} - set(FORMAT_CHECKER.checkers)
if _missing_formats:
    print(
        "ERROR: format checker cannot enforce "
        + ", ".join(sorted(_missing_formats))
        + '. Install with: pip install "jsonschema[format-nongpl]"'
    )
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
#      present. Only query_tokens, response_tokens and content_urls are allowed.
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
# 5. Grounding provenance and fingerprint migration (sections 5.7.5, 6.4, 12.1):
#    agent_fetched requires cached false; agent_cached requires cached true.
#    content_fingerprint MUST NOT carry preserved_in_output: v1 defines no
#    output-side reuse reporting.
#
# 6. Referential integrity within a session document (sections 6.6-6.7):
#    content_engaged.presentation_id references the exact content_presented
#    event id, and citation_id on content_presented
#    references a content_cited event id. JSON Schema cannot compare values
#    across events. Session documents only: standalone envelopes and batch
#    members may reference events delivered elsewhere.
#
# 7. Field placement and source_role (sections 5.2, 5.2.2, 5.7.1, 5.7.5):
#    source_role is required on content_retrieved; presentation_id and the
#    event-level ctx_token appear only on content_engaged, citation_id only on
#    content_presented, turn only on turn events.
#
# 8. Session-document integrity beyond rule 6 (sections 6.6, 6.7, 7.4.1):
#    event ids are distinct; the engagement and the presentation it references,
#    and the presentation and the citation it references, identify
#    the same content; one event-level ctx_token binds to one presentation.
#
# 9. Envelope ctx_token (section 7.1): an envelope carrying ctx_token carries
#    content_engaged events only.
#
# 10. Manifest placement rules (sections 8.5, 8.6): domains only on a manifest
#    served at the domain root; ctx_resolution only on agent/platform manifests.
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
    "privacy-violation-response-text-at-minimal.json": (
        "Turn at minimal privacy includes response_text. "
        "Violates section 5.5: response text MUST NOT be present at minimal level."
    ),
    "privacy-violation-query-intent-at-minimal.json": (
        "Turn at minimal privacy includes query_intent. "
        "Violates section 5.5: intent classification MUST NOT be present at minimal level."
    ),
    "privacy-violation-topics-at-minimal.json": (
        "Turn at minimal privacy includes topics. "
        "Violates section 5.5: topics MUST NOT be present at minimal level."
    ),
    "privacy-violation-response-type-at-minimal.json": (
        "Turn at minimal privacy includes response_type. "
        "Violates section 5.5: response classification MUST NOT be present at minimal level."
    ),
    "privacy-violation-response-mode-at-minimal.json": (
        "Turn at minimal privacy includes response_mode. "
        "Violates section 5.5: platform metadata MUST NOT be present at minimal level."
    ),
    "privacy-violation-model-id-at-minimal.json": (
        "Turn at minimal privacy includes model_id. "
        "Violates section 5.5: platform metadata MUST NOT be present at minimal level."
    ),
    "content-event-missing-identifier.json": (
        "content_grounded event has neither content_url nor content_id. "
        "Violates section 5.7.5: every content event MUST carry at least one."
    ),
    "presented-missing-identifier.json": (
        "content_presented event has neither content_url nor content_id. "
        "Violates section 5.7.5: every content event MUST carry at least one."
    ),
    "retrieved-missing-identifier.json": (
        "content_retrieved event has neither content_url nor content_id. "
        "Violates section 5.7.5: every content event MUST carry at least one."
    ),
    "engaged-missing-identifier.json": (
        "content_engaged event has neither content_url nor content_id. "
        "Violates section 5.7.5: every content event MUST carry at least one."
    ),
    "engaged-presentation-id-unmatched.json": (
        "content_engaged.presentation_id matches no content_presented event id "
        "in the session. Violates section 6.7: every engagement references the "
        "exact content_presented.id on which the action occurred."
    ),
    "presented-citation-id-unmatched.json": (
        "content_presented.citation_id matches no content_cited event id in "
        "the session. Violates section 6.7: citation_id references the "
        "presented content_cited event's id."
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
    "withdrawn-ip-hash.json": (
        "Retrieval event carries ip_hash in data. "
        "Violates section 9.1: the field was withdrawn in v1 and emitters "
        "MUST NOT populate it."
    ),
    "grounding-fingerprint-preserved-in-output.json": (
        "Grounding fingerprint carries preserved_in_output. "
        "Violates section 6.4: v1 defines no output-side reuse reporting and the field is withdrawn (section 12.1)."
    ),
    "grounding-provenance-cached-conflict.json": (
        "Grounding event declares agent_fetched with cached true. "
        "Violates section 6.4: agent_fetched requires cached false."
    ),
    "grounding-provenance-cached-conflict-agent-cached.json": (
        "Grounding event declares agent_cached with cached false. "
        "Violates section 6.4: agent_cached requires cached true."
    ),
    "privacy-violation-response-text-at-intent.json": (
        "Turn at intent privacy includes response_text. "
        "Violates section 5.5: response_text MUST NOT be present at intent level."
    ),
    "privacy-violation-query-at-minimal-standalone.json": (
        "Standalone envelope turn at minimal privacy includes query_text. "
        "Violates section 5.5: the gate applies wherever turns are emitted."
    ),
    "privacy-violation-query-at-minimal-batch.json": (
        "Batch member turn at minimal privacy includes query_text. "
        "Violates section 5.5: the gate applies wherever turns are emitted."
    ),
    "grounded-missing-identifier-standalone.json": (
        "Standalone content_grounded event has neither content_url nor content_id. "
        "Violates section 5.7.5 in the standalone envelope shape."
    ),
    "grounded-missing-identifier-batch.json": (
        "Batch member content_grounded event has neither content_url nor content_id. "
        "Violates section 5.7.5 in the event batch shape."
    ),
    "withdrawn-ip-hash-session.json": (
        "Session document retrieval event carries ip_hash in data. "
        "Violates section 9.1 in the session document shape."
    ),
    "withdrawn-ip-hash-batch.json": (
        "Batch member retrieval event carries ip_hash in data. "
        "Violates section 9.1 in the event batch shape."
    ),
    "retrieved-missing-source-role.json": (
        "content_retrieved event carries no source_role. "
        "Violates sections 5.2.2 and 5.7.1: source_role MUST be set on every retrieval."
    ),
    "ctx-token-on-grounded.json": (
        "Event-level ctx_token on a content_grounded event. "
        "Violates section 5.2: ctx_token is valid only on content_engaged."
    ),
    "citation-id-on-grounded.json": (
        "citation_id on a content_grounded event. "
        "Violates section 5.2: citation_id is valid only on content_presented."
    ),
    "presentation-id-on-cited.json": (
        "presentation_id on a content_cited event. "
        "Violates section 5.2: presentation_id is valid only on content_engaged."
    ),
    "turn-on-content-event.json": (
        "turn object on a content_grounded event. "
        "Violates section 5.2: turn data is carried on turn_started and turn_completed only."
    ),
    "duplicate-event-id.json": (
        "Two content_presented events share one id. "
        "Violates section 6.6: repeated presentations receive distinct event IDs."
    ),
    "engaged-presentation-content-mismatch.json": (
        "content_engaged references a content_presented event of different content. "
        "Violates section 6.7: the engagement identifies the same content as the presentation it acted on."
    ),
    "presented-citation-content-mismatch.json": (
        "content_presented.citation_id references a content_cited event of different content. "
        "Violates section 6.6: the presentation and the citation it realises identify the same content."
    ),
    "engaged-presentation-id-no-presentations.json": (
        "content_engaged carries a presentation_id in a session with no content_presented events. "
        "Violates section 6.7: every engagement references an exact presentation occurrence."
    ),
    "shared-ctx-token-two-presentations.json": (
        "One event-level ctx_token appears on engagements bound to two different presentations. "
        "Violates section 7.4.1: a token is bound to exactly one presentation occurrence."
    ),
    "standalone-ctx-token-non-engagement.json": (
        "Standalone envelope carries ctx_token with a content_grounded event. "
        "Violates section 7.1: an envelope ctx_token accompanies content_engaged events only."
    ),
    "batch-ctx-token-non-engagement.json": (
        "Event batch under ctx_token carries a content_grounded event. "
        "Violates section 7.1: an envelope ctx_token accompanies content_engaged events only."
    ),
    "batch-missing-session-mixed-retrieval.json": (
        "Event batch mixing a retrieval with a grounding event carries neither session_id nor ctx_token. "
        "Violates section 7.1: the retrieval-only exemption does not extend to a batch that carries other events."
    ),
    "manifest-domains-on-path-manifest.json": (
        "Manifest served under a path prefix carries domains. "
        "Violates section 8.6: domains MAY appear only on manifests served from the domain root."
    ),
    "manifest-ctx-resolution-on-content-owner.json": (
        "content_owner manifest declares telemetry.ctx_resolution. "
        "Violates section 8.5: ctx_resolution is valid on agent and platform manifests."
    ),
    "manifest-lookalike-domain.json": (
        "Manifest at example.com claims evilexample.com in domains. "
        "Violates section 8.6: a lookalike host is not a subdomain of the manifest host."
    ),
}

# V0.1 fields prohibited by the v1 migration rule (section 9.1). This is a
# compatibility check for the v1 transition, not a general registry of every
# field the specification may ever withdraw. The schemas cannot catch it:
# event `data` accepts additional properties by design.
V1_PROHIBITED_V0_1_EVENT_DATA_FIELDS = {
    "ip_hash": "prohibited by the v1 migration rule; hashing does not anonymise an IP address",
}

# Event types that carry content and therefore require an identifier
# (content_url or content_id) under section 5.7.5. turn_started and
# turn_completed are turn events, not content events, and are exempt.
CONTENT_EVENT_TYPES = {
    "content_retrieved", "content_grounded",
    "content_cited", "content_presented", "content_engaged",
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
        manifest_validator = Draft202012Validator(manifest_schema, registry=registry, format_checker=FORMAT_CHECKER)
    else:
        manifest_validator = None

    validator = Draft202012Validator(schema, registry=registry, format_checker=FORMAT_CHECKER)
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
        validator = Draft202012Validator(event_schema, registry=registry, format_checker=FORMAT_CHECKER)
        errors = list(validator.iter_errors(data))
    else:
        schema_id = session_schema.get("$id", "")
        wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
        validator = Draft202012Validator(wrapper, registry=registry, format_checker=FORMAT_CHECKER)
        errors = list(validator.iter_errors(data["event"]))
    return errors


def validate_event_batch(data, session_schema, batch_schema, registry):
    """Validate an event batch against the batch envelope schema.

    If the batch envelope schema (telemetry-event-batch.json) is available,
    validates the full envelope. Otherwise falls back to validating each
    event body against the TelemetryEvent definition.
    """
    if batch_schema is not None:
        validator = Draft202012Validator(batch_schema, registry=registry, format_checker=FORMAT_CHECKER)
        return list(validator.iter_errors(data))
    schema_id = session_schema.get("$id", "")
    wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
    validator = Draft202012Validator(wrapper, registry=registry, format_checker=FORMAT_CHECKER)
    errors = []
    for event in data.get("events", []):
        errors.extend(validator.iter_errors(event))
    return errors


def check_privacy_conformance(data):
    """
    Check application-layer privacy conformance rules.

    The privacy field gating of section 5.5 is a property of privacy_level
    itself: it applies wherever conversation turns are emitted - session
    documents, event batches, and standalone event envelopes alike.

    Returns a list of violation descriptions, empty if conforming.
    """
    violations = []

    for event in _iter_events(data):
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
    """Yield the content/turn events in a document, whatever its shape: a
    session or event batch (events list) or a standalone envelope (single
    event under 'event')."""
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


def check_referential_integrity(data):
    """
    Check the intra-document event references of a session document:

    - Every content_engaged.presentation_id MUST reference the exact
      content_presented.id on which the action occurred (section 6.7).
    - Every citation_id on a content_presented event
      references that content_cited event's id (section 6.6).

    Applies only to session documents, where the referenced events live in
    the same document. Standalone envelopes and batch members legitimately
    reference events delivered elsewhere (e.g. a click-out engagement carrying
    a ctx_token), so they are exempt here; the corroborating click-out flow
    is out of scope for this suite. Returns a list of violations.
    """
    if is_standalone_event(data) or is_event_batch(data):
        return []
    events = data.get("events", [])
    presented_ids = {
        e.get("id") for e in events
        if e.get("type") == "content_presented" and e.get("id")
    }
    cited_ids = {
        e.get("id") for e in events
        if e.get("type") == "content_cited" and e.get("id")
    }
    violations = []
    for event in events:
        etype = event.get("type")
        if etype == "content_engaged":
            pid = event.get("presentation_id")
            if pid and pid not in presented_ids:
                violations.append(
                    f"content_engaged presentation_id '{pid}' does not match "
                    "any content_presented event id in the session"
                )
        if etype == "content_presented":
            cid = event.get("citation_id")
            if cid and cid not in cited_ids:
                violations.append(
                    f"{etype} citation_id '{cid}' does not match any "
                    "content_cited event id in the session"
                )
    return violations


def check_v1_migration_prohibitions(data):
    """
    Check v1's explicit prohibitions on fields carried forward from v0.1.
    Returns a list of violation descriptions.
    """
    violations = []
    for event in _iter_events(data):
        event_data = event.get("data")
        if not isinstance(event_data, dict):
            continue
        for field, reason in V1_PROHIBITED_V0_1_EVENT_DATA_FIELDS.items():
            if field in event_data:
                violations.append(
                    f"Event '{event.get('type')}' carries '{field}' in data ({reason})"
                )
    return violations


def check_grounding_provenance(data):
    """Check the provenance/cached pairings required by section 6.4."""
    violations = []
    for event in _iter_events(data):
        if event.get("type") != "content_grounded":
            continue
        event_data = event.get("data")
        if not isinstance(event_data, dict):
            continue
        provenance = event_data.get("provenance")
        cached = event_data.get("cached")
        if provenance == "agent_fetched" and cached is not False:
            violations.append("content_grounded with agent_fetched does not carry cached false")
        if provenance == "agent_cached" and cached is not True:
            violations.append("content_grounded with agent_cached does not carry cached true")
        fingerprint = event_data.get("content_fingerprint")
        if isinstance(fingerprint, dict) and "preserved_in_output" in fingerprint:
            violations.append(
                "content_fingerprint carries preserved_in_output; withdrawn in v1"
            )
    return violations


# Fields that belong to one event type (section 5.2). A key present with a
# non-null value on any other type is a placement violation.
FIELD_PLACEMENT = {
    "presentation_id": {"content_engaged"},
    "ctx_token": {"content_engaged"},
    "citation_id": {"content_presented"},
    "turn": {"turn_started", "turn_completed"},
}


def check_field_placement(data):
    """Check source_role on retrievals (sections 5.2.2, 5.7.1) and the
    event-type scoping of presentation_id, ctx_token, citation_id and turn
    (section 5.2). Applies to every document shape."""
    violations = []
    for event in _iter_events(data):
        etype = event.get("type")
        if etype == "content_retrieved" and not event.get("source_role"):
            violations.append("content_retrieved event carries no source_role")
        for field, allowed in FIELD_PLACEMENT.items():
            if event.get(field) is not None and etype not in allowed:
                violations.append(
                    f"Field '{field}' present on '{etype}' event; valid only on "
                    + ", ".join(sorted(allowed))
                )
    return violations


def _same_content(a, b):
    """Two events identify the same content unless a shared identifier field
    (content_id or content_url) carries different non-null values."""
    for field in ("content_id", "content_url"):
        x, y = a.get(field), b.get(field)
        if x is not None and y is not None and x != y:
            return False
    return True


def check_session_integrity(data):
    """Session-document rules beyond check_referential_integrity (sections
    6.6, 6.7, 7.4.1): distinct event ids; engagement/presentation and
    presentation/citation pairs identify the same content; one
    event-level ctx_token binds to one presentation. Session documents only."""
    if is_standalone_event(data) or is_event_batch(data):
        return []
    events = data.get("events", [])
    violations = []
    seen_ids = set()
    for e in events:
        eid = e.get("id")
        if eid:
            if eid in seen_ids:
                violations.append(f"Duplicate event id '{eid}' in session")
            seen_ids.add(eid)
    presented = {e.get("id"): e for e in events if e.get("type") == "content_presented" and e.get("id")}
    cited = {e.get("id"): e for e in events if e.get("type") == "content_cited" and e.get("id")}
    token_binding = {}
    for e in events:
        etype = e.get("type")
        if etype == "content_engaged":
            pid = e.get("presentation_id")
            if pid in presented and not _same_content(e, presented[pid]):
                violations.append(
                    f"content_engaged references presentation '{pid}' but identifies different content"
                )
            token = e.get("ctx_token")
            if token and pid:
                bound = token_binding.setdefault(token, pid)
                if bound != pid:
                    violations.append(
                        f"ctx_token '{token}' appears on engagements bound to two presentations"
                    )
        if etype == "content_presented":
            cid = e.get("citation_id")
            if cid in cited and not _same_content(e, cited[cid]):
                violations.append(
                    f"{etype} references citation '{cid}' but identifies different content"
                )
    return violations


def check_envelope_ctx_token(data):
    """An envelope ctx_token accompanies content_engaged events only (section
    7.1); any other event type on such an envelope needs session_id instead."""
    if not (is_standalone_event(data) or is_event_batch(data)):
        return []
    if not data.get("ctx_token"):
        return []
    violations = []
    for event in _iter_events(data):
        etype = event.get("type")
        if etype != "content_engaged":
            violations.append(
                f"Envelope ctx_token accompanies a '{etype}' event; ctx_token is carried only for content_engaged"
            )
    return violations


def check_application_layer(data):
    """Run every application-layer conformance rule and return all violations."""
    return (
        check_privacy_conformance(data)
        + check_content_identifier(data)
        + check_session_or_ctx_token(data)
        + check_referential_integrity(data)
        + check_v1_migration_prohibitions(data)
        + check_grounding_provenance(data)
        + check_field_placement(data)
        + check_session_integrity(data)
        + check_envelope_ctx_token(data)
    )


def check_manifest_application_layer(data):
    """
    Check the manifest rejection rules that JSON Schema cannot express:
    duplicate keys[].id values (section 8.7), domains entries that are not the
    manifest's own host or a subdomain of it, domains on a path-prefixed
    manifest (section 8.6), and ctx_resolution on a manifest without the agent
    or platform role (section 8.5). Returns a list of violation descriptions.
    """
    violations = []

    seen = set()
    for key in data.get("keys", []):
        kid = key.get("id")
        if kid in seen:
            violations.append(f"Duplicate keys[].id '{kid}'")
        seen.add(kid)

    parsed = urlparse(data.get("id", ""))
    host = parsed.hostname
    if host:
        for entry in data.get("domains", []):
            bare = entry[2:] if entry.startswith("*.") else entry
            if bare != host and not bare.endswith("." + host):
                violations.append(
                    f"domains entry '{entry}' is not the manifest host "
                    f"'{host}' or a subdomain of it"
                )

    # domains only on a root manifest (section 8.6)
    if "domains" in data and parsed.path != "/.well-known/content-telemetry.json":
        violations.append(
            f"domains present on a manifest served under a path prefix "
            f"('{parsed.path}'); only root manifests carry domains"
        )

    # ctx_resolution only on agent/platform manifests (section 8.5)
    telemetry = data.get("telemetry") or {}
    roles = set(data.get("roles") or [])
    if telemetry.get("ctx_resolution") and not roles & {"agent", "platform"}:
        violations.append(
            f"telemetry.ctx_resolution on a manifest with roles {sorted(roles)}; "
            "valid on agent and platform manifests"
        )

    return violations


def schema_error_haystack(errors):
    """
    Render the first schema error (deterministically chosen) as searchable
    text: its JSON pointer plus its message, recursing into sub-errors of
    combinators like anyOf. Invalid fixtures pin their intended violation by
    requiring an _expected_error substring to appear in this text.
    """
    first = sorted(
        errors,
        key=lambda e: ([str(p) for p in e.absolute_path], e.message),
    )[0]
    parts = []

    def walk(error):
        pointer = "/" + "/".join(str(p) for p in error.absolute_path)
        parts.append(pointer)
        parts.append(error.message)
        for sub in error.context or []:
            walk(sub)

    walk(first)
    return " ".join(parts)


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
        expected_error = data.get("_expected_error")

        is_app_layer = name in APPLICATION_LAYER_VIOLATIONS

        # Every invalid fixture must pin its intended violation: a substring
        # that must appear in the actual error. Without it, a fixture that
        # fails for the wrong reason (e.g. after an unrelated edit) would
        # still count as a pass.
        if not isinstance(expected_error, str) or not expected_error:
            print(f"  FAIL  {name}")
            print("        Fixture missing required _expected_error field")
            failed += 1
            results.append((name, False, "missing _expected_error"))
            continue

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
            # Failed JSON Schema - but only for the pinned reason
            haystack = schema_error_haystack(schema_errors)
            if expected_error in haystack:
                print(f"  PASS  {name}")
                print(f"        Schema error: {schema_errors[0].message}")
                passed += 1
                results.append((name, True, None))
            else:
                print(f"  FAIL  {name}")
                print(f"        Schema error does not match _expected_error {expected_error!r}")
                print(f"        Actual: {haystack[:200]}")
                failed += 1
                results.append((name, False, "wrong schema error"))

        elif is_app_layer:
            # Passes JSON Schema but should fail conformance
            conformance_violations = (
                check_manifest_application_layer(data)
                if is_manifest_fixture(path)
                else check_application_layer(data)
            )
            haystack = "; ".join(conformance_violations)
            if not conformance_violations:
                print(f"  FAIL  {name}")
                print(f"        Expected application-layer violation but none found")
                failed += 1
                results.append((name, False, "Expected conformance violation"))
            elif expected_error not in haystack:
                print(f"  FAIL  {name}")
                print(f"        Violation does not match _expected_error {expected_error!r}")
                print(f"        Actual: {haystack[:200]}")
                failed += 1
                results.append((name, False, "wrong conformance violation"))
            else:
                print(f"  PASS  {name}  [application-layer]")
                print(f"        {APPLICATION_LAYER_VIOLATIONS[name]}")
                passed += 1
                results.append((name, True, None))

        else:
            # Should have failed schema but didn't
            print(f"  FAIL  {name}")
            print(f"        Expected schema validation error but file validated OK")
            failed += 1
            results.append((name, False, "Expected schema error"))

    # --- Reconcile APPLICATION_LAYER_VIOLATIONS against invalid/ ---
    # A dict key with no matching fixture file means an expectation silently
    # dropped out of the suite (e.g. a renamed fixture). Fail the run.
    invalid_names = {p.name for p in invalid_dir.glob("*.json")}
    for name in sorted(set(APPLICATION_LAYER_VIOLATIONS) - invalid_names):
        print(f"  FAIL  {name}")
        print("        APPLICATION_LAYER_VIOLATIONS entry has no matching file in invalid/")
        failed += 1
        results.append((name, False, "orphaned APPLICATION_LAYER_VIOLATIONS entry"))

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
