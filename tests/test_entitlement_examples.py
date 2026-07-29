"""Validate the entitlement-evidence example fixtures (jsonschema + stdlib only).

Structural validation matching the repository's existing tooling: no
cryptographic dependencies. Signature, status-list authentication and binding
semantics are defined in profiles/entitlement-evidence.md and exercised by
external reference implementations; this suite proves the committed fixtures
conform to (a) the entitlement credential schema and (b) the core
telemetry-event.json schema, and that every event's license_ref resolves.

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
CRED_SCHEMA = json.loads((ROOT / "schemas" / "entitlement-credential.json").read_text("utf-8"))

CREDENTIALS = [
    "credential-valid.jwt",
    "credential-revoked.jwt",
    "credential-expired.jwt",
    "credential-tampered.jwt",   # forged payload is still schema-valid; crypto catches it
    "credential-other-issuer.jwt",
    "credential-unknown-kid.jwt",  # schema-valid; fails at signature step (no kid fallback)
    "credential-grantee-mismatch.jwt",  # schema-valid; fails the 5.5 grantee match
    "credential-revoked-late.jwt",  # bit set in current list, clear in signed snapshot
]
EVENTS = ["event-valid.json", "event-revoked.json", "event-expired.json",
          "event-grantee-mismatch.json", "event-revoked-late.json"]


def _jwt_payload(token: str) -> dict:
    seg = token.strip().split(".")[1]
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))


def _core_event_validator():
    """Validator for the core standalone event document schema, resolving the
    cross-file $ref into telemetry-session.json. Both files live at repo root."""
    for name in ("telemetry-event.json", "telemetry-session.json"):
        if not (ROOT / name).exists():
            raise SystemExit(
                f"{name} not found at repository root — this suite runs inside the "
                "SPUR-Coalition/telemetry repository, whose core schemas it validates against."
            )
    event_schema = json.loads((ROOT / "telemetry-event.json").read_text("utf-8"))
    session_schema = json.loads((ROOT / "telemetry-session.json").read_text("utf-8"))
    try:  # jsonschema >= 4.18
        from referencing import Registry, Resource

        registry = Registry().with_resources([
            ("telemetry-session.json", Resource.from_contents(session_schema)),
            ("telemetry-event.json", Resource.from_contents(event_schema)),
        ])
        return jsonschema.Draft202012Validator(event_schema, registry=registry)
    except ImportError:  # older jsonschema
        resolver = jsonschema.RefResolver(
            base_uri="", referrer=event_schema,
            store={"telemetry-session.json": session_schema},
        )
        return jsonschema.Draft202012Validator(event_schema, resolver=resolver)


def test_credentials_match_schema():
    for name in CREDENTIALS:
        payload = _jwt_payload((EX / name).read_text("utf-8"))
        jsonschema.validate(payload, CRED_SCHEMA)


def test_credentials_carry_profile_required_claims():
    for name in CREDENTIALS:
        subject = _jwt_payload((EX / name).read_text("utf-8"))["credentialSubject"]
        assert subject["grantee"], name
        assert subject["terms_ref"].startswith("https://"), name


def test_events_are_valid_core_event_documents():
    """The editors' key requirement: fixture events MUST be valid v1 events."""
    validator = _core_event_validator()
    for name in EVENTS:
        doc = json.loads((EX / name).read_text("utf-8"))
        errors = sorted(validator.iter_errors(doc), key=lambda e: e.json_path)
        assert not errors, f"{name}: {[e.message for e in errors]}"
        assert doc["document_type"] == "event" and doc["schema_version"] == "0.1"


def test_events_resolve_via_manifest():
    manifest = json.loads((EX / "manifest.json").read_text("utf-8"))
    refs = {c["license_ref"]: c for c in manifest["credentials"]}
    for name in EVENTS:
        doc = json.loads((EX / name).read_text("utf-8"))
        ref = doc["event"]["license_ref"]
        assert ref in refs, f"{name}: unresolvable license_ref"
        for key in ("credential", "did_document", "status_list"):
            assert (EX / refs[ref][key]).exists(), f"{name}: missing {refs[ref][key]}"


