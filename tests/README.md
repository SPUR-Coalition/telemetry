# Conformance test suite

Tests for the Content Telemetry Specification v0.1.

## Structure

- `valid/` - JSON files that MUST pass JSON Schema validation
- `invalid/` - JSON files that MUST fail validation (either JSON Schema or application-layer conformance)
- `validate.py` - Test runner (requires `jsonschema` package)

## Running

```
pip install jsonschema
python validate.py
```

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
