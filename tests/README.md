# Conformance test suite

Tests for the Content Telemetry Specification v0.1.

## Structure

- `valid/` - JSON files that MUST pass JSON Schema validation
- `invalid/` - JSON files that MUST fail validation (either JSON Schema or application-layer conformance)
- `validate.py` - Conformance test runner (requires `jsonschema`)
- `check_examples.py` - Validates the worked examples in SPECIFICATION.md and README.md against the schemas

## Running

From a clean checkout, with no setup beyond [uv](https://docs.astral.sh/uv/):

```sh
uv run --with jsonschema python tests/validate.py
uv run --with jsonschema python tests/check_examples.py
```

Run from the repository root. Without uv: `pip install jsonschema`, then `python3 tests/validate.py`. Both commands run in CI on every pull request.

`check_examples.py` extracts every fenced `json` block from the spec and README, validates the complete top-level documents (sessions, standalone events, manifests) against the matching schema, and reports the number of fragments it skipped. A worked example that no longer matches its schema fails the build.

## What it covers

- Session envelope required fields (`schema_version`, `session_id`, `started_at`)
- Event required fields (`type`, `timestamp`)
- Turn required fields (`privacy_level`)
- Outcome required fields (`type`)
- Enum validation (event types, privacy levels, schema version)
- All three conformance levels (Retrieval, Grounding, Attribution)
- Standalone event envelopes (CDN edge, agent with session FK)
- Privacy level field gating (application-layer conformance)
- Funnel exceptions (displayed-no-cited, cited-no-grounded)
- Multi-turn sessions, cached grounding
- Custom response_mode values

Each test file has a `_test_description` field explaining what it demonstrates.

## Application-layer conformance

Some rules cannot be expressed in JSON Schema alone. These are tested as application-layer conformance checks in `validate.py`:

- Privacy level field gating (e.g. `query_text` MUST NOT be present at `minimal` level)
- `agent_id` requirement at Grounding conformance level
- `content_url` or `content_id` requirement on content events

Files in `invalid/` that pass JSON Schema but fail these rules are documented in `validate.py`.