def test_event_digest_matches_credential_asset():
    manifest = json.loads((EX / "manifest.json").read_text("utf-8"))
    refs = {c["license_ref"]: c for c in manifest["credentials"]}
    for name in EVENTS:
        doc = json.loads((EX / name).read_text("utf-8"))
        ref = doc["event"]["license_ref"]
        cred = _jwt_payload((EX / refs[ref]["credential"]).read_text("utf-8"))
        ev_hash = doc["event"]["data"]["content_hash"]
        assert ev_hash == f"sha256:{cred['credentialSubject']['asset']['sha256']}", name


def test_status_lists_are_bitstring_credentials():
    for name in ("statuslist-licensor.jwt", "statuslist-publisher.jwt"):
        payload = _jwt_payload((EX / name).read_text("utf-8"))
        assert "BitstringStatusListCredential" in payload["type"], name
        assert payload["credentialSubject"]["encodedList"].startswith("u"), name


def test_status_list_issuer_matches_credential_issuer():
    """Profile 5.4: the status list must be authenticatable against the same
    issuer trust anchor as the credential that points at it (structural check;
    signature verification is the reference implementations' job)."""
    manifest = json.loads((EX / "manifest.json").read_text("utf-8"))
    for entry in manifest["credentials"]:
        cred = _jwt_payload((EX / entry["credential"]).read_text("utf-8"))
        sl = _jwt_payload((EX / entry["status_list"]).read_text("utf-8"))
        assert sl["issuer"] == cred["issuer"], entry["license_ref"]


def _bit(status_list_jwt: str, index: int) -> bool:
    import gzip
    payload = _jwt_payload(status_list_jwt)
    encoded = payload["credentialSubject"]["encodedList"].lstrip("u")
    bits = gzip.decompress(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    return bool(bits[index // 8] & (1 << (7 - (index % 8))))


def test_status_purpose_is_monotonic_revocation():
    """4.2/5.4(c): the snapshot inference (clear at s >= t implies clear at t) is only
    sound for the monotonic revocation purpose — never reversible suspension. Enforce
    it on every credentialStatus entry and every status-list credential."""
    for name in CREDENTIALS:
        cs = _jwt_payload((EX / name).read_text("utf-8")).get("credentialStatus")
        if cs:
            assert cs.get("statusPurpose") == "revocation", name
    for name in ("statuslist-licensor.jwt", "statuslist-licensor-snapshot.jwt",
                 "statuslist-publisher.jwt"):
        subject = _jwt_payload((EX / name).read_text("utf-8"))["credentialSubject"]
        assert subject.get("statusPurpose") == "revocation", name


def test_grantee_mismatch_is_a_real_mismatch():
    """5.5: the fixture's credential names a different grantee than the reporting agent."""
    cred = _jwt_payload((EX / "credential-grantee-mismatch.jwt").read_text("utf-8"))
    doc = json.loads((EX / "event-grantee-mismatch.json").read_text("utf-8"))
    assert cred["credentialSubject"]["grantee"] != doc["agent_id"]
    # and the positive case really does match, so the pair is discriminating
    valid = _jwt_payload((EX / "credential-valid.jwt").read_text("utf-8"))
    valid_doc = json.loads(json.dumps(doc))
    assert valid["credentialSubject"]["grantee"] == valid_doc["agent_id"]


def test_revoked_late_snapshot_semantics():
    """5.4(c): bit SET in the current list, CLEAR in the issuer-signed snapshot, and the
    snapshot's own signed validFrom is at or after the event time — issuer-attested
    time, not locally recorded retrieval time, is what carries evidential weight."""
    cred = _jwt_payload((EX / "credential-revoked-late.jwt").read_text("utf-8"))
    index = int(cred["credentialStatus"]["statusListIndex"])
    current = (EX / "statuslist-licensor.jwt").read_text("utf-8")
    snapshot = (EX / "statuslist-licensor-snapshot.jwt").read_text("utf-8")
    assert _bit(current, index) is True
    assert _bit(snapshot, index) is False
    doc = json.loads((EX / "event-revoked-late.json").read_text("utf-8"))
    event_time = doc["event"]["timestamp"]
    snapshot_signed_time = _jwt_payload(snapshot)["validFrom"]
    assert snapshot_signed_time >= event_time  # ISO-8601 UTC strings compare lexically
    # the snapshot is issuer-signed: same issuer as the credential it vouches for
    assert _jwt_payload(snapshot)["issuer"] == cred["issuer"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed.")
    sys.exit(0)
