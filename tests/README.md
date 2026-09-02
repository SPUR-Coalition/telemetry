# Conformance test suite

Tests for the Content Telemetry Specification v1.

## Structure

- `valid/` - JSON files that MUST pass JSON Schema validation
- `invalid/` - JSON files that MUST fail validation (either JSON Schema or application-layer conformance)
- `validate.py` - Conformance test runner (requires `jsonschema`)
- `check_examples.py` - Validates the worked examples in SPECIFICATION.md and README.md against the schemas
- `mutation_smoke.py` - Replays known suite-weakening mutations against a scratch copy and confirms the suite fails under each one

## Running

From a clean checkout, with no setup beyond [uv](https://docs.astral.sh/uv/):

```sh
uv run --with "jsonschema[format-nongpl]" python tests/validate.py
uv run --with "jsonschema[format-nongpl]" python tests/check_examples.py
```

Run from the repository root. Without uv: `pip install "jsonschema[format-nongpl]"`, then `python3 tests/validate.py`. `tests/mutation_smoke.py` runs the same way, and in CI. The `format-nongpl` extra pulls in the format validators (`rfc3339-validator` and friends) that make `format: uuid` / `date-time` / `uri` assertions enforce rather than annotate; both scripts hard-error at startup if they are missing. Both commands run in CI on every pull request.

`check_examples.py` extracts every fenced `json` block from the spec and README, validates the complete top-level documents (sessions, standalone events, manifests) against the matching schema and against the application-layer rules of `validate.py`, and reports the number of fragments it skipped. A worked example that no longer matches its schema or violates a conformance rule fails the build.

## What it covers

- Session envelope required fields (`schema_version`, `session_id`, `started_at`)
- Event required fields (`type`, `timestamp`)
- Turn required fields (`privacy_level`)
- Enum validation (event types, privacy levels, source roles, schema version)
- Citation source-reference requirement (content_cited rejected when content_url/content_id are missing or null) and required citation_type
- Required event and output identifiers on cited and presented events
- Closed enums (citation_type, position, scope, provenance, presentation_kind) and non-negative counts
- Required `data.scope` on grounding events; required `source_role` on retrieval events
- Format assertions on every uuid, date-time and uri field (malformed session, event, citation, presentation and parent ids; malformed started_at; malformed turn URL arrays)
- Field placement: presentation_id and event-level ctx_token only on content_engaged, citation_id only on presented events, turn only on turn events; envelope ctx_token only with engagements
- Session integrity: distinct event ids, engagement/presentation and presentation/citation identify the same content, one token per presentation
- Rejection of documents declaring the v0.1 wire version
- All three conformance levels (Retrieval, Grounding, Citation) and all four source roles (origin, edge, index, agent)
- Every core engagement type, citation type, position and presentation type; a destination-reported engagement batch; a multi-owner catalogue session under one agreement
- Manifests for all three roles, including platform; manifest rejection for http endpoints, path-prefixed domains, ctx_resolution on the wrong role, duplicate or empty roles, missing endpoint and coverage mode
- Standalone event envelopes (CDN edge, agent with session FK)
- Privacy level field gating (application-layer conformance), one fixture per forbidden field at minimal and intent, in session, standalone and batch shapes
- Funnel exceptions (presented-no-cited, cited-no-grounded, presented-no-grounded)
- Text, image, audio, video, suppressed-citation, and repeated-presentation cases
- Exact presentation-to-engagement correlation across session and standalone envelopes
- Multi-turn sessions and cached grounding
- Grounding provenance paths and generic fingerprint detection across session, standalone-event, and event-batch envelopes
- Custom response_mode values

Each test file has a `_test_description` field explaining what it demonstrates. Every `invalid/` fixture also has an `_expected_error` field: a substring that must appear in the actual error (the first schema error's JSON pointer and message, or the application-layer violation text). Schema pins carry the pointer (`/events/0 'id' is a required property`) so that the same message at a different location does not satisfy them. The runner fails a fixture that fails for a different reason than the one it pins, and fails any invalid fixture missing the field.

## Application-layer conformance

Some rules cannot be expressed in JSON Schema alone. These are tested as application-layer conformance checks in `validate.py`:

- Privacy level field gating (e.g. `query_text` MUST NOT be present at `minimal` level), applied to turns wherever they appear: session documents, batches, and standalone envelopes - each shape has its own fixture
- `content_url` or `content_id` requirement on every content event, and `source_role` on every `content_retrieved` event (sections 5.2.2, 5.7.5), in every document shape
- Field placement by event type (section 5.7.5): `presentation_id` and event-level `ctx_token` only on `content_engaged`, `citation_id` only on `content_presented`, `turn` only on turn events; an envelope `ctx_token` only with `content_engaged` events
- `session_id` or `ctx_token` on a standalone event or event batch envelope at Grounding conformance and above (sections 5.7.5, 7.1)
- Referential integrity within a session document: event ids are distinct; `content_engaged.presentation_id` matches a `content_presented` event id and `citation_id` on `content_presented` matches a `content_cited` event id, in each case identifying the same content; one event-level `ctx_token` binds to one presentation (sections 6.6-6.7, 7.4.1). Standalone envelopes and batch members are exempt - they may reference events delivered elsewhere.
- Manifest rejection rules: duplicate `keys[].id`; `domains` entries that are not the manifest's own host or a subdomain of it; `domains` on a manifest served under a path prefix; `ctx_resolution` on a manifest without the `agent` or `platform` role (sections 8.5-8.7)
- Withdrawn `ip_hash` prohibition on event data (section 9.1 migration rule), in every document shape
- Grounding provenance/cache consistency and the prohibition on `preserved_in_output` in `content_fingerprint` (sections 5.7.5, 6.4, 12.1)

Valid fixtures must pass both JSON Schema and these checks; `invalid/` fixtures that pass JSON Schema but fail a check are documented in `validate.py`. The `agent_id`-at-Grounding requirement is not fixture-tested: it depends on the emitter's declared conformance level, which the fixtures do not carry.
