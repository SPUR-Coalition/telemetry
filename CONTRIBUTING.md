# Contributing to the Content Telemetry specification

## What belongs here

This repo contains the **specification** - the data model, event types, privacy levels, conformance levels, and transport guidance. It does not contain SDK or server code. It also does not contain the accreditation tiers, conformance mark, or privacy floors - those belong in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile).

| File | Purpose |
|------|---------|
| [SPECIFICATION.md](./SPECIFICATION.md) | The normative specification |
| [telemetry-session.json](./telemetry-session.json) | JSON Schema for session validation |
| [telemetry-event.json](./telemetry-event.json) | JSON Schema for standalone event validation |
| [telemetry-event-batch.json](./telemetry-event-batch.json) | JSON Schema for event batch validation |
| [content-fingerprint-schemes.json](./content-fingerprint-schemes.json) | Non-exclusive fingerprint scheme discovery registry |
| [content-fingerprint-schemes.schema.json](./content-fingerprint-schemes.schema.json) | JSON Schema for the fingerprint scheme registry |
| [survivability-matrix-c2pa-text.json](./survivability-matrix-c2pa-text.json) | Transform-specific C2PA text survivability evidence |
| [survivability-matrix.schema.json](./survivability-matrix.schema.json) | JSON Schema for survivability evidence matrices |
| [tests/](./tests/) | Conformance test suite |
| [GOVERNANCE.md](./GOVERNANCE.md) | Stewardship and preview-status policy |
| [LICENSE](./LICENSE) | Apache License 2.0 |

## Proposing changes

Schema changes affect all implementations. Before submitting a PR:

1. Open an issue describing the change and its motivation
2. Reference the relevant section of SPECIFICATION.md
3. Consider backwards compatibility - can existing consumers ignore new fields?
4. Update both SPECIFICATION.md and the relevant JSON schema
5. Add or update test cases in `tests/` for any new fields or conformance rules
6. Run the test suite to verify everything passes (see below)

## Running the tests

From a clean checkout, with no setup beyond [uv](https://docs.astral.sh/uv/), the checked-in `.python-version` and `uv.lock` reproduce the CI runtime and dependencies:

```sh
uv run --locked python tests/validate.py        # conformance suite
uv run --locked python tests/check_examples.py  # examples in the spec validate against the schemas
uv run --locked python tests/check_registry.py  # registry and survivability-matrix structure
uv run --locked python tests/check_survivability.py  # reproduce executable matrix rows
```

(Without uv: use Python 3.12 and `pip install jsonschema==4.26.0 rfc8785==0.1.4`, then run `python3 tests/validate.py`.)

`check_examples.py` validates every complete worked example in SPECIFICATION.md and README.md against its schema; an example that no longer matches its schema fails the build. `check_registry.py` validates every discovery entry and transform row. `check_survivability.py` reconstructs the C2PA Appendix A.8 fixture and reproduces each executable matrix transform while reporting untested rows separately. All four commands run in CI on every pull request (`.github/workflows/ci.yml`).

## Conformance levels

The spec defines three conformance levels: **Retrieval**, **Grounding**, and **Citation** (section 5.7). When proposing new required fields, specify which conformance level they apply to. New optional fields do not require a conformance level change.

## Conventions

- **British English** in documentation
- **Sentence case** for headings
- Schema fields use **snake_case**
- New optional fields are preferred over breaking changes
- RFC 2119 keywords (MUST, SHOULD, MAY) used per section 1.5
