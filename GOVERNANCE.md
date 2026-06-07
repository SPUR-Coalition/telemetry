# Governance

## Status

Content Telemetry is an open specification stewarded by the SPUR Coalition. It is in preview (v0.x); see [SPECIFICATION.md](./SPECIFICATION.md) section 12 for the versioning policy.

## Stewardship

The SPUR Coalition stewards this specification as an open standard. The repository is kept narrow so the standard stays neutral:

- **The repository contains only the wire format.** Community-specific requirements - accreditation tiers, conformance marks, and privacy floors - are defined in a separate profile (the SPUR Content Telemetry Profile) and carry no weight in the standard. The standard carries no SPUR-specific normative content.
- **Apache 2.0 throughout.** Contributions are accepted under the same licence (see [CONTRIBUTING.md](./CONTRIBUTING.md)). No contributor-side terms restrict redistribution or re-hosting.
- **No dependency on SPUR infrastructure.** The specification can be implemented without access to any SPUR-operated system. It names no operator of any aggregation point and does not require one to exist (SPECIFICATION.md section 7.3); the deployment patterns describe roles, not required intermediaries.

The SPUR Coalition stewards the specification and holds this repository. The standard's name - Content Telemetry - is neutral and carries no SPUR branding. The `SPUR` name, the SPUR conformance mark, and the accreditation programme stay with the Coalition through the profile.

## Who the SPUR Coalition is

The SPUR Coalition is a group of publishers and content owners that maintains the Content Telemetry standard. It holds the intellectual property through the preview period and open-sources the standard under Apache 2.0 on 11 June 2026.

Contributing to the standard does not require membership. The wire format is developed in the open, and anyone - content owner, agent operator, intermediary, or implementer - can take part through the issue tracker and the comment process described in the [README](./README.md#request-for-comment).

The standard is maintained by Alex Springer (alex@spurcoalition.org). The decision-making process will be set out before 1.0.

## Path to 1.0

The specification is at v0.1 (preview). It moves to 1.0 once the open questions are resolved, the conformance suite is stable, and there are independent interoperable implementations from more than one party. There is no fixed date.

## How to participate

- File feedback, questions, and bugs on the [issue tracker](https://github.com/SPUR-Coalition/telemetry/issues) (see the templates).
- Comment during the [public comment window](./README.md#request-for-comment).
- Propose specific changes by pull request, following [CONTRIBUTING.md](./CONTRIBUTING.md).

## Relationship to the SPUR Content Telemetry Profile

This specification - the standard - defines the telemetry wire format: event types, schema, conformance levels, the privacy mechanism, and transport.

The [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile) is a separate document, in a separate repository, maintained on its own cadence. It defines publisher-facing accreditation tiers, the privacy floor for each tier, behavioural commitments, and the SPUR conformance mark. The profile references this specification by version.

The dependency runs one way. The profile references the standard; the standard does not reference the profile. The profile remains with the SPUR Coalition and references the standard by version.

## Changes to the specification

Specification changes follow the process in [CONTRIBUTING.md](./CONTRIBUTING.md). Required-field and conformance-level changes are breaking and follow the versioning policy in SPECIFICATION.md section 12.

## Licensing

Apache License 2.0. See [LICENSE](./LICENSE).
