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

Run from the repository root. Without uv: `pip install "jsonschema[format-nongpl]"`, then `python3 tests/validate.py`. The `format-nongpl` extra pulls in the format validators (`rfc3339-validator` and friends) that make `format: uuid` / `date-time` / `uri` assertions enforce rather than annotate; both scripts hard-error at startup if they are missing. Both commands run in CI on every pull request.

`check_examples.py` extracts every fenced `json` block from the spec and README, validates the complete top-level documents (sessions, standalone events, manifests) against the matching schema, and reports the number of fragments it skipped. A worked example that no longer matches its schema fails the build.

## What it covers

- Session envelope required fields (`schema_version`, `session_id`, `started_at`)
- Event required fields (`type`, `timestamp`)
- Turn required fields (`privacy_level`)
- Enum validation (event types, privacy levels, source roles, schema version)
- Citation source-reference requirement (content_cited rejected when content_url/content_id are missing or null) and required citation_type
- Required event and output identifiers on cited, reproduced, and presented events
- Closed enums (reproduction_type, presentation_kind) and non-negative counts (chars_ingested, reproduced_chars)
- Format assertions (a malformed parent_session_id fails)
- All three conformance levels (Retrieval, Grounding, Citation)
- Standalone event envelopes (CDN edge, agent with session FK)
- Privacy level field gating (application-layer conformance), one fixture per forbidden field at minimal
- Funnel exceptions (presented-no-cited, cited-no-grounded, presented-no-grounded, reproduced-no-grounded)
- Reproduction cases: credited quotation (reproduction + direct_quote citation sharing an output element) and uncredited reproduction in unpresented API output
- Text, image, audio, video, suppressed-citation, and repeated-presentation cases
- Exact presentation-to-engagement correlation across session and standalone envelopes
- Multi-turn sessions and cached grounding
- Grounding provenance paths and generic fingerprint detection across session, standalone-event, and event-batch envelopes
- Custom response_mode values

Each test file has a `_test_description` field explaining what it demonstrates. Every `invalid/` fixture also has an `_expected_error` field: a substring that must appear in the actual error (the first schema error's message and JSON pointer, or the application-layer violation text). The runner fails a fixture that fails for a different reason than the one it pins, and fails any invalid fixture missing the field.

## Application-layer conformance

Some rules cannot be expressed in JSON Schema alone. These are tested as application-layer conformance checks in `validate.py`:

- Privacy level field gating (e.g. `query_text` MUST NOT be present at `minimal` level), applied to turns wherever they appear: session documents, batches, and standalone envelopes
- `content_url` or `content_id` requirement on every content event (section 5.7.5)
- `session_id` or `ctx_token` on a standalone event or event batch envelope at Grounding conformance and above (sections 5.7.5, 7.1)
- Referential integrity within a session document: `content_engaged.presentation_id` matches a `content_presented` event id, and `citation_id` on `content_presented`/`content_reproduced` matches a `content_cited` event id (sections 6.6-6.8). Standalone envelopes and batch members are exempt - they may reference events delivered elsewhere.
- Manifest rejection rules: duplicate `keys[].id`, and `domains` entries that are not the manifest's own host or a subdomain of it (sections 8.6, 8.7)
- Withdrawn `ip_hash` prohibition on `content_retrieved` data (section 9.1 migration rule)
- Grounding provenance/cache consistency and the prohibition on `preserved_in_output` in `content_fingerprint` (sections 5.7.5, 6.4, 12.1)

Valid fixtures must pass both JSON Schema and these checks; `invalid/` fixtures that pass JSON Schema but fail a check are documented in `validate.py`. The `agent_id`-at-Grounding requirement is not fixture-tested: it depends on the emitter's declared conformance level, which the fixtures do not carry.
