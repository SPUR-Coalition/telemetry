# Entitlement evidence profile

**Status:** consultation draft — placement, naming and adoption subject to the v1 core/profile/governing-terms scope decision (#26)
**Profile identifier:** `entitlement-evidence/0.1`
**Depends on:** SPECIFICATION.md §5.2 (`license_ref`), §8 (manifest)
**Related:** #22 (motivating issue), #21/#11 (evidence classifications), #4/#3 (governing-terms reference), #25 (modality — see §7.2)

## 1. Purpose and scope

### 1.1 Purpose

This profile defines how a `license_ref` (§5.2) MAY resolve to a verifiable grant, and how a consumer classifies the resulting **entitlement evidence**. It addresses SCOPE.md question 5 — *was the reported use permitted under an applicable grant or agreement?* — as a bounded evidence classification, using only existing core fields.

### 1.2 Non-goals

Consistent with SCOPE.md ("telemetry does not determine ownership, permission, price or compensation") and §1.3, this profile does NOT:

- define licence terms, tariffs, pricing or compensation logic;
- determine ownership or resolve competing claims — a credential proves a party made a *signed, revocable declaration* about an asset, never that it owns it;
- introduce new event types, envelope fields or transport requirements;
- make core conformance depend on any external registry, resolver or verification service.

An implementation that ignores this profile remains fully core-conformant. A `license_ref` that cannot be verified under this profile is **downgraded in evidence class, never invalidated as an event**.

### 1.3 Relationship to the governing-terms layer

This profile verifies that a grant *exists, was issued by an identifiable issuer to an identifiable grantee, and covered the reported use at the reported time*. What the grant permits in legal detail lives in a governing-terms document, referenced from the credential via `credentialSubject.terms_ref` (§4.2) — the terms-document locator kept distinct from `license_ref`, as proposed in #3/#4. Governing-terms semantics are out of scope here.

## 2. Conformance language

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be interpreted as described in RFC 2119 and RFC 8174 (§1.5).

## 3. Entitlement evidence classes

This profile applies the evidence classifications proposed in #11/#21 to the entitlement axis. If those classifications land in v1 under different names, this profile adopts the landed names; the semantics below are what is normative.

| Class | Meaning for `license_ref` | Verification |
|---|---|---|
| `claim` | Opaque reference (§5.2.3 opaque form or unresolvable URI); resolvable bilaterally, not by third parties | none |
| `origin_corroborated` | Resolves to a well-formed entitlement credential whose declared issuer is identifiable | §5 steps 1–2 |
| `independently_verifiable` | Full recipe against a public trust anchor (`did:web` or manifest keys) with a trusted timestamp for status (§5.4) — matching the #11 tier-3 test of "checkable by any party against a public trust anchor and a trusted timestamp" | §5 steps 1–6 |

Consumers producing settlement or dispute artefacts SHOULD record, per event, the evidence class established, the verification timestamp and (where §5.4(b) applies) the status-list snapshot used.

## 4. The entitlement credential

### 4.1 Format

An entitlement credential is a W3C Verifiable Credential (Data Model 2.0) secured as a JWT per VC-JOSE-COSE: the credential is the JWS payload, header `typ: "vc+jwt"`. The signing algorithm MUST be `EdDSA` (Ed25519); verifiers MUST reject other `alg` values. A header `kid` naming a key absent from the issuer's published keys MUST fail verification — verifiers MUST NOT fall back to another published key.

`license_ref` carries one of: an HTTPS URL dereferencing to the credential; the credential's grant identifier (the §5.2.3 JWT-`jti` form), resolvable against the issuer's declared credential endpoint; or the compact JWS embedded directly (NOT RECOMMENDED above ~4 KB).

### 4.2 Credential body

The decoded payload MUST validate against `schemas/entitlement-credential.json`. In summary:

| Claim | Requirement |
|---|---|
| `issuer` | REQUIRED — `did:web` DID or HTTPS URL under the issuer's apex domain; the grantor or its licensing agent (publisher, collecting society or intermediary) |
| `validFrom` / `validUntil` | REQUIRED — validity window of the credential itself |
| `credentialStatus` | Bitstring Status List v1.0 entry; OPTIONAL only when `validUntil − validFrom` ≤ 30 days, otherwise REQUIRED |
| `credentialSubject.grantee` | REQUIRED — MUST match the reporting session's `agent_id` or a declared parent operator (§5 step 5) |
| `credentialSubject.rights` | REQUIRED — rights object per §4.5, each entry carrying `granted` |
| `credentialSubject.scope.duration` | OPTIONAL `starts`/`ends` licence term, possibly narrower than the credential window; absent → the credential window is the term |
| `credentialSubject.asset.sha256` | per-asset grants: digest the grant binds to (§5 step 6) |
| `credentialSubject.scope.content` | blanket grants: apex domains and/or `content_id` patterns mirroring session `content_scope` (§5.1); at least one of `asset.sha256` / `scope.content` REQUIRED |
| `credentialSubject.terms_ref` | REQUIRED — URL of the governing-terms document; a grant without discoverable terms is not opposable |

Verifiers encountering a credential missing `grantee` or `terms_ref` cap the evidence class at `origin_corroborated` (downgrade, not invalidation).

### 4.3 Sandbox credentials

Credentials whose `type` marks them as sandbox-issued MUST be rejected by production verifiers and yield at most class `claim` with a diagnostic warning.

### 4.4 Issuer key discovery

Consumers MUST support, in order of preference: (1) **`did:web`** — resolve `https://<domain>/.well-known/did.json` and use `verificationMethod` entries carrying `publicKeyJwk` (OKP/Ed25519); (2) **manifest keys** — the issuer's `.well-known/content-telemetry.json` `keys[]` array (§8), reusing the manifest mechanism already in core. Key material MUST be fetched over TLS from the issuer's apex domain or DID document. Consumers SHOULD cache keys and status lists with retrieval timestamps and MUST NOT require online resolution to accept an *event*: offline consumers record the evidence class their cached material supports.

### 4.5 Rights vocabulary and event mapping

Grants use the rights vocabulary `train, rag, embed, display, eval, derive, commercial`. Core telemetry covers inference-time use only (§1.3), so entitlement checks for core events consult:

| Core event type | Covering right |
|---|---|
| `content_retrieved` | `rag` (`embed` where retrieval is for embedding) |
| `content_grounded` | `rag` |
| `content_cited` | `rag` |
| `content_displayed` | `display` |
| engagement events | `display` |

`train`, `eval`, `derive` and `commercial` are carried for the governing-terms layer and non-telemetry consumers; they play no role in classifying core inference-time events.

## 5. Verification recipe (normative)

Given an event `E` carrying `license_ref` `R`, occurrence time `t = E.timestamp`, verification time `T`:

1. **Resolve** `R` to a credential `C` per §4.1. Failure → `claim`; stop.
2. **Parse** `C` against the schema; confirm `issuer` is identifiable per §4.4. Failure → `claim`. Success → at least `origin_corroborated`.
3. **Verify signature** against the issuer key (strict `alg`/`kid`, §4.1). Failure → `claim`; the consumer SHOULD additionally flag the credential as malformed evidence. Flagging is diagnostic, never event-invalidating.
4. **Temporal validity and status:**
   (a) `validFrom ≤ t ≤ validUntil`, and `t` within `scope.duration` where present.
   (b) Check `credentialStatus` against the status list. A set bit fails this step regardless of when the revocation occurred, UNLESS the consumer holds a status-list snapshot retrieved at some time `s ≥ t` in which the bit is clear — the grant was then demonstrably unrevoked when the use occurred, and the consumer MAY pass, recording the snapshot reference. Bitstring status lists carry no revocation timestamps, so the current list cannot prove *when* a bit was set: conservatism is the default, dated snapshots the escape hatch. Settlement-grade consumers SHOULD retain periodic dated snapshots.
   (c) A `statusListIndex` outside the decoded bitstring is an **error** (credential and list disagree), not "not revoked". Fail closed.
5. **Match grantee:** session `agent_id` (or declared parent operator) equals `credentialSubject.grantee`.
6. **Bind content:** for per-asset grants, `E`'s content digest (`content_hash`, or `data.content_fingerprint` where the #10/#21 fields are present) equals `credentialSubject.asset.sha256`; for blanket grants, `E.content_url`/`E.content_id` falls within `scope.content`. `E.type` MUST be covered per §4.5. Digest binding is REQUIRED where both digests are available; URL-pattern matching alone caps a per-asset grant at `origin_corroborated`.

All six steps → `independently_verifiable`.

**Binding of the outcome.** Where the consuming context adopts the canonical assertion binding of #21, the verification result is itself an assertion over `E` and MUST be bound to `E` via its RFC 8785 canonical digest, so an outcome cannot be re-attached to a different event.

## 6. Privacy and operational considerations

Verification is consumer-side and read-only; issuers learn nothing about individual events beyond ordinary web traffic — status lists are bitstring documents, not per-credential endpoints, which is why Bitstring Status List is the required mechanism. Credentials identify parties and grants, not end users; events retain their core `privacy_level` semantics (§9) and this profile adds no personal data. Caching: keys ≤ 24 h or per document `expires`; status lists ≤ 15 min in settlement contexts, ≤ 24 h otherwise — always stored with retrieval timestamps so caches double as §5.4(b) snapshots. Offline operation is first-class: pinned DID documents plus dated snapshots reach `independently_verifiable` with zero network access.

## 7. Limitations and deferred work

### 7.1 Backwards compatibility

Purely additive. All fields are optional at core level; existing consumers ignore `license_ref` resolution entirely and remain conformant. No conformance-level designation is required (per CONTRIBUTING, optional fields carry none).

### 7.2 Derived and bounded representations (deferred to #25)

This version binds **whole-asset digests and URL/identifier scopes only**. Events reporting a *derived or bounded* representation — a transcript of audio, a region of an image, a segment of video — will not digest-match the asset a grant names, and under this version cap at `origin_corroborated`. Rather than invent derivation semantics here, this profile defers to the resolution of #25 and the fingerprint scheme-property model of #11: when the fingerprint layer can express "representation X derives from asset Y" verifiably, step 6 will consume that relation as-is. The `derive` right in §4.5 is the reserved hook for whether such a use is covered.

### 7.3 Reference implementations (informative)

The recipe is implemented independently in Python and TypeScript with an executable cross-runtime parity check (identical `(valid, checks)` on every fixture), from published standards only — W3C VC 2.0, VC-JOSE-COSE, `did:web`, Bitstring Status List v1.0. The fixtures in `examples/entitlement/` are implementation-neutral: two unrelated issuers, no shared infrastructure, regenerable via the included script, and structurally validated by `tests/test_entitlement_examples.py` with the repository's existing jsonschema tooling.
