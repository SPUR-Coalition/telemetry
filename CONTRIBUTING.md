# Contributing to the Content Telemetry specification

## What belongs here

This repo contains the **specification** - the data model, event types, privacy levels, conformance levels, and transport guidance. It does not contain SDK or server code. It also does not contain the accreditation tiers, conformance mark, or privacy floors - those belong in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile).

| File | Purpose |
|------|---------|
| [SPECIFICATION.md](./SPECIFICATION.md) | The normative specification |
| [telemetry-session.json](./telemetry-session.json) | JSON Schema for session validation |
| [telemetry-event.json](./telemetry-event.json) | JSON Schema for standalone event validation |
| [telemetry-event-batch.json](./telemetry-event-batch.json) | JSON Schema for event batch validation |
| [manifest.json](./manifest.json) | JSON Schema for the well-known manifest |
| [SCOPE.md](./SCOPE.md) | The boundary between core, profiles and governing terms |
| [proposals/](./proposals/) | Human-written proposals for new capabilities |
| [tests/](./tests/) | Conformance test suite |
| [GOVERNANCE.md](./GOVERNANCE.md) | Stewardship, versioning status, relationship to profiles |
| [LICENSE](./LICENSE) | Apache License 2.0 |

## Proposing changes

We would like proposals for new capabilities or changes in behaviour to begin
with the people who need them, not with generated specification text or code.

Submit a pull request adding a short Markdown or text file to
[`proposals/`](./proposals/). Write it as you would explain the idea to a
colleague: what you are seeing, what you would like Content Telemetry to
express, and why it matters. It can be informal. Please do not ask an AI agent
to expand the idea into a formal proposal or implementation for us.

A proposal starts a discussion. It is not an accepted change, an item on the
maintainers' implementation backlog, or a commitment to spend time or tokens on
it. We will first consider whether the proposal:

- belongs in the Content Telemetry wire format rather than a profile,
  deployment or application;
- addresses a need shared beyond one implementation;
- fits the scope and direction of the standard; and
- can evolve the standard without unacceptable compatibility costs.

A maintainer will explicitly mark a proposal **aligned** if there is agreement
on the direction. That is the gate for substantial implementation work. Please
wait for it before asking an agent to implement the proposal or opening a pull
request that changes the specification, schemas or tests.

Alignment is not final acceptance of every detail. Maintainers may work with
the proposer to prepare the specification text, schema changes, examples and
tests, and material changes will be discussed with them. Acceptance remains
subject to the project's governance, compatibility and review requirements.
The proposer will be credited as a co-author when their proposal is
implemented.

See the [`proposals/` README](./proposals/README.md) for proposal statuses and
the small amount of information to include.

## Bugs and security vulnerabilities

For concrete schema, example or documentation bugs, open an issue using the
**Schema or example bug** template. A bug fix does not need a proposal first.

Report security vulnerabilities privately as described in
[`SECURITY.md`](./SECURITY.md), not in an issue or public proposal.

## Implementing an aligned proposal

Schema changes affect all implementations. Once a proposal is aligned, an
implementation pull request should:

1. Link to the aligned proposal.
2. Reference the relevant section of SPECIFICATION.md.
3. Address backwards compatibility - can existing consumers ignore new fields?
4. Update both SPECIFICATION.md and the relevant JSON schema.
5. Add or update test cases in `tests/` for any new fields or conformance rules.
6. Run the test suite to verify everything passes (see below).

## Running the tests

From a clean checkout, with no setup beyond [uv](https://docs.astral.sh/uv/):

```sh
uv run --with "jsonschema[format-nongpl]" python tests/validate.py        # conformance suite
uv run --with "jsonschema[format-nongpl]" python tests/check_examples.py  # examples in the spec validate against the schemas
uv run --with "jsonschema[format-nongpl]" python tests/mutation_smoke.py  # suite-weakening mutations are caught
```

(Without uv: `pip install "jsonschema[format-nongpl]"` then `python3 tests/validate.py`.)

`check_examples.py` validates every complete worked example in SPECIFICATION.md and README.md against its schema; an example that no longer matches its schema fails the build. All three commands run in CI on every pull request (`.github/workflows/ci.yml`).

## Conformance levels

The spec defines three conformance levels: **Retrieval**, **Grounding**, and **Citation** (section 5.7). When proposing new required fields, specify which conformance level they apply to. New optional fields do not require a conformance level change.

## Conventions

- **British English** in documentation
- **Sentence case** for headings
- Schema fields use **snake_case**
- New optional fields are preferred over breaking changes
- RFC 2119 keywords (MUST, SHOULD, MAY) used per section 1.5
