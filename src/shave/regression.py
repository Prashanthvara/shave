"""Does the archetype layer earn its place?

Two regressions of the ranking key against the public fields that produce it:

  A. sqft x rate_class              -- if this alone explains the ranking, the
                                      archetype library is decoration.
  B. sqft x rate_class x archetype  -- high, because the score IS a
                                      deterministic function of exactly these
                                      three fields and nothing else.

Publishing B and explaining it is a stronger move than publishing a test that
cannot fail. The tool is a structured prior over three public assessor fields,
not a measurement; B is what that sentence looks like as a number.

B does NOT reach 1.000, and the reason is worth stating rather than hiding.
This fit is linear in floor area within each archetype; the scorer is not. The
shaveable kilowatts come from a root-find against a fixed energy budget and a
250 kW power cap, so a site large enough to saturate the cap stops scaling
with its floor area. `render_markdown` states the measured figure and that
explanation, never a predicted one -- an earlier revision asserted "~1.000"
in prose while its own table printed 0.878.

A is the one that can hurt. The threshold is declared before running.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: If sqft x rate_class alone explains more than this, the archetype layer is
#: adding little and the method page says so plainly. Declared in advance,
#: which is the only time a threshold means anything.
ARCHETYPE_R2_CEILING = 0.90


def r_squared(y: np.ndarray, X: np.ndarray) -> float:
    """Ordinary least squares R-squared, via lstsq so a rank-deficient design is fine."""
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if y.size == 0:
        return 0.0
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ beta
    ss_res = float(residual @ residual)
    centred = y - y.mean()
    ss_tot = float(centred @ centred)
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot


def design_matrix(
    scored: pd.DataFrame, with_archetype: bool
) -> tuple[np.ndarray, list[str]]:
    """Intercept, sqft, the G-3 indicator, their interaction, and optionally
    one-hot archetype terms interacted with floor area.

    The archetype terms are interacted with sqft rather than entered alone
    because that is how the scorer uses them: an archetype sets an intensity
    per square foot, so its effect is multiplicative in area.
    """
    sqft = scored["sqft"].to_numpy(dtype=float)
    is_g3 = (scored["rate_class"] == "G-3").to_numpy(dtype=float)

    columns = [np.ones_like(sqft), sqft, is_g3, sqft * is_g3]
    names = ["intercept", "sqft", "is_g3", "sqft:is_g3"]

    if with_archetype:
        for name in sorted(scored["archetype"].dropna().unique()):
            indicator = (scored["archetype"] == name).to_numpy(dtype=float)
            columns.append(sqft * indicator)
            names.append(f"sqft:{name}")

    return np.column_stack(columns), names


def run(scored: pd.DataFrame) -> dict:
    """Both R-squared figures, per source list, plus the declared verdict."""
    results: dict[str, dict] = {}
    for source in ("comstock", "modeled"):
        subset = scored[
            (scored["source"] == source)
            & scored["keep"].astype(bool)
            & scored["unscored_reason"].isna()
        ]
        if len(subset) < 10:
            results[source] = {"n": int(len(subset)), "skipped": "fewer than 10 rows"}
            continue
        y = subset["annual_savings_usd"].to_numpy(dtype=float)
        X_size, _ = design_matrix(subset, with_archetype=False)
        X_full, _ = design_matrix(subset, with_archetype=True)
        r2_size = r_squared(y, X_size)
        results[source] = {
            "n": int(len(subset)),
            "r2_size_and_rate": r2_size,
            "r2_with_archetype": r_squared(y, X_full),
            "archetype_adds_little": bool(r2_size > ARCHETYPE_R2_CEILING),
        }
    return {"ceiling": ARCHETYPE_R2_CEILING, "by_source": results}


def render_markdown(result: dict) -> str:
    """The method page's regression section, including the honest verdict."""
    lines = [
        "# Regression: does the archetype layer earn its place?",
        "",
        "Two ordinary least squares fits of `annual_savings_usd`, the ranking",
        "key, against the public fields that produce it. Run on kept rows only,",
        "each source list separately.",
        "",
        "| List | n | R2 vs sqft x rate class | R2 vs sqft x rate class x archetype |",
        "|---|---:|---:|---:|",
    ]
    for source, r in result["by_source"].items():
        if "skipped" in r:
            lines.append(f"| {source} | {r['n']} | — | — |")
            continue
        lines.append(
            f"| {source} | {r['n']:,} | {r['r2_size_and_rate']:.3f} | "
            f"{r['r2_with_archetype']:.3f} |"
        )
    fitted = [r for r in result["by_source"].values() if "r2_with_archetype" in r]
    full = max((r["r2_with_archetype"] for r in fitted), default=0.0)
    lines += [
        "",
        "**The second column is high by construction and that is not a",
        "finding.** The score is a deterministic function of exactly three",
        "public assessor fields: use code, building area, municipality. There",
        "is no fourth input and no measurement anywhere in it. This tool is a",
        "structured prior over public data; the second column is what that",
        "sentence looks like as a number.",
        "",
        f"It reaches {full:.3f} rather than 1.000, and the gap is arithmetic",
        "rather than hidden information. The fit above is linear in floor area",
        "within each archetype, but the scorer is not: the shaveable kilowatts",
        "come from a root-find against a fixed 413 kWh energy budget and a",
        "250 kW power cap, then a maximum is taken across twelve months. A",
        "site large enough to saturate the cap stops scaling with its own",
        "floor area entirely. That kink is real physics, it is what separates",
        "this from a size sort, and a straight line cannot follow it.",
        "",
        "Publishing both numbers and explaining them beats publishing a test",
        "that cannot fail.",
        "",
        "**The first column is the one that can hurt.** If floor area and rate",
        f"class alone explain more than {result['ceiling']:.2f} of the spread,",
        "the archetype library is decoration and the ranking is a size sort",
        "wearing a load profile. The threshold was declared before the numbers",
        "were computed.",
        "",
    ]
    for source, r in result["by_source"].items():
        if "skipped" in r:
            continue
        if r["archetype_adds_little"]:
            lines.append(
                f"**{source}: the archetype layer is adding little.** R2 of "
                f"{r['r2_size_and_rate']:.3f} against size and rate class alone is "
                f"above the {result['ceiling']:.2f} threshold declared in advance. "
                "Read this list as close to a size sort."
            )
        else:
            lines.append(
                f"**{source}: the archetype layer adds spread.** Size and rate "
                f"class alone explain {r['r2_size_and_rate']:.3f}; the load shape "
                "accounts for the rest of the ordering."
            )
        lines.append("")
    return "\n".join(lines)
