# Content Telemetry Specification

**Version:** 0.1
**Status:** Preview
**Last updated:** 2026-06-02

## Contents

1. [Introduction](#1-introduction) - problem, goals, non-goals, relationship to access protocols, conventions
2. [Normative references](#2-normative-references)
3. [Terms and definitions](#3-terms-and-definitions)
4. [Concepts](#4-concepts) - roles, sessions, event lifecycle, source roles, content identification
5. [Schema](#5-schema) - session, event, event types, conversation turn, privacy, intent, conformance levels
6. [Data profiles](#6-data-profiles) - retrieval, edge enrichment, origin enrichment, grounding, citation, display, engagement
7. [Transport](#7-transport) - delivery formats, Content-Telemetry-ID header
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
- Model content usage for model training. The five-stage lifecycle covers inference-time usage only. The `bot_category` field on retrieval events (section 6.2) can distinguish training crawls from inference fetches, but training-specific telemetry is out of scope.
- Define accreditation tiers, conformance marks, or community-specific conformance requirements. These belong in profiles layered on this specification (see [GOVERNANCE.md](./GOVERNANCE.md)).

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
| **attribution consumer** | system that receives and processes telemetry to produce per-content-owner usage reports |
| **content owner** | entity that owns or licences content accessed by an AI agent |
| **agent operator** | entity running the AI agent that uses content |
| **grounding** | content entering the generation model's context, the boundary where content can directly influence output (section 4.3) |
| **source role** | classification of the observer reporting a retrieval event: `origin`, `edge`, `index`, or `agent` (section 4.4) |
| **privacy level** | data sharing tier controlling which conversation fields are populated: `full`, `summary`, `intent`, or `minimal` (section 5.5) |
| **conformance level** | emitter capability tier: Retrieval, Grounding, or Attribution (section 5.7) |
| **content scope** | opaque identifier grouping sessions by their content access context (section 5.1.1) |

## 4. Concepts

### 4.1 Roles

Three economic actors participate, by position in the value chain:

| Actor | Position | Description |
|-------|----------|-------------|
| **Content owner** | Supply | Owns or licences the content an agent uses: publishers, creators, and brands with owned content. |
| **Intermediary** | Middle | Sits between content and agent: marketplaces, affiliate and ad networks, search indices, CDN and edge platforms, and attribution vendors. |
| **Agent** | Demand | The AI agent, and the operator running it, that retrieves content and produces responses for an end user. |

The **end user** is the human interacting with the agent. They are not a telemetry participant; no actor reports the end user's identity.

Two further classifications cut across the actors and should not be confused with them:

- **Function** is what a participant does with telemetry. An *emitter* produces events; an *attribution consumer* receives events or whole sessions, resolves content owner identity, and exposes to each content owner only its own events. A participant may be both, and any actor can run an attribution consumer: a content owner for its own events, an agent operator, or an intermediary offering it as a service (see section 7.3).
- **Source role** is how a single event was observed, carried in the `source_role` field on `content_retrieved` events (`origin`, `edge`, `index`, `agent`; see section 4.4). It describes the observation, not the organisation.

A participant therefore has one actor (who it is), one or more functions (what it does), and a source role per event (how it observed that event). An affiliate network, for example, is an intermediary that emits `index` events and also operates an attribution consumer; a CDN is an intermediary that emits `edge` events on a content owner's behalf.

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
          └─────────────►   Attribution consumer    ◄─────────┘
                       resolves each content owner's events;          function
                       any participant above can run one              = what it does
```

The end user sits to the right of the agent and is not shown: they interact with the agent but report nothing and are never a telemetry participant.

| Participant | Actor | Function | Source role |
|-------------|-------|----------|-------------|
| Publisher, creator | Content owner | Emitter; may self-host a consumer | `origin` |
| CDN, edge platform | Intermediary | Emitter | `edge` |
| Search index, repository | Intermediary | Emitter | `index` |
| Marketplace, affiliate or ad network | Intermediary | Emitter and attribution consumer | `index` |
| Attribution vendor | Intermediary | Attribution consumer | (consumes only) |
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
│   ├── content_displayed    (UI layer)
│   ├── turn_completed
│   ├── content_engaged      (user action layer)
│   └── ...
└── ended_at
```

These are the event types a session can contain, not a strict ordering: events are ordered by timestamp. A session-scoped `content_grounded` event (for example, content grounded from cache) can precede the first `turn_started`.

### 4.3 Event lifecycle

Content moves through five stages during an agent interaction:

1. **Retrieved** - Content fetched over HTTP from an origin server, CDN, marketplace, or index. This is an infrastructure event observable by the content owner's infrastructure (origin server, edge network) and the agent. A retrieval may be cached by the agent for use across multiple sessions.

2. **Grounded** - Content loaded into the agent's generation context for this session or turn. The boundary is "this content entered the generation model's context" - the point where content can directly influence the model's output.

   Content used only for retrieval selection (embedding similarity search, re-ranking scores, routing decisions) without entering the generation context is not grounded.

   Grounding is architecture-neutral: same event whether the agent uses RAG, chain-of-thought reasoning, embeddings, or multi-step delegation (see section 6.4 for architecture-specific guidance). Grounding is decoupled from retrieval: content may be grounded from a live fetch, from agent-side cache, or from a pre-loaded index. Only the agent can report grounding events.

3. **Cited** - Content explicitly referenced in the agent's response: quoted, paraphrased, or linked. A subset of grounded content. Content can influence every response in a session without being cited once.

4. **Displayed** - A content reference shown to the end user: a link, snippet, inline quote, or preview card. Not all citations result in display (e.g., when the agent uses content internally without surfacing the source).

5. **Engaged** - The user interacted with displayed content: clicked a link, expanded a preview, copied text, or shared the response.

```
Retrieved (HTTP layer, cacheable)
  → Grounded (influence layer, per-session or per-turn)
    → Cited (response layer, per-turn)
      → Displayed (UI layer, per-turn)
        → Engaged (user action layer)
```

Each stage is typically a progressively narrower subset. The ratios between stages are meaningful for attribution:

- **Retrieval-to-grounding** measures content fetched but not used (irrelevant, stale, or a competing source was preferred)
- **Grounding-to-citation** measures content that influenced the response without explicit attribution
- **Citation-to-display** measures content attributed internally but not shown to the user
- **Display-to-engagement** measures interactions where the user did or did not visit the source

#### Departures from the funnel model

Two edge cases break the strict subset model:

- **Displayed without cited.** An agent may display content references (e.g., a "Sources" sidebar) without citing the content in the response text. In this case, a `content_displayed` event exists with no corresponding `content_cited` event.
- **Cited without grounded.** A hallucinated citation references content the agent never retrieved or loaded into context. The `content_cited` event has no preceding `content_grounded` event. Attribution consumers SHOULD treat uncorroborated citations (no matching grounding event) as lower-confidence signals.

These cases are valid. Emitters SHOULD produce the events that reflect what actually happened, even when the result does not follow the typical funnel ordering.

#### Conversation turns

Conversation turns overlay this lifecycle:

1. **Turn started** - user submits a query
2. **Turn completed** - agent finishes response

A single grounding event with session scope influences all subsequent turns. Citation, display, and engagement events occur within specific turns.

### 4.4 Source roles

A `content_retrieved` event can originate from multiple observers of the same retrieval. The `source_role` field identifies who is reporting:

| Source role | Reporter | Description |
|-------------|----------|-------------|
| `origin` | Content owner's web server | Content owner detected an AI agent request and reported it |
| `edge` | Edge network (CDN, edge compute) | An edge layer (Cloudflare, Fastly, Akamai, etc.) that observed the request |
| `index` | Search index or content repository | An intermediary that served the content to the agent |
| `agent` | AI agent | The agent itself, reporting content it fetched |

The `origin` and `edge` source roles enable content owners to report AI agent traffic using their existing infrastructure, with no cooperation from the AI agent required. Origin emitters typically submit individual events rather than complete sessions, since they do not have visibility into the agent's session context. Attribution consumers correlate these standalone events with agent-reported sessions using the `content_telemetry_id` field. Example B.2 demonstrates this pattern.

A marketplace operating as both emitter and attribution consumer receives telemetry from platforms (as a consumer), resolves content owner identity from `content_id` or `content_url`, and generates per-content-owner usage reports. The marketplace's own `source_role: index` events provide a corroboration layer - it can cross-reference what it served against what platforms reported using.

`content_grounded`, `content_cited`, `content_displayed`, and `content_engaged` events are reported by the agent (or agent operator) only. These events describe what happened inside the agent or in the user interface, which is not observable from the content owner's infrastructure.

When multiple observers report the same retrieval, events are correlated using the `Content-Telemetry-ID` header (see section 7.2). A retrieval corroborated by multiple sources is a stronger signal than either alone. An uncorroborated origin- or edge-reported retrieval (no matching agent event) may indicate a scraper that does not support the telemetry protocol, or missing header propagation.

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
| `schema_version` | string | Yes | Schema version (e.g., "0.1") |
| `session_id` | UUID | Yes | Unique session identifier |
| `agent_id` | string | No | Responding agent identifier |
| `content_scope` | string | No | Opaque content collection identifier (see 5.1.1) |
| `manifest_ref` | string | No | Manifest reference (see 5.1.2 and section 8) |
| `started_at` | datetime | Yes | Session start (UTC) |
| `ended_at` | datetime | No | Session end (UTC) |
| `conformance_level` | string | No | Informational conformance level advertised by the emitter (see section 5.7). Values: `retrieval`, `grounding`, `attribution` |
| `document_type` | string | No | `"session"` for session documents (see section 7.1 for the standalone event format) |
| `events` | Event[] | No | Ordered list of events |

#### 5.1.1 Content scope

The `content_scope` field is an opaque identifier that groups sessions by their content access context. Implementers define its meaning:

| Implementation | Example value |
|----------------|---------------|
| Content platform | `"electronics-reviews"` |
| Manifest-scoped | `"https://example.com/.well-known/content-telemetry.json"` |
| API key scoped | API key identifier |
| Agreement-based | Agreement or contract ID |

Attribution consumers can aggregate across sessions that share the same `content_scope` without the schema mandating a specific access control model. When a session spans multiple licensing agreements, emitters MAY use `license_ref` on individual events as a per-event scope proxy, since `license_ref` is event-level while `content_scope` is session-level.

#### 5.1.2 Manifest reference

The `manifest_ref` field optionally references a manifest (section 8), identifying the participant and its declared telemetry endpoint at session time.

Format: the URL of a manifest served at `/.well-known/content-telemetry.json` under a path the participant controls.

### 5.2 Event

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | No | Unique event identifier (generated by server if not provided) |
| `type` | EventType | Yes | Event type (see 5.3) |
| `timestamp` | datetime | Yes | Event timestamp (UTC) |
| `turn_id` | string | No | Associates this event with a conversation turn (see 5.2.1) |
| `source_role` | SourceRole | No | Who is reporting: `origin`, `edge`, `index`, `agent` (see 4.4) |
| `content_telemetry_id` | UUID | No | Correlation ID for cross-observer deduplication (see 7.2) |
| `content_url` | string | No | Content URL as fetched or canonical URL |
| `content_id` | string | No | Content owner's stable content identifier (see 4.5) |
| `license_ref` | string | No | Reference to the licence under which content was accessed |
| `turn` | ConversationTurn | No | Conversation data (for turn events) |
| `data` | object | No | Type-specific metadata (see section 6) |

#### 5.2.1 Turn association

The `turn_id` field associates content events with a specific conversation turn. Emitters SHOULD set `turn_id` on `content_cited`, `content_displayed`, and `content_engaged` events. Emitters SHOULD also set `turn_id` on `content_grounded` events when `scope` is `turn`. The corresponding `turn_started` and `turn_completed` events SHOULD carry the same `turn_id`.

`turn_id` is scoped to the session. Format is emitter-defined (sequential integers, UUIDs, or any opaque string).

Content events without a `turn_id` (e.g., `content_grounded` with `scope: session`) apply to the session as a whole rather than a specific turn.

#### 5.2.2 Source role

The `source_role` field SHOULD be set on `content_retrieved` events. When multiple systems observe the same retrieval, the `content_telemetry_id` field correlates their events for deduplication.

#### 5.2.3 Licence reference

The `license_ref` field connects a telemetry event to the content access licence that authorised it. The format depends on the access protocol: a JWT `jti` claim, a CoMP package ID, or any opaque identifier that both parties can resolve. When present, attribution consumers can verify that content usage was licensed.

### 5.3 Event types

#### Content events

| Type | Description | Expected fields |
|------|-------------|-----------------|
| `content_retrieved` | Content fetched from source | `content_url`, `source_role`, `data.media_type` |
| `content_grounded` | Content loaded into agent context | `content_url` or `content_id`, `data.scope`, `data.cached` |
| `content_cited` | Content referenced in response | `content_url`, `data.citation_type`, `data.position` |
| `content_displayed` | Content reference shown to user | `content_url`, `data.display_type` |
| `content_engaged` | User interacted with content | `content_url`, `data.engagement_type` (see 6.7) |

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
| `ad_rendered` | boolean | No | Whether advertising was displayed alongside the response |

#### 5.4.1 Response modes

`response_mode` identifies the product surface or generation mode, distinct from `response_type` which classifies the nature of the answer (recommendation, explanation, etc.):

| Value | Description |
|-------|-------------|
| `standard` | Standard conversational response |
| `deep_research` | Multi-step research mode with extended retrieval |
| `search` | Search results presentation |
| `code_generation` | Code generation or editing |

These are the recommended values. Platforms with additional product surfaces (collaborative canvases, voice, image generation, etc.) MAY use custom string values. Attribution consumers MUST tolerate unknown `response_mode` values.

### 5.5 Privacy levels

| Level | Query/response text | Intent | Topics | Token counts | Content URLs | Response classification | Platform metadata |
|-------|---------------------|--------|--------|--------------|-------------|------------------------|-------------------|
| `full` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `summary` | Summarised | Yes | Yes | Yes | Yes | Yes | Yes |
| `intent` | No | Yes | Yes | Yes | Yes | Yes | Yes |
| `minimal` | No | No | No | Yes | Yes | No | No |

An emitter that populates a conversation turn MUST NOT include a field above that turn's declared `privacy_level` - for example, `query_text` MUST NOT be present when `privacy_level` is `intent` or `minimal`. This restriction is a property of `privacy_level` itself: it applies wherever conversation turns are emitted, independent of the emitter's conformance level.

**Token counts** includes `query_tokens` and `response_tokens`. These are available at all levels because they are needed for token-based counting models and do not reveal user intent or platform strategy.

**Response classification** includes `response_type` (e.g., `"recommendation"`, `"explanation"`). Available at `intent` level and above, as it can reveal the nature of the user's query.

**Platform metadata** includes `ad_rendered`, `model_id`, and `response_mode`. These describe the agent or platform, not the user, but may reveal commercially sensitive information. Available at `intent` level and above.

`content_urls_retrieved` and `content_urls_cited` are available at all levels, including `minimal`, because individual content events already expose `content_url` at every privacy level. The `minimal` level protects query-level signals (intent, topics, response categorisation), not the existence of content attribution relationships. The turn-level arrays are a convenience for consumers who process turns without joining to content events. These arrays are **derived, not authoritative**: emitters SHOULD populate them from the corresponding content events in the session. When the arrays conflict with the individual content events, the content events are the source of truth.

These levels control how much of the user's query and the agent's response the recipient sees. They do not hide which content was used - that is the signal the format exists to carry - or how much of it an agent grounds. Both stay visible to whoever receives the telemetry, at every level including `minimal`.

### 5.6 Intent categories

**Information:** `question`, `explanation`, `comparison`, `how_to`, `troubleshooting`, `fact_check`, `analysis`, `opinion_seeking`

**Creative:** `creative`

**Commerce:** `purchase_intent`

**Other:** `chitchat`, `other`

These are the core values. Extensions MAY define additional intent category values (e.g., `price_check`, `availability_check`, `review_seeking` for commerce). Attribution consumers MUST tolerate unknown `query_intent` values.

### 5.7 Conformance levels

Emitters advertise one of three conformance levels. The authoritative declaration lives in the emitter's manifest (section 8). Emitters MAY also include an optional `conformance_level` field on individual session documents; when present it is informational and consumers MUST NOT treat it as a substitute for verifying the manifest's declaration.

| Level | Events | What it proves | Typical emitter |
|-------|--------|----------------|-----------------|
| **Retrieval** | `content_retrieved` | Content was fetched by an agent | Content owner CDN, edge network, origin server |
| **Grounding** | Above + `content_grounded`, turn events | Content entered the agent's context | Agent with basic instrumentation |
| **Attribution** | Above + `content_cited`, `content_displayed`, `content_engaged` | Full content lifecycle from retrieval to user engagement | Agent with full instrumentation |

#### 5.7.1 Retrieval conformance

A conforming **Retrieval** emitter MUST:

- Set `source_role` on `content_retrieved` events
- Include at least one of `content_url` or `content_id` on every event
- Set `type` and `timestamp` on every event

This level requires no agent cooperation. Content owners can implement it using CDN edge compute (Cloudflare Workers, Fastly Compute, etc.).

Origin-side emitters operating at the CDN edge SHOULD include `bot_category`, `response_status`, and `response_bytes` alongside the required fields. These fields make retrieval events useful for bot classification and volume analysis. Without them, the event confirms a fetch occurred but cannot support attribution correlation.

#### 5.7.2 Grounding conformance

A conforming **Grounding** emitter MUST satisfy Retrieval requirements and also:

- Produce sessions with `schema_version`, `session_id`, `agent_id`, and `started_at`
- Emit `content_grounded` events with `data.scope`
- Include at least one of `content_url` or `content_id` on every content event
- Emit `turn_started` and `turn_completed` events with `privacy_level`
- Restrict conversation turn fields to the declared `privacy_level` (section 5.5)

A Grounding emitter SHOULD include `data.tokens_ingested` and `data.cached` on grounding events.

Emitters using standalone event delivery (section 7.1) MUST include `agent_id` and `session_id` on the standalone event envelope to satisfy Grounding conformance.

#### 5.7.3 Attribution conformance

A conforming **Attribution** emitter MUST satisfy Grounding requirements and also:

- Emit `content_cited` events with `data.citation_type`

The privacy-level field restriction (section 5.5) applies to Attribution emitters as it does to any emitter producing conversation turns; it is inherited through the Grounding requirements above.

An Attribution emitter SHOULD:

- Emit `content_displayed` and `content_engaged` events when applicable
- Include `data.position` on citation events
- Include `data.display_type` on display events

#### 5.7.4 Attribution consumers

A conforming **attribution consumer** MUST:

- Accept sessions with any `schema_version` that shares the same major version. During the preview period (0.x), consumers MUST accept sessions with the exact same minor version (e.g., a 0.1 consumer accepts 0.1 only). The major-version compatibility rule takes effect from 1.0.0 onward.
- Tolerate unknown fields without error
- Tolerate events from any conformance level
- Accept both the session-document and standalone-event delivery formats, reconstructing sessions from standalone events where needed (see section 7.1)

#### 5.7.5 Application-layer conformance rules

The JSON Schema (`telemetry-session.json`) validates structure and types but cannot express every conformance rule. The following are normative requirements verified at the application layer, not by schema validation:

- At least one of `content_url` or `content_id` MUST be present on every content event (section 4.5).
- An event MUST carry either `session_id` or `ctx_token` at Grounding conformance and above (section 7.1).
- Conversation-turn fields MUST NOT exceed the turn's declared `privacy_level` (section 5.5).
- The conformance-level requirements (sections 5.7.1 to 5.7.3) are cumulative.

The `tests/` directory provides an informative reference suite for these rules. A consumer that receives a privacy-violating turn (e.g., `query_text` present at `minimal` level) SHOULD strip the offending fields rather than reject the document carrying them.

## 6. Data profiles

The `data` field on events carries type-specific metadata. These profiles document the recommended fields by event type and source role, in lifecycle order. None are required, but emitting them enables richer attribution.

### 6.1 Retrieved content metadata (`content_retrieved`)

When the reporter is the agent (`source_role: agent`), the following fields are recommended:

| Field | Type | Description |
|-------|------|-------------|
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` |

`media_type` on retrieval events allows content owners to see what types of content are being fetched, independent of whether those retrievals result in grounding or citation. Defaults to `text` when absent.

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
| `ip_hash` | string | SHA-256 of client IP (`sha256:{hex}`) |

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
| `ip_hash` | string | SHA-256 of client IP |
| `response_status` | integer | HTTP response status code |

### 6.4 Grounding data (`content_grounded`)

| Field | Type | Description |
|-------|------|-------------|
| `scope` | string | Influence scope: `session` or `turn` (see below) |
| `cached` | boolean | Content served from agent-side cache rather than a live fetch |
| `tokens_ingested` | integer | Token count of content placed in the generation context (see below) |
| `content_version` | string | Content version identifier (ETag, revision ID, CMS version) |
| `content_last_modified` | datetime | When the content was last modified at source |
| `content_hash` | string | SHA-256 of the content as ingested (`sha256:{hex}`) |
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` |

`tokens_ingested` counts tokens actually placed in the generation model's context. For chunked retrieval, count only the tokens used, not the full source document. The token count uses the generation model's tokeniser (the model identified in `model_id` on the corresponding `turn_completed` event), not the retrieval or embedding model's tokeniser.

#### Grounding scope

| Value | Description |
|-------|-------------|
| `session` | Content informed all subsequent responses in the session. |
| `turn` | Content informed this specific response only. |

For session-scoped grounding, the number of turns influenced is derivable from the session's `turn_started` events following the grounding event. This avoids redundant per-turn grounding events for content that persists across responses.

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

Attribution consumers may weight cached and live groundings differently. An agent may cache an article for days or weeks, grounding it in multiple sessions from a single retrieval. A single retrieval produces one `content_retrieved` event but potentially many `content_grounded` events across subsequent sessions.

Agents SHOULD preserve the `license_ref` from the original retrieval when emitting cached grounding events. Without this, attribution consumers cannot link cached usage to the licence that authorised the original access.

#### Freshness and verification

`content_version` and `content_last_modified` enable freshness analysis. Content owners with time-sensitive content (financial news, live events, market data) can use these fields to distinguish real-time use from stale cache hits. When content is grounded from cache, `content_last_modified` reflects when the source content was last modified, not when it was cached. Agents SHOULD preserve the `Last-Modified` header or equivalent metadata from the original retrieval.

`content_hash` is the SHA-256 of the content as it entered the agent's context. When the agent ingests a chunk rather than the full document, this is the chunk hash, not the document hash. The same hash on a corresponding `content_cited` event identifies which grounded content was cited - it matches the grounding hash, not the full source document. Content owners can compare grounding hashes against known document or chunk hashes to detect truncation, modification, or stale content.

### 6.5 Citation data (`content_cited`)

| Field | Type | Description |
|-------|------|-------------|
| `citation_type` | string | How content was used: `direct_quote`, `paraphrase`, `reference`, `contradiction`, `unclassified` |
| `media_type` | string | Content medium: `text`, `image`, `video`, `audio` |
| `excerpt_tokens` | integer | Token count of the excerpt used |
| `excerpt_chars` | integer | Character count of the excerpt used |
| `excerpt_hash` | string | SHA-256 of the cited excerpt text (`sha256:{hex}`). See below. |
| `position` | string | Prominence in response: `primary`, `supporting`, `mentioned`, `unclassified` |
| `content_hash` | string | SHA-256 matching the corresponding `content_grounded` event (`sha256:{hex}`). When the agent chunked the source, this is the chunk hash, not the full document hash. |
| `url_verified` | boolean | Whether the cited URL was verified to resolve to matching content |

`media_type` identifies the content medium. Defaults to `text` when absent.

`excerpt_tokens` is the agent-native measurement. `excerpt_chars` provides the same information in a unit familiar to content owners and licensors. Emitters SHOULD include both when available.

`excerpt_hash` is the SHA-256 of the excerpt text as it appears in the agent's response - the exact string the agent produced, not the source text it was derived from. For `direct_quote` citations, a matching hash against the source content confirms verbatim fidelity. For `paraphrase` citations, a non-matching hash is expected; verification tooling can use the hash to confirm which specific excerpt was cited and compare it against known source passages. Emitters SHOULD include `excerpt_hash` when `excerpt_tokens` or `excerpt_chars` is present. The hash uses the same `sha256:{hex}` format as `content_hash`.

The `contradiction` type supports negative attribution: content that was retrieved but explicitly disagreed with should not receive positive credit.

The `unclassified` value for `citation_type` indicates the agent did not classify this citation. The `unclassified` value for `position` indicates the agent did not determine the prominence of the citation. Emitters SHOULD use `unclassified` rather than forcing a classification when the agent cannot confidently determine the citation type or position.

`url_verified` indicates whether the agent confirmed that the cited URL resolves to content matching the citation. When `false` or absent, the citation may reference a hallucinated or outdated URL. `url_verified` MAY be set asynchronously after response generation. Platforms that batch-verify URLs periodically rather than per-request are conforming. A value of `false` indicates the URL was not verified, not that verification failed.

When `content_hash` is absent or does not match any grounding event's hash (for example, because the agent re-chunked content between grounding and citation), consumers SHOULD fall back to matching on `content_url` or `content_id`, accepting that the correlation may be imprecise when the same content appears in multiple grounding events.

### 6.6 Display data (`content_displayed`)

| Field | Type | Description |
|-------|------|-------------|
| `display_type` | string | How the content reference was presented (see below) |

#### Display types

| Value | Description |
|-------|-------------|
| `link` | URL link in a source list or footnote |
| `snippet` | Text snippet or preview |
| `inline_quote` | Quoted text inline in the response |
| `card` | Rich preview card (title, description, image) |
| `detail_view` | Expanded or full-content presentation |

When a session includes `content_displayed` events but no subsequent `content_engaged` events, the user saw a content reference but did not interact with it. Whether this pattern is meaningful depends on the commercial agreement - a per-citation deal may not care about clickthrough, while a traffic-based deal will. This pattern is only detectable from platform-reported `content_displayed` and `content_engaged` events. Retrieval is the only event stage observable from the CDN edge.

### 6.7 Engagement data (`content_engaged`)

| Field | Type | Description |
|-------|------|-------------|
| `engagement_type` | string | Type of interaction (see below) |

The content URL is identified by the event-level `content_url` field (section 5.2), not duplicated in `data`.

#### Engagement types

| Value | Description |
|-------|-------------|
| `link_click` | User clicked a link to the content |
| `expand` | User expanded a collapsed citation or preview |
| `copy` | User copied content text |
| `share` | User shared the content or agent response containing it |

`link_click` is the primary signal for clickthrough rate calculation. Attribution consumers can derive per-content-owner and aggregate clickthrough rates from the ratio of `link_click` engagements to `content_displayed` events for the same `content_url`.

A `link_click` engagement reported from the landing page after a click-out crosses a trust boundary. Such events carry a `ctx_token` in place of `session_id`, which the attribution consumer resolves to the originating session's click manifest (see section 7.1).

## 7. Transport

Content Telemetry defines a signal format, not a wire protocol. Common delivery patterns include HTTP postback, bulk upload after session end, MCP tool calls, message queues (Kafka, SQS), and direct database writes. The choice of transport is left to implementers.

### 7.1 Delivery formats

The schema supports two delivery formats:

**Session document.** A complete session with nested events, delivered after the session ends or at periodic intervals. This is the primary format described in section 5.1 and validated by `telemetry-session.json`.

**Standalone event.** A single event with a session reference, delivered as it occurs. Suitable for streaming architectures and origin-side emitters (CDNs, origin servers) that do not have visibility into the agent's session.

A standalone event carries `document_type`, `schema_version`, and optionally `session_id` alongside the event fields. The `document_type` field distinguishes standalone events from session documents:

```json
{
  "document_type": "event",
  "schema_version": "0.1",
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

Session documents use `"document_type": "session"`. When `document_type` is absent, consumers SHOULD treat the document as a session (for backwards compatibility with pre-0.1 implementations).

For origin-side emitters at Retrieval conformance level, `session_id` MAY be omitted when the content owner has no session context. Attribution consumers correlate these events with agent-reported sessions using the `content_telemetry_id` field.

For `content_engaged` events emitted from a landing page after a click-out (typically by a content marketplace, affiliate network, or destination site), `session_id` MAY be replaced by a `ctx_token` field that carries an opaque click-token issued by the originating agent. Attribution consumers resolve the token to the owning session. This lets a downstream observer report a corroborating engagement event without sharing the session UUID across trust boundaries. An event MUST carry either `session_id` or `ctx_token` at Grounding conformance and above.

**ctx_token resolution.** An attribution consumer that supports `ctx_token` resolution exposes, for a resolved token, the **click manifest**: the set of `content_grounded`, `content_cited`, and `content_displayed` events belonging to the resolved session, identifying every source that informed the response that produced the click. The manifest is gated by the resolved session's `privacy_level` and by consent. A consumer MUST return the manifest only when the issuing agent has opted in to sharing sessions via click tokens and the content owner whose URLs appear has opted in to being visible in click-token lookups. When either opt-in is absent, the consumer MUST NOT disclose the manifest. The mechanism by which an agent and a content owner record these opt-ins is operator-defined; the consent gate is normative.

The primary schema (`telemetry-session.json`) validates session documents. A standalone event envelope schema (`telemetry-event.json`) validates the event delivery format. Both schemas share the `TelemetryEvent` definition.

**Conformance constraints.** Standalone event delivery is sufficient for Retrieval conformance, where the emitter reports individual `content_retrieved` events with no session context. Grounding and Attribution conformance require session-level fields (`session_id`, `agent_id`, `started_at`) that the standalone event envelope does not carry by default.

An agent emitter that uses standalone events for streaming delivery and wants to achieve Grounding or Attribution conformance MUST include the optional `agent_id` and `started_at` fields on the standalone event envelope. The `session_id` field, which is already defined on the envelope, becomes REQUIRED (not optional) at Grounding conformance and above. Consumers reconstruct the session from the stream of standalone events sharing the same `session_id`.

Origin-side emitters (source role `origin` or `edge`) are not expected to achieve Grounding conformance and do not need these fields.

Attribution consumers MUST accept both delivery formats and reconstruct sessions from standalone events where needed.

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

Agent emitters SHOULD send session documents to a single **attribution consumer** - an aggregation point that receives complete sessions and provides filtered views to individual content owners. The attribution consumer resolves content owner identity from `content_url` domains (via verified domain registrations) and exposes only the events relevant to each content owner.

Two deployment patterns are common:

| Pattern | Operator | Description |
|---------|----------|-------------|
| **Platform-hosted** | Agent operator | The agent operator runs their own compatible consumer and sends filtered reports to content owners under licensing agreements. |
| **Marketplace-hosted** | Licensing intermediary | A content marketplace aggregates telemetry for its catalogue of content owners and provides per-content-owner dashboards and royalty data. |

Any party may operate a consumer: an agent operator, a licensing intermediary, or an independent third party offering it as a service. Both patterns above consume the same session format. The attribution consumer is responsible for domain resolution, content owner filtering, and access control. The spec does not mandate a specific aggregation topology, nor does it require any particular operator to provide one.

**Origin-side `.well-known/content-telemetry.json` manifests** declare where origin-emitted retrieval events are sent (CDN → content owner's chosen endpoint). They do not instruct agents where to send session documents. Agent routing is governed by the agent's telemetry configuration, not by content owner manifests.

**Content owner resolution.** Attribution consumers resolve content owner identity from `content_url` domains. Content owners register and verify their domains with the attribution consumer; the consumer maps incoming event URLs to the owning organisation. This is the primary resolution path and requires `content_url` to be present on events. Events identified only by `content_id` (e.g., cached groundings where the URL was not preserved, or marketplace API content with no canonical URL) cannot be resolved by domain alone. Attribution consumers SHOULD support `content_id` prefix-based resolution as a secondary path when content owners register their identifier schemes, but this is not yet a normative requirement.

**Cross-consumer correlation.** Origin-side emitters and agent-side emitters MAY use different attribution consumers. A content owner's CDN sends retrieval events to one attribution consumer; an agent sends sessions to another. The `content_telemetry_id` field (section 7.2) correlates the same retrieval across consumers - both sides share the same UUID from the HTTP request. This correlation operates at the retrieval level only. Grounding, citation, and engagement events have no independent origin-side counterpart to correlate against.

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

Trust derives from TLS and DNS control of the domain. Manifests are unsigned in v0.1.

### 8.2 Schema

Machine-readable schema: [`./manifest.json`](./manifest.json) (JSON Schema draft 2020-12).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Manifest schema version. v0.1 emitters MUST use `"0.1"`. |
| `id` | string | Yes | The manifest's canonical URL (e.g. `https://example.com/.well-known/content-telemetry.json`). |
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

Public keys used to sign telemetry events emitted by this participant. Per-event signing is informational in v0.1; consumers MAY verify signatures but are not required to.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Key identifier, unique within the manifest. |
| `type` | string | Yes | Key type. v0.1: `Ed25519`. |
| `publicKey` | string | Yes | Multibase-encoded public key (multicodec prefix, base58btc - the same format as `did:key`). |
| `expires` | datetime | No | ISO 8601 expiry. |

### 8.5 Telemetry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint` | string | Yes | HTTPS URL. For agents and platforms, the outbound submission endpoint. For content owners, the inbound destination for events about the content owner's content. |
| `conformance_level` | string | No | Conformance level advertised by this participant's own emitter(s). One of `retrieval`, `grounding`, `attribution` (see 5.7). |

`conformance_level` is informational. It advertises the level of telemetry the manifest's participant emits. It does **not** constrain what an inbound `endpoint` accepts - an endpoint accepts whatever events it is configured to accept, regardless of any level declared here - and it places **no requirement** on other emitters. On a `content_owner` manifest it describes only the events the owner's own infrastructure emits (typically a CDN edge worker at `retrieval`); it says nothing about what agents or platforms report about the owner's content, which those parties advertise in their own manifests. A `content_owner` manifest SHOULD omit `conformance_level` unless the owner operates its own emitter. There is no field for a content owner to *request* a minimum level from agents; consumers tolerate events from any level (see 5.7), and the protocol does not give a manifest a way to demand more.

### 8.6 Domains

The `domains` array MAY appear only on manifests served from the domain root (`https://<domain>/.well-known/content-telemetry.json`). Manifests under path prefixes MUST NOT include `domains`.

In v0.1, every entry in `domains` MUST be self-validating: either the manifest's own host, or a subdomain of it (literal `news.example.com` or wildcard `*.example.com`). Control of the apex - proven by serving the manifest at the apex over TLS - implies DNS control of subdomains, so no further validation is needed. A manifest containing entries that are not subdomains of its own host is malformed.

This keeps the v0.1 protocol fully decentralised: every manifest is a self-contained credential, validated by TLS plus the well-known location, with no dependency on consumer-side validation state or any external registry. Cross-apex claims (one operator unifying several unrelated apex domains in a single manifest) are deferred to a later version.

### 8.7 Consumer behaviour

When resolving a manifest from `manifest_ref`, a `content_url` domain, or any other reference:

- **404 or network error.** Treat the participant as unverified. Do not reject telemetry events on this basis alone.
- **Invalid JSON or schema validation failure.** Reject the manifest. Treat the participant as unverified.
- **Unknown `schema_version`.** During the v0.x preview period, consumers MUST accept only the exact same minor version. The semver-major compatibility rule applies from 1.0.0 onward (see section 12).
- **Duplicate `keys[].id`.** Reject the manifest.
- **`domains` entry that is not the manifest's host or a subdomain of it.** Reject the manifest as malformed (see 8.6).
- **Missing `keys` on a manifest referenced by `manifest_ref`.** Not an error in v0.1, since signing is informational.

Consumers SHOULD cache resolved manifests respecting the response's `Cache-Control` headers. Manifest hosts SHOULD set `Cache-Control: max-age=3600` during onboarding and `max-age=86400` steady-state.

### 8.8 Examples

**Content owner.**

```json
{
  "schema_version": "0.1",
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
  "schema_version": "0.1",
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
  "schema_version": "0.1",
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
  "schema_version": "0.1",
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

### 8.9 Out of scope for v0.1

The following are deferred to later versions:

- Content licence declarations (what content the participant is licensed to access)
- Manifest signing (W3C Verifiable Credentials, JWS proofs)
- Training data and model provenance
- Deployment context, purpose, brand affiliation
- Revocation registries
- Key rotation procedures beyond the `expires` field
- `did:web` compatibility (the `id` field uses the manifest URL in v0.1)
- Cross-apex claims (one operator unifying several unrelated apex domains in a single manifest)

---

## 9. Privacy

### 9.1 Data minimisation

Emitters SHOULD:

- Use the minimum `privacy_level` necessary
- Hash or anonymise identifiers where possible

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
- **Position-based** - weighted by position in journey
- **SHAP-based** - game-theoretic contribution scores

### 10.1 Counting semantics

The schema records discrete events. A `content_grounded` event represents content entering the agent's context. A `content_cited` event represents content being explicitly referenced in a response. These are independent signals.

A session where one article is grounded with session scope, the user asks ten questions, and the article is cited three times produces:

- 1 `content_grounded` event
- 10 `turn_completed` events
- 3 `content_cited` events

Whether this constitutes one royalty event, three, or ten depends on the commercial agreement. The schema provides the raw signals; attribution consumers choose the counting model.

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
- At the **display** level: counts only content references shown to users. Narrowest scope, highest confidence.

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

### 11.2 Custom intent categories

`query_intent` accepts custom string values beyond the core set. Extensions SHOULD namespace their values to avoid collisions (e.g., `price_check` for a commerce extension). For ad-hoc categories that don't warrant a formal extension, use `other` with details in `topics`.

Attribution consumers MUST tolerate unknown `query_intent` values.

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

Attribution consumers MUST tolerate unknown `response_mode` values.

## 12. Versioning

Preview versions (0.x) use two-component version numbers. From 1.0.0 onward, versions follow [semantic versioning](https://semver.org/):

- **Major** (1.0.0 → 2.0.0) - breaking changes to required fields
- **Minor** (1.0.0 → 1.1.0) - new optional fields, new event types
- **Patch** (1.0.0 → 1.0.1) - clarifications

From 1.0.0 onward, consumers SHOULD accept sessions with any compatible minor version (same major version). During the preview period (0.x) the stricter rule in section 5.7.4 applies: a consumer accepts only the exact same minor version (a 0.1 consumer accepts 0.1 only).

## Annex A (normative): JSON Schema

See `telemetry-session.json` for the formal JSON Schema definition.

## Annex B (informative): Examples

### B.1 User-to-agent session with grounding

A user asks a shopping assistant to compare noise-cancelling headphones. The agent retrieves a review, grounds it, cites it, and the user clicks through. This demonstrates the full funnel from retrieval to engagement.

```json
{
  "schema_version": "0.1",
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
        "tokens_ingested": 4200,
        "content_last_modified": "2026-01-10T14:00:00Z",
        "media_type": "text"
      }
    },
    {
      "type": "content_cited",
      "timestamp": "2026-01-15T10:30:05Z",
      "turn_id": "1",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "citation_type": "paraphrase",
        "excerpt_tokens": 85,
        "position": "primary"
      }
    },
    {
      "type": "content_displayed",
      "timestamp": "2026-01-15T10:30:05Z",
      "turn_id": "1",
      "content_url": "https://www.wirecutter.com/reviews/best-wireless-headphones",
      "content_id": "wirecutter:best-wireless-headphones-2026",
      "data": {
        "display_type": "link"
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
    "country": "US",
    "ip_hash": "sha256:d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5"
  }
}
```

These share `content_telemetry_id` and `content_url`, representing one corroborated retrieval from two observers.

### B.3 Cached grounding

An AI agent previously fetched an FT article and cached it. In a new session, the cached article is loaded into context and influences multiple turns. The user never clicks through to the source.

```json
{
  "schema_version": "0.1",
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
      "type": "content_cited",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
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
      "type": "content_displayed",
      "timestamp": "2026-03-28T09:00:05Z",
      "turn_id": "1",
      "content_url": "https://www.ft.com/content/abc123",
      "content_id": "ft:abc123",
      "data": {
        "display_type": "link"
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
      "type": "content_cited",
      "timestamp": "2026-03-28T09:01:08Z",
      "turn_id": "2",
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
- 1 display event (link shown in turn 1)
- 0 engagement events (user did not click through to ft.com)
- Advertising was rendered alongside the first response

The content owner can derive: article `ft:abc123` was in context for all turns, cited twice, displayed once, never clicked. The content was 14.5 hours old (cached from previous day). The response was monetised with advertising.

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
