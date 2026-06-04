# Contributing to the Content Telemetry specification

## What belongs here

This repo contains the **specification** - the data model, event types, privacy levels, conformance levels, and transport guidance. It does not contain SDK or server code. It also does not contain the accreditation tiers, conformance mark, or privacy floors - those belong in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile).

| File | Purpose |
|------|---------|
| [SPECIFICATION.md](./SPECIFICATION.md) | The normative specification |
| [telemetry-session.json](./telemetry-session.json) | JSON Schema for session validation |
| [telemetry-event.json](./telemetry-event.json) | JSON Schema for standalone event validation |
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
6. Run `python tests/validate.py` to verify all tests pass

## Conformance levels

The spec defines three conformance levels: **Retrieval**, **Grounding**, and **Attribution** (section 5.7). When proposing new required fields, specify which conformance level they apply to. New optional fields do not require a conformance level change.

## Conventions

- **British English** in documentation
- **Sentence case** for headings
- Schema fields use **snake_case**
- New optional fields are preferred over breaking changes
- RFC 2119 keywords (MUST, SHOULD, MAY) used per section 1.5
