#!/usr/bin/env python3
"""Mutation smoke test for the conformance suite.

Replays the review's key mutations - each of which the suite previously
missed - against a scratch copy of the repository and confirms validate.py
now fails under every one of them. The working tree is never modified.

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
