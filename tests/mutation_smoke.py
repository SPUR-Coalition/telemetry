#!/usr/bin/env python3
"""Mutation smoke test for the conformance suite.

Replays suite-weakening mutations - each of which the suite once missed -
against a scratch copy of the repository and confirms validate.py fails under
every one of them. The working tree is never modified.

A mutation "survives" when the mutated suite still exits 0; any survivor
is a real detection gap and fails this script.

Usage:
    python tests/mutation_smoke.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def mutate_drop_format_checker(root):
    """Build every validator without a format checker (formats become no-ops)."""
    p = root / "tests" / "validate.py"
    src = p.read_text()
    mutated = src.replace(", format_checker=FORMAT_CHECKER", "")
    assert mutated != src
    p.write_text(mutated)
    return "malformed-parent-session-id.json"


def mutate_gut_withdrawn_ip_hash(root):
    """Gut the withdrawn-ip-hash fixture: drop ip_hash and break the event
    some other way, so it fails schema for a reason unrelated to its rule."""
    p = root / "tests" / "invalid" / "withdrawn-ip-hash.json"
    doc = json.loads(p.read_text())
    del doc["event"]["data"]["ip_hash"]
    del doc["event"]["timestamp"]
    p.write_text(json.dumps(doc, indent=2) + "\n")
    return "withdrawn-ip-hash.json"


def mutate_shrink_content_event_types(root):
    """Remove content_presented from CONTENT_EVENT_TYPES."""
    p = root / "tests" / "validate.py"
    src = p.read_text()
    mutated = src.replace('"content_cited", "content_presented", "content_engaged",',
                          '"content_cited", "content_engaged",')
    assert mutated != src
    p.write_text(mutated)
    return "presented-missing-identifier.json"


def mutate_shrink_privacy_forbidden_fields(root):
    """Remove topics from the fields forbidden at minimal privacy."""
    p = root / "tests" / "validate.py"
    src = p.read_text()
    mutated = src.replace('"query_text", "response_text", "query_intent", "topics",',
                          '"query_text", "response_text", "query_intent",')
    assert mutated != src
    p.write_text(mutated)
    return "privacy-violation-topics-at-minimal.json"


def mutate_zero_uuid_engagement(root):
    """Point a valid session's engagement at an all-zeros presentation_id."""
    p = root / "tests" / "valid" / "session-citation-tier.json"
    doc = json.loads(p.read_text())
    mutated = False
    for event in doc["events"]:
        if event.get("type") == "content_engaged":
            event["presentation_id"] = "00000000-0000-0000-0000-000000000000"
            mutated = True
    assert mutated
    p.write_text(json.dumps(doc, indent=2) + "\n")
    return "session-citation-tier.json"


MUTATIONS = [
    ("drop format_checker", mutate_drop_format_checker),
    ("gut withdrawn-ip-hash fixture", mutate_gut_withdrawn_ip_hash),
    ("remove content_presented from CONTENT_EVENT_TYPES", mutate_shrink_content_event_types),
    ("shrink PRIVACY_FORBIDDEN_FIELDS", mutate_shrink_privacy_forbidden_fields),
    ("engagement at all-zeros presentation_id", mutate_zero_uuid_engagement),
]


# ---------------------------------------------------------------------------
# Review mutations (22 August pre-freeze review). Each weakens one rule the
# suite previously pinned in a single document shape, or not at all, and names
# the fixture that now fails under it.
# ---------------------------------------------------------------------------

def _edit_text(root, rel, old, new):
    path = root / rel
    src = path.read_text()
    assert old in src, (rel, old)
    path.write_text(src.replace(old, new))


def _edit_json(root, rel, fn):
    path = root / rel
    doc = json.loads(path.read_text())
    fn(doc)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def _event_branch(schema, etype):
    for branch in schema["$defs"]["TelemetryEvent"]["allOf"]:
        if branch["if"]["properties"]["type"]["const"] == etype:
            return branch["then"]
    raise KeyError(etype)


def _text(rel, old, new, fixture):
    def mutate(root):
        _edit_text(root, rel, old, new)
        return fixture
    return mutate


def _json(rel, fn, fixture):
    def mutate(root):
        _edit_json(root, rel, fn)
        return fixture
    return mutate


