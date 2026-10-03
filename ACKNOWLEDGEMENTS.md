# Acknowledgements

Content Telemetry is stewarded by the SPUR Coalition and maintained by Alex Springer (alex@spurcoalition.org). The specification is shaped in public: proposals, criticism and implementation evidence arrive through the [issue tracker](https://github.com/SPUR-Coalition/telemetry/issues) and pull requests, and every thread's outcome is recorded there.

This file credits the people whose work changed the specification. Contributors are listed per release, with the handle they used on GitHub and the change they drove. Organisations are given where the contributor stated one publicly. To correct or add an entry, open a pull request against this file.

## Version 1.0

The public comment period for the v0.1 preview ran from 12 June to 24 July 2026. Most of what changed between the preview and 1.0 traces back to it.

- **James Rosewell** ([@jwrosewell](https://github.com/jwrosewell), 51Degrees) - governing-terms references (`terms_ref`), occurrence boundaries and coverage declarations, the manifest's domain-identity scoping, the withdrawal of `ip_hash`, and the presentation-tokens proposal now open for discussion.
- **Pedro Santos** ([@pedroamaralsantos](https://github.com/pedroamaralsantos)) - the click-context design end to end: token transport, per-presentation binding, resolver discovery, and the custody trade-off now recorded in the specification.
- **Leandro Oliva** ([@landomo](https://github.com/landomo)) - grounding provenance and content fingerprints ([PR #10](https://github.com/SPUR-Coalition/telemetry/pull/10)), and the discovery and ranking analysis behind the outcome-layer clarification.
- **Erik Svilich** ([@erik-sv](https://github.com/erik-sv), EncypherAI) - completing the v1 grounding provenance and fingerprint semantics ([PR #41](https://github.com/SPUR-Coalition/telemetry/pull/41)), and the evidentiary-tiers work feeding the evidence profile.
- **Wallace Wilkins** ([@ReadBridge](https://github.com/ReadBridge), LicenseFoundry) - the entitlement-evidence profile draft ([PR #34](https://github.com/SPUR-Coalition/telemetry/pull/34)) and the sharpened `license_ref` semantics.
- [@redpinecode](https://github.com/redpinecode) (Redpine.ai) - `content_id` prefix resolution, now a co-primary routing path, and the multi-publisher `content_scope` model.
- **Anna Vissens** ([@avissens](https://github.com/avissens), the Guardian) - portable character counts and the `purpose` classification that replaced vendor bot labels.
- **Brady Ridgway** ([@RedHorseMane](https://github.com/RedHorseMane), ObraVera) - content-derived fingerprinting and identifier-scheme registration.
- **Romain Benabdelkader** ([@romainbenabdelkader](https://github.com/romainbenabdelkader)) - verifiable content identity and the evidence reference slot.
- [@pwright-bf](https://github.com/pwright-bf) - the publisher-seeded-markers verification profile proposal.
- **Abner Guzman-Rivera** ([@abnerguzman](https://github.com/abnerguzman)) - attribution carriers and verification governance.
- [@CKBrennan](https://github.com/CKBrennan) (Overtone) - the advertising purpose value and the signals use case.
- **Jérémy Chomat** ([@jchomat](https://github.com/jchomat), Ouest-France) - press-publisher implementation evidence across the provenance and click-context threads.
- **Laura Crimmons** ([@lauracrimmons1](https://github.com/lauracrimmons1)) - cross-language citation matching.
- [@B-Szymbo](https://github.com/B-Szymbo) - the counting-model guidance for commercial teams.
- **Scott Switzer** ([@switzer](https://github.com/switzer)) - the multi-agent session model behind `parent_session_id` and worked example B.6.

And everyone else who filed, commented, and pushed back during the consultation.
