Status: discussing

Proposed by: James Rosewell

# Make presented citations verifiable from the outside

**What I am seeing.** A citation shown on an AI surface, where the user
reads the quotation and never clicks, produces `content_cited` and
`content_presented` events that only the emitter can send and nobody
else can check. Publishers already measure these surfaces from the
outside by sampling, which is how AI Overviews get measured today, but a
sampled quotation cannot be matched to any telemetry, so sampling tells
a publisher what appeared and telemetry tells it what was reported, and
the two cannot be joined. The click-out design does not have this
problem, because the `ctx_token` rides the click onto the destination's
server, and the destination can then resolve it. That only helps when
there is a click, and the case everyone is worried about is the one
where there is not.

**What I would like Content Telemetry to express.** A token carried with
a presented source reference, in the same family as `ctx_token`, opaque
and resolvable only by its issuer, but bound to the presentation rather
than to a click. Anyone who can see the surface can collect the token.
The content owner, or a consumer acting for it, resolves the token and
receives the presentation context, in the way click context resolution
already works. The issuer-state pattern from the click-out work seems to
carry over directly, so nothing sensitive needs to appear on the
surface.

**Why it matters.** This would let a publisher join its two existing
sources of truth. Sample the surface, collect the tokens seen, and match
them against the events received. A quotation observed in the wild with
no matching event becomes visible as under-reporting, and a coverage
declaration of `complete` under 5.7.6 becomes something an outside party
can test by sampling, rather than something it can only take on trust.
It gives the verification layer, which the README lists as an open
question for grounding and citation, one mechanism that works without
any access to the emitter's internals. The same pattern as
`Content-Telemetry-ID` corroborating retrievals, applied at the other
end of the funnel.

The obvious questions are cost on the surface, whether the token is per
presentation or per citation, and abuse of the resolution endpoint by
parties who scraped tokens they have no interest in. I have views but no
fixed ones, and none of this needs settling before deciding whether the
direction is worth pursuing.
