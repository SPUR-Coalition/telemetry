"""Validate the entitlement-evidence example fixtures (jsonschema + stdlib only).

Structural validation matching the repository's existing tooling: no
cryptographic dependencies. Signature, revocation and binding semantics are
defined in profiles/entitlement-evidence.md and exercised by external
reference implementations; this suite proves the committed fixtures conform
to the credential schema and that every event's license_ref resolves.

Run: python tests/test_entitlement_examples.py  (or via pytest / uv run)
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "entitlement"
SCHEMA = json.loads((ROOT / "schemas" / "entitlement-credential.json").read_text("utf-8"))

CREDENTIALS = [
    "credential-valid.jwt",
    "credential-revoked.jwt",
    "credential-expired.jwt",
    "credential-tampered.jwt",  # forged payload is still schema-valid; crypto catches it
    "credential-other-issuer.jwt",
]
EVENTS = ["event-valid.json", "event-revoked.json", "event-expired.json"]


def _jwt_payload(token: str) -> dict:
    seg = token.strip().split(".")[1]
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))


def test_credentials_match_schema():
    for name in CREDENTIALS:
        payload = _jwt_payload((EX / name).read_text("utf-8"))
        jsonschema.validate(payload, SCHEMA)


def test_credentials_carry_profile_required_claims():
    for name in CREDENTIALS:
        subject = _jwt_payload((EX / name).read_text("utf-8"))["credentialSubject"]
        assert subject["grantee"], name
        assert subject["terms_ref"].startswith("https://"), name


def test_events_resolve_via_manifest():
    manifest = json.loads((EX / "manifest.json").read_text("utf-8"))
    refs = {c["license_ref"]: c for c in manifest["credentials"]}
    for name in EVENTS:
        ev = json.loads((EX / name).read_text("utf-8"))
        assert ev["license_ref"] in refs, f"{name}: unresolvable license_ref"
        entry = refs[ev["license_ref"]]
        for key in ("credential", "did_document", "status_list"):
            assert (EX / entry[key]).exists(), f"{name}: missing {entry[key]}"


def test_event_digest_matches_credential_asset():
    manifest = json.loads((EX / "manifest.json").read_text("utf-8"))
    refs = {c["license_ref"]: c for c in manifest["credentials"]}
    for name in EVENTS:
        ev = json.loads((EX / name).read_text("utf-8"))
        cred = _jwt_payload((EX / refs[ev["license_ref"]]["credential"]).read_text("utf-8"))
        ev_sha = ev["data"]["content_fingerprint"]["sha256"]
        assert ev_sha == cred["credentialSubject"]["asset"]["sha256"], name


def test_status_lists_are_bitstring_credentials():
    for name in ("statuslist-licensor.jwt", "statuslist-publisher.jwt"):
        payload = _jwt_payload((EX / name).read_text("utf-8"))
        assert "BitstringStatusListCredential" in payload["type"], name
        assert payload["credentialSubject"]["encodedList"].startswith("u"), name


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed.")
    sys.exit(0)
