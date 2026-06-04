# Content Telemetry

**Signal format for AI content attribution.**

When an AI agent uses a content owner's content to generate a response, five things can happen - and today content owners can only see one of them. Content Telemetry defines a schema for tracking all five.

This is a preview specification. Field names, event types, and schema structure may change before 1.0.

## Contents

- [The problem](#the-problem)
- [The five stages](#the-five-stages)
- [Design principles](#design-principles)
- [What's in this repo](#whats-in-this-repo)
- [Quick example](#quick-example)
- [Relationship to other protocols](#relationship-to-other-protocols)
- [Open questions in v0.1](#open-questions-in-v01)
- [Versioning](#versioning)

## The problem

AI agents retrieve a content owner's content, use it to generate responses, and sometimes cite it. Content owners currently see one signal: HTTP requests hitting their servers. Everything after that - whether the content actually influenced the response, whether it was cited, whether a user saw the citation, whether they clicked through - is invisible.

Platforms self-report usage metrics (if they report at all), and content owners have no way to verify the numbers or compare across platforms.

## The five stages

Content Telemetry tracks content through five stages:

```
Retrieved    →  content fetched over HTTP (content owner can see this today)
  Grounded   →  content loaded into the agent's generation context
    Cited    →  content explicitly referenced in the response
      Displayed  →  user saw the reference
        Engaged  →  user clicked, expanded, copied, or shared
```

Each stage is a progressively narrower subset. What ties them together is the **session** - a single user journey from query to outcome, identified by a session ID. Every event in the journey, from retrieval through engagement, carries that session ID; it is the thread that connects content to outcome within a single agent interaction.

The gaps between stages are where the interesting questions live:

- **Retrieval without grounding** - your content was fetched but not used
- **Grounding without citation** - your content influenced the answer but you got no credit
- **Citation without engagement** - your content was cited but the user didn't click through

The grounding event captures the boundary "this content entered the agent's generation context." It is architecture-neutral and decoupled from retrieval: content cached by the agent for days still produces a grounding event in every session it influences, even when the content owner's CDN sees nothing.

## Design principles

**Post-hoc, not pre-declared.** Events report what actually happened, not what the agent said it would do at request time. An agent cannot reliably declare how it will use content before reading it. Telemetry captures observed reality after the fact.

**Observable boundaries, not agent internals.** The five event types mark boundary crossings. What happens between them - the fan-out, relevance evaluation, re-ranking, reasoning chains - is internal to the agent and changes constantly. The spec does not model it.

**Multiple observers, one event.** A content retrieval can be reported by the content owner's CDN, the content owner's origin server, and the AI agent independently. The `Content-Telemetry-ID` header correlates these into a single corroborated event. Uncorroborated retrievals (no matching agent event) may indicate an agent that does not yet support the telemetry protocol.

**Privacy by default.** Four privacy levels control what conversation data is shared: from `full` (query and response text) down to `minimal` (token counts and content URLs only).

## What's in this repo

- [SPECIFICATION.md](./SPECIFICATION.md) - the full protocol specification
- [telemetry-session.json](./telemetry-session.json) - JSON Schema for session documents
- [telemetry-event.json](./telemetry-event.json) - JSON Schema for standalone event envelopes
- [manifest.json](./manifest.json) - JSON Schema for the `.well-known/content-telemetry.json` manifest ([section 8](./SPECIFICATION.md#8-manifest))
- [tests/](./tests/) - conformance test suite
- [CONSIDERATIONS.md](./CONSIDERATIONS.md) - deferred design items and open questions, with rationale
- [GOVERNANCE.md](./GOVERNANCE.md) - stewardship, preview status, relationship to the profile
- [LICENSE](./LICENSE) - Apache License 2.0

This repository is the **standard** - the wire format. Publisher-facing accreditation tiers, the SPUR conformance mark, and the privacy floor that comes with each tier are defined separately in the [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile), which references this specification by version. See [GOVERNANCE.md](./GOVERNANCE.md).

## Quick example

A user asks an AI agent about UK interest rates. The agent grounds its response in a cached FT article, cites it, and shows a link. The user reads the answer and leaves without clicking through.

```json
{
  "document_type": "session",
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

No `content_retrieved` event - the article was cached from a previous fetch. The content owner's CDN saw nothing. The grounding event is the only signal that content was used.

The content owner can derive: FT article `abc123` was in context for the response, cited as a paraphrase, link was displayed, user never clicked, ads were shown alongside.

## Relationship to other protocols

Content Telemetry is the **reporting** side. Content **access** protocols (peek-then-pay, IAB CoMP, bilateral APIs) govern how agents discover and license content. The `license_ref` field on events connects telemetry to whatever access protocol issued the licence. The schemas are independent - telemetry works with any access protocol, or none.

## Open questions in v0.1

This is a preview specification. Two areas are under active discussion and will be refined with implementer input:

**Grounding boundary.** The spec defines grounding as content entering the generation model's context (sections 4.3 and 6.4). For straightforward RAG pipelines this is clear. For pipelines with multiple processing stages - embedding, re-ranking, summarisation before context insertion - the boundary requires judgement. The spec draws the line at the generation context (not earlier retrieval stages), but edge cases remain. Input from platform engineering teams building real implementations will sharpen this definition.

**Event volume at scale.** A single deep-research query can produce 100+ retrieval events and dozens of grounding/citation events. The session document format already handles transport - one POST with all events after the session ends, not one request per event. Volume management beyond that (storage, processing, consumer-side aggregation) is an implementation concern, not a protocol gap. Sampling and aggregation are options for future versions but are deliberately not in v0.1 - what gets reported and at what granularity is a commercial decision between the parties, not a protocol default.

## Versioning

This repo tracks the specification version. SDK repos have their own release cadences and declare which spec version they support.

Current spec version: **0.1** (preview)