_V = "tests/validate.py"
_S = "telemetry-session.json"
_E = "telemetry-event.json"
_B = "telemetry-event-batch.json"
_M = "manifest.json"

REVIEW_MUTATIONS = [
    # validate.py application-layer weakenings
    ("exempt any envelope containing a retrieval from the session/ctx_token rule",
     _text(_V, 'if types <= {"content_retrieved"}:', 'if "content_retrieved" in types:',
           "batch-missing-session-mixed-retrieval.json")),
    ("stop forbidding response_text at intent",
     _text(_V, '"intent": {\n        "query_text", "response_text",\n    },', '"intent": {\n        "query_text",\n    },',
           "privacy-violation-response-text-at-intent.json")),
    ("drop the agent_cached -> cached:true half of the provenance rule",
     _text(_V, 'if provenance == "agent_cached" and cached is not True:', 'if False:',
           "grounding-provenance-cached-conflict-agent-cached.json")),
    ("skip referential integrity when the session has no content_presented events",
     _text(_V, 'if pid and pid not in presented_ids:', 'if presented_ids and pid and pid not in presented_ids:',
           "engaged-presentation-id-no-presentations.json")),
    ("privacy gating on session documents only",
     _text(_V, '    violations = []\n\n    for event in _iter_events(data):\n        turn = event.get("turn")',
           '    violations = []\n    if is_standalone_event(data) or is_event_batch(data):\n        return []\n    for event in _iter_events(data):\n        turn = event.get("turn")',
           "privacy-violation-query-at-minimal-standalone.json")),
    ("content-identifier rule on session documents only",
     _text(_V, '    violations = []\n    for event in _iter_events(data):\n        if event.get("type") not in CONTENT_EVENT_TYPES:',
           '    violations = []\n    if is_standalone_event(data) or is_event_batch(data):\n        return []\n    for event in _iter_events(data):\n        if event.get("type") not in CONTENT_EVENT_TYPES:',
           "grounded-missing-identifier-standalone.json")),
    ("ip_hash prohibition on standalone envelopes only",
     _text(_V, '    violations = []\n    for event in _iter_events(data):\n        event_data = event.get("data")\n        if not isinstance(event_data, dict):\n            continue\n        for field, reason',
           '    violations = []\n    if not is_standalone_event(data):\n        return []\n    for event in _iter_events(data):\n        event_data = event.get("data")\n        if not isinstance(event_data, dict):\n            continue\n        for field, reason',
           "withdrawn-ip-hash-session.json")),
    ("domains check accepts lookalike hosts (endswith without the dot)",
     _text(_V, 'not bare.endswith("." + host)', 'not bare.endswith(host)', "manifest-lookalike-domain.json")),
    ("drop the source_role requirement on retrievals",
     _text(_V, 'if etype == "content_retrieved" and not event.get("source_role"):', 'if False:',
           "retrieved-missing-source-role.json")),
    ("drop the field-placement rules",
     _text(_V, '            if event.get(field) is not None and etype not in allowed:', '            if False:',
           "ctx-token-on-grounded.json")),
    ("drop the duplicate event id rule",
     _text(_V, '            if eid in seen_ids:', '            if False:', "duplicate-event-id.json")),
    ("drop the same-content rule for engagements",
     _text(_V, 'if pid in presented and not _same_content(e, presented[pid]):', 'if False:',
           "engaged-presentation-content-mismatch.json")),
    ("drop the one-token-one-presentation rule",
     _text(_V, '                if bound != pid:', '                if False:', "shared-ctx-token-two-presentations.json")),
    ("drop the envelope ctx_token rule",
     _text(_V, "    if not data.get(\"ctx_token\"):\n        return []\n    violations = []", "    return []\n    violations = []",
           "standalone-ctx-token-non-engagement.json")),
    ("drop the root-manifest rule for domains",
     _text(_V, 'if "domains" in data and parsed.path != "/.well-known/content-telemetry.json":', 'if False:',
           "manifest-domains-on-path-manifest.json")),
    ("drop the agent/platform rule for ctx_resolution",
     _text(_V, 'if telemetry.get("ctx_resolution") and not roles & {"agent", "platform"}:', 'if False:',
           "manifest-ctx-resolution-on-content-owner.json")),
    # telemetry-session.json
    ("accept the v0.1 wire version",
     _text(_S, '"const": "1.0",\n      "description": "Content Telemetry schema version"',
           '"enum": ["0.1", "1.0"],\n      "description": "Content Telemetry schema version"',
           "legacy-schema-version-0-1.json")),
    ("remove the event-level ctx_token pattern",
     _json(_S, lambda d: d["$defs"]["TelemetryEvent"]["properties"]["ctx_token"].pop("pattern"),
           "event-level-ctx-token-bad-pattern.json")),
    ("remove format:uuid from event ids",
     _json(_S, lambda d: [d["$defs"]["TelemetryEvent"]["properties"][k].pop("format") for k in ("id", "citation_id", "presentation_id")],
           "malformed-event-id.json")),
    ("open the CitationType enum",
     _json(_S, lambda d: d["$defs"]["CitationType"].pop("enum"), "citation-type-invalid.json")),
    ("open the CitationPosition enum",
     _json(_S, lambda d: d["$defs"]["CitationPosition"].pop("enum"), "citation-position-invalid.json")),
    ("open the GroundingScope enum",
     _json(_S, lambda d: d["$defs"]["GroundingScope"].pop("enum"), "grounding-scope-invalid.json")),
    ("open the SourceProvenance enum",
     _json(_S, lambda d: d["$defs"]["SourceProvenance"].pop("enum"), "grounding-provenance-invalid.json")),
    ("drop required scope on content_grounded",
     _json(_S, lambda d: _event_branch(d, "content_grounded")["properties"]["data"].pop("required"),
           "grounding-scope-missing.json")),
    ("drop required data on content_grounded",
     _json(_S, lambda d: _event_branch(d, "content_grounded")["required"].remove("data"), "grounding-missing-data.json")),
    ("drop required data on content_presented",
     _json(_S, lambda d: _event_branch(d, "content_presented")["required"].remove("data"), "presented-missing-data.json")),
    ("drop required data on content_cited",
     _json(_S, lambda d: _event_branch(d, "content_cited")["required"].remove("data"), "cited-missing-data.json")),
    ("remove the sha256 hash patterns",
     _text(_S, '"pattern": "^sha256:[a-f0-9]{64}$"', '"type": "string"', "malformed-content-hash.json")),
    ("remove minLength on identifier-scheme prefix",
     _json(_M, lambda d: d["properties"]["identifier_schemes"]["items"]["properties"]["prefix"].pop("minLength"), "manifest-identifier-scheme-empty-prefix.json")),
    ("drop the identifier_schemes owner-role placement check",
     _text(_V, 'if data.get("identifier_schemes") and "content_owner" not in roles:', 'if False:',
           "manifest-identifier-schemes-on-non-owner.json")),
    ("remove minLength on output_id",
     _json(_S, lambda d: d["$defs"]["TelemetryEvent"]["properties"]["output_id"].pop("minLength"), "empty-output-id.json")),
    ("remove minimum on tokens_ingested",
     _json(_S, lambda d: _event_branch(d, "content_grounded")["properties"]["data"]["properties"]["tokens_ingested"].pop("minimum"),
           "grounded-negative-tokens-ingested.json")),
    ("remove minimum on excerpt_chars",
     _json(_S, lambda d: _event_branch(d, "content_cited")["properties"]["data"]["properties"]["excerpt_chars"].pop("minimum"),
           "cited-negative-excerpt-chars.json")),
    ("remove the response_status bounds",
     _json(_S, lambda d: _event_branch(d, "content_retrieved")["properties"]["data"]["properties"]["response_status"].pop("maximum"),
           "retrieved-response-status-out-of-range.json")),
    ("remove the country pattern",
     _json(_S, lambda d: _event_branch(d, "content_retrieved")["properties"]["data"]["properties"]["country"].pop("pattern"),
           "retrieved-bad-country.json")),
    ("drop required scheme on content_fingerprint",
     _json(_S, lambda d: d["$defs"]["ContentFingerprint"]["required"].remove("scheme"), "grounding-fingerprint-missing-scheme.json")),
    ("drop format:uri from the turn URL arrays",
     _json(_S, lambda d: [d["$defs"]["ConversationTurn"]["properties"][k]["items"].pop("format") for k in ("content_urls_retrieved", "content_urls_cited")],
           "malformed-content-urls-cited.json")),
    ("drop format:date-time from started_at",
     _json(_S, lambda d: d["properties"]["started_at"].pop("format"), "malformed-started-at.json")),
    ("drop format:uuid from session_id",
     _json(_S, lambda d: d["properties"]["session_id"].pop("format"), "malformed-session-id.json")),
    # envelope schemas
    ("batch: drop the presentation_id-unless-ctx_token conditional",
     _json(_B, lambda d: d.pop("allOf"), "batch-engaged-missing-presentation-id.json")),
    ("batch: remove the envelope ctx_token pattern",
     _json(_B, lambda d: d["properties"]["ctx_token"].pop("pattern"), "batch-ctx-token-bad-pattern.json")),
    ("event envelope: drop schema_version from required",
     _json(_E, lambda d: d["required"].remove("schema_version"), "standalone-missing-schema-version.json")),
    ("event envelope: drop format:uuid from session_id",
     _json(_E, lambda d: d["properties"]["session_id"].pop("format"), "standalone-malformed-session-id.json")),
    # manifest.json
    ("manifest: drop required mode on coverage entries",
     _json(_M, lambda d: d["properties"]["telemetry"]["properties"]["coverage"]["additionalProperties"].pop("required"),
           "manifest-coverage-missing-mode.json")),
    ("manifest: drop required endpoint",
     _json(_M, lambda d: d["properties"]["telemetry"].pop("required"), "manifest-missing-endpoint.json")),
    ("manifest: drop minItems on roles",
     _json(_M, lambda d: d["properties"]["roles"].pop("minItems"), "manifest-empty-roles.json")),
    ("manifest: drop uniqueItems on roles",
     _json(_M, lambda d: d["properties"]["roles"].pop("uniqueItems"), "manifest-duplicate-roles.json")),
    ("manifest: drop the https pattern on ctx_resolution",
     _json(_M, lambda d: d["properties"]["telemetry"]["properties"]["ctx_resolution"].pop("pattern"), "manifest-ctx-resolution-http.json")),
    ("manifest: drop the https pattern on endpoint",
     _json(_M, lambda d: d["properties"]["telemetry"]["properties"]["endpoint"].pop("pattern"), "manifest-endpoint-http.json")),
    ("manifest: drop the https pattern on id",
     _json(_M, lambda d: d["properties"]["id"].pop("pattern"), "manifest-id-http.json")),
    ("manifest: drop the well-known location pattern on id",
     _json(_M, lambda d: d["properties"]["id"].pop("pattern"), "manifest-id-not-well-known.json")),
    ("manifest: drop format:uri on id",
     _json(_M, lambda d: d["properties"]["id"].pop("format"), "manifest-id-not-a-uri.json")),
    ("manifest: drop const Ed25519 on keys[].type",
     _json(_M, lambda d: d["properties"]["keys"]["items"]["properties"]["type"].pop("const"), "manifest-bad-key-type.json")),
    ("manifest: drop required id on keys[]",
     _json(_M, lambda d: d["properties"]["keys"]["items"]["required"].remove("id"), "manifest-key-missing-id.json")),
]

