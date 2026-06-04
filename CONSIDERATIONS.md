# Future considerations

Items considered during v0.1 development and deferred for future versions. Each item includes the motivation, the design tension, and the conditions under which it would be added.

## Index

- [Share-of-voice denominator (`total_sources_grounded`)](#share-of-voice-denominator-total_sources_grounded) - the missing denominator for share-of-influence calculations
- [Audit trail requirements](#audit-trail-requirements) - immutability, completeness detection, receipt timestamps for royalty audits
- [Content owner identification](#content-owner-identification) - a structured content-owner identity field on events
- [Domain-specific intent categories](#domain-specific-intent-categories) - vertical intent extensions for news, education, legal, etc.
- [Grounding boundary definition](#grounding-boundary-definition) - where in a multi-stage pipeline grounding is counted
- [Event volume and scale guidance](#event-volume-and-scale-guidance) - batching, sampling, aggregation for high-volume sessions
- [Platform-reported grounding verification](#platform-reported-grounding-verification) - making self-reported grounding/citation counts credible
- [Access-level signal on retrieval events](#access-level-signal-on-retrieval-events) - distinguishing authorised from unauthorised retrieval
- [Cached grounding and licence validity windows](#cached-grounding-and-licence-validity-windows) - detecting cached use after licence expiry
- [Content host versus rights holder](#content-host-versus-rights-holder) - repositories that host content they do not own
- [Display duration measurement (`display_duration_ms`)](#display-duration-measurement-display_duration_ms) - dwell time on displayed content
- [Agent-to-agent sessions (`initiator_type`, `initiator`)](#agent-to-agent-sessions-initiator_type-initiator) - attribution in multi-agent delegation chains
- [Cross-session journey linking (`prior_session_ids`)](#cross-session-journey-linking-prior_session_ids) - end-to-end attribution across sessions
- [User context (`user_context`)](#user-context-user_context) - user segmentation data on the session
- [Event-level content scope](#event-level-content-scope) - per-event content scope for multi-agreement sessions
- [Content-owner-requested conformance level](#content-owner-requested-conformance-level) - a non-binding requested level on content-owner manifests

## Share-of-voice denominator (`total_sources_grounded`)

**Motivation:** Content owners cannot calculate their share of content influence without knowing the denominator - how many total sources were in context for a given turn. A content owner seeing "your article was grounded" cannot distinguish "1 of 2 sources" from "1 of 50 sources" without this count.

**Proposed field:** `total_sources_grounded` (integer) on `turn_completed` events. No URLs, no content owner identification - just the count of distinct content sources in context.

**Design tension:** Platforms consider context window composition to be competitive intelligence. The count reveals retrieval strategy (how many sources are typically grounded per turn) and may vary across product surfaces in ways platforms prefer not to disclose.

**Conditions for inclusion:** Add when at least two major platforms confirm willingness to share this metric. A count is less sensitive than a list, so this may be an early candidate for v1.1.

## Audit trail requirements

**Motivation:** Marketplaces and licensing intermediaries need telemetry data suitable for royalty audits. This requires immutability guarantees (submitted data cannot be amended retroactively), completeness detection (ability to identify missing or dropped sessions), and provenance timestamps (server-side receipt time, not just agent-reported event time).

**Proposed additions:**
- `received_at` (datetime) on events, populated by the attribution consumer at ingestion time
- Guidance on append-only event storage for audit purposes
- Completeness detection via corroboration: marketplace-emitted `source_role: index` events cross-referenced against agent-reported grounding events to identify unreported usage

**Design tension:** Audit requirements push the spec toward protocol territory (delivery guarantees, receipt acknowledgement, data retention). The v0.1 position is that Content Telemetry defines a signal format, not a wire protocol. Adding audit semantics blurs that boundary.

**Conditions for inclusion:** Add as a companion document (not in the core spec) when marketplace implementations demonstrate concrete audit workflows. The `received_at` field could be added to the core schema without protocol implications - it is metadata about the event's journey, not a transport requirement.

## Content owner identification

**Motivation:** Marketplaces and attribution consumers need to identify which content owner owns a given piece of content. Currently, content owner identification requires inferring from `content_url` domain or `content_id` prefix, which breaks for syndicated content, marketplace APIs, and multi-domain content owners.

**Why deferred:** Multiple content identification standards are in development ([ISCC/ISO 24138](https://www.iso.org/standard/88469.html), [C2PA](https://c2pa.org/), marketplace-specific schemes). Adding a content owner identity field to the telemetry schema would require choosing or accommodating these competing approaches. The telemetry spec should be agnostic to content identification schemes. Note: the `content_id` field already accepts any of these identifiers as values - this deferred item is specifically about a structured *content owner identity* field, not content identification itself.

**Current approach:** Content owners communicate their identity through manifests (section 8) and `manifest_ref` references on sessions, or content access protocol metadata. Attribution consumers resolve content owner identity from these sources, not from the telemetry events themselves.

**Conditions for inclusion:** Revisit if a dominant content identification standard emerges and the market converges on a single scheme for content owner identity in telemetry contexts. Until then, identity resolution belongs in the manifest layer (section 8), not the event layer.

## Domain-specific intent categories

**Context:** The v0.1 intent taxonomy was restructured from a commerce-heavy set to a general-purpose set (`question`, `explanation`, `comparison`, `how_to`, `troubleshooting`, `fact_check`, `analysis`, `opinion_seeking`, `creative`, `purchase_intent`, `chitchat`, `other`). Commerce-specific categories (`price_check`, `availability_check`, `review_seeking`) moved to the ACP extension.

**Future consideration:** Domain-specific intent extensions for news (`investigation`, `breaking_news`), education (`tutorial`, `assessment`), legal (`case_research`, `compliance`), and other verticals. These would follow the same pattern as ACP: defined in domain extensions, not the core spec. The `other` + `topics` pattern provides an escape hatch until domain extensions exist.

## Grounding boundary definition

**Motivation:** The spec defines grounding as "content loaded into the agent's context" and provides an architecture table covering RAG, reasoning models, multi-step agents, and embedding-based systems. But the boundary is ambiguous for real-world pipelines with multiple processing stages. If an agent retrieves 100 articles, generates embeddings for all 100, re-ranks to 10, and puts 5 in the generation context - is the grounding count 100, 10, or 5? The spec does not distinguish embedding-for-selection from embedding-for-generation. Similarly, if content is summarised before entering context, is the original grounded or the summary?

**Why it matters:** This directly affects the denominator for royalty calculations and share-of-voice metrics. A platform counting only final-context articles reports far less usage than one counting everything that entered any processing stage. Both interpretations are defensible under the current wording.

**Design tension:** Content owners want the broadest possible definition (anything the platform touched). Platforms want the narrowest (only what directly influenced the response). The answer probably sits at the generation-stage input boundary, but this needs validation from implementers building real RAG pipelines.

**Conditions for resolution:** Requires input from at least two AI platform engineering teams on where they can practically draw the line in their pipelines. SPUR group and Microsoft collaboration expected. The definition must be precise enough that two independent implementations would count the same events for the same pipeline.

## Event volume and scale guidance

**Motivation:** A single deep-research query can produce 100+ retrieval events, 30+ grounding events, and dozens of citation/display events - over 140 events per turn. At millions of queries per day, this is hundreds of millions of events daily. The spec provides no guidance on batching, sampling, compression, or aggregation.

**Why it matters:** Implementation cost is the primary barrier to platform adoption. If the spec implies every retrieval and every grounding must be individually reported without exception, platforms will push back on the volume.

**Options under consideration:**
- Sampling with a `sample_rate` field on the session, so consumers can extrapolate
- Aggregated events (a single grounding event with a `content_urls` array instead of one event per URL)
- Compressed delivery guidance (gzip for bulk upload)
- Tiered reporting: full events for cited content, aggregated counts for grounded-but-not-cited

**Design tension:** Sampling reduces data quality. Aggregation changes the event model. Tiered reporting is pragmatic but privileges some content events over others. Content owners want complete data; platforms want manageable volume.

**Conditions for resolution:** Requires scale testing with real telemetry volumes. A platform implementing at even modest scale (100K queries/day) would surface the practical limits quickly. This is a v1.1 candidate once at least one platform has implemented and reported on volume.

## Platform-reported grounding verification

**Motivation:** Content owners can independently verify retrieval events via CDN/origin logs, but everything from grounding onward is platform self-reported. A platform could retrieve 1,000 articles and report grounding 50. The multi-observer corroboration model (section 5.2) works at the retrieval layer but not beyond it.

**Why it matters:** For licensing enforcement, grounding and citation counts determine compensation. The party reporting the numbers has a financial incentive to undercount. Without any verification mechanism, telemetry-based licensing rests on trust.

**Reality check:** Grounding is inherently self-reported. There is no independent way to observe what enters a platform's context window. This is not a gap in the spec - it is a structural property of the architecture. The question is what mechanisms make self-reporting credible enough for commercial relationships.

**Possible approaches:**
- Grounding-to-retrieval ratio monitoring: content owners compute the ratio of `content_grounded` to `content_retrieved` per platform over time. Anomalous ratios (heavy retrieval, minimal grounding) are audit triggers, not proof of undercounting, but they surface platforms that warrant scrutiny
- Marketplace corroboration: `source_role: index` emitters (marketplaces) know what content they served to which platform. Cross-referencing marketplace-emitted retrieval events against platform-reported grounding events identifies unreported usage
- Third-party audit provisions in licensing contracts (outside the spec's scope, but the spec should provide the data needed for audits)

**Design tension:** Any verification mechanism that goes beyond ratio monitoring requires either platform cooperation (self-defeating) or access to platform internals (unrealistic). The spec can provide the data surface for audit patterns but cannot solve the trust problem at the protocol level.

**Conditions for resolution:** This needs discussion with the SPUR group, Microsoft, and at least one content owner licensing team. The spec may need a companion "audit patterns" document rather than core schema changes. The `total_sources_grounded` deferred field (above) would strengthen ratio monitoring if adopted.

## Access-level signal on retrieval events

**Motivation:** Content repositories and content owners with mixed access policies (open access, institutional subscription, embargoed, authenticated) need to distinguish between authorised and unauthorised retrieval in telemetry. An AI agent retrieving open-access content is expected; an agent retrieving restricted content without authorisation is a licensing breach.

**Proposed field:** `access_level` (string) on `content_retrieved` events, populated by the content owner/origin. Values: `open`, `authenticated`, `licensed`, `embargoed`. This is an origin-side enrichment field - the origin knows the access level, not the agent.

**Design tension:** This overlaps with `license_ref` (restricted content has a licence reference, open content may not). A separate field is more explicit but adds schema weight. The access level could also be inferred from the absence or presence of `license_ref`.

**Conditions for inclusion:** Add when repository or mixed-access content owner implementations demonstrate the need. The `license_ref` inference approach should be evaluated first - if it proves sufficient in practice, a separate field is unnecessary.

## Cached grounding and licence validity windows

**Motivation:** The spec says agents SHOULD preserve `license_ref` from the original retrieval when emitting cached grounding events. But a licence may expire between retrieval and grounding. An agent that cached an article under a 24-hour licence and grounds it 48 hours later emits an expired `license_ref`. The spec does not provide the data needed to detect this.

**Proposed field:** `originally_retrieved_at` (datetime, ISO 8601) on `content_grounded` events with `cached: true`. This lets attribution consumers compare the retrieval time against the licence window without the spec taking a position on whether cached use after licence expiry is licensed.

**Design tension:** Adding a retrieval timestamp to grounding events blurs the boundary between retrieval and grounding. The spec positions these as distinct events precisely to separate observation from influence. However, the caching case inherently bridges this boundary.

**Conditions for inclusion:** Add when caching patterns are better understood from platform implementations. If most caching operates within licence windows, the field adds little value. If cross-window caching is common, the field is necessary for audit integrity.

## Content host versus rights holder

**Motivation:** Content repositories (archives, academic repositories, government document stores) host content where the repository is not the rights holder. When a repository reports `content_retrieved` events with `source_role: origin`, there is no field to indicate who the actual rights holder is. The `content_url` resolves to the repository domain, not the creator.

**Relationship to content owner identification:** This is a specific instance of the broader content owner identification problem (above). Repositories need to route usage telemetry to depositors and rights holders. The current approach (resolve identity from manifests) works when the repository and the rights holder share an identity layer, but breaks when depositors do not publish manifests.

**Conditions for inclusion:** Address alongside the broader content owner identification work. Repositories can use `content_id` with canonical identifiers (DOIs, ISCCs) as an interim approach - these resolve to the rights holder through existing identifier registries.

## Display duration measurement (`display_duration_ms`)

**Motivation:** Measuring how long content is visible to the user, useful for distinguishing glanced-at from read content. A `display_duration_ms` field on `content_displayed` events would record dwell time in milliseconds. Combined with the presence or absence of a subsequent `content_engaged` event, this distinguishes content that was read in place from content that was glanced at and ignored.

**Why deferred:** The concept maps well to search result cards and standalone content embeds, but poorly to chat-based responses that synthesise from multiple sources. In a chat response drawing on 8 sources, display duration is not meaningfully measurable per-source without eye tracking. The dual-event emission pattern required to support it (emit `content_displayed` at display-start without duration, then emit a second `content_displayed` at display-end with duration populated) also adds complex stateful deduplication requirements for consumers - matching on `content_url`/`content_id` within `turn_id`, resolving authoritative events when both carry duration values, discarding superseded event IDs.

**Conditions for inclusion:** Revisit when display surfaces stabilise and per-source visibility becomes measurable (e.g., expandable citation cards, dedicated content panels). At that point the field and its deduplication semantics can be specified against concrete UI patterns rather than hypothetical ones.

## Agent-to-agent sessions (`initiator_type`, `initiator`)

**Motivation:** In multi-agent pipelines, the session initiator may be another AI agent rather than a human. Tracking the calling agent's identity (agent ID, manifest, operator) enables attribution in agent-to-agent delegation chains.

**Proposed fields:** `initiator_type` (string, `"user"` or `"agent"`) and `initiator` (object with `agent_id`, `manifest_ref`, `operator_id`) on the session. When `initiator_type` is `"agent"`, the `initiator` object identifies the calling agent. The `prior_session_ids` field (see below) enables chain traversal.

**Why deferred:** No known v0.1 implementer needs agent-to-agent attribution. The schema surface area (four fields plus a nested object definition) is significant for a use case with no current demand. Agent-to-agent delegation patterns are still evolving rapidly.

**Conditions for inclusion:** Add when at least one platform implements agent-to-agent delegation and needs cross-session attribution. The fields can be added as optional without breaking changes.

## Cross-session journey linking (`prior_session_ids`)

**Motivation:** A user journey may span multiple sessions (e.g., initial research in one session, follow-up purchase in another). Linking sessions enables end-to-end attribution from content retrieval to final outcome.

**Proposed field:** `prior_session_ids` (UUID array) on the session, referencing previous sessions in the journey.

**Why deferred:** Requires significant implementation effort (chain traversal, cross-session storage). No known v0.1 implementer needs multi-session linking. The field can be added as optional without breaking changes.

**Conditions for inclusion:** Add when attribution consumers demonstrate concrete multi-session workflows (e.g., research-to-purchase journeys) that cannot be served by single-session attribution.

## User context (`user_context`)

**Motivation:** Agent operators may want to share user segmentation data (e.g., premium vs free tier, returning vs new) with attribution consumers to enable segment-level analysis.

**Proposed fields:** `user_context` (object) on the session, with `external_id` (opaque, non-PII user identifier), `segments` (string array), and `attributes` (open object).

**Why deferred:** Privacy concerns will prevent this in nearly all third-party scenarios. Agent operators sharing user segmentation with content owners or attribution consumers requires explicit data sharing agreements. No known v0.1 implementer needs this.

**Conditions for inclusion:** Add when data sharing agreements between platforms and content owners mature to the point where user segmentation is a standard part of attribution reporting.

## Event-level content scope

**Motivation:** `content_scope` is session-level only. When a single session spans multiple licensing agreements (e.g., a platform accesses content from two different marketplace catalogues), one session-level scope is insufficient.

**Why deferred:** Adding `content_scope` to events increases payload size for every event in every session, even when only one scope applies. The common case is one scope per session.

**Conditions for inclusion:** Add when marketplace implementations demonstrate multi-agreement sessions as a common pattern rather than an edge case. Could be added as an optional event-level field without breaking changes.

## Content-owner-requested conformance level

**Motivation:** A content owner may want to signal that it expects (or would prefer) richer telemetry than bare `retrieval` - e.g. "I want grounding-level reporting on my content." The v0.1 `telemetry.conformance_level` field looks like it might serve this, but it does not: it advertises what the manifest's own participant emits, it is informational, and it cannot gate an inbound endpoint (which accepts whatever it is configured to accept) or bind other emitters.

**Proposed field:** something like `telemetry.requested_level` on a `content_owner` manifest - a non-binding declaration of the level the owner would like agents to report at.

**Design tension:** It conflicts with the tolerant-consumer model (5.7.4: consumers accept events from any level) and the decentralised manifest model (a manifest is a self-contained credential, not a policy others must honour). A "request" with no enforcement risks misleading owners into thinking it does something. If anything in this space is added, it likely belongs in the policy layer (alongside training/use permissions) rather than the telemetry manifest, and needs a clear story for who, if anyone, acts on it.

**Conditions for inclusion:** Add only if content owners and at least one agent platform converge on a concrete workflow where a declared-but-non-binding requested level changes behaviour. Until then, `conformance_level` stays emitter-side and informational, and content-owner manifests SHOULD omit it.
