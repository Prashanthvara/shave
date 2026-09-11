# Regression: does the archetype layer earn its place?

Two ordinary least squares fits of `annual_savings_usd`, the ranking
key, against the public fields that produce it. Run on kept rows only,
each source list separately.

| List | n | R2 vs sqft x rate class | R2 vs sqft x rate class x archetype |
|---|---:|---:|---:|
| comstock | 528 | 0.614 | 0.878 |
| modeled | 209 | 0.493 | 0.749 |

**The second column is high by construction and that is not a
finding.** The score is a deterministic function of exactly three
public assessor fields: use code, building area, municipality. There
is no fourth input and no measurement anywhere in it. This tool is a
structured prior over public data; the second column is what that
sentence looks like as a number.

It reaches 0.878 rather than 1.000, and the gap is arithmetic
rather than hidden information. The fit above is linear in floor area
within each archetype, but the scorer is not: the shaveable kilowatts
come from a root-find against a fixed 413 kWh energy budget and a
250 kW power cap, then a maximum is taken across twelve months. A
site large enough to saturate the cap stops scaling with its own
floor area entirely. That kink is real physics, it is what separates
this from a size sort, and a straight line cannot follow it.

Publishing both numbers and explaining them beats publishing a test
that cannot fail.

**The first column is the one that can hurt.** If floor area and rate
class alone explain more than 0.90 of the spread,
the archetype library is decoration and the ranking is a size sort
wearing a load profile. The threshold was declared before the numbers
were computed.

**comstock: the archetype layer adds spread.** Size and rate class alone explain 0.614; the load shape accounts for the rest of the ordering.

**modeled: the archetype layer adds spread.** Size and rate class alone explain 0.493; the load shape accounts for the rest of the ordering.
