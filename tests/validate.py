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
    uv run --locked python tests/validate.py
"""

import base64
import binascii
import copy
import hashlib
import ipaddress
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlsplit

import check_survivability
from check_registry import check_registry_and_matrix

try:
    import rfc8785
    from jsonschema import Draft202012Validator, FormatChecker, ValidationError
    from referencing import Registry, Resource
except ImportError:
    print("ERROR: jsonschema and rfc8785 packages required. Install with: pip install jsonschema rfc8785")
    sys.exit(1)

MAX_INLINE_ENCODED_CHARS = 11_184_812
MAX_INLINE_DECODED_BYTES = 8 * 1024 * 1024
MAX_ENTRY_DECODED_BYTES = 16 * 1024 * 1024
MAX_EVENT_DECODED_BYTES = 32 * 1024 * 1024


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
# 5. Evidence-tier application rules (section 5.8): assertion pointers and
#    digests, subject binding, tier-specific artifacts, and fingerprint profile
#    binding. These checks deliberately validate only local deterministic
#    structure; they never retrieve artifacts or perform cryptography.

# Not checked here: agent_id at Grounding/Citation conformance (section
# 5.7) depends on the emitter's declared conformance level, which fixtures do
# not carry, so it is out of scope for the fixture suite.
# ---------------------------------------------------------------------------

# Files in invalid/ that pass JSON Schema but fail application-layer rules,
# mapped to descriptions of their conformance violations.
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
    "standalone-privacy-query-at-minimal.json": (
        "Standalone turn at minimal privacy includes query_text. "
        "Violates section 5.5 identically to session delivery."
    ),
    "standalone-privacy-ad-rendered-at-minimal.json": (
        "Standalone turn at minimal privacy includes ad_rendered. "
        "Violates section 5.5 identically to session delivery."
    ),
    "standalone-privacy-query-at-intent.json": (
        "Standalone turn at intent privacy includes query_text. "
        "Violates section 5.5 identically to session delivery."
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
    "evidence-unresolved-assertion-path.json": (
        "Evidence assertion_path does not resolve within its containing event."
    ),
    "evidence-targets-evidence.json": (
        "Evidence assertion_path targets the event evidence array."
    ),
    "evidence-tier-above-claim-missing-event-id.json": (
        "Evidence above claim requires an id on the containing event."
    ),
    "evidence-assertion-digest-mismatch.json": (
        "Evidence assertion_digest does not bind the resolved assertion and subjects."
    ),
    "evidence-detected-subject-mismatch.json": (
        "Fingerprint detection evidence does not bind data.content_hash."
    ),
    "evidence-preserved-missing-grounded-subject.json": (
        "Output-preservation evidence omits the grounded_content subject."
    ),
    "evidence-preserved-missing-output-subject.json": (
        "Output-preservation evidence omits the generated_output subject."
    ),
    "evidence-tier2-retrieval-for-grounding.json": (
        "Retrieval/access evidence alone cannot corroborate grounding."
    ),
    "evidence-tier2-access-for-detection.json": (
        "Retrieval/access evidence alone cannot corroborate fingerprint detection."
    ),
    "evidence-tier3-missing-attestation.json": (
        "Tier 3 evidence omits a verifier_attestation artifact."
    ),
    "evidence-tier3-missing-timestamp.json": (
        "Tier 3 evidence omits a trusted_timestamp artifact."
    ),
    "evidence-fingerprint-profile-missing-digest.json": (
        "Fingerprint evidence above claim uses an unbound scheme profile reference."
    ),
    "evidence-conflict-does-not-upgrade.json": (
        "A conflicting evidence entry is a mismatch and cannot upgrade its assertion."
    ),
    "evidence-inline-digest-mismatch.json": (
        "Inline artifact digest does not match its strictly decoded bytes."
    ),
    "evidence-inline-malformed-base64.json": (
        "Inline artifact content is not strict base64."
    ),
    "evidence-preservation-wrong-occurrence.json": (
        "Preservation evidence was copied from a different event occurrence."
    ),
    "evidence-scheme-verification-profile-mismatch.json": (
        "Fingerprint scheme profile does not match the selected verification profile."
    ),
    "evidence-tier2-missing-origin-access.json": (
        "Tier 2 evidence omits both an origin_event and access_record."
    ),
    "evidence-tier2-irrelevant-grounding-artifact.json": (
        "An irrelevant extension artifact does not corroborate grounding."
    ),
    "evidence-tier2-irrelevant-detection-artifact.json": (
        "An irrelevant extension artifact does not corroborate fingerprint detection."
    ),
    "evidence-tier2-attestation-selector-missing.json": (
        "Sensitive Tier 2 evidence omits its verifier_attestation digest selector."
    ),
    "evidence-tier2-attestation-selector-wrong-type.json": (
        "Sensitive Tier 2 evidence selects origin material instead of an attestation."
    ),
    "evidence-tier2-attestation-selector-ambiguous.json": (
        "Sensitive Tier 2 evidence ambiguously selects two attestations by digest."
    ),
    "evidence-conflicting-event-occurrences.json": (
        "Two different occurrences reuse the same event id in one delivery."
    ),
    "evidence-tier3-fingerprint-content-borne-false.json": (
        "Tier 3 fingerprint evidence exceeds a false content_borne capability."
    ),
    "evidence-tier3-fingerprint-identity-false.json": (
        "Tier 3 fingerprint evidence exceeds a false identity_bearing capability."
    ),
    "evidence-tier3-fingerprint-verifiable-false.json": (
        "Tier 3 fingerprint evidence exceeds a false verifiable capability."
    ),
    "evidence-tier3-timestamp-selects-attestation.json": (
        "The timestamp selector names an attestation rather than a timestamp artifact."
    ),
    "evidence-uri-only-non-upgrade.json": (
        "An unretrieved URI-only artifact cannot raise the effective tier."
    ),
    "evidence-uri-relative.json": (
        "Artifact reference is relative rather than absolute."
    ),
    "evidence-preservation-requires-detection.json": (
        "Above-claim preservation evidence cannot establish preservation when "
        "the same fingerprint was not detected."
    ),
    "evidence-uri-credentials.json": (
        "Artifact reference embeds credentials."
    ),
    "evidence-uri-loopback.json": (
        "Artifact reference targets a loopback address."
    ),
    "evidence-uri-link-local.json": (
        "Artifact reference targets a link-local address."
    ),
    "evidence-uri-private.json": (
        "Artifact reference targets a private address."
    ),
}

# New security regression fixtures pin the exact conformance rule they defend.
# This prevents an unrelated digest/profile error from making a blocker fixture
# appear green after its intended check has regressed.
EXPECTED_APPLICATION_VIOLATION_FRAGMENTS = {
    "privacy-violation-query-at-minimal.json": "Field 'query_text' present",
    "privacy-violation-ad-rendered-at-minimal.json": "Field 'ad_rendered' present",
    "privacy-violation-query-at-intent.json": "Field 'query_text' present",
    "standalone-privacy-query-at-minimal.json": "Field 'query_text' present",
    "standalone-privacy-ad-rendered-at-minimal.json": "Field 'ad_rendered' present",
    "standalone-privacy-query-at-intent.json": "Field 'query_text' present",
    "content-event-missing-identifier.json": "neither content_url nor content_id",
    "standalone-missing-session-and-ctx-token.json": "neither session_id nor ctx_token",
    "batch-missing-session-and-ctx-token.json": "neither session_id nor ctx_token",
    "manifest-duplicate-key-id.json": "Duplicate keys[].id",
    "manifest-foreign-domain.json": "is not the manifest host",
    "evidence-unresolved-assertion-path.json": "is unresolved",
    "evidence-targets-evidence.json": "targets evidence",
    "evidence-tier-above-claim-missing-event-id.json": "without an event id",
    "evidence-tier2-retrieval-for-grounding.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier2-access-for-detection.json": "does not select exactly one verifier_attestation artifact",
    "evidence-conflicting-event-occurrences.json": "conflicting occurrence digests",
    "evidence-assertion-digest-mismatch.json": "assertion_digest mismatch",
    "evidence-conflict-does-not-upgrade.json": "assertion_digest mismatch",
    "evidence-detected-subject-mismatch.json": "no grounded_content subject matching",
    "evidence-fingerprint-profile-missing-digest.json": "has no digest-bound scheme profile",
    "evidence-preserved-missing-grounded-subject.json": "no grounded_content subject matching",
    "evidence-preserved-missing-output-subject.json": "omits generated_output subject",
    "evidence-tier3-missing-attestation.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier3-missing-timestamp.json": "does not select exactly one trusted_timestamp artifact",
    "evidence-inline-digest-mismatch.json": "artifact[0] digest mismatch",
    "evidence-inline-malformed-base64.json": "malformed base64 content",
    "evidence-preservation-wrong-occurrence.json": "assertion_digest mismatch",
    "evidence-scheme-verification-profile-mismatch.json": "verification profile scheme digest does not match",
    "evidence-tier2-missing-origin-access.json": "omits origin_event or access_record",
    "evidence-tier2-irrelevant-grounding-artifact.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier2-irrelevant-detection-artifact.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier2-attestation-selector-missing.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier2-attestation-selector-wrong-type.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier2-attestation-selector-ambiguous.json": "does not select exactly one verifier_attestation artifact",
    "evidence-tier3-fingerprint-content-borne-false.json": "exceeds the fingerprint scheme capability ceiling",
    "evidence-tier3-fingerprint-identity-false.json": "exceeds the fingerprint scheme capability ceiling",
    "evidence-tier3-fingerprint-verifiable-false.json": "exceeds the fingerprint scheme capability ceiling",
    "evidence-tier3-timestamp-selects-attestation.json": "does not select exactly one trusted_timestamp artifact",
    "evidence-uri-only-non-upgrade.json": "URI bytes were not retrieved and digest-verified",
    "evidence-uri-relative.json": "allowed https scheme",
    "evidence-preservation-requires-detection.json": (
        "cannot establish preservation when detected is not true"
    ),
    "evidence-uri-credentials.json": "contains credentials",
    "evidence-uri-loopback.json": "disallowed IP address",
    "evidence-uri-link-local.json": "disallowed IP address",
    "evidence-uri-private.json": "disallowed IP address",
}

# Event types that carry content and therefore require an identifier
# (content_url or content_id) under section 5.7.5. turn_started and
# turn_completed are turn events, not content events, and are exempt.
CONTENT_EVENT_TYPES = {
    "content_retrieved", "content_grounded", "content_cited",
    "content_displayed", "content_engaged",
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
        manifest_validator = Draft202012Validator(manifest_schema, registry=registry, format_checker=FormatChecker())
    else:
        manifest_validator = None

    validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
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
        validator = Draft202012Validator(event_schema, registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(data))
    else:
        schema_id = session_schema.get("$id", "")
        wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
        validator = Draft202012Validator(wrapper, registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(data["event"]))
    return errors


def validate_event_batch(data, session_schema, batch_schema, registry):
    """Validate an event batch against the batch envelope schema.

    If the batch envelope schema (telemetry-event-batch.json) is available,
    validates the full envelope. Otherwise falls back to validating each
    event body against the TelemetryEvent definition.
    """
    if batch_schema is not None:
        validator = Draft202012Validator(batch_schema, registry=registry, format_checker=FormatChecker())
        return list(validator.iter_errors(data))
    schema_id = session_schema.get("$id", "")
    wrapper = {"$ref": f"{schema_id}#/$defs/TelemetryEvent"}
    validator = Draft202012Validator(wrapper, registry=registry, format_checker=FormatChecker())
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


def _resolve_json_pointer(document, pointer):
    """Resolve an RFC 6901 pointer, raising ValueError when it is malformed.

    The evidence schema requires a non-empty pointer, but this resolver remains
    strict about escape sequences and array indices because those details are
    application-layer semantics rather than JSON Schema shape constraints.
    """
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("pointer must begin with '/'")

    value = document
    for raw_token in pointer.split("/")[1:]:
        token_chars = []
        index = 0
        while index < len(raw_token):
            char = raw_token[index]
            if char != "~":
                token_chars.append(char)
                index += 1
                continue
            if index + 1 >= len(raw_token) or raw_token[index + 1] not in "01":
                raise ValueError("invalid RFC 6901 escape")
            token_chars.append("~" if raw_token[index + 1] == "0" else "/")
            index += 2
        token = "".join(token_chars)

        if isinstance(value, dict):
            if token not in value:
                raise ValueError("object member does not exist")
            value = value[token]
        elif isinstance(value, list):
            if token == "-" or not token.isdigit() or (
                len(token) > 1 and token.startswith("0")
            ):
                raise ValueError("invalid array index")
            item_index = int(token)
            if item_index >= len(value):
                raise ValueError("array index is out of range")
            value = value[item_index]
        else:
            raise ValueError("pointer traverses a scalar")
    return value


def _canonical_json(value):
    """Return RFC 8785 JCS bytes or raise ValueError for invalid input."""
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, UnicodeError, ValueError, TypeError) as error:
        raise ValueError(str(error)) from error


def _delivery_context(document):
    """Return the exact delivery context bound by section 5.8.2."""
    return {
        "document_type": document.get("document_type", "session"),
        "schema_version": document.get("schema_version"),
        "session_id": document.get("session_id"),
        "ctx_token": document.get("ctx_token"),
        "agent_id": document.get("agent_id"),
        "content_scope": document.get("content_scope"),
        "manifest_ref": document.get("manifest_ref"),
        "started_at": document.get("started_at"),
    }


def _occurrence_digest(document, event):
    """Hash delivery context and the complete evidence-free event."""
    evidence_free_event = {
        key: value for key, value in event.items() if key != "evidence"
    }
    occurrence = {
        "delivery_context": _delivery_context(document),
        "event": evidence_free_event,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(occurrence)).hexdigest()


def _assertion_digest(document, event, evidence, assertion_value):
    """Recompute the delivery-occurrence-bound section 5.8 assertion digest."""
    subjects = sorted(
        evidence.get("subjects", []),
        key=lambda subject: (subject.get("role", ""), subject.get("digest", "")),
    )
    binding = {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "occurrence_digest": _occurrence_digest(document, event),
        "assertion_path": evidence.get("assertion_path"),
        "assertion_value": assertion_value,
        "subjects": subjects,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(binding)).hexdigest()

def _artifact_uri_error(uri):
    """Return why an artifact URI violates the local safe-retrieval policy."""
    try:
        parsed = urlsplit(uri)
    except (TypeError, ValueError) as error:
        return f"malformed artifact URI: {error}"
    if parsed.scheme not in {"https"}:
        return "artifact URI does not use the allowed https scheme"
    if parsed.username is not None or parsed.password is not None:
        return "artifact URI contains credentials"
    if not parsed.hostname:
        return "artifact URI has no host"
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return None
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_private
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return "artifact URI targets a disallowed IP address"
    return None


def _artifact_integrity_violations(
    label, artifacts, event_bytes_remaining, allow_unresolved_uris=False
):
    """Validate bounded local bytes and refuse unresolved references by default."""
    violations = []
    entry_decoded_bytes = 0
    for artifact_position, artifact in enumerate(artifacts):
        artifact_label = f"{label} artifact[{artifact_position}]"
        if "content" in artifact:
            encoded = artifact["content"]
            if not isinstance(encoded, str):
                violations.append(f"{artifact_label} has malformed base64 content")
                continue
            if len(encoded) > MAX_INLINE_ENCODED_CHARS:
                violations.append(f"{artifact_label} exceeds the encoded byte limit")
                continue
            padding = 2 if encoded.endswith("==") else 1 if encoded.endswith("=") else 0
            decoded_size = (len(encoded) // 4) * 3 - padding
            if decoded_size > MAX_INLINE_DECODED_BYTES:
                violations.append(f"{artifact_label} exceeds the decoded byte limit")
                continue
            if entry_decoded_bytes + decoded_size > MAX_ENTRY_DECODED_BYTES:
                violations.append(f"{label} exceeds the decoded bytes per entry limit")
                continue
            if entry_decoded_bytes + decoded_size > event_bytes_remaining:
                violations.append(f"{label} exceeds the decoded bytes per event limit")
                continue
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (binascii.Error, TypeError, ValueError):
                violations.append(f"{artifact_label} has malformed base64 content")
                continue
            entry_decoded_bytes += len(decoded)
            actual_digest = "sha256:" + hashlib.sha256(decoded).hexdigest()
            if artifact.get("digest") != actual_digest:
                violations.append(
                    f"{artifact_label} digest mismatch: expected {actual_digest}"
                )
        elif "uri" in artifact:
            uri_error = _artifact_uri_error(artifact.get("uri"))
            if uri_error:
                violations.append(f"{artifact_label} {uri_error}")
            elif not allow_unresolved_uris:
                violations.append(
                    f"{artifact_label} URI bytes were not retrieved and digest-verified"
                )
    return violations, entry_decoded_bytes


def _event_resource_violations(event):
    """Check evidence ceilings without decoding or allocating artifact bytes."""
    violations = []
    evidence_entries = event.get("evidence", [])
    if len(evidence_entries) > 32:
        violations.append("Event exceeds the evidence entries limit")
    event_decoded_bytes = 0
    for position, evidence in enumerate(evidence_entries):
        label = f"Evidence[{position}] at '{evidence.get('assertion_path', '')}'"
        subjects = evidence.get("subjects", [])
        artifacts = evidence.get("artifacts", [])
        if len(subjects) > 16:
            violations.append(f"{label} exceeds the subjects limit")
        if len(artifacts) > 16:
            violations.append(f"{label} exceeds the artifacts limit")
        entry_decoded_bytes = 0
        for artifact_position, artifact in enumerate(artifacts):
            encoded = artifact.get("content")
            if not isinstance(encoded, str):
                continue
            artifact_label = f"{label} artifact[{artifact_position}]"
            if len(encoded) > MAX_INLINE_ENCODED_CHARS:
                violations.append(f"{artifact_label} exceeds the encoded byte limit")
                continue
            padding = 2 if encoded.endswith("==") else 1 if encoded.endswith("=") else 0
            decoded_size = max(0, (len(encoded) // 4) * 3 - padding)
            if decoded_size > MAX_INLINE_DECODED_BYTES:
                violations.append(f"{artifact_label} exceeds the decoded byte limit")
            entry_decoded_bytes += decoded_size
        if entry_decoded_bytes > MAX_ENTRY_DECODED_BYTES:
            violations.append(f"{label} exceeds the decoded bytes per entry limit")
        event_decoded_bytes += entry_decoded_bytes
    if event_decoded_bytes > MAX_EVENT_DECODED_BYTES:
        violations.append("Event exceeds the decoded bytes per event limit")
    return violations


def check_evidence_conformance(data, allow_unresolved_uris=False):
    """Check deterministic section 5.8 evidence-tier application rules.

    The harness validates local binding and inline artifact integrity. It never
    retrieves remote artifacts or claims to perform profile cryptography.
    """
    violations = []
    sensitive_event_types = {
        "content_grounded",
        "content_cited",
        "content_displayed",
        "content_engaged",
    }
    for event in _iter_events(data):
        resource_violations = _event_resource_violations(event)
        violations.extend(resource_violations)
        if resource_violations:
            continue
        event_decoded_bytes = 0
        for position, evidence in enumerate(event.get("evidence", [])):
            path = evidence.get("assertion_path", "")
            label = f"Evidence[{position}] at '{path}'"

            try:
                first_token = path.split("/", 2)[1].replace("~1", "/").replace("~0", "~")
            except (AttributeError, IndexError):
                first_token = ""
            if first_token == "evidence":
                violations.append(f"{label} targets evidence")
                continue

            try:
                assertion_value = _resolve_json_pointer(event, path)
            except ValueError as error:
                violations.append(f"{label} is unresolved: {error}")
                continue

            tier = evidence.get("tier", "claim")
            if tier == "claim":
                continue

            if not event.get("id"):
                violations.append(f"{label} requests '{tier}' without an event id")
                continue

            try:
                expected_digest = _assertion_digest(data, event, evidence, assertion_value)
            except ValueError as error:
                violations.append(f"{label} cannot be canonically bound: {error}")
                continue
            if evidence.get("assertion_digest") != expected_digest:
                violations.append(
                    f"{label} assertion_digest mismatch: expected {expected_digest}"
                )

            subjects = evidence.get("subjects", [])
            roles = {subject.get("role") for subject in subjects}
            if len(roles) != len(subjects):
                violations.append(f"{label} repeats a subject role")
            data_object = event.get("data", {})
            content_hash = data_object.get("content_hash")
            fingerprint = data_object.get("content_fingerprint", {})
            fingerprint_path = path.startswith("/data/content_fingerprint/")

            if path in {
                "/data/content_fingerprint/detected",
                "/data/content_fingerprint/preserved_in_output",
            }:
                if not any(
                    subject.get("role") == "grounded_content"
                    and subject.get("digest") == content_hash
                    for subject in subjects
                ):
                    violations.append(
                        f"{label} has no grounded_content subject matching data.content_hash"
                    )
            if path == "/data/content_fingerprint/preserved_in_output":
                if assertion_value is True and fingerprint.get("detected") is not True:
                    violations.append(
                        f"{label} cannot establish preservation when detected is not true"
                    )
                if "generated_output" not in roles:
                    violations.append(f"{label} omits generated_output subject")
            if path == "/type" and event.get("type") == "content_grounded":
                for required_role in ("grounded_content", "generation_context"):
                    if required_role not in roles:
                        violations.append(f"{label} omits {required_role} subject")
            if path == "/type" and event.get("type") == "content_cited":
                for required_role in ("grounded_content", "generated_output"):
                    if required_role not in roles:
                        violations.append(f"{label} omits {required_role} subject")

            if fingerprint_path:
                scheme_ref = fingerprint.get("scheme_profile_ref")
                scheme_digest = fingerprint.get("scheme_profile_digest")
                if not scheme_ref or not scheme_digest:
                    violations.append(f"{label} has no digest-bound scheme profile")
                profile = evidence.get("verification_profile", {})
                if (
                    scheme_digest
                    and profile.get("scheme_profile_digest") != scheme_digest
                ):
                    violations.append(
                        f"{label} verification profile scheme digest does not match "
                        "the selected scheme profile"
                    )
                if tier == "independently_verifiable" and not all(
                    fingerprint.get("scheme_properties", {}).get(property_name) is True
                    for property_name in (
                        "content_borne",
                        "identity_bearing",
                        "verifiable",
                    )
                ):
                    violations.append(
                        f"{label} exceeds the fingerprint scheme capability ceiling"
                    )

            artifacts = evidence.get("artifacts", [])
            artifact_violations, decoded_bytes = _artifact_integrity_violations(
                label,
                artifacts,
                MAX_EVENT_DECODED_BYTES - event_decoded_bytes,
                allow_unresolved_uris=allow_unresolved_uris,
            )
            violations.extend(artifact_violations)
            event_decoded_bytes += decoded_bytes
            artifact_types = {artifact.get("type") for artifact in artifacts}
            profile_digest = evidence.get("verification_profile", {}).get("digest")
            profile_material = [
                artifact
                for artifact in artifacts
                if artifact.get("type") == "verification_material"
                and artifact.get("digest") == profile_digest
            ]
            if len(profile_material) != 1:
                violations.append(
                    f"{label} does not bind exactly one verification profile artifact"
                )
            if fingerprint_path and scheme_digest:
                scheme_material = [
                    artifact
                    for artifact in artifacts
                    if artifact.get("type") == "verification_material"
                    and artifact.get("digest") == scheme_digest
                ]
                if len(scheme_material) != 1:
                    violations.append(
                        f"{label} does not bind exactly one scheme profile artifact"
                    )

            if tier == "origin_corroborated":
                if not artifact_types & {"origin_event", "access_record"}:
                    violations.append(f"{label} omits origin_event or access_record")
                sensitive_assertion = fingerprint_path or (
                    path == "/type" and event.get("type") in sensitive_event_types
                )
                if sensitive_assertion:
                    selected_attestation = evidence.get("verification", {}).get(
                        "verifier_attestation_digest"
                    )
                    matching_attestations = [
                        artifact
                        for artifact in artifacts
                        if artifact.get("type") == "verifier_attestation"
                        and artifact.get("digest") == selected_attestation
                    ]
                    if len(matching_attestations) != 1:
                        violations.append(
                            f"{label} does not select exactly one verifier_attestation artifact"
                        )
            elif tier == "independently_verifiable":
                verification = evidence.get("verification", {})
                selectors = {
                    "verifier_attestation": verification.get(
                        "verifier_attestation_digest"
                    ),
                    "trusted_timestamp": verification.get(
                        "trusted_timestamp_digest"
                    ),
                }
                for artifact_type, selected_digest in selectors.items():
                    matching = [
                        artifact
                        for artifact in artifacts
                        if artifact.get("type") == artifact_type
                        and artifact.get("digest") == selected_digest
                    ]
                    if len(matching) != 1:
                        violations.append(
                            f"{label} does not select exactly one {artifact_type} artifact"
                        )

    return violations

def check_occurrence_conflicts(data, replay_state=None):
    """Surface same-ID/different-occurrence conflicts within and across deliveries.

    ``replay_state`` maps event IDs to occurrence digests. A ``None`` value
    records a previously observed conflict and tells callers to retract any
    cached upgrade for that event ID.
    """
    replay_state = replay_state if replay_state is not None else {}
    observed = {}
    conflicts = set()
    for event in _iter_events(data):
        event_id = event.get("id")
        if not event_id:
            continue
        try:
            digest = _occurrence_digest(data, event)
        except ValueError:
            continue
        previous = observed.get(event_id, replay_state.get(event_id, "<absent>"))
        if previous is None or (previous != "<absent>" and previous != digest):
            conflicts.add(event_id)
            observed[event_id] = None
        else:
            observed[event_id] = digest
    replay_state.update(observed)
    return conflicts


def _single_evidence_document(data, event_index, evidence):
    """Build a shallow single-entry view without copying attacker bytes."""
    candidate = dict(data)
    if is_standalone_event(data):
        candidate_event = dict(data["event"])
        candidate["event"] = candidate_event
    else:
        events = list(data.get("events", []))
        candidate_event = dict(events[event_index])
        events[event_index] = candidate_event
        candidate["events"] = events
    candidate_event["evidence"] = [evidence]
    return candidate, candidate_event


def derive_evidence_tiers(data, consumer_verifier=None, replay_state=None):
    """Derive effective tiers per assertion under consumer-selected trust.

    No entry above ``claim`` is promoted unless ``consumer_verifier`` validates
    profile cryptography, local trust, time, replay, and semantic support. The
    result reports conflicted event IDs so consumers can retract prior cached
    upgrades. Entries are evaluated independently and array order is irrelevant.
    """
    ranks = {"claim": 0, "origin_corroborated": 1, "independently_verifiable": 2}
    names = {rank: name for name, rank in ranks.items()}
    results = {}
    original_events = list(_iter_events(data))
    resource_invalid_event_ids = {
        event.get("id")
        for event in original_events
        if _event_resource_violations(event)
    }
    conflicts = check_occurrence_conflicts(data, replay_state)
    for event_index, event in enumerate(original_events):
        seen = set()
        for evidence in event.get("evidence", []):
            path = evidence.get("assertion_path", "")
            key = f"{event.get('id', '<missing>')}:{path}"
            results.setdefault(key, "claim")
            if event.get("id") in resource_invalid_event_ids:
                continue
            if event.get("id") in conflicts:
                continue
            try:
                normalized = _canonical_json(evidence)
            except ValueError:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)

            candidate, candidate_event = _single_evidence_document(
                data, event_index, evidence
            )
            if check_evidence_conformance(
                candidate, allow_unresolved_uris=consumer_verifier is not None
            ):
                continue
            if consumer_verifier is None:
                continue
            established_tier = consumer_verifier(candidate, candidate_event, evidence)
            established_rank = ranks.get(established_tier, 0)
            requested_rank = ranks.get(evidence.get("tier", "claim"), 0)
            current_rank = ranks[results[key]]
            results[key] = names[
                max(current_rank, min(requested_rank, established_rank))
            ]
    return {
        "tiers": results,
        "conflicted_event_ids": sorted(conflicts),
    }


def check_occurrence_conflict_conformance(data):
    """Return application violations for reused IDs with changed occurrences."""
    return [
        f"Event id '{event_id}' has conflicting occurrence digests"
        for event_id in sorted(check_occurrence_conflicts(data))
    ]


def check_application_layer(data):
    """Run every application-layer conformance rule and return all violations."""
    return (
        check_privacy_conformance(data)
        + check_content_identifier(data)
        + check_session_or_ctx_token(data)
        + check_evidence_conformance(data)
        + check_occurrence_conflict_conformance(data)
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

    fixture_maps_match = (
        set(APPLICATION_LAYER_VIOLATIONS)
        == set(EXPECTED_APPLICATION_VIOLATION_FRAGMENTS)
    )
    if fixture_maps_match:
        print("  PASS  every application-layer fixture pins its intended violation")
        passed += 1
        results.append(("application-fixture-reasons", True, None))
    else:
        print("  FAIL  application-layer fixture reason maps differ")
        failed += 1
        results.append(("application-fixture-reasons", False, "fixture maps differ"))
    print()

    print("=" * 60)
    print("REGISTRY/MATRIX tests")
    print("=" * 60)
    registry_violations = check_registry_and_matrix()
    if registry_violations:
        print("  FAIL  content-fingerprint registry and c2pa-text matrix")
        for violation in registry_violations:
            print(f"        {violation}")
        failed += 1
        results.append(("registry/matrix", False, "; ".join(registry_violations)))
    else:
        print("  PASS  content-fingerprint registry and c2pa-text matrix")
        passed += 1
        results.append(("registry/matrix", True, None))

    registry_document = load_test_file(tests_dir.parent / "content-fingerprint-schemes.json")
    matrix_document = load_test_file(tests_dir.parent / "survivability-matrix-c2pa-text.json")
    malformed_cases = []
    for malformed_value in ([], {}):
        malformed_registry = copy.deepcopy(registry_document)
        malformed_registry["schemes"][0]["scheme"] = malformed_value
        malformed_cases.append(
            (
                "registry scheme",
                check_registry_and_matrix(malformed_registry, matrix_document),
                "schemes/0/scheme",
            )
        )

        malformed_matrix = copy.deepcopy(matrix_document)
        malformed_matrix["transforms"][0]["transform"] = malformed_value
        malformed_cases.append(
            (
                "matrix transform",
                check_registry_and_matrix(registry_document, malformed_matrix),
                "transforms/0/transform",
            )
        )

    malformed_contract_holds = all(
        violations
        and any(
            "schema violation" in violation and expected_path in violation
            for violation in violations
        )
        for _label, violations, expected_path in malformed_cases
    )
    if malformed_contract_holds:
        print("  PASS  non-string scheme and transform values yield violations")
        passed += 1
        results.append(("registry-malformed-name-types", True, None))
    else:
        print("  FAIL  malformed scheme or transform did not yield a controlled violation")
        failed += 1
        results.append(("registry-malformed-name-types", False, "missing violation"))

    unknown_registry_schema = copy.deepcopy(registry_document)
    unknown_registry_schema["$schema"] = "https://contenttelemetry.org/schema/v0.2/missing-registry.json"
    unknown_matrix_schema = copy.deepcopy(matrix_document)
    unknown_matrix_schema["$schema"] = "https://contenttelemetry.org/schema/v0.2/missing-matrix.json"
    registry_schema_violations = check_registry_and_matrix(
        unknown_registry_schema, matrix_document
    )
    matrix_schema_violations = check_registry_and_matrix(
        registry_document, unknown_matrix_schema
    )
    local_schema_resolution_holds = (
        any(
            "registry advertised $schema does not resolve" in violation
            for violation in registry_schema_violations
        )
        and any(
            "matrix advertised $schema does not resolve" in violation
            for violation in matrix_schema_violations
        )
    )
    if local_schema_resolution_holds:
        print("  PASS  both advertised $schema IDs resolve only to checked-in schemas")
        passed += 1
        results.append(("registry-local-schema-resolution", True, None))
    else:
        print("  FAIL  an advertised $schema ID bypassed local resolution")
        failed += 1
        results.append(("registry-local-schema-resolution", False, "schema resolution"))

    malformed_transform_matrix = copy.deepcopy(matrix_document)
    malformed_transform_matrix["transforms"] = [None]
    malformed_survivability_inputs = ([], {}, malformed_transform_matrix)
    original_matrix_loader = check_survivability._load_matrix
    survivability_failure_results = []
    try:
        for malformed_input in malformed_survivability_inputs:
            check_survivability._load_matrix = (
                lambda value=malformed_input: copy.deepcopy(value)
            )
            first_result = check_survivability.run_checks()
            second_result = check_survivability.run_checks()
            survivability_failure_results.append((first_result, second_result))
    except Exception as error:
        survivability_failure_results.append((error, None))
    finally:
        check_survivability._load_matrix = original_matrix_loader

    survivability_malformed_contract_holds = (
        len(survivability_failure_results) == len(malformed_survivability_inputs)
        and all(
            isinstance(first, tuple)
            and first == second
            and first[0:2] == (0, 0)
            and first[2]
            and all(isinstance(failure, str) for failure in first[2])
            for first, second in survivability_failure_results
        )
    )
    if survivability_malformed_contract_holds:
        print("  PASS  malformed survivability matrices return deterministic failures")
        passed += 1
        results.append(("survivability-malformed-matrix", True, None))
    else:
        print("  FAIL  malformed survivability matrix raised or returned unstable failures")
        print(f"        results: {survivability_failure_results}")
        failed += 1
        results.append(("survivability-malformed-matrix", False, "unstable failure"))

    privacy_pairs = (
        (
            "privacy-violation-query-at-minimal.json",
            "standalone-privacy-query-at-minimal.json",
            "Field 'query_text' present on turn with privacy_level 'minimal'",
        ),
        (
            "privacy-violation-ad-rendered-at-minimal.json",
            "standalone-privacy-ad-rendered-at-minimal.json",
            "Field 'ad_rendered' present on turn with privacy_level 'minimal'",
        ),
        (
            "privacy-violation-query-at-intent.json",
            "standalone-privacy-query-at-intent.json",
            "Field 'query_text' present on turn with privacy_level 'intent'",
        ),
    )
    privacy_paths_match = all(
        check_privacy_conformance(load_test_file(invalid_dir / session_name))
        == check_privacy_conformance(load_test_file(invalid_dir / standalone_name))
        == [expected]
        for session_name, standalone_name, expected in privacy_pairs
    )
    if privacy_paths_match:
        print("  PASS  session and standalone turns enforce identical privacy violations")
        passed += 1
        results.append(("privacy-session-standalone-parity", True, None))
    else:
        print("  FAIL  session and standalone privacy paths diverged")
        failed += 1
        results.append(("privacy-session-standalone-parity", False, "privacy path mismatch"))
    print()
    base_derivation_document = load_test_file(
        valid_dir / "event-independently-verifiable-grounding.json"
    )
    derivation_document = copy.deepcopy(base_derivation_document)
    derivation_document["event"]["evidence"].append(
        {"assertion_path": "/type", "tier": "claim"}
    )
    reversed_document = copy.deepcopy(derivation_document)
    reversed_document["event"]["evidence"].reverse()

    def deterministic_consumer_verifier(_document, _event, evidence):
        profile = evidence.get("verification_profile", {})
        verification = evidence.get("verification", {})
        if profile.get("ref") and profile.get("digest") and verification.get("status") == "pass":
            return "independently_verifiable"
        return "claim"

    forward_result = derive_evidence_tiers(
        derivation_document, consumer_verifier=deterministic_consumer_verifier
    )
    reversed_result = derive_evidence_tiers(
        reversed_document, consumer_verifier=deterministic_consumer_verifier
    )
    unverified_result = derive_evidence_tiers(derivation_document)
    expected_key = "860e8400-e29b-41d4-a716-446655440000:/type"
    derivation_contract_holds = (
        forward_result == reversed_result
        and forward_result["tiers"].get(expected_key) == "independently_verifiable"
        and unverified_result["tiers"].get(expected_key) == "claim"
    )
    if derivation_contract_holds:
        print("  PASS  tier derivation is verifier-gated and array-order independent")
        passed += 1
        results.append(("evidence-consumer-verifier", True, None))
    else:
        print("  FAIL  tier derivation bypassed verifier gating or depended on order")
        failed += 1
        results.append(("evidence-consumer-verifier", False, "derivation contract"))

    tier2_false = load_test_file(
        valid_dir / "event-sensitive-tier2-fingerprint-detection.json"
    )
    tier2_false["event"]["data"]["content_fingerprint"]["scheme_properties"][
        "verifiable"
    ] = False
    tier2_false_evidence = tier2_false["event"]["evidence"][0]
    tier2_false_evidence["assertion_digest"] = _assertion_digest(
        tier2_false,
        tier2_false["event"],
        tier2_false_evidence,
        True,
    )
    tier2_false_result = derive_evidence_tiers(
        tier2_false, consumer_verifier=deterministic_consumer_verifier
    )
    tier2_key = (
        "860e8400-e29b-41d4-a716-446655440000:"
        "/data/content_fingerprint/detected"
    )
    tier3_false = load_test_file(
        invalid_dir / "evidence-tier3-fingerprint-verifiable-false.json"
    )
    tier3_false_result = derive_evidence_tiers(
        tier3_false, consumer_verifier=deterministic_consumer_verifier
    )
    ceiling_contract_holds = (
        tier2_false_result["tiers"].get(tier2_key) == "origin_corroborated"
        and tier3_false_result["tiers"].get(tier2_key) == "claim"
    )
    if ceiling_contract_holds:
        print("  PASS  false scheme properties cap Tier 2 and reject requested Tier 3")
        passed += 1
        results.append(("fingerprint-capability-ceiling", True, None))
    else:
        print("  FAIL  scheme capability ceiling granted an excessive tier")
        failed += 1
        results.append(("fingerprint-capability-ceiling", False, "ceiling bypass"))

    within_delivery = load_test_file(
        invalid_dir / "evidence-conflicting-event-occurrences.json"
    )
    within_conflicts = check_occurrence_conflicts(within_delivery)
    replay_state = {}
    first_delivery = derive_evidence_tiers(
        base_derivation_document,
        consumer_verifier=deterministic_consumer_verifier,
        replay_state=replay_state,
    )
    conflicting_delivery = copy.deepcopy(base_derivation_document)
    conflicting_delivery["event"]["timestamp"] = "2026-07-11T12:00:03Z"
    second_delivery = derive_evidence_tiers(
        conflicting_delivery,
        consumer_verifier=deterministic_consumer_verifier,
        replay_state=replay_state,
    )
    replay_event_id = "860e8400-e29b-41d4-a716-446655440000"
    replay_contract_holds = (
        "860e8400-e29b-41d4-a716-446655440099" in within_conflicts
        and first_delivery["tiers"].get(expected_key) == "independently_verifiable"
        and second_delivery["tiers"].get(expected_key) == "claim"
        and second_delivery["conflicted_event_ids"] == [replay_event_id]
    )
    if replay_contract_holds:
        print("  PASS  occurrence conflicts surface within and across deliveries")
        passed += 1
        results.append(("evidence-replay-conflicts", True, None))
    else:
        print("  FAIL  replay conflict did not retract the effective tier")
        failed += 1
        results.append(("evidence-replay-conflicts", False, "replay conflict"))

    class OneOverInlineLimit(str):
        def __len__(self):
            return MAX_INLINE_ENCODED_CHARS + 1

    oversized_artifact = {"content": OneOverInlineLimit("")}
    resource_violations, _ = _artifact_integrity_violations(
        "Resource fixture", [oversized_artifact], MAX_EVENT_DECODED_BYTES
    )
    evidence_schema = schema["$defs"]["TelemetryEvent"]["properties"]["evidence"]
    assertion_schema = schema["$defs"]["EvidenceAssertion"]["properties"]
    artifact_schema = schema["$defs"]["EvidenceArtifact"]["properties"]["content"]
    resource_contract_holds = (
        evidence_schema.get("maxItems") == 32
        and assertion_schema["subjects"].get("maxItems") == 16
        and assertion_schema["artifacts"].get("maxItems") == 16
        and artifact_schema.get("maxLength") == MAX_INLINE_ENCODED_CHARS
        and MAX_INLINE_DECODED_BYTES == 8 * 1024 * 1024
        and MAX_ENTRY_DECODED_BYTES == 16 * 1024 * 1024
        and MAX_EVENT_DECODED_BYTES == 32 * 1024 * 1024
        and any("exceeds the encoded byte limit" in item for item in resource_violations)
    )
    if resource_contract_holds:
        print("  PASS  schema and pre-decode resource boundaries are enforced")
        passed += 1
        results.append(("evidence-resource-limit", True, None))
    else:
        print("  FAIL  evidence resource boundary contract is inconsistent")
        failed += 1
        results.append(("evidence-resource-limit", False, "resource limit bypass"))

    class AggregateSizedContent(str):
        def __len__(self):
            return MAX_INLINE_ENCODED_CHARS - 4

    aggregate_document = copy.deepcopy(base_derivation_document)
    aggregate_evidence = []
    for _position in range(5):
        evidence = copy.deepcopy(aggregate_document["event"]["evidence"][0])
        evidence["artifacts"] = [
            {
                "type": "verification_material",
                "media_type": "application/octet-stream",
                "digest": "sha256:" + "0" * 64,
                "content": AggregateSizedContent(""),
            }
        ]
        aggregate_evidence.append(evidence)
    aggregate_document["event"]["evidence"] = aggregate_evidence
    aggregate_verifier_calls = []

    def aggregate_verifier(_document, _event, _evidence):
        aggregate_verifier_calls.append(True)
        return "independently_verifiable"

    aggregate_violations = _event_resource_violations(aggregate_document["event"])
    aggregate_result = derive_evidence_tiers(
        aggregate_document, consumer_verifier=aggregate_verifier
    )
    aggregate_contract_holds = (
        "Event exceeds the decoded bytes per event limit" in aggregate_violations
        and not aggregate_verifier_calls
        and aggregate_result["tiers"].get(expected_key) == "claim"
    )
    if aggregate_contract_holds:
        print("  PASS  aggregate event resource overflow blocks all tier derivation")
        passed += 1
        results.append(("evidence-aggregate-resource-derivation", True, None))
    else:
        print("  FAIL  aggregate resource-invalid event reached tier verification")
        failed += 1
        results.append(("evidence-aggregate-resource-derivation", False, "resource bypass"))

    uri_document = load_test_file(invalid_dir / "evidence-uri-only-non-upgrade.json")
    uri_event = uri_document["event"]
    uri_evidence = uri_event["evidence"][0]
    uri_evidence["artifacts"].append(
        {
            "type": "verification_material",
            "media_type": "application/json",
            "digest": "sha256:" + "f" * 64,
            "uri": "https://artifacts.example/profile.json",
        }
    )
    uri_evidence["assertion_digest"] = _assertion_digest(
        uri_document, uri_event, uri_evidence, uri_event["type"]
    )
    uri_verifier_calls = []

    def uri_verifier(_document, _event, evidence):
        uri_verifier_calls.append(
            tuple(artifact["uri"] for artifact in evidence["artifacts"])
        )
        return "origin_corroborated"

    uri_default_violations = check_evidence_conformance(uri_document)
    uri_callback_result = derive_evidence_tiers(
        uri_document, consumer_verifier=uri_verifier
    )
    uri_key = "860e8400-e29b-41d4-a716-446655440000:/type"
    uri_callback_contract_holds = (
        any("URI bytes were not retrieved" in item for item in uri_default_violations)
        and uri_verifier_calls == [
            (
                "https://artifacts.example/origin-event.json",
                "https://artifacts.example/profile.json",
            )
        ]
        and uri_callback_result["tiers"].get(uri_key) == "origin_corroborated"
    )
    if uri_callback_contract_holds:
        print("  PASS  safe HTTPS URI evidence reaches only an explicit consumer verifier")
        passed += 1
        results.append(("evidence-uri-consumer-verifier", True, None))
    else:
        print("  FAIL  safe URI evidence did not preserve fail-closed callback semantics")
        print(f"        default violations: {uri_default_violations}")
        print(f"        verifier calls: {uri_verifier_calls}")
        print(f"        derived tier: {uri_callback_result['tiers'].get(uri_key)}")
        failed += 1
        results.append(("evidence-uri-consumer-verifier", False, "URI callback contract"))
    print()

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

        if schema_errors and is_app_layer:
            msg = schema_errors[0].message
            print(f"  FAIL  {name}")
            print(f"        Application-layer fixture is not schema-valid: {msg}")
            failed += 1
            results.append((name, False, "Application-layer fixture failed schema"))

        elif schema_errors:
            # Failed JSON Schema for its intended structural reason.
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
            expected_fragment = EXPECTED_APPLICATION_VIOLATION_FRAGMENTS[name]
            has_intended_violation = any(
                expected_fragment in violation for violation in conformance_violations
            )
            if has_intended_violation:
                print(f"  PASS  {name}  [application-layer]")
                print(f"        {APPLICATION_LAYER_VIOLATIONS[name]}")
                passed += 1
                results.append((name, True, None))
            else:
                print(f"  FAIL  {name}")
                if conformance_violations:
                    print(f"        Expected intended violation containing: {expected_fragment}")
                else:
                    print("        Expected application-layer violation but none found")
                failed += 1
                results.append((name, False, "Expected intended conformance violation"))

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
