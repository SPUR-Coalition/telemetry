Status: discussing

Proposed by: Alex Springer

# OpenTelemetry names for Content Telemetry

**What I'm seeing**

- Agents already record OpenTelemetry. None of it says what content was grounded, cited or shown.
- The OpenTelemetry GenAI conventions have no citation or provenance fields, only `gen_ai.data_source.id` and a retrieved document's id and score.
- OpenTelemetry now wants domain conventions in separate registries ([OTEP 4815](https://github.com/open-telemetry/opentelemetry-specification/blob/main/oteps/4815-semantic-conventions-schema-v2.md)). The GenAI conventions moved out on that basis.

**What I'd like**

- An OpenTelemetry registry mapping the five content events, turns and fields to OpenTelemetry names. The specification stays normative.
- It lives in the neutral contenttelemetry GitHub org, with a one-way dependency on the specification, like the profiles.
- A working draft exists and passes these checks. It will be published there if this is aligned.

**Why it matters**

- Implementers report from instrumentation they already have.
- The section 5.7.5 rules become a check anyone can run against their own emitter.
- It gives us something concrete to take to the OpenTelemetry GenAI SIG.

**Questions for discussion**

- `content_telemetry.*` or `content.*` as the prefix.
- Turns as spans only.
- OpenTelemetry signals are not conformance until converted to section 7.1 documents. Is that line clear enough?

**Declared interest**

- SPUR tech lead and Content Telemetry maintainer.
