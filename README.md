# Content Telemetry

**Signal format for AI content attribution.**

This is a preview specification. Field names, event types, and schema structure may change before 1.0.

## Contents

- [Problem](#problem)
- [Five tracked events](#five-tracked-events)
- [Design principles](#design-principles)
- [Repo contents](#repo-contents)
- [Example](#example)
- [Relationship to other protocols](#relationship-to-other-protocols)
- [Request for comment](#request-for-comment)
- [Open questions in v0.1](#open-questions-in-v01)
- [Versioning](#versioning)

## Problem

AI agents retrieve a content owner's content, use it to generate responses, and sometimes cite it. Content owners currently see an initial retrieval event - HTTP requests hitting their servers or access logs from content repositories. Whether the content actually influenced the response, whether it was cited, whether a user saw the citation, whether they clicked through - is not reported back to content owners.

Platforms self-report usage metrics (if they report at all), and content owners have no way to verify the numbers or compare across platforms.

## Five tracked events

Content Telemetry tracks content through five stages:

```
Retrieved    →  content fetched over HTTP (content owner can see this today)
  Grounded   →  content loaded into the agent's generation context
    Cited    →  content explicitly referenced in the response
      Displayed  →  user saw the reference
        Engaged  →  user clicked, expanded, copied, or shared
```

The **session** ties these events together - a single user journey from query to outcome, identified by a session ID that every event carries, from retrieval through engagement.

The gaps between stages show how content was used:

- **Retrieval without grounding** - your content was fetched but not used
- **Grounding without citation** - your content influenced the answer but you got no credit
- **Citation without engagement** - your content was cited but the user didn't click through

The grounding event captures the boundary "this content entered the agent's generation context." It is architecture-neutral and decoupled from retrieval: content cached by the agent for days still produces a grounding event in every session it influences.

## Design principles

**Post-hoc, not pre-declared.** Events report what actually happened, not what the agent said it would do at request time. An agent cannot reliably declare how it will use content before reading it.

**Observable boundaries, not agent internals.** The five event types mark boundary crossings. What happens between them - the fan-out, relevance evaluation, re-ranking, reasoning chains - is internal to the agent and changes constantly. The spec does not model it.

**Multiple observers, one event.** A content retrieval can be reported by the content owner's CDN, the content owner's origin server, and the AI agent independently. The `Content-Telemetry-ID` header correlates these into a single corroborated event. Uncorroborated retrievals (no matching agent event) may indicate an agent that does not yet support the telemetry protocol.

## Repo contents

- [SPECIFICATION.md](./SPECIFICATION.md) - the full protocol specification
- [telemetry-session.json](./telemetry-session.json) - JSON Schema for session documents
- [telemetry-event.json](./telemetry-event.json) - JSON Schema for standalone event envelopes
- [manifest.json](./manifest.json) - JSON Schema for the `.well-known/content-telemetry.json` manifest ([section 8](./SPECIFICATION.md#8-manifest))
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

No `content_retrieved` event - the article was cached from a previous fetch. The grounding event is the only signal that content was used.

The content owner can derive: FT article `abc123` was in context for the response, cited as a paraphrase, link was displayed, user never clicked, ads were shown alongside.

## Relationship to other protocols

Content Telemetry is the **reporting** side. Content **access** protocols (peek-then-pay, IAB CoMP, bilateral APIs) govern how agents discover and license content. The `license_ref` field on events connects telemetry to whatever access protocol issued the licence. The schemas are independent - telemetry works with any access protocol, or none.

## Request for comment

This specification is open for public comment from **11 June to 10 July 2026**, a 30-day window. Feedback is triaged on the issue tracker as it arrives and incorporated into the next revision after the window closes. The wire format is held stable during the window; the only changes made before it closes are fixes to defects that block review.

Comment is most useful on:

- The [open questions below](#open-questions-in-v01).
- Whether the conformance and privacy levels (sections 5.5 and 5.7) are implementable as written by a team building an emitter or consumer.
- How the five-stage event model fits real agent architectures (section 6.4).
- Anything that would require an implementer to depend on a particular operator or service to participate. The standard should be implementable from the public schemas alone.
- Any worked example that does not validate against its schema, or any mismatch between the prose and the schemas.

File an issue on this repository. Two templates are available: *Spec feedback / open question* for design questions and proposed changes, and *Schema or example bug* for concrete defects. Pull requests are welcome for specific schema or text fixes; for larger changes, open an issue first (see [CONTRIBUTING.md](./CONTRIBUTING.md)). Feedback on the accreditation tiers, the conformance mark, or the privacy floor belongs on the [profile repository](https://github.com/SPUR-Coalition/telemetry-profile/issues).

Some areas are out of scope for this round. The non-goals are in [section 1.3](./SPECIFICATION.md#13-non-goals) and the deferred manifest features in [section 8.9](./SPECIFICATION.md#89-out-of-scope-for-v01); please read those before filing. Comment on whether a non-goal is the right call is welcome, provided it says which one and why.

Required fields, event types, and schema structure may all change before 1.0 (section 12). Nothing is settled except the items listed as out of scope.

## Open questions in v0.1

This is a preview specification. The following areas are under active discussion and will be refined with implementer input:

**Grounding boundary.** The spec defines grounding as content entering the generation model's context (sections 4.3 and 6.4). For straightforward RAG pipelines this is clear. For pipelines with multiple processing stages - embedding, re-ranking, summarisation before context insertion - the boundary requires judgement. The spec draws the line at the generation context (not earlier retrieval stages), but edge cases remain. Input from platform engineering teams building real implementations will sharpen this definition.

**Event volume at scale.** A single deep-research query can produce 100+ retrieval events and dozens of grounding/citation events. The session document format already handles transport - one POST with all events after the session ends, not one request per event. Volume management beyond that (storage, processing, consumer-side aggregation) is an implementation concern, not a protocol gap. Sampling and aggregation are options for future versions but are not in v0.1; the standard sets no default for reporting granularity, leaving it to profiles and deployments.

**Verification of grounding and citation.** Grounding and citation events are reported by the agent, which is also the party that may owe compensation under a licence. In v0.1, manifest signing is informational: consumers may verify signatures but are not required to, and the specification defines no required proof binding an event to its emitter (sections 8.4 and 8.9). The events attribution depends on are therefore self-reported by the reporting party. Verifiable credentials and signed events are deferred (section 8.9). One corroboration mechanism works without signing: the `Content-Telemetry-ID` field correlates an agent-reported retrieval with an origin- or edge-reported one (section 7.2), but it covers retrieval only - grounding, citation, display, and engagement have no independent observer. Input is wanted on what a verification layer should cover and where it belongs.

**Reporting granularity.** The standard sets no default for reporting granularity, leaving it to profiles and deployments (see *Event volume* above). The SPUR profile requires event-level delivery and does not permit aggregation. The open question is whether the standard should say more about sampling and aggregation so that profiles do not each define it separately, and how event-level delivery scales for the highest-volume case. No mechanism is selected in v0.1.

## Versioning

This repo tracks the specification version. SDK repos have their own release cadences and declare which spec version they support.

Current spec version: **0.1** (preview)
