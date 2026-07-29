#!/usr/bin/env python3
"""Regenerate the entitlement-evidence example fixtures (optional dev tool).

Requires ``cryptography`` (not needed by the CI test suite, which validates the
committed fixtures with jsonschema only). Mints fresh Ed25519 keys per run:

  * two independent issuers — ``did:web:licensor.example`` (a collecting
    society / licensing agent) and ``did:web:publisher.example`` (a publisher
    issuing directly) — no shared infrastructure, proving issuer neutrality;
  * credentials: valid / revoked / expired / tampered / other-issuer;
  * a DID document and a Bitstring Status List (revoked bit set) per issuer;
  * core-shaped telemetry events whose ``license_ref`` resolves to the
    credentials, with ``data.content_fingerprint`` digest binding;
  * ``manifest.json`` mapping ``license_ref`` -> fixture files.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

OUT = Path(__file__).parent
SAMPLE_TEXT = b"The quick brown fox jumps over the lazy dog."
ASSET_SHA = hashlib.sha256(SAMPLE_TEXT).hexdigest()


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def sign_jwt(priv: Ed25519PrivateKey, header: dict, payload: dict) -> str:
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    return f"{h}.{p}.{b64url(priv.sign((h + '.' + p).encode()))}"


def jwk_of(priv: Ed25519PrivateKey) -> dict:
    return {"kty": "OKP", "crv": "Ed25519",
            "x": b64url(priv.public_key().public_bytes_raw())}


def did_document(issuer: str, kid: str, priv: Ed25519PrivateKey) -> dict:
    return {
        "@context": ["https://www.w3.org/ns/did/v1",
                     "https://w3id.org/security/suites/jws-2020/v1"],
        "id": issuer,
        "verificationMethod": [{"id": kid, "type": "JsonWebKey2020",
                                "controller": issuer, "publicKeyJwk": jwk_of(priv)}],
        "assertionMethod": [kid],
    }


def status_list(issuer: str, url: str, priv: Ed25519PrivateKey,
                revoked: list[int], valid_from: str = "2026-01-01T00:00:00Z") -> str:
    bits = bytearray(16384)
    for idx in revoked:
        bits[idx // 8] |= 1 << (7 - (idx % 8))  # MSB-first per W3C Bitstring Status List
    payload = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": url,
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "issuer": issuer,
        "validFrom": valid_from,
        "credentialSubject": {"id": url, "type": "BitstringStatusList",
                              "statusPurpose": "revocation",
                              "encodedList": "u" + b64url(gzip.compress(bytes(bits)))},
    }
    return sign_jwt(priv, {"alg": "EdDSA", "typ": "vc+jwt", "cty": "vc"}, payload)


def credential(issuer, kid, priv, *, jti, index, sl_url,
               valid_from="2026-05-01T00:00:00Z", valid_until="2027-05-01T00:00:00Z",
               grantee="agent.assistant.example"):
    payload = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": f"https://{issuer.split(':')[2]}/credentials/{jti}",
        "jti": jti,
        "type": ["VerifiableCredential", "ContentLicenceCredential"],
        "issuer": issuer,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            "id": f"urn:asset:{ASSET_SHA}",
            "grantee": grantee,
            "asset": {"sha256": ASSET_SHA, "media_type": "text"},
            "rights": {
                "rag": {"granted": True, "scope": {"max_excerpt_tokens": 512}},
                "display": {"granted": True, "scope": {"max_excerpt_tokens": 128}},
                "train": {"granted": False},
                "embed": {"granted": False},
                "eval": {"granted": True},
                "derive": {"granted": False},
                "commercial": {"granted": False},
            },
            "scope": {
                "duration": {"starts": valid_from, "ends": valid_until},
                "jurisdiction": ["EU"],
                "attribution": {"required": True, "format": "Source: {issuer}"},
                "revocable": True,
            },
            "terms_ref": f"https://{issuer.split(':')[2]}/terms/2026-v1",
        },
        "credentialStatus": {
            "id": f"{sl_url}#{index}",
            "type": "BitstringStatusListEntry", "statusPurpose": "revocation",
            "statusListIndex": str(index), "statusListCredential": sl_url,
        },
    }
    return sign_jwt(priv, {"alg": "EdDSA", "typ": "vc+jwt", "cty": "vc", "kid": kid},
                    payload), payload


def event(ref: str, ts: str, event_id: str) -> dict:
    """A valid v1 standalone event document (telemetry-event.json)."""
    return {
        "document_type": "event",
        "schema_version": "0.1",
        "session_id": "6f1c2a54-0000-4000-8000-000000000001",
        "agent_id": "agent.assistant.example",
        "started_at": "2026-07-01T09:58:00Z",
        "event": {
            "id": event_id,
            "type": "content_grounded",
            "timestamp": ts,
            "turn_id": "turn-1",
            "source_role": "agent",
            "content_url": "https://publisher.example/articles/8123",
            "content_id": "ct:publisher.example:8123",
            "license_ref": ref,
            "data": {
                "scope": "turn",
                "media_type": "text",
                "tokens_ingested": 512,
                "content_hash": f"sha256:{ASSET_SHA}",
            },
        },
    }


def main() -> None:
    a_issuer, b_issuer = "did:web:licensor.example", "did:web:publisher.example"
    a_kid, b_kid = f"{a_issuer}#key-1", f"{b_issuer}#key-1"
    a_priv, b_priv = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    a_sl_url = "https://licensor.example/status/2026"
    b_sl_url = "https://publisher.example/status/2026"

    valid_jwt, valid_pl = credential(a_issuer, a_kid, a_priv,
                                     jti="grant-valid-001", index=0, sl_url=a_sl_url)
    revoked_jwt, _ = credential(a_issuer, a_kid, a_priv,
                                jti="grant-revoked-002", index=1, sl_url=a_sl_url)
    expired_jwt, _ = credential(a_issuer, a_kid, a_priv, jti="grant-expired-003",
                                index=2, sl_url=a_sl_url,
                                valid_from="2024-01-01T00:00:00Z",
                                valid_until="2025-01-01T00:00:00Z")
    # tampered: valid signature, mutated payload (a right forged on)
    h, p, s = valid_jwt.split(".")
    pl = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    pl["credentialSubject"]["rights"]["commercial"]["granted"] = True
    tampered_jwt = f"{h}.{b64url(json.dumps(pl, separators=(',', ':')).encode())}.{s}"

    b_valid_jwt, _ = credential(b_issuer, b_kid, b_priv,
                                jti="pub-grant-001", index=0, sl_url=b_sl_url)

    # negative fixture: signed with key-1 but header names an unpublished key-2 —
    # verifiers MUST fail this (no fallback to another published key)
    unknown_kid_jwt, _ = credential(a_issuer, f"{a_issuer}#key-2", a_priv,
                                    jti="grant-unknownkid-004", index=3, sl_url=a_sl_url)

    # negative fixture: grant issued to a different agent than the one reporting
    # the event — fails the grantee match (profile 5.5)
    grantee_mismatch_jwt, _ = credential(a_issuer, a_kid, a_priv,
                                         jti="grant-granteemismatch-005", index=4,
                                         sl_url=a_sl_url, grantee="agent.other.example")

    # revoked-after-use: bit 5 is SET in the current list (signed validFrom 2026-07-24)
    # but CLEAR in the issuer-signed snapshot (signed validFrom 2026-07-05, after the
    # 2026-07-01 event). The snapshot's own signed validFrom — not any locally recorded
    # retrieval time — is what proves the grant was unrevoked at the use (profile 5.4(c)).
    revoked_late_jwt, _ = credential(a_issuer, a_kid, a_priv,
                                     jti="grant-revokedlate-006", index=5, sl_url=a_sl_url)

    files = {
        "credential-valid.jwt": valid_jwt,
        "credential-revoked.jwt": revoked_jwt,
        "credential-expired.jwt": expired_jwt,
        "credential-tampered.jwt": tampered_jwt,
        "credential-other-issuer.jwt": b_valid_jwt,
        "credential-unknown-kid.jwt": unknown_kid_jwt,
        "credential-grantee-mismatch.jwt": grantee_mismatch_jwt,
        "credential-revoked-late.jwt": revoked_late_jwt,
        "did-licensor.example.json": json.dumps(did_document(a_issuer, a_kid, a_priv), indent=2),
        "did-publisher.example.json": json.dumps(did_document(b_issuer, b_kid, b_priv), indent=2),
        "statuslist-licensor.jwt": status_list(
            a_issuer, a_sl_url, a_priv, [1, 5], valid_from="2026-07-24T00:00:00Z"),
        "statuslist-licensor-snapshot.jwt": status_list(
            a_issuer, a_sl_url, a_priv, [1], valid_from="2026-07-05T00:00:00Z"),
        "statuslist-publisher.jwt": status_list(b_issuer, b_sl_url, b_priv, []),
        "event-valid.json": json.dumps(event(
            "grant-valid-001", "2026-07-01T10:00:00Z",
            "9a3c7c10-0000-4000-8000-000000000101"), indent=2),
        "event-revoked.json": json.dumps(event(
            "grant-revoked-002", "2026-07-01T10:00:00Z",
            "9a3c7c10-0000-4000-8000-000000000102"), indent=2),
        "event-expired.json": json.dumps(event(
            "grant-expired-003", "2026-07-01T10:00:00Z",
            "9a3c7c10-0000-4000-8000-000000000103"), indent=2),
        "event-grantee-mismatch.json": json.dumps(event(
            "grant-granteemismatch-005", "2026-07-01T10:00:00Z",
            "9a3c7c10-0000-4000-8000-000000000104"), indent=2),
        "event-revoked-late.json": json.dumps(event(
            "grant-revokedlate-006", "2026-07-01T10:00:00Z",
            "9a3c7c10-0000-4000-8000-000000000105"), indent=2),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")

    manifest = {
        "description": "license_ref -> credential resolution map for offline verification. "
                       "Historical-status reasoning (profile section 5.4(c)) trusts only the "
                       "signed validFrom inside a status-list credential — issuer-attested time — "
                       "never a locally recorded retrieval time, which proves nothing about what "
                       "the issuer had published. expect states the reference outcome, reported "
                       "as 'grant evidence verified' at the stated class — never as an "
                       "adjudication of entitlement.",
        "credentials": [
            {"license_ref": "grant-valid-001", "credential": "credential-valid.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "expect": "grant evidence verified (independently_verifiable)"},
            {"license_ref": "grant-revoked-002", "credential": "credential-revoked.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "expect": "fails 5.4(b): status bit set"},
            {"license_ref": "grant-expired-003", "credential": "credential-expired.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "expect": "fails 5.4(a): outside validity window"},
            {"license_ref": "pub-grant-001", "credential": "credential-other-issuer.jwt",
             "did_document": "did-publisher.example.json", "status_list": "statuslist-publisher.jwt",
             "expect": "grant evidence verified (independently_verifiable), second issuer"},
            {"license_ref": "grant-unknownkid-004", "credential": "credential-unknown-kid.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "expect": "fails 5.3/4.1: kid absent from DID document, no fallback"},
            {"license_ref": "grant-granteemismatch-005",
             "credential": "credential-grantee-mismatch.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "expect": "fails 5.5: credential grantee agent.other.example does not match "
                       "reporting agent_id"},
            {"license_ref": "grant-revokedlate-006", "credential": "credential-revoked-late.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt",
             "snapshot_status_list": "statuslist-licensor-snapshot.jwt",
             "expect": "current list: bit set -> fails 5.4(c) by default (retroactive). With the "
                       "issuer-signed snapshot (signed validFrom 2026-07-05 >= event time, bit "
                       "clear): grant evidence verified (independently_verifiable) via the "
                       "5.4(c) signed-snapshot path"},
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(files) + 1} fixtures to {OUT} (asset sha256 {ASSET_SHA[:16]}...)")


if __name__ == "__main__":
    main()
