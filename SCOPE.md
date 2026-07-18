# Content Telemetry: scope for core, profiles and governing terms

Content Telemetry core defines a small event vocabulary and the records needed to exchange those events. An implementation must be able to emit, receive and validate core telemetry without selecting a profile or using an external registry, resolver or verification service.

A profile adds shared semantics or processing rules that independent implementations need to interpret in the same way. Profiles depend on a pinned core version and cannot redefine core events. A deployment may select a small profile bundle in its endpoint, SDK, manifest or relationship configuration. That bundle is resolved once at build, startup or configuration time. It is not negotiated per event, turn or assertion, and conflicts are configuration errors.

Core keeps a small reserved event vocabulary. Profiles that need relationship-specific events use one controlled, namespaced extension mechanism. A core-only consumer remains conforming when it ignores extension events it does not support.

`content_cited` records an explicit source association in an output artifact. `content_presented` records that content or a reference was made perceivable on a recipient-facing surface. Either may occur without the other, and neither proves human attention.

External services may resolve identifiers, retrieve evidence, verify signatures, apply trust policy or report derived aggregates. Those services can support a deployment, but they are not required for core conformance. Governing terms decide which events, fields, privacy level, delivery destination, cadence and reports a relationship requires. They also decide commercial meaning. Telemetry does not determine ownership, permission, price or compensation.

These five questions remain separate:

1. **Syntactic validity:** does the record satisfy the schema and deterministic local rules?
2. **Cryptographic validity:** do its digests, signatures or timestamps verify?
3. **Trust-policy acceptance:** does this consumer accept the issuer, verifier, method and evidence?
4. **Factual truth and completeness:** did the event happen as claimed, and were all qualifying events reported?
5. **Entitlement:** was the reported use permitted under an applicable grant or agreement?

Events are claims by identified emitters. Evidence applies to a particular assertion, and origin or access evidence can corroborate only what that observer could see. It cannot by itself prove grounding, citation, presentation, activation, truth, completeness or entitlement.

Relationship configuration should avoid profile proliferation. A publisher may require Grounding and Citation, intent-level topics, event delivery to a named endpoint, and a set of aggregate reports. Another may require Citation, Presentation and Engagement with a different privacy level. Those are selections from capabilities already supported by the implementation, compiled into one deployment configuration and backed by governing terms. They do not create a publisher-specific protocol profile. A new profile is justified only when a relationship class introduces shared semantics or processing rules that multiple implementations must interpret identically.

The normal implementation path is the core schema and specification, a small curated profile bundle where needed, and the governing terms. The bundle is resolved into one effective deployment configuration at build, startup or relationship setup. Profiles are not discovered, negotiated or selected per event or turn. Core alone remains a complete path.

For example, an operator could choose a SPUR advertising deployment recipe and supply the publisher endpoints and commercial requirements. The SDK or collector would resolve the required delivery, advertising and evidence capabilities at startup. The agent would then emit ordinary lifecycle events; the collector would route publisher reports and send relevant evidence to the configured verification service. The developer would not select profiles or negotiate capabilities inside each agent turn.

The consultation will feed a v1 release candidate rather than an intermediate v0.2 release. Compatibility with an avoidable preview-version mistake is not a constraint. A breaking change is acceptable when it produces a clearer and more implementable v1 model. It must include migration notes and replacement fixtures, and must not silently change meaning within an existing version.
