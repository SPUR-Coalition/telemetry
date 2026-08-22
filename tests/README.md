# Conformance test suite

Tests for the Content Telemetry Specification v0.1.

## Structure

- `valid/` - JSON files that MUST pass JSON Schema validation
- `invalid/` - JSON files that MUST fail validation (either JSON Schema or application-layer conformance)
- `validate.py` - Conformance test runner (requires the locked `jsonschema` and `rfc8785` dependencies)
- `check_examples.py` - Validates worked examples against schemas and application-layer rules
- `check_registry.py` - Validates all registry and survivability-matrix entries
- `check_survivability.py` - Reproduces executable C2PA text carrier transforms and reports untested rows

## Running

From a clean checkout, with no setup beyond [uv](https://docs.astral.sh/uv/), use the checked-in Python and dependency lock:

```sh
uv run --locked python tests/validate.py
uv run --locked python tests/check_examples.py
uv run --locked python tests/check_registry.py
uv run --locked python tests/check_survivability.py
```

Run from the repository root. Without uv: use Python 3.12 and `pip install jsonschema==4.26.0 rfc8785==0.1.4`, then run the scripts with `python3`. All four commands run in CI on every pull request.

`check_examples.py` extracts every fenced `json` block from the spec and README, validates the complete top-level documents (sessions, standalone events, manifests) against the matching schema, and reports the number of fragments it skipped. A worked example that no longer matches its schema fails the build.

`check_registry.py` validates every registry entry and matrix row. `check_survivability.py` reconstructs the checked-in C2PA text fixture and executes each supported transform, while listing `not_tested` rows separately rather than treating them as passes.

## What it covers

- Session envelope required fields (`schema_version`, `session_id`, `started_at`)
- Event required fields (`type`, `timestamp`)
- Turn required fields (`privacy_level`)
- Enum validation (event types, privacy levels, source roles, schema version)
- All three conformance levels (Retrieval, Grounding, Citation)
- Standalone event envelopes (CDN edge, agent with session FK)
- Privacy level field gating (application-layer conformance)
- Funnel exceptions (displayed-no-cited, cited-no-grounded, displayed-no-grounded)
- Embedded display (`display_type: embed`) and agent-mediated engagement (`agent_navigate`)
- Multi-turn sessions, cached grounding
- Custom response_mode values

Each test file has a `_test_description` field explaining what it demonstrates.

## Application-layer conformance

Some rules cannot be expressed in JSON Schema alone. These are tested as application-layer conformance checks in `validate.py`:

- Privacy level field gating (e.g. `query_text` MUST NOT be present at `minimal` level)
- `content_url` or `content_id` requirement on every content event (section 5.7.5)
- `session_id` or `ctx_token` on a standalone event or event batch envelope at Grounding conformance and above (sections 5.7.5, 7.1)
- Manifest rejection rules: duplicate `keys[].id`, and `domains` entries that are not the manifest's own host or a subdomain of it (sections 8.6, 8.7)
- Assertion-scoped evidence binding, artifact integrity, profile relationships, consumer-gated derivation, replay conflicts, safe references, and resource ceilings (section 5.8)
- Fingerprint registry and survivability-matrix schemas plus semantic invariants

Valid fixtures must pass both JSON Schema and these checks; `invalid/` fixtures that pass JSON Schema but fail a check are documented in `validate.py`. The `agent_id`-at-Grounding requirement is not fixture-tested: it depends on the emitter's declared conformance level, which the fixtures do not carry.
