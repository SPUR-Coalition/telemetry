# Content Telemetry

**Signal format for AI content usage reporting.**

This is a preview specification. Field names, event types, and schema structure may change before 1.0.

> **Consultation status — 12 August 2026:** The public comment period closed on
> **24 July 2026**. The SPUR Steering Board has approved the v1 direction, and a
> final disposition is now recorded on every consultation thread: each carries
> an outcome label, and accepted core changes sit on the
> [v1 release candidate milestone](https://github.com/SPUR-Coalition/telemetry/milestone/1)
> with a schema freeze targeted for **21 August 2026**. Accepted changes are
> merging on the `v1-draft` integration line. Version 0.1 remains the current
> published preview. See [Consultation status](#consultation-status) below.

## Contents

- [Problem](#problem)
- [Telemetry events](#telemetry-events)
- [Design principles](#design-principles)
- [Repo contents](#repo-contents)
- [Example](#example)
- [Relationship to other protocols](#relationship-to-other-protocols)
- [Consultation status](#consultation-status)
- [Open questions in v0.1](#open-questions-in-v01)
- [Versioning](#versioning)

## Problem

AI agents retrieve a content owner's content, use it to generate responses, and sometimes cite it. Content owners currently see an initial retrieval event - HTTP requests hitting their servers or access logs from content repositories. Whether the content actually influenced the response, whether it was cited, whether a user saw the citation, whether they clicked through - is not reported back to content owners.

Platforms self-report usage metrics (if they report at all), and content owners have no way to verify the numbers or compare across platforms.

## Telemetry events

Content Telemetry tracks content through five stages:

```
Retrieved    →  content fetched over HTTP (content owner can see this today)
  Grounded   →  content loaded into the agent's generation context
    Cited    →  content explicitly referenced in the response
      Displayed  →  user saw it - a reference, or the content embedded in the answer
        Engaged  →  user clicked, copied, shared, or directed the agent to act
```

The **session** ties these events together - one bounded interaction from query to outcome, identified by a session ID that every event carries, from retrieval through engagement.

The gaps between stages show how content was used:

- **Retrieval without grounding** - your content was fetched but not used
- **Grounding without citation** - your content influenced the answer but you got no credit
- **Citation without engagement** - your content was cited but the user didn't click through

The grounding event captures the boundary "this content entered the agent's generation context." It is architecture-neutral and decoupled from retrieval: content cached by the agent for days still produces a grounding event in every session it influences.

Grounding and display record two different kinds of influence: grounding means the content influenced the agent, display means it reached the user. The two diverge as agent experiences move beyond the chat window - an agentic browser can render a page to the user that never entered a generation context, reported as a `content_displayed` event with `display_type: embed` and no grounding event.

## Design principles

**Post-hoc, not pre-declared.** Events report what actually happened, not what the agent said it would do at request time. An agent cannot reliably declare how it will use content before reading it.

**Observable boundaries, not agent internals.** The five event types mark boundary crossings. What happens between them - the fan-out, relevance evaluation, re-ranking, reasoning chains - is internal to the agent and changes constantly. The spec does not model it.

**Multiple observers, one event.** A content retrieval can be reported by the content owner's CDN, the content owner's origin server, and the AI agent independently. The `Content-Telemetry-ID` header correlates these into a single corroborated event. Uncorroborated retrievals (no matching agent event) may indicate an agent that does not yet support the telemetry protocol.

## Repo contents

- [SPECIFICATION.md](./SPECIFICATION.md) - the full protocol specification
- [SCOPE.md](./SCOPE.md) - the boundary between core, profiles, governing terms and external services
- [telemetry-session.json](./telemetry-session.json) - JSON Schema for session documents
- [telemetry-event.json](./telemetry-event.json) - JSON Schema for standalone event envelopes
- [telemetry-event-batch.json](./telemetry-event-batch.json) - JSON Schema for event batch envelopes
- [manifest.json](./manifest.json) - JSON Schema for the `.well-known/content-telemetry.json` manifest ([section 8](./SPECIFICATION.md#8-manifest))
- [content-fingerprint-schemes.json](./content-fingerprint-schemes.json) - non-exclusive discovery registry for fingerprint scheme profiles and capability ceilings
- [content-fingerprint-schemes.schema.json](./content-fingerprint-schemes.schema.json) - JSON Schema for every registry entry and registration status
- [survivability-matrix-c2pa-text.json](./survivability-matrix-c2pa-text.json) - transform-specific C2PA text association recovery results and explicit untested cases
- [survivability-matrix.schema.json](./survivability-matrix.schema.json) - JSON Schema for transform-specific survivability evidence
- [tests/](./tests/) - conformance test suite
- [GOVERNANCE.md](./GOVERNANCE.md) - stewardship, preview status, relationship to profiles
- [LICENSE](./LICENSE) - Apache License 2.0

This repository is the **standard** - the wire format. Publisher-facing accreditation and the SPUR conformance mark are defined separately in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile), which references this specification by version. The standard defines the privacy mechanism (section 5.5); whether a profile makes any privacy level binding is the profile's choice. See [GOVERNANCE.md](./GOVERNANCE.md).

## Example

A user asks an AI agent about UK interest rates. The agent grounds its response in a cached FT article, cites it, and shows a link. The user reads the answer and leaves without clicking through.

```json
{
  "schema_version": "0.1",
  "session_id": "660e8400-e29b-41d4-a716-446655440000",
  "agent_id": "copilot-v3",
  "started_at": "2026-03-28T09:00:00Z",
  "events": [
    {
      "type": "content_grounded",
      "timestamp": "2026-03-28T09:00:00Z",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "scope": "session",
        "cached": true,
        "tokens_ingested": 3200,
        "content_last_modified": "2026-03-27T18:30:00Z"
      }
    },
    {
      "type": "turn_started",
      "timestamp": "2026-03-28T09:00:01Z",
      "turn_id": "1",
      "turn": {
        "privacy_level": "intent",
        "query_intent": "question",
        "topics": ["UK economy", "interest rates"]
      }
    },
    {
      "type": "content_cited",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "citation_type": "paraphrase",
        "position": "primary"
      }
    },
    {
      "type": "content_displayed",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": { "display_type": "link" }
    },
    {
      "type": "turn_completed",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "turn": {
        "privacy_level": "intent",
        "response_mode": "standard",
        "response_tokens": 280,
        "ad_rendered": true
      }
    }
  ]
}
```

The content owner can derive: FT article `abc123` was in context for the response, cited as a paraphrase, link was displayed, user never clicked, ads were shown alongside.

## Relationship to other protocols

Content Telemetry is focussed on **reporting**, while content **access** protocols (Really Simple Licensing, peek-then-pay, IAB CoMP, bilateral APIs) aim to govern how agents discover and license content. The `license_ref` field on events connects telemetry to whatever access protocol issued the licence, but the schemas are independent - telemetry works with any access protocol, or none.

## Consultation status

The public comment period ran from **12 June to 24 July 2026** and is now closed.
Thank you to everyone who opened an issue, submitted a pull request, joined a
working session or supplied implementation evidence.

The consultation produced 29 specification issue threads, three profile issue
threads and five pull requests. The maintainers are now:

- [x] reviewing the full consultation record;
- [x] preparing a proposed disposition for every thread;
- [x] recording the approved dispositions on the issue tracker;
- [ ] completing focused v1 changes and migration fixtures on `v1-draft`;
- [ ] publishing a v1 release candidate for implementer testing; and
- [ ] publishing final v1 only after publisher, intermediary and agent/platform
  acceptance cases pass.

A final disposition is now recorded on every consultation thread, and accepted
core changes are tracked on the
[v1 release candidate milestone](https://github.com/SPUR-Coalition/telemetry/milestone/1)
towards the 21 August 2026 schema freeze. Each thread's outcome label and
disposition comment, not its open or closed state, record the decision: threads
that remain open do so pending their recorded follow-ups. A preparation branch
does not change the published specification. The issue tracker and pull-request
history remain the public decision record.

Concrete schema, fixture and documentation bugs may still be filed using the
*Schema or example bug* template, and questions or unclear requirements using
*Spec feedback / open question*. For a new capability or change in behaviour,
submit a short human-written note to [`proposals/`](./proposals/) and wait for
explicit maintainer alignment before beginning implementation (see
[CONTRIBUTING.md](./CONTRIBUTING.md)); new design proposals are not
automatically part of the v1 consultation scope. Pull requests remain welcome
for specific fixes. Feedback on accreditation or the conformance mark belongs
on the [profile
repository](https://github.com/SPUR-Coalition/telemetry-profile/issues).

Required fields, event types and schema structure may still change before 1.0
(section 12). Version 0.1 remains the current published preview until a later
version is released.

## Open questions in v0.1

This is a preview specification. The following areas are under active discussion and will be refined with implementer input:

**Grounding boundary.** The spec defines grounding as content entering the generation model's context (sections 4.3 and 6.4). For straightforward RAG pipelines this is clear. For pipelines with multiple processing stages - embedding, re-ranking, summarisation before context insertion - the boundary requires judgement. The spec draws the line at the generation context (not earlier retrieval stages), but edge cases remain. When a re-ranking or summarisation stage is itself a generative model, the multi-step rule in section 6.4 (content entering a sub-agent's generation context is grounded) can pull selection stages back inside the boundary. Input from platform engineering teams building real implementations will sharpen this definition.

**Event volume at scale.** A single deep-research query can produce 100+ retrieval events and dozens of grounding/citation events. The session document format already handles transport - one POST with all events after the session ends, not one request per event. Volume management beyond that (storage, processing, consumer-side aggregation) is an implementation concern, not a protocol gap. Sampling and aggregation are options for future versions but are not in v0.1; the standard sets no default for reporting granularity, leaving it to profiles and deployments.

**Verification of grounding and citation.** Section 5.8 now defines assertion-scoped evidentiary tiers. An event remains a report, but an emitter can attach exact-subject origin corroboration or a portable independent-verifier attestation. Consumers derive the effective tier under their own trust policy; a signed report, scheme name, registry entry, or self-declared capability never upgrades itself. The remaining open question is deployment evidence for completeness: no tier proves that every qualifying event was emitted. Sampled audits, reconciliation, and publisher-seeded canary content remain important profile-level mechanisms.

**Reporting granularity.** The standard sets no default for reporting granularity, leaving it to profiles and deployments (see *Event volume* above). The SPUR profile requires event-level delivery and does not permit aggregation. The open question is whether the standard should say more about sampling and aggregation so that profiles do not each define it separately, and how event-level delivery scales for the highest-volume case. No mechanism is selected in v0.1.

## Versioning

This repo tracks the specification version. SDK repos have their own release cadences and declare which spec version they support.

Current spec version: **0.1** (preview)
