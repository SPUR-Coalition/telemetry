# Content Telemetry Specification

**Version:** 1.0 (release candidate draft)
**Status:** Release candidate in preparation (feature freeze 21 August 2026)
**Last updated:** 2026-08-12

## Contents

1. [Introduction](#1-introduction) - problem, goals, non-goals, inference-time scope, relationship to access protocols, conventions
2. [Normative references](#2-normative-references)
3. [Terms and definitions](#3-terms-and-definitions)
4. [Concepts](#4-concepts) - roles, sessions, event lifecycle, source roles, content identification
5. [Schema](#5-schema) - session, event, event types, conversation turn, privacy, intent, conformance levels
6. [Data profiles](#6-data-profiles) - retrieval, edge enrichment, origin enrichment, grounding, citation, presentation, engagement
7. [Transport](#7-transport) - delivery formats, Content-Telemetry-ID header, routing, click context
8. [Manifest](#8-manifest) - discovery, schema, operator, keys, telemetry, domains
9. [Privacy](#9-privacy) - data minimisation, recommended levels, retention
10. [Attribution](#10-attribution) - counting semantics, grounding without citation
11. [Extensibility](#11-extensibility) - custom event metadata, intent categories, response modes
12. [Versioning](#12-versioning)
- [Annex A (normative): JSON Schema](#annex-a-normative-json-schema)
- [Annex B (informative): Examples](#annex-b-informative-examples)

## 1. Introduction

This document specifies a telemetry schema for tracking AI agent content usage from retrieval through user engagement.

### 1.1 Problem statement

AI agents use content to generate responses. There is no standardised way to:

1. Track which content was retrieved, loaded into agent context, and used
2. Distinguish content that was explicitly cited from content that silently influenced a response
3. Measure content influence from retrieval through to user engagement
4. Provide data that could inform compensation arrangements
5. Verify platform-reported usage independently

### 1.2 Goals

Content Telemetry defines:

- A **minimal, extensible schema** for telemetry events across the content lifecycle
- **Privacy-preserving** data sharing levels between parties
- Data structures for **attribution calculation** from retrieval through to user engagement
- **Content identification** that works across URLs, caches, and content delivery paths
- An **open source** schema (Apache 2.0) with no vendor-specific dependencies

### 1.3 Non-goals

Content Telemetry does not:

- Define specific attribution algorithms (left to implementers)
- Mandate specific privacy policies (left to agreements between parties)
- Require specific transport protocols (HTTP, gRPC, etc. all valid)
- Define content access or licensing protocols (see 1.4)
- Model what a system does with content other than at inference time. Assembling a training corpus, training or fine-tuning a model, computing embeddings and constructing a retrieval index are all outside scope (see 1.3.1).
- Define accreditation tiers, conformance marks, or community-specific conformance requirements. These belong in profiles layered on this specification (see [GOVERNANCE.md](./GOVERNANCE.md)).

#### 1.3.1 Inference-time scope

The five-stage lifecycle reports content use observable at inference time: identified content entered a generation context for a particular response, and what the resulting output did with it.

Retrieval is the boundary case. A crawl whose purpose is training or index building can be reported as a `content_retrieved` event, and `bot_category` (section 6.2) distinguishes it, but the event is non-attributable: no grounding, citation, presentation or engagement follows it. What the system then does with the content, whether it enters a training corpus, a fine-tuning set, an embedding store or a search index, is outside this specification. Nothing here reports that a model was trained on a work, and a conforming implementation says nothing either way about it.

Using such a store at inference time is inside scope. When an index built over a content owner's material is queried during a response and returns content that grounds the answer, that is a `content_grounded` event like any other, with `source_role: index` on the retrieval that served it (section 4.4). The line is between constructing a derived artefact and using one to answer a query, not whether an index was involved.

### 1.4 Relationship to content access protocols

Content access protocols govern how AI agents discover and license content. Examples include peek-then-pay (HTTP 203 previews with JWT licensing), IAB CoMP (content package negotiation), and bilateral API agreements.

Content Telemetry is the reporting counterpart: it records what actually happened after content was accessed.

An agent cannot reliably declare how it will use content before reading it - a retrieved article may prove irrelevant, or be used differently than intended at request time. Telemetry events are post-hoc: they report what actually happened.

Events can reference a licence via the `license_ref` field (section 5.2), connecting telemetry to whatever access protocol issued the licence. The telemetry schema does not depend on any specific access protocol.

### 1.5 Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).

## 2. Normative references

The following documents are referenced in this specification:

| Reference | Description |
|-----------|-------------|
| [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) | Key words for use in RFCs to indicate requirement levels |
| [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) | Ambiguity of uppercase vs lowercase in RFC 2119 key words |
| [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562) | Universally Unique IDentifiers (UUIDs); obsoletes RFC 4122 |
| [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) | Date and time on the internet: timestamps |
| [ISO 8601-1](https://www.iso.org/standard/70907.html) | Date and time representations |
| [ISO 3166-1](https://www.iso.org/standard/72482.html) | Country codes (alpha-2) |
| [JSON Schema draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) | JSON Schema validation |

## 3. Terms and definitions

For the purposes of this specification, the following terms apply.

| Term | Definition |
|------|------------|
| **session** | bounded interaction between an end user and a responding AI agent, identified by a session ID (section 4.2) |
| **event** | discrete record of a boundary crossing in the content lifecycle (section 4.3) |
| **emitter** | system that produces telemetry events - an AI agent, CDN edge, origin server, or content index |
| **telemetry consumer** | system that receives and processes telemetry to produce per-content-owner usage reports |
| **content owner** | entity that owns or licences content accessed by an AI agent |
| **agent operator** | entity running the AI agent that uses content |
| **grounding** | content entering the generation model's context, the boundary where content can directly influence output (section 4.3) |
| **presentation** | content or a source reference made perceivable on a recipient-facing surface (section 4.3) |
| **source role** | classification of the observer reporting a retrieval event: `origin`, `edge`, `index`, or `agent` (section 4.4) |
| **privacy level** | data sharing tier controlling which conversation fields are populated: `full`, `summary`, `intent`, or `minimal` (section 5.5) |
| **conformance level** | emitter capability tier: Retrieval, Grounding, or Citation (section 5.7) |
| **content scope** | opaque identifier grouping sessions by their content access context (section 5.1.1) |
| **governing terms** | licence, contract or other terms selecting which events a relationship requires and the coverage, cadence, delivery, privacy and reports owed (sections 5.2.4, 5.7.6) |
| **qualifying occurrence** | occurrence satisfying an event type's core definition and occurrence boundary within the relationship scope reported under (section 5.7.6) |
| **coverage** | declared relationship between qualifying occurrences and emitted events: `complete`, `sampled`, `aggregated` or `selected` (section 5.7.6) |

## 4. Concepts

### 4.1 Roles

Three economic actors participate, by position in the value chain:

| Actor | Position | Description |
|-------|----------|-------------|
| **Content owner** | Supply | Owns or licences the content an agent uses: publishers, creators, and brands with owned content. |
| **Intermediary** | Middle | Sits between content and agent: marketplaces, affiliate and ad networks, search indices, CDN and edge platforms, and telemetry vendors. |
| **Agent** | Demand | The AI agent, and the operator running it, that retrieves content and produces responses for an end user. |

The **end user** is the human interacting with the agent. They are not a telemetry participant; no actor reports the end user's identity.

Two further classifications cut across the actors and should not be confused with them:

- **Function** is what a participant does with telemetry. An *emitter* produces events; a *telemetry consumer* receives events or whole sessions, resolves content owner identity, and exposes to each content owner only its own events. A participant may be both, and any actor can run a telemetry consumer: a content owner for its own events, an agent operator, or an intermediary offering it as a service (see section 7.3).
- **Source role** is how a single event was observed, carried in the `source_role` field on `content_retrieved` events (`origin`, `edge`, `index`, `agent`; see section 4.4). It describes the observation, not the organisation.

A participant therefore has one actor (who it is), one or more functions (what it does), and a source role per event (how it observed that event). A content marketplace network, for example, is an intermediary that emits `index` events and also operates a telemetry consumer; a CDN is an intermediary that emits `edge` events on a content owner's behalf.

```
        SUPPLY                      MIDDLE                       DEMAND
  ┌────────────────┐   ┌──────────────────────────┐   ┌────────────────┐
  │ Content owner  │   │ Intermediary             │   │ Agent operator │   actor
  │ publisher,     │   │ CDN/edge · search index  │   │ the AI agent   │   = who it is
  │ creator        │   │ marketplace · vendor     │   │                │
  └───────┬────────┘   └─────────────┬────────────┘   └───────┬────────┘
          │ origin       edge / index │                       │ agent        source_role
          │                          │                        │              = how observed
          ▼                          ▼                        ▼
          └─────────────►    Telemetry consumer     ◄─────────┘
                       resolves each content owner's events;          function
                       any participant above can run one              = what it does
```

The end user sits to the right of the agent and is not shown: they interact with the agent but report nothing and are never a telemetry participant.

| Participant | Actor | Function | Source role |
|-------------|-------|----------|-------------|
| Publisher, creator | Content owner | Emitter; may self-host a consumer | `origin` |
| CDN, edge platform | Intermediary | Emitter | `edge` |
| Search index, repository | Intermediary | Emitter | `index` |
| Marketplace, ad network | Intermediary | Emitter and telemetry consumer | `index` |
| Telemetry vendor | Intermediary | Telemetry consumer | (consumes only) |
| AI agent operator | Agent | Emitter; may self-host a consumer | `agent` |

In the identity and onboarding layer, the three actors are represented by the org types `content_owner`, `platform`, and `agent`; `platform` is the intermediary's identity-layer label.

### 4.2 Sessions

A **session** represents a bounded interaction between a user and a responding AI agent.

Sessions:

- Have a unique identifier
- Track the content collection used (`content_scope`)
- Contain **events** ordered chronologically by timestamp

```
Session
├── started_at
├── events[]
│   ├── turn_started
│   ├── content_retrieved    (HTTP layer)
│   ├── content_grounded     (influence layer)
│   ├── content_cited        (response layer)
│   ├── content_presented    (recipient-facing surface)
│   ├── turn_completed
│   ├── content_engaged      (user action layer)
│   └── ...
└── ended_at
```

These are the event types a session can contain, not a strict ordering: events are ordered by timestamp. A session-scoped `content_grounded` event (for example, content grounded from cache) can precede the first `turn_started`.

### 4.3 Event lifecycle

Content moves through five stages during an agent interaction:

1. **Retrieved** - Content fetched over HTTP from an origin server, CDN, marketplace, or index. This is an infrastructure event observable by the content owner's infrastructure (origin server, edge network) and the agent. A retrieval may be cached by the agent for use across multiple sessions.

   One retrieval occurrence is one completed fetch of a content representation as observed by the reporting party: a redirect chain resolving to one representation is one occurrence, and a revalidation returning no new representation (an HTTP 304) is not a new occurrence. Serving content from the agent's own cache is not a new retrieval; the reuse surfaces as grounding (stage 2), not as a repeated `content_retrieved` event.

2. **Grounded** - Content used in the agent's generation context for this session or turn. The boundary is "this content entered the generation model's context" - the point where content can directly influence the model's output.

   Content used only for retrieval selection (embedding similarity search, re-ranking scores, routing decisions) without entering the generation context is not grounded.

   Grounding is architecture-neutral: same event whether the agent uses RAG, chain-of-thought reasoning, embeddings, or multi-step delegation (see section 6.4 for architecture-specific guidance). Grounding is decoupled from retrieval: content may be grounded from a live fetch, from agent-side cache, or from a pre-loaded index. Only the agent can report grounding events.

   One grounding occurrence is one distinct content item entering a generation context at the declared `data.scope`: at `session` scope, a content item grounds once per session; at `turn` scope, once per turn it enters. A distinct content item is a distinct `content_id`, or its canonical `content_url` where no stable identifier exists (section 4.5). Continued presence within the declared scope is not a further occurrence; re-entry in a later turn is, when the scope is `turn`, and a change of `content_version` is a new occurrence at either scope. An emitter that ingests a content item in chunks MAY emit one grounding event per chunk, preserving the chunk-level hashes of section 6.4; events sharing content identity within one scope describe one occurrence, and consumers count occurrences by deduplicating on content identity and scope, not by counting events.

3. **Cited** - An output artifact explicitly associates identified source content with a response, claim, passage, quotation, or other output element. Citation is an output-construction relationship, not evidence that the output was delivered. A subset of grounded content is commonly cited, but a citation can also be emitted without a matching grounding event when an agent produces an uncorroborated or hallucinated source association.

   A citation MUST carry a resolvable reference to the source it associates: a `content_url` or a `content_id`. A source association with no resolvable reference is not a citation and MUST NOT be emitted as `content_cited`. Unlike other content events, where the identifier requirement is an application-layer rule (section 5.7.5), for `content_cited` it is enforced by the JSON Schema.

   One citation occurrence is one distinct association between a source and an output element (or the output artifact, where no element identity exists). Associating the same source with three separate output elements produces three citation events; repeating the same association is not a further occurrence.

4. **Presented** - Content or a source reference was rendered, played, spoken, embedded, or otherwise made perceivable on a recipient-facing surface. Presentation does not assert that a person noticed or attended to it. `presentation_kind` distinguishes source content (an excerpt, an embedded page, played media) from a source reference (such as a link, credit, or card). Not all citations are presented: an output can be stored, suppressed, or passed to another system before delivery.

   Grounding and presentation record different boundary crossings: grounding records entry into a generation context, while presentation records a recipient-facing delivery occurrence. As agent experiences evolve beyond the chat window the two diverge - content can shape an answer whose source is never presented, and an agent can present content that never entered a generation context (see *Departures from the funnel model* below).

   One presentation occurrence is one rendering of content or a source reference on a recipient-facing surface; the event's `id` names that occurrence. Presenting the same artifact again - on a new surface, or in a new delivery - is a new occurrence.

5. **Engaged** - The recipient or agent performed an observable action on a presentation: clicked a link, expanded a preview, copied text, shared the response, or directed the agent to act on the content. It does not imply attention beyond the reported action. `presentation_id` links the action to the exact presentation occurrence; a click-out can also carry a `ctx_token` that a destination resolves to the click context (section 7.4).

   One engagement occurrence is one observed action on one presentation occurrence.

```
Retrieved (HTTP layer, cacheable)
  → Grounded (influence layer, per-session or per-turn)
    → Cited (response layer, per-turn)
      → Presented (recipient-facing surface, per-turn)
        → Engaged (user action layer)
```

Each stage after retrieval is typically a progressively narrower subset. The ratios between stages are meaningful for potential attribution:

- **Retrieval-to-grounding** measures content fetched but not used (irrelevant, stale, or a competing source was preferred)
- **Grounding-to-citation** measures content that influenced the response without explicit attribution
- **Citation-to-presentation** measures source associations constructed in output but not made perceivable
- **Presentation-to-engagement** measures observable actions on exact presentation occurrences

These ratios are computed over reported events and are comparable across emitters only at known coverage (section 5.7.6).

#### Departures from the funnel model

Three cases break the strict subset model:

- **Presented without cited.** An agent may present content references (e.g., a "Sources" sidebar) without semantically associating them with a response element. In this case, a `content_presented` event exists with no corresponding `content_cited` event.
- **Cited without grounded.** A hallucinated citation references content the agent never retrieved or loaded into context. The `content_cited` event has no preceding `content_grounded` event. Telemetry consumers SHOULD treat uncorroborated citations (no matching grounding event) as lower-confidence signals.
- **Presented without grounded.** An agent can present content without that content entering a generation context: an agentic browser showing a page or an embedded video played on a response surface. A `content_presented` event (typically `presentation_kind: content` and `presentation_type: embed`) exists with no corresponding `content_grounded` event.

These cases are valid. Emitters SHOULD produce the events that reflect what actually happened, even when the result does not follow the typical funnel ordering.

#### Conversation turns

Conversation turns overlay this lifecycle:

1. **Turn started** - user submits a query
2. **Turn completed** - agent finishes response

A single grounding event with session scope influences all subsequent turns. Citation, presentation, and engagement events occur within specific turns.

### 4.4 Source roles

A `content_retrieved` event can originate from multiple observers of the same retrieval. The `source_role` field identifies who is reporting:

| Source role | Reporter | Description |
|-------------|----------|-------------|
| `origin` | Content owner's web server | Content owner detected an AI agent request and reported it |
| `edge` | Edge network (CDN, edge compute) | An edge layer (Cloudflare, Fastly, Akamai, etc.) that observed the request |
| `index` | Search index or content repository | An intermediary that served the content to the agent |
| `agent` | AI agent | The agent itself, reporting content it fetched |

The `origin` and `edge` source roles enable content owners to report AI agent traffic using their existing infrastructure, with no cooperation from the AI agent required. Origin emitters typically submit individual events rather than complete sessions, since they do not have visibility into the agent's session context. Telemetry consumers correlate these standalone events with agent-reported sessions using the `content_telemetry_id` field. Example B.2 demonstrates this pattern.

A marketplace operating as both emitter and telemetry consumer receives telemetry from platforms (as a consumer), resolves content owner identity from `content_id` or `content_url`, and generates per-content-owner usage reports. The marketplace's own `source_role: index` events provide a corroboration layer - it can cross-reference what it served against what platforms reported using.

`content_grounded`, `content_cited`, and `content_presented` events are reported by the agent (or agent operator) only. These events describe what happened inside the agent, during output construction, or on a recipient-facing surface, which is not observable from the content owner's infrastructure. A third party that detects source content in a delivered output is corroborating or contradicting the emitter's claims, not observing construction; detection results belong to verification tooling, not to these event types.

`content_engaged` events are usually reported by the agent for in-product interactions. For a click-out to a landing page, a downstream marketplace, affiliate network, or destination site MAY report a corroborating `content_engaged` event using `ctx_token` in place of `session_id` (section 7.1).

When multiple observers report the same retrieval, events are correlated using the `Content-Telemetry-ID` header (see section 7.2). A retrieval corroborated by multiple sources is a stronger signal than either alone. An uncorroborated origin- or edge-reported retrieval (no matching agent event) may indicate a scraper that does not support the telemetry protocol, or missing header propagation.

#### Supply paths with a non-emitting intermediary

Telemetry cannot describe a supply path whose middle does not emit. Where an agent obtains content from an intermediary that is not a telemetry participant, the agent's events are the only record, and they carry what the agent was told: usually a URL or identifier supplied by that intermediary. Core provides no way to establish from telemetry alone that the intermediary held the content lawfully, or that the content owner ever served it.

An origin or edge event correlated by `Content-Telemetry-ID` is what closes the gap, and it exists only where the content owner observed the original request. Where it is absent, a consumer SHOULD treat the path back to the content owner as unestablished rather than infer it from the agent's report. This is a limit of the observation model, not a defect in the emitter: an agent reporting honestly cannot supply evidence about a party it did not observe.

### 4.5 Content identification

Events identify content using at least one of two fields:

| Field | Scope | Purpose |
|-------|-------|---------|
| `content_url` | Event | URL as fetched, or canonical URL |
| `content_id` | Event | Stable content identifier (CMS ID, DOI, ISBN, ISCC, C2PA manifest hash, marketplace catalogue ID) |

Either field is sufficient. Both SHOULD be included when available.

`content_url` is convenient for origin-side emitters (CDN, edge, origin) where the URL is directly observable. `content_id` is more reliable when:

- URLs change over time but the underlying article is the same
- Content is accessed through multiple paths (CDN, marketplace, cache)
- The emitter is a marketplace or index with its own identifier scheme
- Content was grounded from cache and the original URL was not preserved
- The content owner needs to match telemetry to internal systems

Emerging content identification standards - including [ISCC](https://www.iso.org/standard/88469.html) (ISO 24138, content-derived fingerprints) and [C2PA](https://c2pa.org/) (provenance manifests) - can be used as `content_id` values. The spec does not mandate a specific identifier scheme. Content owners communicate their scheme through structured data on the page, `.well-known/content-telemetry.json` manifests, content access protocol metadata, or HTTP response headers.

Repositories and mirrors SHOULD use the canonical content identifier from the original source as `content_id` (e.g., the original DOI, ISCC, or publisher-assigned ID) rather than a repository-internal identifier, so that telemetry from multiple hosts of the same content can be correlated without requiring identifier translation.

When correlating events across observers (section 7.2), emitters SHOULD use the canonical URL (from `<link rel="canonical">` or HTTP `Link` header) rather than the URL as fetched, to avoid mismatches caused by redirects, query parameters, or mobile/AMP variants. When both fields are present, `content_url` values MUST match exactly for URL-based correlation. When exact URL matching is unreliable, `content_id` provides a stable alternative.

Additional content metadata - version, last-modified timestamp, content hash, media type - is carried in event data profiles (section 6) where its relevance varies by event type and source role.

## 5. Schema

### 5.1 Session

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Schema version as `major.minor` (v1 documents declare "1.0"; see section 12) |
| `session_id` | UUID | Yes | Unique session identifier |
| `parent_session_id` | UUID | No | Immediate parent session that delegated work to this session |
| `agent_id` | string | No | Responding agent identifier |
| `content_scope` | string | No | Opaque content collection identifier (see 5.1.1) |
| `manifest_ref` | string | No | Manifest reference (see 5.1.2 and section 8) |
| `started_at` | datetime | Yes | Session start (UTC) |
| `ended_at` | datetime | No | Session end (UTC) |
| `conformance_level` | string | No | Informational conformance level advertised by the emitter (see section 5.7). Values: `retrieval`, `grounding`, `citation` |
| `document_type` | string | No | `"session"` for session documents (see section 7.1 for the standalone event and event batch formats) |
| `data` | object | No | Session-level extension container, including access context (see 5.1.3) |
| `events` | Event[] | No | Ordered list of events |

`parent_session_id` links a delegated session to its immediate parent without
requiring an emitter to disclose the agent system's full internal topology. A
child session retains its own `session_id`, events and conformance obligations.
Emitters MAY omit the link when the relationship is unavailable or its disclosure
is not appropriate. Consumers MUST NOT infer that an unlinked session had no
parent.

The event boundary does not change in a multi-agent system. Content entering a
sub-agent's generation context is grounded in the child session. A source
reference that appears only in the sub-agent's response to its orchestrator is
not thereby a citation or presentation to the end user; those events require the
corresponding relationship or presentation in the recipient-facing output.

#### 5.1.1 Content scope

The `content_scope` field is an opaque identifier that groups sessions by their content access context. Implementers define its meaning:

| Implementation | Example value |
|----------------|---------------|
| Content platform | `"electronics-reviews"` |
| Manifest-scoped | `"https://example.com/.well-known/content-telemetry.json"` |
| API key scoped | API key identifier |
| Agreement-based | Agreement or contract ID |

Telemetry consumers can aggregate across sessions that share the same `content_scope` without the schema mandating a specific access control model. When a session spans multiple licensing agreements, emitters MAY use `license_ref` on individual events as a per-event scope proxy, since `license_ref` is event-level while `content_scope` is session-level.

#### 5.1.2 Manifest reference

The `manifest_ref` field optionally references a manifest (section 8), identifying the participant and its declared telemetry endpoint at session time.

Format: the URL of a manifest served at `/.well-known/content-telemetry.json` under a path the participant controls.

#### 5.1.3 Session data and access context

Sessions carry an optional `data` object mirroring the event-level `data` field (section 11.1): an extension container for session-scoped metadata. Extensions SHOULD namespace custom fields or use containers documented in this specification, and consumers MUST tolerate unknown fields within it. The session root itself is not an extension point: custom top-level siblings of `events` are not defined by this specification, and consumers are not required to preserve or interpret them.

One container is defined in core. `access_context` records the context from which the session's access rights derive - the institution, not the individual:

```json
{
  "schema_version": "1.0",
  "session_id": "770e8400-e29b-41d4-a716-446655440000",
  "content_scope": "consortium-agreement-4471",
  "started_at": "2026-08-13T14:02:10Z",
  "data": {
    "access_context": {
      "identifiers": [
        { "scheme": "ror", "value": "https://ror.org/013meh722" },
        { "scheme": "saml_entity_id", "value": "https://idp.example.ac.uk/shibboleth" }
      ]
    }
  },
  "events": []
}
```

`identifiers` is an array of typed identifiers, each a `scheme` and a `value`. `ror`, `saml_entity_id` and `isni` are the core scheme values; emitters MAY use other schemes and telemetry consumers MUST tolerate unknown ones, as with `media_type` (section 6.1). Access rights can derive through consortia, federated identity and proxies at once, so a session may carry both a SAML entity ID and the ROR ID it maps to.

`access_context` identifies an institution, never an individual, and like every session field it is a claim by the emitter. The field serves the third-party agent that holds the entitlement and asserts the affiliation to the content owner; where the owner authenticated the session itself (`source_role` of `origin` or `edge`), it already knows the institution. Corroborating an asserted affiliation is verification-layer work, outside core.

Emitters MUST NOT populate `access_context` unless the governing terms of the relationship require it, and SHOULD pair it with `intent` or `minimal` conversation-turn data (section 5.5): an identified institution combined with query text can come close to identifying an individual at a small subscriber.

### 5.2 Event

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | For cited/presented | Emitter-assigned unique event identifier; optional on other event types |
| `type` | EventType | Yes | Event type (see 5.3) |
| `timestamp` | datetime | Yes | Event timestamp (UTC) |
| `turn_id` | string | No | Associates this event with a conversation turn (see 5.2.1) |
| `output_id` | string | For cited/presented | Opaque output-artifact identifier joining construction to later delivery |
| `output_element_id` | string | No | Opaque element within `output_id`, such as a passage, media track, caption, link, or card |
| `citation_id` | UUID | No | On `content_presented`, the `id` of the associated citation event; absent for uncited presentations |
| `presentation_id` | UUID | For engaged | On agent-reported `content_engaged`, the `id` of the exact presentation occurrence acted upon. Destination-reported events carrying an envelope `ctx_token` omit it (section 7.4) |
| `ctx_token` | string | No | On agent-reported `content_engaged`, the click token minted for this engagement's presentation, recorded so destination reports join to it (section 7.4) |
| `source_role` | SourceRole | No | Who is reporting: `origin`, `edge`, `index`, `agent` (see 4.4) |
| `content_telemetry_id` | UUID | No | Correlation ID for cross-observer deduplication (see 7.2) |
| `content_url` | string | No | Content URL as fetched or canonical URL |
| `content_id` | string | No | Content owner's stable content identifier (see 4.5) |
| `license_ref` | string | No | Reference to a licence or grant the emitter associates with this event (see 5.2.3) |
| `terms_ref` | string | No | Reference to the governing terms the emitter associates with this event (see 5.2.4) |
| `turn` | ConversationTurn | No | Conversation data (for turn events) |
| `data` | object | No | Type-specific metadata (see section 6) |

#### 5.2.1 Turn association

The `turn_id` field associates content events with a specific conversation turn. Emitters SHOULD set `turn_id` on `content_cited`, `content_presented`, and `content_engaged` events. Emitters SHOULD also set `turn_id` on `content_grounded` events when `scope` is `turn`. The corresponding `turn_started` and `turn_completed` events SHOULD carry the same `turn_id`.

`turn_id` is scoped to the session. Format is emitter-defined (sequential integers, UUIDs, or any opaque string).

Content events without a `turn_id` (e.g., `content_grounded` with `scope: session`) apply to the session as a whole rather than a specific turn.

#### 5.2.2 Source role

The `source_role` field MUST be set on `content_retrieved` events (section 5.7.1): without it a consumer cannot tell an agent-reported fetch from an origin- or edge-reported one, or correlate the observers of one retrieval. When multiple systems observe the same retrieval, the `content_telemetry_id` field correlates their events for deduplication.

#### 5.2.3 Licence reference

The `license_ref` field associates a telemetry event with a licence or grant the emitter references. The format depends on the access protocol: a JWT `jti` claim, a CoMP package ID, or any opaque identifier that both parties can resolve.

Core does not resolve, validate or interpret the reference. `license_ref` is part of the emitter's claim about the event: it records which grant the emitter says applied. It does not establish that the grant existed, that it covered this content, that it was valid at the time of use, or that the use was permitted. A consumer that needs any of those has to check the issuer's own records, or use evidence defined outside this specification.

`license_ref` also does not identify the party whose entitlement was used. Where a publisher issues one grant per subscriber the value may work as a proxy for that subscriber, but only within the issuing publisher's namespace: nothing here requires the value to be typed, stable across sessions, or comparable between emitters.

#### 5.2.4 Terms reference

The `terms_ref` field associates a telemetry event with the governing terms under which it is reported: a licence agreement, a standard-form contract, a tariff, a profile's terms, or any other terms document. Like `license_ref`, the value MAY be a public URL or an opaque identifier that both parties can resolve. Nothing requires the terms to be published: per-relationship terms are often confidential, and an opaque identifier resolved privately is a conforming reference.

`license_ref` records which grant the emitter says applied (5.2.3). `terms_ref` records which terms govern the event's commercial consequences and the emitter's reporting obligations. Either may appear without the other: an access outside any grant carries no `license_ref`, and can still carry the `terms_ref` of the terms that attach consequences to that access.

Core does not resolve, validate or interpret the reference, and `terms_ref` does not redefine core event semantics. Governing terms select which events a relationship requires and at what coverage (section 5.7.6), together with the cadence, delivery, privacy and reports owed (SCOPE.md); the meaning and occurrence boundary of each event remain those defined in sections 4.3 and 6, whatever `terms_ref` points to.

A processor that stores, forwards or transforms a document MUST preserve `terms_ref` unchanged and MUST NOT remove or rewrite it. A `terms_ref` value MUST always refer to the same terms: when terms change, the emitter references them with a new value, so events emitted under earlier terms remain resolvable to them. A consumer MUST NOT read the absence of `terms_ref` as a statement that no terms governed the event (the same rule as event absence under coverage, section 5.7.6).

### 5.3 Event types

#### Content events

| Type | Description | Expected fields |
|------|-------------|-----------------|
| `content_retrieved` | Content fetched from source | `content_url`, `source_role`, `data.media_type` |
| `content_grounded` | Content loaded into agent context | `content_url` or `content_id`, `data.scope`, `data.cached` |
| `content_cited` | Output explicitly associates source content with an output element | `id`, `output_id`, `content_url` or `content_id`, `data.citation_type` |
| `content_presented` | Content or a source reference was made perceivable | `id`, `output_id`, `content_url` or `content_id`, `data.presentation_kind`, `data.presentation_type` |
| `content_engaged` | Observable action on an exact presentation | `presentation_id`, `content_url` or `content_id`, `data.engagement_type` (see 6.7) |

#### Conversation events

| Type | Description | Expected fields |
|------|-------------|-----------------|
| `turn_started` | User initiated a turn | `turn_id`, `turn` |
| `turn_completed` | Agent finished responding | `turn_id`, `turn` |

#### Extension events

The core schema defines content and conversation events. Implementations MAY define additional event types using the `data` field for type-specific metadata. Commerce-specific fields (product identifiers, checkout events) are a planned extension.

### 5.4 Conversation turn

A conversation turn represents one query-response exchange. Turn data is carried on `turn_started` and `turn_completed` events via the `turn` field. The `privacy_level` controls which fields are populated (see 5.5).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `privacy_level` | PrivacyLevel | Yes | Data sharing level |
| `query_text` | string | No | User's query (full/summary) |
| `response_text` | string | No | Agent's response (full/summary) |
| `query_intent` | IntentCategory | No | Classified intent (available at `intent`, `summary`, and `full` levels) |
| `response_type` | string | No | Response classification (free-form; e.g., `"recommendation"`, `"explanation"`, `"comparison"`) |
| `response_mode` | ResponseMode | No | Product surface or generation mode (see 5.4.1) |
| `topics` | string[] | No | Detected topics/entities |
| `content_urls_retrieved` | URI[] | No | Content fetched |
| `content_urls_cited` | URI[] | No | Content cited in response |
| `query_tokens` | integer | No | Query token count |
| `response_tokens` | integer | No | Response token count |
| `model_id` | string | No | Model identifier |
| `ad_rendered` | boolean | No | Whether advertising was rendered alongside the response |

#### 5.4.1 Response modes

`response_mode` identifies the product surface or generation mode, distinct from `response_type` which classifies the nature of the answer (recommendation, explanation, etc.):

| Value | Description |
|-------|-------------|
| `standard` | Standard conversational response |
| `deep_research` | Multi-step research mode with extended retrieval |
| `search` | Search results presentation |
| `code_generation` | Code generation or editing |

These are the recommended values. Platforms with additional product surfaces (collaborative canvases, voice, image generation, etc.) MAY use custom string values. Telemetry consumers MUST tolerate unknown `response_mode` values.

### 5.5 Privacy levels

| Level | Query/response text | Intent | Topics | Token counts | Content URLs | Response classification | Platform metadata |
|-------|---------------------|--------|--------|--------------|-------------|------------------------|-------------------|
| `full` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `summary` | Summarised | Yes | Yes | Yes | Yes | Yes | Yes |
| `intent` | No | Yes | Yes | Yes | Yes | Yes | Yes |
| `minimal` | No | No | No | Yes | Yes | No | No |

An emitter that populates a conversation turn MUST NOT include a field above that turn's declared `privacy_level` - for example, `query_text` MUST NOT be present when `privacy_level` is `intent` or `minimal`. This restriction is a property of `privacy_level` itself: it applies wherever conversation turns are emitted, independent of the emitter's conformance level.

The session-level `access_context` container (section 5.1.3) does not appear in this table but is subject to the privacy model. It is populated only where governing terms require it, and pairing it with `full` or `summary` turn data is discouraged (section 5.1.3): `privacy_level` controls how much of the query and response is visible, `access_context` identifies whose access rights the session used, and populating both makes re-identification easier.

**Token counts** includes `query_tokens` and `response_tokens`. These are available at all levels because they are needed for token-based counting models and do not reveal user intent or platform strategy. They carry the same portability limit as `tokens_ingested` (section 6.4): both are measured in the emitter's own tokeniser and are not comparable between agents. Version 1 does not define corresponding turn-level character counts; `chars_ingested` measures source content placed in a generation context, not query or response length.

**Response classification** includes `response_type` (e.g., `"recommendation"`, `"explanation"`). Available at `intent` level and above, as it can reveal the nature of the user's query.

**Platform metadata** includes `ad_rendered`, `model_id`, and `response_mode`. These describe the agent or platform, not the user, but may reveal commercially sensitive information. Available at `intent` level and above.

`content_urls_retrieved` and `content_urls_cited` are available at all levels, including `minimal`, because individual content events already expose `content_url` at every privacy level. The `minimal` level protects query-level signals (intent, topics, response categorisation), not the existence of content attribution relationships. The turn-level arrays are a convenience for consumers who process turns without joining to content events. These arrays are **derived, not authoritative**: emitters SHOULD populate them from the corresponding content events in the session. When the arrays conflict with the individual content events, the content events are the source of truth.

These levels control how much of the user's query and the agent's response the recipient sees. They do not hide which content was used - that is the signal the format exists to carry - or how much of it an agent grounds. Both stay visible to whoever receives the telemetry, at every level including `minimal`.

### 5.6 Intent categories

**Information:** `question`, `explanation`, `comparison`, `how_to`, `troubleshooting`, `fact_check`, `analysis`, `opinion_seeking`

**Creative:** `creative`

**Commerce:** `purchase_intent`

**Other:** `chitchat`, `other`

These are the core values. Extensions MAY define additional intent category values (e.g., `price_check`, `availability_check`, `review_seeking` for commerce). Telemetry consumers MUST tolerate unknown `query_intent` values.

### 5.7 Conformance levels

Emitters that advertise a standard capability tier use one of three conformance levels. The authoritative declaration lives in the emitter's manifest (section 8). Emitters MAY also include an optional `conformance_level` field on individual session documents; when present it is informational and consumers MUST NOT treat it as a substitute for verifying the manifest's declaration.

Each level is named for the event it adds: a level proves the emitter produces that event and everything below it. A level does not assert that every qualifying occurrence was reported (section 5.7.6). These levels describe what an emitter reports, not what a consumer computes from it; attribution - the apportioning of credit across content - is performed by a telemetry consumer at whatever funnel level the parties agree (section 10), and can be computed from grounding alone, without citation. An emitter does not need to reach the Citation level for its telemetry to support attribution.

| Level | Events | What it proves | Typical emitter |
|-------|--------|----------------|-----------------|
| **Retrieval** | `content_retrieved` | Content was fetched by an agent | Content owner CDN, edge network, origin server |
| **Grounding** | Above + `content_grounded`, turn events | Content entered the agent's context | Agent with basic instrumentation |
| **Citation** | Above + `content_cited` | Content was explicitly referenced in the agent's response | Agent with citation instrumentation |

Presentation and engagement events are optional lifecycle signals outside the Retrieval/Grounding/Citation ladder. A Citation emitter SHOULD emit them when applicable (section 5.7.3), but the Citation level proves citation support, not full retrieval-to-engagement coverage.

#### 5.7.1 Retrieval conformance

A conforming **Retrieval** emitter MUST:

- Set `source_role` on `content_retrieved` events
- Include at least one of `content_url` or `content_id` on every content event
- Set `type` and `timestamp` on every event

This level requires no agent cooperation. Content owners can implement it using CDN edge compute (Cloudflare Workers, Fastly Compute, etc.).

Origin-side emitters operating at the CDN edge SHOULD include `bot_category`, `response_status`, and `response_bytes` alongside the required fields. These fields make retrieval events useful for bot classification and volume analysis. Without them, the event confirms a fetch occurred but cannot support attribution correlation.

#### 5.7.2 Grounding conformance

A conforming **Grounding** emitter MUST satisfy Retrieval requirements and also:

- Produce sessions with `schema_version`, `session_id`, `agent_id`, and `started_at`
- Emit `content_grounded` events with `data.scope` (schema-enforced; section 6.4)
- Include at least one of `content_url` or `content_id` on every content event
- Emit `turn_started` and `turn_completed` events with `privacy_level`
- Restrict conversation turn fields to the declared `privacy_level` (section 5.5)

A Grounding emitter SHOULD include `data.chars_ingested` and `data.cached` on grounding events, and MAY add `data.tokens_ingested` alongside them (section 6.4).

Emitters using standalone event delivery (section 7.1) MUST include `agent_id`, `started_at`, and either `session_id` or, for click-out engagement events, `ctx_token` on the standalone event envelope to satisfy Grounding conformance.

#### 5.7.3 Citation conformance

A conforming **Citation** emitter MUST satisfy Grounding requirements and also:

- Emit `content_cited` events with `id`, `output_id`, `data.citation_type`, and a non-null `content_url` or `content_id` (schema-enforced; section 6.5)

The privacy-level field restriction (section 5.5) applies to Citation emitters as it does to any emitter producing conversation turns; it is inherited through the Grounding requirements above.

A Citation emitter SHOULD:

- Emit `content_presented` and `content_engaged` events when applicable
- Include `data.position` on citation events
- Include `output_element_id` when the cited or presented element has a stable identity
- Include `citation_id` on a presentation of a cited source association

#### 5.7.4 Telemetry consumers

A conforming **telemetry consumer** MUST:

- Accept documents declaring any `schema_version` with the same major version as the one the consumer implements. `schema_version` is `major.minor` (section 12): v1.0 documents declare `"1.0"`, and the v1.0 schemas accept that value only. Each minor version publishes its own schemas. A consumer implementing 1.y validates a document declaring 1.x, x ≤ y, against the 1.x schemas, and a document declaring a later minor against the latest schemas it implements, tolerating the optional fields that minor added. A v1 consumer MUST reject documents declaring `"0.1"`: v0.1 is a different wire version, not a compatible minor. Conversely, a v0.1 consumer following the preview rule (a 0.x consumer accepts only the exact same minor version, so a 0.1 consumer accepts 0.1 only) rejects documents declaring `"1.0"`.
- Tolerate unknown fields without error
- Tolerate events from any conformance level
- Accept the session-document, standalone-event, and event-batch delivery formats, reconstructing sessions from standalone events and event batches where needed (see section 7.1)

#### 5.7.5 Application-layer conformance rules

The JSON Schema (`telemetry-session.json`) validates structure and types but cannot express every conformance rule. The following are normative requirements verified at the application layer, not by schema validation:

- At least one of `content_url` or `content_id` MUST be present on every content event (section 4.5). For `content_cited` events this requirement is additionally enforced by the JSON Schema, which rejects an event whose reference is absent or null (section 6.5).
- An event MUST carry either `session_id` or `ctx_token` at Grounding conformance and above (section 7.1).
- Conversation-turn fields MUST NOT exceed the turn's declared `privacy_level` (section 5.5).
- The conformance-level requirements (sections 5.7.1 to 5.7.3) are cumulative.
- When `content_grounded.data.provenance` is `agent_fetched`, `data.cached` MUST be `false`; when it is `agent_cached`, `data.cached` MUST be `true` (section 6.4).
- `content_grounded.data.content_fingerprint` MUST NOT contain `preserved_in_output`; v1 defines no output-side reuse reporting (sections 6.4 and 12.1).
- `source_role` MUST be present on every `content_retrieved` event (sections 5.2.2, 5.7.1).
- Fields scoped to an event type MUST NOT appear on other types: `presentation_id` and the event-level `ctx_token` only on `content_engaged`; `citation_id` only on `content_presented`; `turn` only on `turn_started` and `turn_completed` (section 5.2).
- Within a session document, event `id` values MUST be distinct; a `content_engaged.presentation_id` MUST reference a `content_presented` event, and a `citation_id` a `content_cited` event, that identifies the same content - where both events carry `content_id` the values MUST be equal, and likewise for `content_url` (sections 6.6, 6.7); one event-level `ctx_token` MUST NOT appear on engagements bound to two different presentations (section 7.4.1).
- An envelope `ctx_token` (section 7.1) MUST accompany `content_engaged` events only.
- Manifests: `domains` MUST appear only on a manifest served at the domain root, and `telemetry.ctx_resolution` only on a manifest declaring the `agent` or `platform` role (sections 8.5, 8.6).

The `tests/` directory provides an informative reference suite for these rules. A consumer that receives a privacy-violating turn (e.g., `query_text` present at `minimal` level) SHOULD strip the offending fields rather than reject the document carrying them.

#### 5.7.6 Occurrence, qualifying events and coverage

Each core event type has the meaning and occurrence boundary defined in sections 4.3 and 6. Profiles, deployment configurations and governing terms MUST NOT redefine them. A relationship that needs a different assertion defines a namespaced extension event (sections 5.3 and 11.1); it does not reuse a core type with altered semantics.

An occurrence is **qualifying** for an emitter when it satisfies the core definition and occurrence boundary of its event type and falls within the relationship scope the emitter reports under - the content, domains or relationships selected by the applicable governing terms or deployment configuration.

A conformance level (sections 5.7.1 to 5.7.3) does not assert that every qualifying occurrence was reported. Reporting coverage is a separate, explicit declaration, stated as one of four modes:

- **complete** - every qualifying occurrence is emitted
- **sampled** - qualifying occurrences are emitted under a stated sampling rule
- **aggregated** - qualifying occurrences are reported only through a stated aggregation rule
- **selected** - only qualifying occurrences satisfying a further stated condition are emitted

A coverage declaration states its mode together with the relationship scope it applies over; both MUST be disclosed to the receiving party. The rule or condition for `sampled`, `aggregated` and `selected` MUST be objectively decidable from information available at emission time and MUST NOT depend on the emitter's discretion at the moment of emission. An emitter reporting under governing terms that state a coverage mode MUST report at that mode, and an emitter MUST NOT declare or describe its reporting as `complete` for an event type unless every qualifying occurrence is emitted. A consumer MUST NOT treat the absence of an event as evidence that no occurrence happened except where complete coverage applies.

An emitter MAY declare its coverage modes machine-readably in its manifest (`telemetry.coverage`, section 8.5); a manifest declaration is subject to the same rules, and where governing terms and a manifest declaration conflict, the governing terms take precedence for the relationships they cover.

Whether an emitter's reporting in fact met its declared coverage is the completeness question of SCOPE.md's conformance list: it is answered by verification and audit mechanisms outside core, not by the declaration itself.

## 6. Data profiles

The `data` field on events carries type-specific metadata. These profiles document the recommended fields by event type and source role. None are required except where a section states otherwise - `scope` in 6.4, `citation_type` in 6.5, `presentation_kind` and `presentation_type` in 6.6, each enforced by the JSON Schema - but emitting them enables richer attribution.

### 6.1 Retrieved content metadata (`content_retrieved`)

When the reporter is the agent (`source_role: agent`), the following fields are recommended:

| Field | Type | Description |
|-------|------|-------------|
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` (see below) |
| `content_depth` | string | Depth of the content record reached: `metadata`, `abstract`, `full` (see below) |

`media_type` on retrieval events allows content owners to see what types of content are being fetched, independent of whether those retrievals result in grounding or citation. Defaults to `text` when absent.

`text`, `image`, `video`, and `audio` are the core values. Emitters MAY use custom string values for media outside the core set (for example `3d` or `dataset`). Telemetry consumers MUST tolerate unknown `media_type` values. This rule applies to `media_type` on every event type that carries it (sections 6.4, 6.5, 6.6).

`content_depth` records how much of the content record the retrieval reached: `metadata` for a bibliographic or descriptive record only, `abstract` for an abstract or summary record, `full` for the full content record. These are the core values; emitters MAY use custom values and telemetry consumers MUST tolerate unknown ones. Where entitlement gates depth, a retrieval that reached only an abstract and a retrieval of full text are otherwise indistinguishable at the retrieval layer. Depth records what was reachable at retrieval, independent of what portion later entered a generation context.

Although listed in the agent profile, `content_depth` applies to `content_retrieved` events from any `source_role`. The origin that served the response knows the depth authoritatively, and origin and edge reporters SHOULD include it alongside their fields in sections 6.2 and 6.3 where entitlement gates depth.

### 6.2 Edge enrichment (`content_retrieved` + `source_role: edge`)

CDN and edge network integrations SHOULD include these fields:

| Field | Type | Description |
|-------|------|-------------|
| `user_agent` | string | Request User-Agent header |
| `bot_category` | string | Edge platform's bot classification (see below) |
| `bot_name` | string | Recognised bot family parsed from the User-Agent (e.g., `Claude-User`, `GPTBot`, `Perplexity-User`) |
| `verified` | boolean | Whether the bot identity was cryptographically verified |
| `cache_status` | string | Edge cache result: `hit`, `miss`, `bypass`, `dynamic` |
| `response_status` | integer | HTTP response status code |
| `response_bytes` | integer | Response body size in bytes |
| `ja4` | string | JA4 TLS client fingerprint |
| `asn` | integer | Client AS number |
| `asn_org` | string | Client AS organisation name |
| `country` | string | ISO 3166-1 alpha-2 country code |

#### Bot categories

The `bot_category` field carries the edge platform's classification of the requesting bot. Recommended values:

| Value | Description | Fastly signal | Cloudflare signal |
|-------|-------------|---------------|-------------------|
| `training` | Crawling for model training | `AI-CRAWLER` | `AI Crawler` |
| `inference` | Fetching at query time (RAG) | `AI-FETCHER` | `AI Assistant` |
| `search` | AI search indexing | - | `AI Search` |

The `inference` category is where content attribution is most relevant - there is a user, a query, and a session behind the retrieval. `training` crawls have no session context. `bot_category` can distinguish training crawls from inference fetches, but training-specific telemetry is out of scope for this specification (see section 1.3). Edge platforms map their native classification to these values.

Emitting a `training`-category `content_retrieved` event is permitted but non-attributable - there is no session, grounding, or citation to follow it. An edge emitter can report these events through its normal pipeline and need not special-case or suppress them.

### 6.3 Origin enrichment (`content_retrieved` + `source_role: origin`)

| Field | Type | Description |
|-------|------|-------------|
| `user_agent` | string | Request User-Agent header |
| `response_status` | integer | HTTP response status code |

### 6.4 Grounding data (`content_grounded`)

| Field | Type | Description |
|-------|------|-------------|
| `scope` | string | Required. Influence scope: `session` or `turn` (see below) |
| `cached` | boolean | Content served from agent-side cache rather than a live fetch |
| `provenance` | string | How content reached the context: `agent_fetched`, `agent_cached`, or `third_party_sourced` (see below) |
| `chars_ingested` | integer | Character count of content placed in the generation context (see below) |
| `tokens_ingested` | integer | Token count of the same content, supplementary (see below) |
| `content_version` | string | Content version identifier (ETag, revision ID, CMS version) |
| `content_last_modified` | datetime | When the content was last modified at source |
| `content_hash` | string | SHA-256 of the content as ingested (`sha256:{hex}`) |
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` (open vocabulary, see 6.1) |
| `content_fingerprint` | object | Agent-reported detection of a fingerprint or provenance signal in the grounded content (see below) |

Both fields measure the content actually placed in the generation model's context. For chunked retrieval, count only the portion used, not the full source document.

`chars_ingested` counts Unicode code points in the exact text placed in context. Count the string as ingested: an emitter MUST NOT apply Unicode normalisation solely to calculate this field. It is the portable measure: two emitters that ingest the same code-point sequence agree, so a content owner can compare volumes across agents and over time without knowing which model produced the number. Different normalised representations remain different ingested sequences and may therefore produce different counts.

`tokens_ingested` counts the same content in the generation model's tokeniser (the model identified in `model_id` on the corresponding `turn_completed` event), not the retrieval or embedding model's tokeniser. It is supplementary. Token counts are model-specific, change when a vendor revises a tokeniser, and are not comparable between agents, so a consumer cannot aggregate them across emitters or treat a difference as a difference in volume. Emitters SHOULD send `chars_ingested` where they send `tokens_ingested`, and consumers that receive only token counts SHOULD record which model produced them. At `minimal` privacy the turn carries no `model_id` (section 5.5); token counts reported at that level name no tokeniser, and consumers SHOULD NOT compare them with counts from any other emitter or model.

#### Provenance and content fingerprints

`provenance` describes the delivery path by which the grounded representation reached the agent:

| Value | Description |
|-------|-------------|
| `agent_fetched` | The agent obtained the representation directly from the publisher or from publisher-authorised origin or edge infrastructure for this session |
| `agent_cached` | The agent reused a representation it had obtained before this session |
| `third_party_sourced` | The representation reached the agent through an intermediary rather than through a direct publisher-authorised retrieval by the agent in this session |

The field describes delivery path, not evidence quality. An emitter declaring Grounding or Citation conformance SHOULD include it when the path is known. It remains optional because an agent may not be able to distinguish its own earlier fetch from intermediary delivery. Consumers MUST NOT infer a value when it is absent.

Emitters MUST keep `provenance` and `cached` consistent: `agent_fetched` requires `cached: false`, and `agent_cached` requires `cached: true`. `third_party_sourced` leaves `cached` unconstrained because an intermediary-sourced representation may be used immediately or cached by the agent before grounding.

`content_fingerprint` contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheme` | string | Yes | Open identifier for the fingerprint or provenance scheme checked |
| `detected` | boolean | Yes | Emitter claim that the scheme's signal was found in the exact grounded representation |
| `value` | string | No | Scheme-defined fingerprint or identifier value, when the scheme produces one |

`detected` reports a grounding-time observation by the emitter. It does not establish that the signal is authentic, identify who applied it, prove that the content was used later in the output, or raise the evidentiary status of the grounding event. Those questions require profile-defined evidence and consumer trust policy outside the core schema.

The fingerprint is a grounding-time claim only: v1 defines no field asserting that a fingerprinted signal was preserved in the output (the pre-release `preserved_in_output` field is withdrawn; section 12.1). A consumer MAY compare a grounding fingerprint with evidence about the output gathered outside this specification, but the two remain separate assertions about separate lifecycle stages.

`scheme` is an open identifier. Emitters SHOULD use a globally collision-resistant value. Core does not register schemes, interpret `value`, or assign capabilities or evidence status from a scheme identifier. A profile MAY define scheme-specific processing rules.

#### Grounding scope

| Value | Description |
|-------|-------------|
| `session` | Content informed all subsequent responses in the session. |
| `turn` | Content informed this specific response only. |

For session-scoped grounding, the number of turns influenced is derivable from the session's `turn_started` events following the grounding event. This avoids redundant per-turn grounding events for content that persists across responses.

`scope` is required on every `content_grounded` event and the JSON Schema enforces it: the occurrence boundary of section 4.3 and every counting model in section 10 depend on knowing whether a grounding informed one response or the rest of the session.

#### Agent architecture and the grounding boundary

The grounding event marks the point where content enters the generation model's context - the boundary where content can directly influence the model's output text. Content used only for retrieval selection (embedding similarity search, re-ranking, query routing) without entering the generation context is not grounded.

In a pipeline that retrieves 100 articles, generates embeddings for all 100, re-ranks to 10, and places 5 in the generation prompt - the grounding count is 5. The 95 articles used only for selection are retrievals, not groundings. The 10 that survived re-ranking but were not placed in context are also retrievals, not groundings.

The grounding event is drawn at the same point - entry into the generation context - regardless of agent architecture:

| Architecture | What grounding means | What is NOT grounded |
|---|---|---|
| Standard RAG | Content placed in the LLM prompt after retrieval and re-ranking | Content retrieved but eliminated during re-ranking |
| Reasoning model | Content ingested before a chain-of-thought that may span thousands of internal tokens | Content used only to select which reasoning chain to invoke |
| Multi-step agent | Content that entered a sub-agent's generation context | Content used only by the orchestrator to decide which sub-agents to invoke |
| Embedding-based | Content chunks whose embeddings were placed in the generation context | Embeddings used only for similarity search or candidate selection |

The boundary is drawn at the generation context rather than at earlier processing stages, the point most directly tied to content influence on the output.

The boundary is consistent; the resulting grounding *count* is not. An agent that loads fifty results into a long context and one that places three re-ranked chunks produce very different grounding counts for the same answer. The counting model is therefore left to commercial agreement (section 10) rather than fixed by the format.

#### Caching

The `cached` field distinguishes live fetches from cached reuse. A live fetch produces both a `content_retrieved` and a `content_grounded` event. A cached grounding produces `content_grounded` only - there is no corresponding HTTP request for the content owner's infrastructure to observe.

`cached: true` asserts only that the content was grounded without a live fetch this session - the agent already held the bytes. It does not distinguish the kind of cache (a days-old stored document, a semantic cache, or infrastructure-level prompt caching) and makes no claim about freshness; freshness is carried by `content_version`, `content_last_modified`, and `content_hash`.

Telemetry consumers may weight cached and live groundings differently. An agent may cache an article for days or weeks, grounding it in multiple sessions from a single retrieval. A single retrieval produces one `content_retrieved` event but potentially many `content_grounded` events across subsequent sessions.

Agents SHOULD preserve the `license_ref` from the original retrieval when emitting cached grounding events. Without this, telemetry consumers cannot link cached usage to the grant referenced at the original access.

#### Freshness and verification

`content_version` and `content_last_modified` enable freshness analysis. Content owners with time-sensitive content (financial news, live events, market data) can use these fields to distinguish real-time use from stale cache hits. When content is grounded from cache, `content_last_modified` reflects when the source content was last modified, not when it was cached. Agents SHOULD preserve the `Last-Modified` header or equivalent metadata from the original retrieval.

`content_hash` is the SHA-256 of the content as it entered the agent's context. When the agent ingests a chunk rather than the full document, this is the chunk hash, not the document hash. The same hash on a corresponding `content_cited` event identifies which grounded content was cited - it matches the grounding hash, not the full source document. Content owners can compare grounding hashes against known document or chunk hashes to detect truncation, modification, or stale content.

### 6.5 Citation data (`content_cited`)

| Field | Type | Description |
|-------|------|-------------|
| `citation_type` | string | Required. How content was used: `direct_quote`, `paraphrase`, `reference`, `contradiction`, `unclassified` |
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` (open vocabulary, see 6.1) |
| `excerpt_tokens` | integer | Token count of the excerpt used |
| `excerpt_chars` | integer | Character count of the excerpt used |
| `excerpt_hash` | string | SHA-256 of the cited excerpt text (`sha256:{hex}`). See below. |
| `position` | string | Prominence in response: `primary`, `supporting`, `mentioned`, `unclassified` |
| `content_hash` | string | SHA-256 matching the corresponding `content_grounded` event (`sha256:{hex}`). When the agent chunked the source, this is the chunk hash, not the full document hash. |
| `url_verified` | boolean | Whether the cited URL was verified to resolve to matching content |

A citation MUST carry a resolvable source reference: a non-null `content_url` or `content_id` at the event level. This is what distinguishes a citation from vague attribution - the credit names a source that owner routing (section 7.3) can resolve. The JSON Schema enforces this for `content_cited` events; an association the emitter cannot resolve to a URL or identifier is not reportable as a citation. This is stricter than the application-layer identifier rule that applies to content events generally (section 5.7.5). `citation_type` is likewise required and schema-enforced; an emitter that cannot classify a citation uses `unclassified` rather than omitting the field.

`media_type` identifies the content medium. Defaults to `text` when absent.

`excerpt_chars` counts Unicode code points in the cited excerpt under the same counting rule as `chars_ingested` (section 6.4): no normalisation applied solely for counting. It is the portable primary measurement, comparable across emitters and stated in a unit familiar to content owners and licensors. `excerpt_tokens` counts the same excerpt in the generation model's tokeniser; it is the agent-native supplementary measurement, carrying the same portability limits as `tokens_ingested`. Emitters SHOULD send `excerpt_chars` where they send `excerpt_tokens`.

`excerpt_hash` is the SHA-256 of the excerpt text as it appears in the agent's response - the exact string the agent produced, not the source text it was derived from. For `direct_quote` citations, a matching hash against the source content confirms verbatim fidelity. For `paraphrase` citations, a non-matching hash is expected; verification tooling can use the hash to confirm which specific excerpt was cited and compare it against known source passages. Emitters SHOULD include `excerpt_hash` when `excerpt_tokens` or `excerpt_chars` is present. The hash uses the same `sha256:{hex}` format as `content_hash`.

The `contradiction` type supports negative attribution: content that was retrieved but explicitly disagreed with should not receive positive credit.

The `unclassified` value for `citation_type` indicates the agent did not classify this citation. The `unclassified` value for `position` indicates the agent did not determine the prominence of the citation. Emitters SHOULD use `unclassified` rather than forcing a classification when the agent cannot confidently determine the citation type or position.

`url_verified` indicates whether the agent confirmed that the cited URL resolves to content matching the citation. When `false` or absent, the citation may reference a hallucinated or outdated URL. `url_verified` MAY be set asynchronously after response generation. Platforms that batch-verify URLs periodically rather than per-request are conforming. A value of `false` indicates the URL was not verified, not that verification failed.

When `content_hash` is absent or does not match any grounding event's hash (for example, because the agent re-chunked content between grounding and citation), consumers SHOULD fall back to matching on `content_url` or `content_id`, accepting that the correlation may be imprecise when the same content appears in multiple grounding events.

### 6.6 Presentation data (`content_presented`)

| Field | Type | Description |
|-------|------|-------------|
| `presentation_kind` | string | What was made perceivable: `content` or `source_reference` |
| `presentation_type` | string | How it was made perceivable (see below) |
| `media_type` | string | Medium made perceivable: `text`, `image`, `video`, `audio` (open vocabulary, see 6.1). Defaults to `text` when absent. |

`presentation_kind: content` means source content itself, a bounded excerpt, or a derived representation was made perceivable. It does not claim that the whole source was reproduced. `presentation_kind: source_reference` means a credit, identifier, link, card, or other reference to the source was made perceivable. This distinction is independent of modality: a spoken credit is a source reference; played source audio is content.

#### Presentation types

| Value | Description |
|-------|-------------|
| `link` | URL link in a source list or footnote |
| `snippet` | Text snippet or preview |
| `inline_quote` | Quoted text inline in the response |
| `card` | Rich preview card (title, description, image) |
| `detail_view` | Expanded or full-content presentation within the agent's own interface |
| `embed` | Source content rendered in the response surface: an iframe, a page rendered by an agentic browser, an embedded media player |
| `spoken_credit` | Source reference spoken in an audio output or assistive surface |

`presentation_kind`, rather than `presentation_type`, determines whether the occurrence carries source content or a source reference. For example, a snippet may be an attributed source reference or an uncredited content excerpt. An embed can occur without a grounding event when the content never entered a generation context (section 4.3, *Departures from the funnel model*).

These are the core values. Platforms with additional presentation surfaces MAY use custom string values. Telemetry consumers MUST tolerate unknown `presentation_type` values.

Each presentation event MUST have an `id` and `output_id`. When it presents a citation, `citation_id` references that `content_cited` event's `id`, and the two events identify the same content; an uncited presentation omits `citation_id`. Repeated presentations of the same source or output element MUST receive distinct event IDs - event `id` values are unique within a session document. This allows a later `content_engaged.presentation_id` to identify the exact surface occurrence rather than matching only by URL.

When a session includes `content_presented` events but no subsequent `content_engaged` events, the telemetry establishes only that content or a reference was made perceivable and no reported interaction followed. It does not establish human attention. Whether this pattern is meaningful depends on the governing terms. Retrieval remains the only lifecycle stage observable from the CDN edge.

### 6.7 Engagement data (`content_engaged`)

| Field | Type | Description |
|-------|------|-------------|
| `engagement_type` | string | Type of interaction (see below) |

The content URL is identified by the event-level `content_url` field (section 5.2), not duplicated in `data`. Every agent-reported engagement MUST carry `presentation_id`, referencing the exact `content_presented.id` on which the action occurred, and identifies the same content as that presentation (section 5.7.5). Matching on URL alone is insufficient because the same source reference can be presented more than once. A destination-reported engagement carries `ctx_token` on its envelope instead: the destination cannot know the presentation UUID, and the telemetry consumer restores the binding from the token at resolution (section 7.4).

#### Engagement types

| Value | Description |
|-------|-------------|
| `link_click` | User clicked a link to the content |
| `expand` | User expanded a collapsed citation or preview |
| `copy` | User copied content text |
| `share` | User shared the content or agent response containing it |
| `agent_navigate` | User directed the agent to open or retrieve the content on their behalf |

These are the core values. Extensions MAY define additional engagement actions - commerce actions such as directing the agent to purchase a listed item belong in a commerce extension or profile (section 5.3, extension events). Telemetry consumers MUST tolerate unknown `engagement_type` values.

`agent_navigate` is the agent-mediated counterpart of a click: the user reached the source through the agent rather than through a browser. Consumers measuring traffic SHOULD count it alongside `link_click`, distinguishing the two where the commercial agreement does.

An action that touches several presentations at once - a `share` of a response containing three source cards - is one engagement occurrence per presentation shared (section 4.3), each bound to its own `presentation_id`; a surface that shares a single card reports one. An `agent_navigate` to a URL the recipient supplied, which no presentation made perceivable, is not an engagement: it begins with a `content_retrieved` event like any other fetch.

`link_click` is the primary signal for clickthrough rate calculation. Telemetry consumers can derive per-content-owner and aggregate clickthrough rates from `link_click` engagements and link presentations, joining each engagement through `presentation_id` rather than URL alone.

A `link_click` or `agent_navigate` engagement reported from the landing page after a click-out crosses a trust boundary. Such events carry a `ctx_token` in place of `session_id`, which the telemetry consumer resolves to the click context (see section 7.4). The agent-authored engagement itself reaches the engaged content's owner through owner-scoped routing whether or not the token survived the redirect chain (section 7.4.5).

## 7. Transport

Content Telemetry defines a signal format, not a wire protocol. Common delivery patterns include HTTP postback, bulk upload after session end, MCP tool calls, message queues (Kafka, SQS), and direct database writes. The choice of transport is left to implementers.

### 7.1 Delivery formats

The schema supports three delivery formats:

**Session document.** A complete session with nested events, delivered after the session ends or at periodic intervals. This is the primary format described in section 5.1 and validated by `telemetry-session.json`.

**Standalone event.** A single event with a session reference, delivered as it occurs. Suitable for streaming architectures and origin-side emitters (CDNs, origin servers) that do not have visibility into the agent's session.

**Event batch.** Multiple events sharing one session context, delivered together. The envelope carries the same fields as a standalone event, with an `events` array in place of the single `event`. Suitable for emitters that buffer events and flush periodically: edge platforms aggregating detections across requests, or SDKs batching events within a session.

A standalone event carries `document_type`, `schema_version`, and optionally `session_id` and `parent_session_id` alongside the event fields. The `document_type` field distinguishes standalone events from session documents:

```json
{
  "document_type": "event",
  "schema_version": "1.0",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": {
    "type": "content_retrieved",
    "timestamp": "2026-01-15T10:30:01Z",
    "source_role": "edge",
    "content_telemetry_id": "770e8400-e29b-41d4-a716-446655440300",
    "content_url": "https://www.ft.com/content/abc123",
    "data": {
      "bot_category": "inference",
      "cache_status": "miss",
      "response_status": 200
    }
  }
}
```

An event batch carries the same envelope fields with `"document_type": "event_batch"` and an `events` array. Envelope-level fields (`session_id`, `parent_session_id`, `ctx_token`, `agent_id`, `started_at`, `manifest_ref`) apply to every event in the batch; events belonging to different sessions MUST be delivered in separate batches or as session documents.

```json
{
  "document_type": "event_batch",
  "schema_version": "1.0",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "type": "content_retrieved",
      "timestamp": "2026-01-15T10:30:01Z",
      "source_role": "agent",
      "content_url": "https://www.ft.com/content/abc123"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440301",
      "type": "content_cited",
      "timestamp": "2026-01-15T10:30:04Z",
      "output_id": "response:1",
      "source_role": "agent",
      "content_url": "https://www.ft.com/content/abc123",
      "data": {
        "citation_type": "reference"
      }
    }
  ]
}
```

Session documents use `"document_type": "session"`. When `document_type` is absent, consumers SHOULD treat the document as a session (for backwards compatibility with pre-0.1 implementations).

For origin-side emitters at Retrieval conformance level, `session_id` MAY be omitted when the content owner has no session context. Telemetry consumers correlate these events with agent-reported sessions using the `content_telemetry_id` field.

For `content_engaged` events emitted from a landing page after a click-out (typically by a content marketplace, affiliate network, or destination site), `session_id` MAY be replaced by a `ctx_token` field that carries an opaque click token issued by the originating agent. This lets a downstream observer report a corroborating engagement event without sharing the session UUID across trust boundaries. An event MUST carry either `session_id` or `ctx_token` at Grounding conformance and above, and an envelope `ctx_token` accompanies `content_engaged` events only: an envelope carrying any other event type carries `session_id`. Token issuance, carriage, binding, resolver discovery, and the resolution response are defined in section 7.4.

The primary schema (`telemetry-session.json`) validates session documents. A standalone event envelope schema (`telemetry-event.json`) validates the event delivery format, and a batch envelope schema (`telemetry-event-batch.json`) validates the event batch format. All three schemas share the `TelemetryEvent` definition.

**Conformance constraints.** Standalone event and event batch delivery are sufficient for Retrieval conformance, where the emitter reports `content_retrieved` events with no session context. Grounding and Citation conformance require session-level fields (`session_id` or `ctx_token`, `agent_id`, `started_at`) that these envelopes do not carry by default.

An agent emitter that uses standalone events or event batches for streaming delivery and wants to achieve Grounding or Citation conformance MUST include the optional `agent_id` and `started_at` fields on the envelope. Each envelope MUST also carry `session_id`, except for click-out engagement events where `ctx_token` is used instead. Consumers reconstruct the session from the stream of envelopes sharing the same `session_id`, or resolve the owning session from `ctx_token`.

The optional `manifest_ref` field is available on standalone event and event batch envelopes, mirroring the session-level field (section 5.1.2). It identifies the emitter's manifest where no session document carries one. An event delivered standalone in support of settlement, audit or other obligations under governing terms (section 5.2.4) SHOULD carry `manifest_ref`, since it is the only envelope field that names the manifest - and so the domain - under which the emitter claims to report; verifying that claim uses the manifest mechanisms of section 8.

Origin-side emitters (source role `origin` or `edge`) are not expected to achieve Grounding conformance and do not need these fields.

Telemetry consumers MUST accept all three delivery formats, reconstructing sessions from standalone events and event batches where needed.

### 7.2 Content-Telemetry-ID header

When an AI agent fetches content over HTTP, it SHOULD include a `Content-Telemetry-ID` header containing a UUID:

```
GET /article/best-wireless-headphones HTTP/1.1
Host: www.wirecutter.com
Content-Telemetry-ID: 550e8400-e29b-41d4-a716-446655440000
```

The agent includes this same UUID as the `content_telemetry_id` field on its `content_retrieved` event. If the content owner's infrastructure (origin server, edge layer) detects the header, it includes the same UUID on its own event.

**Deduplication:**

1. Group `content_retrieved` events by `content_telemetry_id` + `content_url`
2. Multiple events in a group represent one retrieval observed by multiple parties
3. Events with no `content_telemetry_id` are standalone

The presence of the header signals that the requesting agent participates in the telemetry protocol. Its absence indicates the scraper is either unaware of the protocol or choosing not to participate. Content owners can use this distinction without blocking any traffic.

**Redirect chains:** HTTP clients typically do not forward custom headers through 301/302 redirects. When a retrieval involves redirects (e.g., from a short URL or paywall negotiation endpoint to the canonical URL), the content owner's origin or edge may not see the `Content-Telemetry-ID` header. Agents SHOULD re-attach the header on redirect requests to the same domain. For cross-domain redirects, agents MAY omit the header on the redirected request (the target domain may not be a telemetry participant). Content owners that rely on redirect-based routing SHOULD place telemetry instrumentation on the initial request handler, not only on the final origin. Content owners with redirect-based paywalls or authentication flows SHOULD instrument at the earliest point in the chain (the CDN edge, before any redirect) and SHOULD propagate the `Content-Telemetry-ID` value through their redirect chain as an internal parameter.

When the agent's reported `content_url` differs from the content owner's observed URL due to redirects, `content_id` provides a stable correlation alternative (see section 4.5).

Note: the header creates a correlation point visible to the content owner's infrastructure before the agent has decided what privacy level to share. Agents MAY limit header emission to content domains where they have a telemetry agreement.

### 7.3 Routing and aggregation

A single session typically contains events referencing content from multiple content owners. The agent cannot send the complete session to each content owner's endpoint individually - doing so would expose each content owner's content usage to the others (content owner A would see content owner B's content URLs in the same session).

Agent emitters SHOULD send session documents to a single **telemetry consumer** - an aggregation point that receives complete sessions and provides filtered views to individual content owners. The telemetry consumer resolves content owner identity from `content_url` domains (via verified domain registrations) and exposes only the events relevant to each content owner.

Two deployment patterns are common:

| Pattern | Operator | Description |
|---------|----------|-------------|
| **Platform-hosted** | Agent operator | The agent operator runs their own compatible consumer and sends filtered reports to content owners under licensing agreements. |
| **Marketplace-hosted** | Licensing intermediary | A content marketplace aggregates telemetry for its catalogue of content owners and provides per-content-owner dashboards and royalty data. |

Any party may operate a consumer: an agent operator, a licensing intermediary, or an independent third party offering it as a service. Both patterns above consume the same session format. The telemetry consumer is responsible for domain resolution, content owner filtering, and access control. The spec does not mandate a specific aggregation topology, nor does it require any particular operator to provide one.

**Origin-side `.well-known/content-telemetry.json` manifests** declare where origin-emitted retrieval events are sent (CDN → content owner's chosen endpoint). They do not instruct agents where to send session documents. Agent routing is governed by the agent's telemetry configuration, not by content owner manifests.

**Content owner resolution.** Telemetry consumers resolve content owner identity from `content_url` domains. Content owners register and verify their domains with the telemetry consumer; the consumer maps incoming event URLs to the owning organisation. This is the primary resolution path and requires `content_url` to be present on events. Events identified only by `content_id` (e.g., cached groundings where the URL was not preserved, or marketplace API content with no canonical URL) cannot be resolved by domain alone. Telemetry consumers SHOULD support `content_id` prefix-based resolution as a secondary path when content owners register their identifier schemes, but this is not yet a normative requirement.

**Cross-consumer correlation.** Origin-side emitters and agent-side emitters MAY use different telemetry consumers. A content owner's CDN sends retrieval events to one telemetry consumer; an agent sends sessions to another. The `content_telemetry_id` field (section 7.2) correlates the same retrieval across consumers - both sides share the same UUID from the HTTP request. This correlation operates at the retrieval level only. Grounding, citation, presentation, and engagement events have no independent origin-side counterpart to correlate against.

### 7.4 Click context (`ctx_token`)

A click-out is the moment content usage becomes traffic the destination can observe. The click token lets the destination corroborate that moment and learn what produced it, without receiving the session UUID or any other publisher's activity.

#### 7.4.1 Token issuance

A `ctx_token` is an opaque token minted by the originating agent. Its value MUST match `^ct_[A-Za-z0-9_-]{16,240}$`, MUST be unguessable - the suffix is drawn from at least 96 bits of cryptographically secure randomness, or is a keyed construction of equivalent strength, so that holding one token gives no way to derive or enumerate another - and MUST NOT encode content, session, or user identifiers recoverable without the issuer's state.

A token MUST be bound to exactly one `content_presented` occurrence at mint time. The same URL presented twice receives two tokens; a token observed on two presentations is malformed issuance and consumers MUST NOT resolve it. Surfaces that route outbound navigation through the agent SHOULD mint per click, additionally binding the token to the resulting `content_engaged` event. Direct-link surfaces mint per presentation; repeated clicks on one presentation then share a token, and are distinguished at resolution by the destination's event timestamps.

The token-to-presentation binding is issuer state. It never travels in the URL: destinations do not receive `presentation_id`, and the consumer restores the binding at resolution. The agent SHOULD record the minted token on its own `content_engaged` event (the event-level `ctx_token` field) so the consumer can join destination reports to it.

#### 7.4.2 Carriage and redirects

Agents that decorate outbound link URLs MUST use the reserved query parameters `ctx_token` (the token) and `ctx_iss` (the issuer locator, section 7.4.3), and MUST NOT place other telemetry data in the URL.

Parties operating redirects SHOULD propagate both parameters through same-domain redirect hops, mirroring the `Content-Telemetry-ID` redirect guidance in section 7.2. Destinations relying on redirect-based routing SHOULD capture the parameters at the earliest point in the chain. This is a transport and correlation convention: it does not claim that every intermediary preserved the value, and it does not enforce downstream behaviour.

#### 7.4.3 Resolver discovery

`ctx_iss` carries the issuer manifest locator: a host, optionally with a path prefix, identifying a well-known manifest location (section 8.1). `ctx_iss=example.com/agents/search` resolves to `https://example.com/agents/search/.well-known/content-telemetry.json`. That manifest declares the resolution endpoint in `telemetry.ctx_resolution` (section 8.5).

The token stays opaque and carries no routing; the locator travels alongside it. No central registry is required or defined.

#### 7.4.4 Resolution response - the click context

A telemetry consumer that supports resolution exposes, for a presented token, the **click context**:

1. **The engagement.** The `content_engaged` occurrence(s) bound to the token, including the presentation record the token restores: `presentation_id`, `output_id`, `output_element_id` where present, and timestamps.
2. **The lineage of the clicked content, selected by content identity.** The resolved session's `content_retrieved`, `content_grounded`, `content_cited`, and `content_presented` events whose `content_url` or `content_id` identify the same content as the clicked reference - across all turns. The cut is by content identity, not by turn or click timestamp: a click in turn 5 on content grounded in turn 2 resolves that content's full lineage.
3. **The contributing sources, gated per owner.** The sources that informed the response the click came from: `content_grounded` events in scope for the engaged presentation's turn (including session-scoped groundings) and that turn's `content_cited` and `content_presented` events, for content other than the clicked content. A contributing owner's events appear only when that owner has opted in to contributing-source disclosure with the resolving consumer; owners without a recorded opt-in are visible only through the counts in the session summary. This is the component that supports multi-citation attribution when the clicked content is not the contributing content - a click through to a commerce destination whose recommendation a publisher's review produced - and it restores the consent-gated role of the v0.1 click manifest (section 12.1), scoped to the click's provenance rather than the whole session.
4. **An optional privacy-bounded session summary.** Event counts by type and a distinct-source count. Counts, not events, and no content identifiers of owners not disclosed above.

A resolution response MUST NOT include the resolved session's raw `session_id`: the token exists so the session UUID never crosses the trust boundary. Outside the contributing-source component, a resolution response MUST NOT include events for content other than the clicked content; within it, a response MUST NOT include events for an owner without a recorded contributing-source opt-in. Whole-session cross-content detail remains a reporting concern, delivered through publisher-filtered views (section 7.3), not through per-click resolution. A consumer MUST resolve a token only when the issuing agent has opted in to click-token resolution. The response is further gated by the `privacy_level` of the turn the engaged presentation belongs to - the turn named by the presentation's `turn_id`, or the turn in progress at its timestamp: at `minimal` the consumer returns the engagement and the lineage (components 1 and 2) only, withholding the contributing-source component and the session summary; at `intent` and above all four components are available. A resolution response never carries conversation-turn fields at any level. The mechanisms by which the issuer and contributing-owner opt-ins are recorded are operator-defined; all three gates are normative.

A worked resolution response (informative):

```
{
  "engagement": {
    "engagement_type": "link_click",
    "timestamp": "2026-08-10T09:02:31Z",
    "presentation_id": "880e8400-e29b-41d4-a716-446655440213",
    "output_id": "response:2"
  },
  "lineage": [
    { "type": "content_grounded", "timestamp": "2026-08-10T09:00:01Z", "turn_id": "1", "data": { "chars_ingested": 9400 } },
    { "type": "content_cited", "timestamp": "2026-08-10T09:00:04Z", "turn_id": "1", "data": { "citation_type": "paraphrase", "position": "primary" } },
    { "type": "content_presented", "timestamp": "2026-08-10T09:00:04Z", "turn_id": "1", "data": { "presentation_kind": "source_reference", "presentation_type": "link" } },
    { "type": "content_presented", "timestamp": "2026-08-10T09:02:10Z", "turn_id": "2", "data": { "presentation_kind": "source_reference", "presentation_type": "link" } }
  ],
  "contributing_sources": [
    {
      "content_url": "https://publisher-a.example/heaters/space-heater-review",
      "events": [
        { "type": "content_grounded", "timestamp": "2026-08-10T09:02:08Z", "turn_id": "2", "data": { "chars_ingested": 7200 } },
        { "type": "content_cited", "timestamp": "2026-08-10T09:02:10Z", "turn_id": "2", "data": { "citation_type": "paraphrase", "position": "primary" } }
      ]
    }
  ],
  "session_summary": { "turns": 2, "distinct_sources": 3, "events_by_type": { "content_grounded": 4, "content_cited": 3, "content_presented": 5 } }
}
```

The response shape above is informative in v1; the constraints in this section are normative. A response schema can follow implementation evidence during the release-candidate window.

#### 7.4.5 Owner-scoped delivery of the engagement

The agent-authored click `content_engaged` is a session event like any other: it reaches content owners through routing and aggregation (section 7.3), independent of whether the token in the URL survived the redirect chain. A telemetry consumer that provides owner-filtered views MUST include the agent-authored `content_engaged` event in the filtered view of the engaged content's owner, on the same terms as `content_grounded` and `content_cited` events - including the session identifier that owner-scoped delivery carries. The `session_id` prohibition in section 7.4.4 binds token resolution, where the requesting party is authenticated by nothing more than possession of a URL-carried value; it does not bind section 7.3 delivery to an owner whose domain registration the consumer has verified.

This delivery is deliberately redundant with the token path. It notifies the destination owner of the click even when `ctx_token` was stripped in transit; it lets that owner join the click to their own grounded and cited events on `session_id` without calling a resolver; and it lets a party processing owner-scoped streams for both a contributing publisher and a click destination match its clients' events on `session_id` for attribution. The owner's filtered view SHOULD carry the event-level `ctx_token`, so a destination that captured the query parameters at landing can join the URL-channel observation to the server-side event directly. This is not token distribution to contributing owners (the limit recorded in section 7.4.6): only the owner of the clicked content receives the event, and that owner already saw the token in the URL. Where the clicked content's owner is also the destination, that owner therefore holds both the token from the URL and the session identifier from this delivery: the boundary of section 7.4.4 protects sessions from unregistered holders of a URL, not from the verified owner of the content that was clicked.

#### 7.4.6 Recorded limit: consumer custody

Resolution depends on the telemetry consumer the agent chose, because that consumer holds the session. Grounding and citation events precede the click and cannot carry its later token, and distributing tokens to every contributing content owner after the fact would weaken the privacy boundary this section maintains. Publisher-derived tokens would require a federation and key-management design; that belongs in a later attribution or evidence profile. Core v1 mitigates the dependency with resolver discoverability (7.4.3) and exact click binding (7.4.1).

Token lifetime and requester authentication are likewise not defined in v1: a token resolves for as long as the consumer retains the session, and the resolver authenticates the requester by possession of the token alone (section 7.4.5). A resolution window after issuance, and requester credentials - for example authenticating a destination against the manifest its domain serves (section 8) - belong to the evidence profile, together with the federation design above.

## 8. Manifest

Content owners, agents, and platforms publish a manifest declaring their identity and telemetry endpoints. The `manifest_ref` field on session documents (5.1.2) and the routing logic for origin-side emitters (7.3) resolve to manifests defined in this section.

### 8.1 Discovery

Manifests are served as JSON at:

```
https://<domain>/.well-known/content-telemetry.json
```

A domain MAY publish additional manifests under path prefixes for agents or platform services it operates:

```
https://example.com/.well-known/content-telemetry.json                # domain manifest
https://example.com/agents/search/.well-known/content-telemetry.json  # operated agent
```

Each manifest is self-contained at its own well-known URL.

Trust derives from TLS and DNS control of the domain. Manifests are unsigned in v1 (section 8.9).

### 8.2 Schema

Machine-readable schema: [`./manifest.json`](./manifest.json) (JSON Schema draft 2020-12).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Manifest schema version. v1 emitters MUST use `"1.0"`. |
| `id` | string | Yes | The manifest's canonical `https://` URL, ending in `/.well-known/content-telemetry.json` (e.g. `https://example.com/.well-known/content-telemetry.json`); the schema rejects other schemes and locations (section 8.1). |
| `roles` | string[] | Yes | One or more of `content_owner`, `agent`, `platform`. |
| `operator` | object | Yes | Operating organisation (see 8.3). |
| `keys` | object[] | No | Public keys for signing telemetry events (see 8.4). |
| `telemetry` | object | No | Telemetry endpoint declaration (see 8.5). |
| `domains` | string[] | No | Domains the participant claims authority over (see 8.6). MAY appear only on root manifests. |

Consumers MUST tolerate unknown fields and treat absent optional sections as "not declared" rather than rejecting the manifest.

A manifest MAY declare multiple roles (e.g. `["content_owner", "agent"]`). A more common pattern for an organisation acting in multiple roles is two separate manifests on the same domain - one at the root for the content owner role, one under a path prefix for an operated agent - each with its own `telemetry.endpoint`.

### 8.3 Operator

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name of the operating organisation. |
| `domain` | string | No | Primary domain. Defaults to the manifest URL's host. |

### 8.4 Keys

Public keys used to sign telemetry events emitted by this participant. Per-event signing remains informational in v1; consumers MAY verify signatures but are not required to.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Key identifier, unique within the manifest. |
| `type` | string | Yes | Key type. v1 defines `Ed25519` only. |
| `publicKey` | string | Yes | Multibase-encoded public key (multicodec prefix, base58btc - the same format as `did:key`). |
| `expires` | datetime | No | ISO 8601 expiry. |

### 8.5 Telemetry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint` | string | Yes | HTTPS URL (schema-enforced). For agents and platforms, the outbound submission endpoint. For content owners, the inbound destination for events about the content owner's content. |
| `conformance_level` | string | No | Conformance level advertised by this participant's own emitter(s). One of `retrieval`, `grounding`, `citation` (see 5.7). |
| `ctx_resolution` | string | No | HTTPS URL of the click-token resolution endpoint operated by or for this participant (see 7.4). Valid on `agent` and `platform` manifests. |
| `coverage` | object | No | Per-event-type coverage declaration: a map from event type to `{ "mode": …, "terms_ref": … }`, where `mode` is one of `complete`, `sampled`, `aggregated`, `selected` (see 5.7.6) and `terms_ref` optionally names the terms stating the rule or condition. |

`coverage` makes the emitter's declared coverage machine-visible. It is a claim like the rest of the manifest, subject to the rules of section 5.7.6: a `complete` entry asserts that every qualifying occurrence of that event type within the declared relationship scope is emitted, and the other modes are meaningful only with their rule or condition reachable through `terms_ref` or otherwise disclosed to the receiving party.

`conformance_level` is informational. It advertises the level of telemetry the manifest's participant emits. It does **not** constrain what an inbound `endpoint` accepts - an endpoint accepts whatever events it is configured to accept, regardless of any level declared here - and it places **no requirement** on other emitters. On a `content_owner` manifest it describes only the events the owner's own infrastructure emits (typically a CDN edge worker at `retrieval`); it says nothing about what agents or platforms report about the owner's content, which those parties advertise in their own manifests. A `content_owner` manifest SHOULD omit `conformance_level` unless the owner operates its own emitter. There is no field for a content owner to *request* a minimum level from agents; consumers tolerate events from any level (see 5.7), and the protocol does not give a manifest a way to demand more.

### 8.6 Domains

The `domains` array MAY appear only on manifests served from the domain root (`https://<domain>/.well-known/content-telemetry.json`). Manifests under path prefixes MUST NOT include `domains`.

In v1, every entry in `domains` MUST be self-validating: either the manifest's own host, or a subdomain of it (literal `news.example.com` or wildcard `*.example.com`). Control of the apex - proven by serving the manifest at the apex over TLS - implies DNS control of subdomains, so no further validation is needed. A manifest containing entries that are not subdomains of its own host is malformed.

This keeps the v1 protocol fully decentralised: every manifest is a self-contained credential, validated by TLS plus the well-known location, with no dependency on consumer-side validation state or any external registry. Cross-apex claims (one operator unifying several unrelated apex domains in a single manifest) are deferred to a later version.

### 8.7 Consumer behaviour

When resolving a manifest from `manifest_ref`, a `content_url` domain, or any other reference:

- **404 or network error.** Treat the participant as unverified. Do not reject telemetry events on this basis alone.
- **Invalid JSON or schema validation failure.** Reject the manifest. Treat the participant as unverified.
- **Unknown `schema_version`.** Manifests follow the same rule as telemetry documents (section 5.7.4): accept any `1.x` the consumer implements, validating against that minor's schema, and reject `0.x` manifests. During the v0.x preview period consumers accepted only the exact same minor version.
- **Duplicate `keys[].id`.** Reject the manifest.
- **`domains` entry that is not the manifest's host or a subdomain of it.** Reject the manifest as malformed (see 8.6).
- **Missing `keys` on a manifest referenced by `manifest_ref`.** Not an error in v1, since signing is informational.

Consumers SHOULD cache resolved manifests respecting the response's `Cache-Control` headers. Manifest hosts SHOULD set `Cache-Control: max-age=3600` during onboarding and `max-age=86400` steady-state.

### 8.8 Examples

**Content owner.**

```json
{
  "schema_version": "1.0",
  "id": "https://example.com/.well-known/content-telemetry.json",
  "roles": ["content_owner"],
  "operator": { "name": "Example Media" },
  "telemetry": {
    "endpoint": "https://telemetry.example.com/v1/events"
  },
  "domains": ["example.com", "*.example.com"]
}
```

**Agent.**

```json
{
  "schema_version": "1.0",
  "id": "https://searchco.com/agents/web-search/.well-known/content-telemetry.json",
  "roles": ["agent"],
  "operator": { "name": "SearchCo" },
  "keys": [
    { "id": "key-1", "type": "Ed25519", "publicKey": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK" }
  ],
  "telemetry": {
    "endpoint": "https://telemetry.example.com/v1/events",
    "conformance_level": "grounding"
  }
}
```

**Mixed-role organisation - two manifests on one domain.** A content owner operating its own AI assistant publishes one manifest at the domain root for content ownership and a second under a path prefix for the agent it operates:

```json
// https://publisher.com/.well-known/content-telemetry.json
{
  "schema_version": "1.0",
  "id": "https://publisher.com/.well-known/content-telemetry.json",
  "roles": ["content_owner"],
  "operator": { "name": "Publisher Co" },
  "telemetry": {
    "endpoint": "https://telemetry.example.com/v1/events"
  },
  "domains": ["publisher.com"]
}
```

```json
// https://publisher.com/agents/assistant/.well-known/content-telemetry.json
{
  "schema_version": "1.0",
  "id": "https://publisher.com/agents/assistant/.well-known/content-telemetry.json",
  "roles": ["agent"],
  "operator": { "name": "Publisher Co" },
  "keys": [
    { "id": "key-1", "type": "Ed25519", "publicKey": "z6Mk..." }
  ],
  "telemetry": {
    "endpoint": "https://telemetry.example.com/v1/events",
    "conformance_level": "grounding"
  }
}
```

The two manifests live independently at distinct well-known URLs. The content-owner manifest's `domains` and `telemetry` apply to publisher.com's content; the agent manifest's `keys` and `telemetry` apply to events emitted by the assistant.

### 8.9 Out of scope for v1

The following are deferred to later versions:

- Content licence declarations (what content the participant is licensed to access)
- Manifest signing (W3C Verifiable Credentials, JWS proofs)
- Training data and model provenance
- Deployment context, purpose, brand affiliation
- Revocation registries
- Key rotation procedures beyond the `expires` field
- `did:web` compatibility (the `id` field uses the manifest URL in v1)
- Cross-apex claims (one operator unifying several unrelated apex domains in a single manifest)

---

## 9. Privacy

### 9.1 Data minimisation

Emitters SHOULD:

- Use the minimum `privacy_level` necessary
- Use coarse `topics` values that do not identify sensitive categories (health, political or religious affiliation, sexuality)
- Carry network-level context about the request rather than about the client: `asn`, `asn_org` and `country` describe the network path and do not identify the individual behind it

Hashing does not anonymise a value drawn from a space small enough to enumerate. The entire IPv4 address space can be hashed and compared against a candidate digest on commodity hardware, so a hashed IP address is a pseudonym rather than an anonymous value and should be treated as personal data. Version 0.1 defined an `ip_hash` field in the edge and origin data profiles (sections 6.2 and 6.3). Version 1 withdraws it, and emitters MUST NOT populate it.

The schemas cannot enforce this v1 migration rule: event `data` accepts additional properties by design, so `ip_hash` would otherwise validate as an ordinary extension. The conformance suite therefore checks this specific prohibition at the application layer. This does not establish a general registry of withdrawn extension names.

`privacy_level` gates the named conversation-turn fields of section 5.5 and nothing else. Extension fields in `turn` or `data`, content identifiers and URLs, `license_ref`, `terms_ref`, `output_id`, `turn_id` and every other opaque string pass through at every level, so their contents are the emitter's responsibility: an emitter MUST NOT use them to carry the end user's identity, or the query and response text that the declared level withholds, and SHOULD apply the minimisation guidance above to them as it does to the named fields.

### 9.2 Recommended levels

| Scenario | Recommended level |
|----------|-------------------|
| First-party analytics | `full` |
| Trusted partner | `summary` or `intent` |
| Third-party attribution | `intent` or `minimal` |
| Public benchmarking | `minimal` |

These recommendations are informative. This specification defines the privacy-level mechanism - the `privacy_level` field, the four levels, and the fields each permits (section 5.5) - but does not make any level binding for a given relationship. A binding privacy floor for a community or accreditation programme is set by a profile layered on this specification (see GOVERNANCE.md), not by this section.

### 9.3 Retention

This specification does not mandate retention periods. Consumers SHOULD document their retention policies.

## 10. Attribution

Content Telemetry provides the telemetry data needed for attribution but does not mandate specific algorithms. Common approaches:

- **Last-touch** - credit to last content before session end
- **First-touch** - credit to first content in session
- **Linear** - equal credit to all content
- **Position-based** - weighted by position in the session
- **SHAP-based** - game-theoretic contribution scores

### 10.1 Counting semantics

The schema records discrete events. A `content_grounded` event represents content entering the agent's context. A `content_cited` event represents content being explicitly referenced in a response. These are independent signals.

A session where one article is grounded with session scope, the user asks ten questions, and the article is cited three times produces:

- 1 `content_grounded` event
- 10 `turn_completed` events
- 3 `content_cited` events

Whether this constitutes one royalty event, three, or ten depends on the commercial agreement. The schema provides the raw signals; telemetry consumers choose the counting model.

| Counting model | Counts | Suited for |
|----------------|--------|-----------|
| Per-grounding | One event per article entering context per session | Access-based or flat-fee licensing ("you used our content") |
| Per-citation | One event per explicit reference in a response | Performance-based licensing ("you cited our content") |
| Per-turn-influenced | One event per turn where content was in context | Usage-based licensing ("our content informed N answers") |

The `content_grounded` event with `scope: session` plus the count of subsequent `turn_completed` events provides the inputs for all three models without requiring the schema to embed a commercial opinion.

### 10.2 Grounding without citation

Content can influence every response in a session without being explicitly cited. A common royalty formula (individual content owner usage / total content owner usage x royalty rate) can be applied at any level of the funnel:

- At the **grounding** level: counts all content that was in the agent's context, regardless of citation. This captures the full extent of content influence, including silent grounding.
- At the **citation** level: counts only explicitly attributed content. Simpler to verify but undercounts content influence.
- At the **presentation** level: counts content or source references made perceivable. It does not prove attention.

Content owners and platforms should agree on which level to count at. The telemetry data supports all three; the choice is commercial, not technical.

## 11. Extensibility

### 11.1 Custom event metadata

Implementations MAY extend core event types with custom fields in the `data` object:

```json
{
  "type": "content_engaged",
  "data": {
    "engagement_type": "link_click",
    "custom_event_subtype": "video_watched",
    "watch_duration_seconds": 45
  }
}
```

New event types (e.g., a commerce extension's `checkout_completed`) require a schema extension. The core schema validates only the event types listed in section 5.3.

Sessions carry a parallel extension container: the session-level `data` object (section 5.1.3). Session-scoped extension metadata belongs there, not in custom top-level fields on the session document.

### 11.2 Custom intent categories

`query_intent` accepts custom string values beyond the core set. Extensions SHOULD namespace their values to avoid collisions (e.g., `price_check` for a commerce extension). For ad-hoc categories that don't warrant a formal extension, use `other` with details in `topics`.

Telemetry consumers MUST tolerate unknown `query_intent` values.

Extension example:

```json
{
  "query_intent": "price_check"
}
```

Fallback example using `other`:

```json
{
  "query_intent": "other",
  "topics": ["legal_advice", "contract_review"]
}
```

### 11.3 Custom response modes

`response_mode` accepts custom string values beyond the recommended set:

```json
{
  "type": "turn_completed",
  "turn": {
    "response_mode": "podcast_generation"
  }
}
```

Telemetry consumers MUST tolerate unknown `response_mode` values.

## 12. Versioning

### 12.1 Migration from the v0.1 preview

V1 documents declare `schema_version` `"1.0"`, and the schemas' `$id` URLs move
from `/schema/v0.1/` to `/schema/v1/`. The two versions are distinguishable on
the wire and do not interoperate: a v0.1 consumer, applying the preview rule of
section 5.7.4, rejects a document declaring `"1.0"`, and a v1 consumer rejects a
document declaring `"0.1"`. An emitter moves to v1 by declaring `"1.0"` on
documents that satisfy this section; it MUST NOT declare `"0.1"` on a document
using v1 event types or fields.

V1 replaces `content_displayed` with `content_presented`; emitters MUST NOT send
the old event name on the v1 integration line. Rename `data.display_type` to
`data.presentation_type` and add `data.presentation_kind` with either `content`
or `source_reference`. This is an intentional pre-1.0 breaking change: merely
renaming the event would preserve the visual-only ambiguity and would not say
what crossed the presentation boundary.

For every `content_cited` event, assign an event `id` and `output_id`. For every
`content_presented` event, assign a distinct event `id` and the `output_id` of the
artifact made perceivable; add `output_element_id` when a stable element identity
exists and `citation_id` when the presentation carries a citation. For every
`content_engaged` event, add `presentation_id` referencing the exact presentation
event. Do not migrate clicks by matching URL alone: repeated presentations of the
same URL are distinct occurrences.

V1 requires `data.citation_type` on every `content_cited` event and `data.scope`
on every `content_grounded` event; both are schema-enforced. A v0.1 emitter that
omitted them migrates a citation it cannot classify with `citation_type:
unclassified`, and a grounding whose scope it did not record with `scope: turn`
where the event carries a `turn_id` and `scope: session` otherwise. V1 also
rejects a `content_cited` event whose `content_url` and `content_id` are both
absent or null (section 6.5): a v0.1 citation with no resolvable reference is
not migrated as a citation.

V1 withdraws `ip_hash` from the edge and origin retrieval profiles (section 9.1).
Emitters remove the field and MUST NOT populate it; `asn`, `asn_org` and `country`
remain. V1 also requires `source_role` on every `content_retrieved` event
(section 5.7.1); preview emitters that omitted it add the role they report under.

`license_ref` keeps its wire form but no longer asserts that the use was licensed
(section 5.2.3): a consumer that read a v0.1 `license_ref` as verification of
entitlement now reads it as the emitter's claim about which grant applied.

V1 grounding fingerprints report detection only. The published v0.1 preview
defined no `content_fingerprint` object; the object, and a
`preserved_in_output` field within it, appeared only on the pre-release
`v1-draft` line, which also carried a `content_reproduced` event type that is
not part of v1. An implementation built against that draft removes
`preserved_in_output` and any `content_reproduced` events during migration;
v1 defines no output-side reuse reporting. A grounding event MAY retain
`content_fingerprint.scheme`, `detected`, and a scheme-defined `value`.

V1 narrows `ctx_token` resolution. The v0.1 click manifest returned every
source that informed the resolved session, gated by per-owner opt-in; the v1
click context (section 7.4) returns the engagement, the clicked content's
lineage by content identity, a contributing-source set under the same
per-owner opt-in gate - scoped to the turn the click came from rather than
the whole session - and at most a count-based session summary. Consumers
implementing v0.1 resolution narrow the contributing-source scope accordingly
and MUST NOT return events for owners without a recorded opt-in. Token values
gain the `ct_` pattern and the unguessability rule of section 7.4.1. The binding
from a token to the presentation it was minted for is issuer state: v0.1 defined
no `presentation_id`, and v1 never places one in a URL; a destination reports
the token, and the consumer restores the binding at resolution.

V1 tightens occurrence boundaries (section 4.3). Each core event now has a stated occurrence and cardinality: retrieval per completed fetch (a cache serve is not a retrieval), grounding per distinct content item per declared scope (chunk-level events deduplicate to one occurrence by content identity), citation per source-to-element association, presentation per rendering occurrence, engagement per observed action. Preview emitters that emitted per chunk, per passage, or re-emitted `content_retrieved` on cache serves remain schema-valid but SHOULD re-map to the stated boundaries; consumers comparing preview and v1 volumes should expect counts to shift where emitters previously chose finer or coarser units. Coverage becomes an explicit declaration (section 5.7.6) rather than an implication of conformance level. Session-scoped extension metadata belongs in the session-level `data` container (section 5.1.3); custom top-level siblings of `events`, accepted by the preview schema, are undefined.

Version numbers are `major.minor`, and a document declares the version it was produced under in `schema_version`. From 1.0 onward:

- **Major** (1.0 → 2.0) - breaking changes to required fields or to the meaning of an event
- **Minor** (1.0 → 1.1) - new optional fields and new event types; each minor version publishes its own schemas
- **Patch** - clarifications and errata to prose, examples and fixtures that change no field or constraint; a patch does not change `schema_version`

From 1.0 onward, consumers accept documents with any compatible minor version (same major version) as described in section 5.7.4. During the preview period (0.x) the stricter rule applied: a consumer accepted only the exact same minor version (a 0.1 consumer accepts 0.1 only).

## Annex A (normative): JSON Schema

See `telemetry-session.json` for the formal JSON Schema definition.

## Annex B (informative): Examples

### B.1 User-to-agent session with grounding

A user asks a shopping assistant to compare noise-cancelling headphones. The agent retrieves a review, grounds it, cites it, and the user clicks through. This demonstrates the full funnel from retrieval to engagement.

```json
{
  "schema_version": "1.0",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "shopping-assistant-v2",
  "content_scope": "electronics-reviews",
  "manifest_ref": "https://retailer.example.com/.well-known/content-telemetry.json",
  "started_at": "2026-01-15T10:30:00Z",
  "ended_at": "2026-01-15T10:35:00Z",
  "events": [
    {
      "type": "turn_started",
      "timestamp": "2026-01-15T10:30:00Z",
      "turn_id": "1",
      "turn": {
        "privacy_level": "intent",
        "query_intent": "comparison",
        "topics": ["headphones", "noise-cancelling"],
        "query_tokens": 15
      }
    },
    {
      "type": "content_retrieved",
      "timestamp": "2026-01-15T10:30:01Z",
      "source_role": "agent",
      "content_telemetry_id": "770e8400-e29b-41d4-a716-446655440300",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones"
    },
    {
      "type": "content_grounded",
      "timestamp": "2026-01-15T10:30:01Z",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "scope": "session",
        "cached": false,
        "chars_ingested": 16800,
        "tokens_ingested": 4200,
        "content_last_modified": "2026-01-10T14:00:00Z",
        "media_type": "text"
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440302",
      "type": "content_cited",
      "timestamp": "2026-01-15T10:30:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:recommendation:1",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "citation_type": "paraphrase",
        "excerpt_tokens": 85,
        "position": "primary"
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440303",
      "type": "content_presented",
      "timestamp": "2026-01-15T10:30:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:recommendation:1",
      "citation_id": "770e8400-e29b-41d4-a716-446655440302",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "presentation_kind": "source_reference",
        "presentation_type": "link"
      }
    },
    {
      "type": "turn_completed",
      "timestamp": "2026-01-15T10:30:05Z",
      "turn_id": "1",
      "turn": {
        "privacy_level": "intent",
        "query_intent": "comparison",
        "response_type": "recommendation",
        "response_mode": "standard",
        "topics": ["headphones", "Sony WH-1000XM5", "Bose QC45"],
        "content_urls_retrieved": [
          "https://www.wirecutter.com/reviews/best-wireless-headphones"
        ],
        "content_urls_cited": [
          "https://www.wirecutter.com/reviews/best-wireless-headphones"
        ],
        "response_tokens": 150
      }
    },
    {
      "type": "content_engaged",
      "timestamp": "2026-01-15T10:32:00Z",
      "turn_id": "1",
      "presentation_id": "770e8400-e29b-41d4-a716-446655440303",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "engagement_type": "link_click"
      }
    }
  ]
}
```

### B.2 Edge-reported retrieval with correlation

A content owner's CDN detects an AI agent fetching content. The agent also reports the retrieval. Both events share the same `content_telemetry_id`.

**Agent's event:**

```json
{
  "type": "content_retrieved",
  "timestamp": "2026-01-15T10:30:01Z",
  "source_role": "agent",
  "content_telemetry_id": "770e8400-e29b-41d4-a716-446655440300",
  "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones"
}
```

**Edge event** (reported by the CDN):

```json
{
  "type": "content_retrieved",
  "timestamp": "2026-01-15T10:30:01Z",
  "source_role": "edge",
  "content_telemetry_id": "770e8400-e29b-41d4-a716-446655440300",
  "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
  "data": {
    "user_agent": "ClaudeBot/1.0",
    "bot_category": "inference",
    "bot_name": "ClaudeBot",
    "verified": true,
    "cache_status": "miss",
    "response_status": 200,
    "response_bytes": 48230,
    "ja4": "t13d1517h2_8daaf6152771_02e4c6ae3e16",
    "asn": 14618,
    "asn_org": "Anthropic",
    "country": "US"
  }
}
```

These share `content_telemetry_id` and `content_url`, representing one corroborated retrieval from two observers.

### B.3 Cached grounding

An AI agent previously fetched an FT article and cached it. In a new session, the cached article is loaded into context and influences multiple turns. The user never clicks through to the source.

```json
{
  "schema_version": "1.0",
  "session_id": "660e8400-e29b-41d4-a716-446655440000",
  "agent_id": "copilot-v3",
  "started_at": "2026-03-28T09:00:00Z",
  "ended_at": "2026-03-28T09:08:00Z",
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
        "content_last_modified": "2026-03-27T18:30:00Z",
        "content_hash": "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "media_type": "text"
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
      "id": "770e8400-e29b-41d4-a716-446655440304",
      "type": "content_cited",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:paragraph:2",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "citation_type": "paraphrase",
        "excerpt_tokens": 95,
        "excerpt_chars": 412,
        "position": "primary",
        "url_verified": true
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440305",
      "type": "content_presented",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:paragraph:2",
      "citation_id": "770e8400-e29b-41d4-a716-446655440304",
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
        "response_type": "explanation",
        "response_mode": "standard",
        "content_urls_cited": ["https://www.ft.com/content/abc123"],
        "response_tokens": 280,
        "ad_rendered": true
      }
    },
    {
      "type": "turn_started",
      "timestamp": "2026-03-28T09:01:00Z",
      "turn_id": "2",
      "turn": {
        "privacy_level": "intent",
        "query_intent": "question",
        "topics": ["Bank of England", "monetary policy"]
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440306",
      "type": "content_cited",
      "timestamp": "2026-03-28T09:01:08Z",
      "turn_id": "2",
      "output_id": "response:2",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "citation_type": "reference",
        "position": "supporting"
      }
    },
    {
      "type": "turn_completed",
      "timestamp": "2026-03-28T09:01:08Z",
      "turn_id": "2",
      "turn": {
        "privacy_level": "intent",
        "response_type": "explanation",
        "response_mode": "standard",
        "content_urls_cited": ["https://www.ft.com/content/abc123"],
        "response_tokens": 340
      }
    },
    {
      "type": "turn_started",
      "timestamp": "2026-03-28T09:03:00Z",
      "turn_id": "3",
      "turn": {
        "privacy_level": "intent",
        "query_intent": "question",
        "topics": ["housing market"]
      }
    },
    {
      "type": "turn_completed",
      "timestamp": "2026-03-28T09:03:06Z",
      "turn_id": "3",
      "turn": {
        "privacy_level": "intent",
        "response_type": "explanation",
        "response_mode": "standard",
        "response_tokens": 200
      }
    }
  ]
}
```

In this session:

- 1 article grounded from cache (no `content_retrieved` event - the CDN saw nothing)
- 3 turns of conversation
- 2 explicit citations (turns 1 and 2)
- 1 presentation event (link made perceivable in turn 1)
- 0 engagement events (no click-through was reported)
- Advertising was rendered alongside the first response

The content owner can derive: article `ft:abc123` was in context for all turns, cited twice, presented once, and had no reported engagement. The content was 14.5 hours old (cached from previous day). The response was monetised with advertising.

### B.4 Minimal privacy level

The same turn from B.3 at `minimal` privacy. No intent, no topics, no platform metadata - only token counts and content URLs.

```json
{
  "type": "turn_completed",
  "timestamp": "2026-03-28T09:00:05Z",
  "turn_id": "1",
  "turn": {
    "privacy_level": "minimal",
    "content_urls_cited": ["https://www.ft.com/content/abc123"],
    "response_tokens": 280
  }
}
```

Compare with the `intent` version in B.3: `query_intent`, `topics`, `response_type`, `response_mode`, and `ad_rendered` are all absent.

### B.5 Multi-owner catalogue under one agreement

A marketplace intermediary delivers content from many publishers under a single agreement. `content_scope` identifies the agreement, and is the same for every session reported under it; content owner resolution is per event, from each event's `content_url` domain or registered `content_id` prefix (section 7.3). One session, two owners, each event resolving to its own owner.

```json
{
  "schema_version": "1.0",
  "session_id": "990e8400-e29b-41d4-a716-446655440500",
  "agent_id": "research-assistant-v5",
  "content_scope": "marketplace-agreement-2026-017",
  "manifest_ref": "https://assistant.example.com/.well-known/content-telemetry.json",
  "started_at": "2026-08-20T09:00:00Z",
  "ended_at": "2026-08-20T09:00:09Z",
  "events": [
    {
      "type": "turn_started",
      "timestamp": "2026-08-20T09:00:00Z",
      "turn_id": "1",
      "turn": { "privacy_level": "intent", "query_intent": "comparison", "topics": ["electric vehicles", "charging"] }
    },
    {
      "type": "content_retrieved",
      "timestamp": "2026-08-20T09:00:01Z",
      "source_role": "index",
      "content_telemetry_id": "990e8400-e29b-41d4-a716-446655440501",
      "content_url": "https://www.autoreview.example/ev/charging-networks-2026",
      "content_id": "mkt:autoreview:88213",
      "license_ref": "agreement-2026-017:autoreview",
      "data": { "media_type": "text", "content_depth": "full" }
    },
    {
      "type": "content_retrieved",
      "timestamp": "2026-08-20T09:00:01Z",
      "source_role": "index",
      "content_telemetry_id": "990e8400-e29b-41d4-a716-446655440502",
      "content_id": "mkt:gridnews:5520",
      "license_ref": "agreement-2026-017:gridnews",
      "data": { "media_type": "text", "content_depth": "full" }
    },
    {
      "type": "content_grounded",
      "timestamp": "2026-08-20T09:00:02Z",
      "turn_id": "1",
      "content_url": "https://www.autoreview.example/ev/charging-networks-2026",
      "content_id": "mkt:autoreview:88213",
      "data": { "scope": "turn", "cached": false, "provenance": "third_party_sourced", "chars_ingested": 11200 }
    },
    {
      "type": "content_grounded",
      "timestamp": "2026-08-20T09:00:02Z",
      "turn_id": "1",
      "content_id": "mkt:gridnews:5520",
      "data": { "scope": "turn", "cached": false, "provenance": "third_party_sourced", "chars_ingested": 6400 }
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440503",
      "type": "content_cited",
      "timestamp": "2026-08-20T09:00:06Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:networks:1",
      "content_url": "https://www.autoreview.example/ev/charging-networks-2026",
      "content_id": "mkt:autoreview:88213",
      "data": { "citation_type": "paraphrase", "position": "primary" }
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440504",
      "type": "content_cited",
      "timestamp": "2026-08-20T09:00:06Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:tariffs:1",
      "content_id": "mkt:gridnews:5520",
      "data": { "citation_type": "reference", "position": "supporting" }
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440505",
      "type": "content_presented",
      "timestamp": "2026-08-20T09:00:07Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:networks:1",
      "citation_id": "990e8400-e29b-41d4-a716-446655440503",
      "content_url": "https://www.autoreview.example/ev/charging-networks-2026",
      "content_id": "mkt:autoreview:88213",
      "data": { "presentation_kind": "source_reference", "presentation_type": "link" }
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440506",
      "type": "content_presented",
      "timestamp": "2026-08-20T09:00:07Z",
      "turn_id": "1",
      "output_id": "response:1",
      "output_element_id": "answer:tariffs:1",
      "citation_id": "990e8400-e29b-41d4-a716-446655440504",
      "content_id": "mkt:gridnews:5520",
      "data": { "presentation_kind": "source_reference", "presentation_type": "card" }
    },
    {
      "type": "turn_completed",
      "timestamp": "2026-08-20T09:00:09Z",
      "turn_id": "1",
      "turn": { "privacy_level": "intent", "response_type": "comparison", "response_mode": "standard", "response_tokens": 410 }
    }
  ]
}
```

The telemetry consumer resolves `autoreview.example` by domain registration and the `mkt:gridnews:` prefix by identifier registration, and produces two owner-filtered views: AutoReview sees its retrieval, grounding, citation and link presentation; GridNews sees its own four events and nothing of AutoReview's. Neither view carries the other owner's identifiers, and both carry the shared `content_scope` so the marketplace can reconcile the session against the agreement. The second retrieval has no `content_url` at all - marketplace API content with no canonical URL - and resolves by `content_id` alone.
