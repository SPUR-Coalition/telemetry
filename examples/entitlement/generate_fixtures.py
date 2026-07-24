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
                revoked: list[int]) -> str:
    bits = bytearray(16384)
    for idx in revoked:
        bits[idx // 8] |= 1 << (7 - (idx % 8))  # MSB-first per W3C Bitstring Status List
    payload = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": url,
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "issuer": issuer,
        "validFrom": "2026-01-01T00:00:00Z",
        "credentialSubject": {"id": url, "type": "BitstringStatusList",
                              "statusPurpose": "revocation",
                              "encodedList": "u" + b64url(gzip.compress(bytes(bits)))},
    }
    return sign_jwt(priv, {"alg": "EdDSA", "typ": "vc+jwt", "cty": "vc"}, payload)


def credential(issuer, kid, priv, *, jti, index, sl_url,
               valid_from="2026-05-01T00:00:00Z", valid_until="2027-05-01T00:00:00Z"):
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
            "grantee": "agent.assistant.example",
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


def event(ref: str, ts: str) -> dict:
    return {
        "type": "content_grounded",
        "timestamp": ts,
        "content_url": "https://publisher.example/articles/8123",
        "content_id": "ct:publisher.example:8123",
        "license_ref": ref,
        "data": {"content_fingerprint": {"sha256": ASSET_SHA},
                 "provenance": {"source": "publisher-feed"}},
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

    files = {
        "credential-valid.jwt": valid_jwt,
        "credential-revoked.jwt": revoked_jwt,
        "credential-expired.jwt": expired_jwt,
        "credential-tampered.jwt": tampered_jwt,
        "credential-other-issuer.jwt": b_valid_jwt,
        "did-licensor.example.json": json.dumps(did_document(a_issuer, a_kid, a_priv), indent=2),
        "did-publisher.example.json": json.dumps(did_document(b_issuer, b_kid, b_priv), indent=2),
        "statuslist-licensor.jwt": status_list(a_issuer, a_sl_url, a_priv, [1]),
        "statuslist-publisher.jwt": status_list(b_issuer, b_sl_url, b_priv, []),
        "event-valid.json": json.dumps(event("grant-valid-001", "2026-07-01T10:00:00Z"), indent=2),
        "event-revoked.json": json.dumps(event("grant-revoked-002", "2026-07-01T10:00:00Z"), indent=2),
        "event-expired.json": json.dumps(event("grant-expired-003", "2026-07-01T10:00:00Z"), indent=2),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")

    manifest = {
        "description": "license_ref -> credential resolution map for offline verification",
        "credentials": [
            {"license_ref": "grant-valid-001", "credential": "credential-valid.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt"},
            {"license_ref": "grant-revoked-002", "credential": "credential-revoked.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt"},
            {"license_ref": "grant-expired-003", "credential": "credential-expired.jwt",
             "did_document": "did-licensor.example.json", "status_list": "statuslist-licensor.jwt"},
            {"license_ref": "pub-grant-001", "credential": "credential-other-issuer.jwt",
             "did_document": "did-publisher.example.json", "status_list": "statuslist-publisher.jwt"},
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(files) + 1} fixtures to {OUT} (asset sha256 {ASSET_SHA[:16]}...)")


if __name__ == "__main__":
    main()
