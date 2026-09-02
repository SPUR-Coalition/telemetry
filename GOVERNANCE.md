# Governance

## Status

Content Telemetry is an open specification stewarded by the SPUR Coalition. Version 1.0 is the current specification; see [SPECIFICATION.md](./SPECIFICATION.md) section 12 for the versioning policy.

## Stewardship

The SPUR Coalition stewards this specification as an open standard. The repository is kept narrow so the standard stays neutral:

- **The repository contains only the wire format.** Community-specific requirements - accreditation and the conformance mark - are defined in a separate profile (the SPUR Content Telemetry Profile) and carry no weight in the standard. The standard carries no SPUR-specific normative content.
- **Apache 2.0 throughout.** Contributions are accepted under the same licence (see [CONTRIBUTING.md](./CONTRIBUTING.md)). No contributor-side terms restrict redistribution or re-hosting.
- **No dependency on SPUR infrastructure.** The specification can be implemented without access to any SPUR-operated system. It names no operator of any aggregation point and does not require one to exist (SPECIFICATION.md section 7.3); the deployment patterns describe roles, not required intermediaries.

The SPUR Coalition stewards the specification and holds this repository. The standard's name - Content Telemetry - is neutral and carries no SPUR branding. The `SPUR` name, the SPUR conformance mark, and the accreditation programme stay with the Coalition through the profile.

## Who the SPUR Coalition is

The SPUR Coalition is a group of publishers and content owners that maintains the Content Telemetry standard. It holds the intellectual property through the preview period and releases the standard under Apache 2.0 from 12 June 2026.

Contributing to the standard does not require membership. The wire format is developed in the open, and anyone - content owner, agent operator, intermediary, or implementer - can take part through the issue tracker and the process described in the [README](./README.md#consultation-record).

The standard is maintained by Alex Springer (alex@spurcoalition.org).

## Version 1.0 and decisions

The specification reached 1.0 on 2 September 2026, following the public consultation of 12 June to 24 July 2026 and the release-candidate work recorded on the issue tracker.

Decisions follow the proposal and alignment process in [CONTRIBUTING.md](./CONTRIBUTING.md): anyone may propose a change, a maintainer records the disposition publicly on the issue tracker, and the SPUR Steering Board approves releases. The tracker and pull-request history are the public decision record. Minor versions add optional fields and event types; breaking changes require a major version (SPECIFICATION.md section 12).

## How to participate

- File questions and bugs on the [issue tracker](https://github.com/SPUR-Coalition/telemetry/issues) (see the templates).
- See the [consultation record](./README.md#consultation-record). The formal
  v1 comment window is closed, but concrete bugs and implementation evidence
  remain welcome on the issue tracker.
- Propose new capabilities or changes in behaviour as a short human-written note
  in [`proposals/`](./proposals/), following
  [CONTRIBUTING.md](./CONTRIBUTING.md).

## Relationship to the SPUR Content Telemetry Profile

This specification - the standard - defines the telemetry wire format: event types, schema, conformance levels, the privacy mechanism, and transport.

The [SPUR Content Telemetry Profile](https://github.com/SPUR-Coalition/telemetry-profile) is a separate document, in a separate repository, maintained on its own cadence. It defines the publisher-facing accreditation tier, the telemetry-delivery requirements an implementer must meet for it, and the SPUR conformance mark. The profile references this specification by version.

The dependency runs one way. The profile references the standard; the standard does not reference the profile. The profile remains with the SPUR Coalition and references the standard by version.

## Changes to the specification

Specification changes follow the proposal and maintainer-alignment process in
[CONTRIBUTING.md](./CONTRIBUTING.md). Required-field and conformance-level
changes are breaking and follow the versioning policy in SPECIFICATION.md
section 12.

## Licensing

Apache License 2.0. See [LICENSE](./LICENSE).