MUTATIONS += REVIEW_MUTATIONS


def run_one(name, mutate):
    with tempfile.TemporaryDirectory(prefix="ct-mutation-") as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        for schema in ("telemetry-session.json", "telemetry-event.json",
                       "telemetry-event-batch.json", "manifest.json"):
            shutil.copy(REPO / schema, root / schema)
        shutil.copytree(REPO / "tests", root / "tests")
        expected_fixture = mutate(root)
        proc = subprocess.run(
            [sys.executable, str(root / "tests" / "validate.py")],
            capture_output=True, text=True,
        )
        caught = proc.returncode != 0 and f"FAIL  {expected_fixture}" in proc.stdout
        return caught, expected_fixture, proc


def main():
    survivors = 0
    for name, mutate in MUTATIONS:
        caught, fixture, proc = run_one(name, mutate)
        if caught:
            print(f"  CAUGHT    {name}  (failed via {fixture})")
        else:
            survivors += 1
            print(f"  SURVIVED  {name}  (expected {fixture} to fail)")
            print(f"            exit={proc.returncode}")
            for line in proc.stdout.splitlines()[-5:]:
                print(f"            {line}")
    print()
    print("=" * 60)
    print(f"SUMMARY: {len(MUTATIONS) - survivors}/{len(MUTATIONS)} mutations caught")
    print("=" * 60)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
