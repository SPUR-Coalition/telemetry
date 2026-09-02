# Content Telemetry

**Signal format for AI content usage reporting.**

**Version 1.0** is the current specification. Migration from the v0.1 preview is recorded in [SPECIFICATION.md section 12.1](./SPECIFICATION.md#121-migration-from-the-v01-preview).

## Contents

- [Problem](#problem)
- [Telemetry events](#telemetry-events)
- [Design principles](#design-principles)
- [Repo contents](#repo-contents)
- [Example](#example)
- [Relationship to other protocols](#relationship-to-other-protocols)
- [Feedback](#feedback)
- [Open questions in v1](#open-questions-in-v1)
- [Versioning](#versioning)

## Problem

AI agents retrieve a content owner's content, use it to generate responses, and sometimes cite it. Content owners currently see an initial retrieval event - HTTP requests hitting their servers or access logs from content repositories. Whether the content actually entered a generation context, whether it was cited, whether content or a source reference was made perceivable, and whether anyone interacted with that presentation is not reported back to content owners.

Platforms self-report usage metrics (if they report at all), and content owners have no way to verify the numbers or compare across platforms.

## Telemetry events

Content Telemetry tracks content through five stages:

```
Retrieved    →  content fetched over HTTP (content owner can see this today)
  Grounded   →  content loaded into the agent's generation context
    Cited    →  content explicitly referenced in the response
      Presented  →  content or a source reference made perceivable on a recipient-facing surface
        Engaged  →  user clicked, copied, shared, or directed the agent to act
```

The **session** ties these events together - one bounded interaction from query to outcome, identified by a session ID that every event carries, from retrieval through engagement.

The gaps between stages show how content was used:

- **Retrieval without grounding** - your content was fetched but not used
- **Grounding without citation** - your content influenced the answer but you got no credit
- **Citation without presentation** - your content was credited in the output but the credit never reached the user
- **Presentation without engagement** - your link was shown but the user didn't click through

The grounding event captures the boundary "this content entered the agent's generation context." It is architecture-neutral and decoupled from retrieval: content cached by the agent for days still produces a grounding event in every session it influences.

Grounding and presentation record different boundary crossings: grounding means the content entered a generation context; presentation means content or a source reference was made perceivable on a recipient-facing surface. Presentation does not prove attention. The two diverge as agent experiences move beyond the chat window - an agentic browser can render a page that never entered a generation context, reported as a `content_presented` event with `presentation_kind: content` and `presentation_type: embed` and no grounding event.

## Design principles

**Post-hoc, not pre-declared.** Events report what actually happened, not what the agent said it would do at request time. An agent cannot reliably declare how it will use content before reading it.

**Observable boundaries, not agent internals.** The five content event types mark boundary crossings. What happens between them - the fan-out, relevance evaluation, re-ranking, reasoning chains - is internal to the agent and changes constantly. The spec does not model it.

**Multiple observers, one event.** A content retrieval can be reported by the content owner's CDN, the content owner's origin server, and the AI agent independently. The `Content-Telemetry-ID` header correlates these into a single corroborated event. Uncorroborated retrievals (no matching agent event) may indicate an agent that does not yet support the telemetry protocol.

## Repo contents

- [SPECIFICATION.md](./SPECIFICATION.md) - the full protocol specification
- [SCOPE.md](./SCOPE.md) - the boundary between core, profiles, governing terms and external services
- [telemetry-session.json](./telemetry-session.json) - JSON Schema for session documents
- [telemetry-event.json](./telemetry-event.json) - JSON Schema for standalone event envelopes
- [telemetry-event-batch.json](./telemetry-event-batch.json) - JSON Schema for event batch envelopes
- [manifest.json](./manifest.json) - JSON Schema for the `.well-known/content-telemetry.json` manifest ([section 8](./SPECIFICATION.md#8-manifest))
- [tests/](./tests/) - conformance test suite
- [GOVERNANCE.md](./GOVERNANCE.md) - stewardship, versioning status, relationship to profiles
- [LICENSE](./LICENSE) - Apache License 2.0

This repository is the **standard** - the wire format. Publisher-facing accreditation and the SPUR conformance mark are defined separately in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile), which references this specification by version. The standard defines the privacy mechanism (section 5.5); whether a profile makes any privacy level binding is the profile's choice. See [GOVERNANCE.md](./GOVERNANCE.md).

## Example

A user asks an AI agent about UK interest rates. The agent grounds its response in a cached FT article, cites it, and shows a link. The user reads the answer and leaves without clicking through.

```json
{
  "schema_version": "1.0",
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
        "chars_ingested": 12800,
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
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "content_cited",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:paragraph:2",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "citation_type": "paraphrase",
        "position": "primary"
      }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "type": "content_presented",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:paragraph:2",
      "citation_id": "550e8400-e29b-41d4-a716-446655440001",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "presentation_kind": "source_reference",
        "presentation_type": "link"
      }
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

The content owner can derive: FT article `abc123` was in context for the response, cited as a paraphrase, its link was made perceivable, and no engagement was reported; ads were shown alongside.

## Relationship to other protocols

Content Telemetry is focussed on **reporting**, while content **access** protocols (Really Simple Licensing, peek-then-pay, IAB CoMP, bilateral APIs) aim to govern how agents discover and license content. The `license_ref` field on events connects telemetry to whatever access protocol issued the licence, but the schemas are independent - telemetry works with any access protocol, or none.

## Feedback

File concrete schema, fixture and documentation bugs with the *Schema or
example bug* template, and questions or unclear requirements with *Spec
feedback / open question*. For a new capability or change in behaviour, submit
a short human-written note to [`proposals/`](./proposals/) and wait for
explicit maintainer alignment before beginning implementation (see
[CONTRIBUTING.md](./CONTRIBUTING.md)). Pull requests are welcome for specific
fixes. Feedback on accreditation or the conformance mark belongs on the
[profile
repository](https://github.com/SPUR-Coalition/telemetry-profile/issues).

The [issue tracker](https://github.com/SPUR-Coalition/telemetry/issues) and
pull-request history are the public decision record, including the v1
consultation (12 June - 24 July 2026) and the
[v1 release candidate milestone](https://github.com/SPUR-Coalition/telemetry/milestone/1).

## Open questions in v1

The following areas are expected to develop in 1.x minor versions and profiles, with implementer input:

**Grounding boundary.** The spec defines grounding as content entering the generation model's context (sections 4.3 and 6.4). For straightforward RAG pipelines this is clear. For pipelines with multiple processing stages - embedding, re-ranking, summarisation before context insertion - the boundary requires judgement. The spec draws the line at the generation context (not earlier retrieval stages), but edge cases remain. When a re-ranking or summarisation stage is itself a generative model, the multi-step rule in section 6.4 (content entering a sub-agent's generation context is grounded) can pull selection stages back inside the boundary. Input from platform engineering teams building real implementations will sharpen this definition.

**Event volume at scale.** A single deep-research query can produce 100+ retrieval events and dozens of grounding/citation events. The session document format already handles transport - one POST with all events after the session ends, not one request per event. Volume management beyond that (storage, processing, consumer-side aggregation) is an implementation concern, not a protocol gap. Version 1 adds an explicit coverage declaration - `complete`, `sampled`, `aggregated` or `selected` (section 5.7.6) - and a manifest field for it (section 8.5); the standard still sets no default for reporting granularity, leaving it to profiles and deployments.

**Verification of grounding and citation.** Grounding and citation events are reported by the agent, which is also the party that may owe compensation under a licence. In v1, manifest signing is informational: consumers may verify signatures but are not required to, and the specification defines no required proof binding an event to its emitter (sections 8.4 and 8.9). The events attribution depends on are therefore self-reported by the reporting party. Verifiable credentials and signed events are deferred (section 8.9). One corroboration mechanism works without signing: the `Content-Telemetry-ID` header correlates an agent-reported retrieval with an origin- or edge-reported one (section 7.2), but it covers retrieval only - grounding, citation, presentation, and engagement have no independent observer. Signing, even once required, would prove who reported an event, not that the event is true or that all qualifying events were reported. Input is wanted on what a verification layer should cover and where it belongs. Mechanisms that test truthfulness and completeness rather than origin, such as sampled audits or publisher-seeded canary content, are of particular interest.

**Reporting granularity.** The standard sets no default for reporting granularity, leaving it to profiles and deployments (see *Event volume* above). The SPUR profile requires event-level delivery and does not permit aggregation. Version 1 answers the first half of the question: coverage modes are defined once, in section 5.7.6, so that profiles reference them rather than each define their own. How event-level delivery scales for the highest-volume case remains open.

## Versioning

This repo tracks the specification version. SDK repos have their own release cadences and declare which spec version they support.

Current spec version: **1.0**
