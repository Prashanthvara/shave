import { describe, expect, it } from "vitest";
import {
  chipClass,
  daySVG,
  drawerHTML,
  fmtMoney,
  methodHTML,
  rowHTML,
  sparkSVG,
} from "../public/app.js";

const ROW = {
  loc_id: "F_1",
  rank: 1,
  occupant: "UMass Chan Medical School",
  occupant_source: "https://www.umassmed.edu/",
  owner: "COMMONWEALTH OF MASS EDUCATION",
  site_addr: "360 PLANTATION ST",
  city: "WORCESTER",
  use_desc: "DOE: UMass, State and Community Colleges",
  archetype: "university",
  source: "modeled",
  sqft: 1628495,
  avg_12mo_kw: 3957.7,
  peak_kw: 4500,
  peak_to_avg: 1.14,
  rate_class: "G-3",
  demand_charge_per_kw: 10.48,
  annual_savings_usd: 31440,
  shaved_fraction: 0.0636,
  shaveable_kw: 250,
  confidence: "MED",
  flags: ["power_limited"],
  sweet_spot: false,
  reason: "Runs flat at 1.1x its 12-month average, so there is little peak to remove.",
  window_kw: [0.8, 0.82, 0.85, 0.9, 0.95, 1.0, 0.98, 0.96, 0.9, 0.86, 0.83, 0.81],
};

describe("fmtMoney", () => {
  it("is whole dollars with separators, never cents", () => {
    expect(fmtMoney(31440)).toBe("$31,440");
    expect(fmtMoney(0)).toBe("$0");
  });
});

describe("chipClass", () => {
  it("maps confidence to its semantic token class", () => {
    expect(chipClass("HIGH")).toBe("hi");
    expect(chipClass("MED")).toBe("med");
    expect(chipClass("LOW")).toBe("lo");
  });
});

describe("sparkSVG", () => {
  it("marks the peak with the accent and nothing else", () => {
    const svg = sparkSVG([0.2, 1.0, 0.4], 68, 22);
    expect(svg).toContain("<svg");
    expect(svg).toContain('aria-hidden="true"');
    // --signal is spent on the peak dot only. One occurrence, not two.
    expect(svg.match(/var\(--signal\)/g)).toHaveLength(1);
  });

  it("survives an all-zero series without dividing by zero", () => {
    const svg = sparkSVG([0, 0, 0], 68, 22);
    expect(svg).toContain("<svg");
    expect(svg).not.toContain("NaN");
  });

  it("survives an empty series", () => {
    expect(sparkSVG([], 68, 22)).toContain("<svg");
    expect(sparkSVG(undefined, 68, 22)).toContain("<svg");
  });
});

describe("rowHTML", () => {
  it("shows the occupant, not the owner of record", () => {
    const html = rowHTML(ROW);
    expect(html).toContain("UMass Chan Medical School");
    expect(html).not.toContain("COMMONWEALTH OF MASS EDUCATION");
  });

  it("falls back to the use description when no occupant is resolved", () => {
    const html = rowHTML({ ...ROW, occupant: "" });
    expect(html).toContain("DOE: UMass, State and Community Colleges");
    // and never silently presents the holding company as the occupant
    expect(html).not.toContain("COMMONWEALTH OF MASS EDUCATION");
  });

  it("renders the rate class through its semantic class", () => {
    expect(rowHTML(ROW)).toContain('class="rate g3"');
    expect(rowHTML({ ...ROW, rate_class: "G-2" })).toContain('class="rate g2"');
  });

  it("escapes text that came from an assessor record", () => {
    const html = rowHTML({ ...ROW, occupant: '<img src=x onerror="alert(1)">' });
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
  });
});

describe("drawerHTML", () => {
  it("carries the lineage and the flags in plain words", () => {
    const html = drawerHTML(ROW, { power_limited: "The battery hits its rating." });
    expect(html).toContain("The battery hits its rating.");
    expect(html).toContain("360 PLANTATION ST");
  });

  it("links the occupant source so the claim is checkable", () => {
    expect(drawerHTML(ROW, {})).toContain('href="https://www.umassmed.edu/"');
  });

  it("says so plainly when the occupant is unresolved", () => {
    const html = drawerHTML({ ...ROW, occupant: "", occupant_source: "" }, {});
    expect(html).toContain("not yet resolved");
  });
});

const METHOD = {
  assumptions: [
    {
      key: "g2_demand_charge",
      value: "15.06 $/kW",
      provenance: "FILED",
      source: "MECO summary of rates",
      note: "Rate G-2 distribution demand charge.",
    },
  ],
  limitations: [
    { key: "no_measurement", statement: "This tool contains no per-building measurement." },
  ],
  known_gaps: [{ key: "one_municipality", statement: "Worcester only." }],
  flag_meanings: { power_limited: "The battery hits its rating." },
  lineage: { parcels: "MassGIS Level 3", tariff: "M.D.P.U. No. 1591" },
  coverage: {
    parcels_total: 2099,
    kept: 737,
    sweet_spot: 172,
    assess_years: [2026],
    unscored: { no_intensity_anchor: 6 },
  },
  occupants: { resolved_total: 4, top_n: 50, top_n_resolved: 4 },
  regression: {
    ceiling: 0.9,
    by_source: {
      comstock: {
        n: 528,
        r2_size_and_rate: 0.614,
        r2_with_archetype: 0.878,
        archetype_adds_little: false,
      },
      modeled: {
        n: 209,
        r2_size_and_rate: 0.493,
        r2_with_archetype: 0.749,
        archetype_adds_little: false,
      },
    },
  },
};

describe("methodHTML", () => {
  it("renders every limitation, because criterion 6 is the list", () => {
    const { cannot } = methodHTML(METHOD);
    expect(cannot).toContain("This tool contains no per-building measurement.");
  });

  it("renders every assumption with its source and provenance", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).toContain("15.06 $/kW");
    expect(prose).toContain("MECO summary of rates");
    expect(prose).toContain("FILED");
  });

  it("renders the real regression shape, per list, never undefined", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).toContain("0.614");
    expect(prose).toContain("0.878");
    expect(prose).toContain("0.493");
    expect(prose).not.toContain("undefined");
    expect(prose).not.toContain("NaN");
  });

  it("reports an unrun regression as unrun, never as zero", () => {
    const { prose } = methodHTML({
      ...METHOD,
      regression: { status: "not yet run; the figures below are unreported, not zero" },
    });
    expect(prose).toContain("not yet run");
    expect(prose).not.toMatch(/R².{0,12}0\.00/);
  });

  it("never claims a figure its own table contradicts", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).not.toContain("1.000 by construction");
    expect(prose).toContain("power cap");
  });

  it("fires the verdict when size alone explains the ranking", () => {
    const { prose } = methodHTML({
      ...METHOD,
      regression: {
        ceiling: 0.9,
        by_source: {
          comstock: {
            n: 10,
            r2_size_and_rate: 0.97,
            r2_with_archetype: 0.99,
            archetype_adds_little: true,
          },
        },
      },
    });
    expect(prose).toContain("adding little");
    expect(prose).toContain("close to a size sort");
  });

  it("states the known gaps rather than hiding them", () => {
    const { cannot } = methodHTML(METHOD);
    expect(cannot).toContain("Worcester only.");
  });

  it("reports occupant coverage truthfully", () => {
    const { foot } = methodHTML(METHOD);
    expect(foot).toContain("4 of 50");
  });
});

import { mapSVG, parcelHTML } from "../public/app.js";

const MAP_ROWS = [
  { ...ROW, loc_id: "A", annual_savings_usd: 30000, rate_class: "G-3",
    path: "M10,10L20,10L20,20L10,20Z", occupant: "Big Slate Co" },
  { ...ROW, loc_id: "B", annual_savings_usd: 6000, rate_class: "G-2",
    path: "M40,40L45,40L45,45L40,45Z", occupant: "Small Teal Co" },
  { ...ROW, loc_id: "C", annual_savings_usd: 1000, rate_class: "G-2", path: "" },
];

describe("parcelHTML", () => {
  it("encodes rate class in the outline and never in the accent", () => {
    const a = parcelHTML(MAP_ROWS[0], 30000);
    const b = parcelHTML(MAP_ROWS[1], 30000);
    expect(a).toContain("var(--g3)");
    expect(b).toContain("var(--g2)");
    // the accent is reserved for fill weight; an outline must never take it
    expect(a).not.toMatch(/stroke="var\(--signal\)"/);
  });

  it("encodes saving as fill opacity, heavier for more money", () => {
    const rich = parcelHTML(MAP_ROWS[0], 30000);
    const poor = parcelHTML(MAP_ROWS[1], 30000);
    const op = (s) => parseFloat(s.match(/fill-opacity="([\d.]+)"/)[1]);
    expect(op(rich)).toBeGreaterThan(op(poor));
    expect(op(poor)).toBeGreaterThan(0);
  });

  it("is keyboard reachable and labelled for a screen reader", () => {
    const html = parcelHTML(MAP_ROWS[0], 30000);
    expect(html).toContain('tabindex="0"');
    expect(html).toContain('role="button"');
    expect(html).toMatch(/aria-label="[^"]*Big Slate Co[^"]*"/);
  });

  it("escapes the label, which came from an assessor record", () => {
    const html = parcelHTML({ ...MAP_ROWS[0], occupant: '"><script>x' }, 30000);
    expect(html).not.toContain("<script>");
  });
});

describe("mapSVG", () => {
  it("draws only the rows that have geometry", () => {
    const svg = mapSVG(MAP_ROWS, "0 0 620 818", 30000);
    expect(svg.match(/class="parcel"/g)).toHaveLength(2);
    expect(svg).not.toContain('data-id="C"');
  });

  it("carries the build's viewBox rather than inventing one", () => {
    expect(mapSVG(MAP_ROWS, "0 0 620 818", 30000)).toContain('viewBox="0 0 620 818"');
  });

  it("says so plainly when there is nothing to draw", () => {
    const svg = mapSVG([MAP_ROWS[2]], "0 0 620 818", 1000);
    expect(svg).toMatch(/no mapped parcel|nothing to draw/i);
  });
});

import { parcelSelectionClasses } from "../public/app.js";

describe("parcelSelectionClasses", () => {
  const rows = [
    { loc_id: "A", path: "M0,0L1,1Z" },
    { loc_id: "B", path: "M0,0L1,1Z" },
    { loc_id: "C", path: "" },
  ];

  it("highlights the selected parcel and dims the others", () => {
    const cls = parcelSelectionClasses(rows, "A");
    expect(cls.A).toContain("on");
    expect(cls.A).not.toContain("dim");
    expect(cls.B).toContain("dim");
  });

  it("dims nothing when there is no selection", () => {
    const cls = parcelSelectionClasses(rows, null);
    expect(cls.A).not.toContain("dim");
    expect(cls.B).not.toContain("dim");
  });

  it("ignores rows with no geometry", () => {
    expect(parcelSelectionClasses(rows, "A")).not.toHaveProperty("C");
  });

  it("dims everything when the selection is not on the map", () => {
    // The selected row exists in the table but has no parcel: the map must
    // not silently keep a stale highlight on a different building.
    const cls = parcelSelectionClasses(rows, "C");
    expect(cls.A).toContain("dim");
    expect(cls.B).toContain("dim");
  });
});

const DAY_AXIS = { window_start_hour: 8, window_end_hour: 21, step_hours: 0.25 };
const DAY_ROW = {
  ...ROW,
  peak_day_month: 7,
  peak_day_held_kw: 150,
  monthly_billed_demand_kw: [100, 100, 100, 100, 100, 100, 400, 100, 100, 100, 100, 100],
  day_kw: Array.from({ length: 52 }, (_, i) => (i >= 20 && i < 24 ? 1 : 0.25)),
  day_held: 0.375,
  day_offpeak: 0.2,
};

describe("daySVG", () => {
  const svg = daySVG(DAY_ROW, DAY_AXIS, 302, 84);

  it("shades exactly the billed window on a 24-hour axis", () => {
    // x(h) = 1 + h/24 * 300, so 08:00 is 101.0 and 13 hours is 162.5 wide.
    expect(svg).toMatch(/<rect class="billed" x="101\.0" y="0" width="162\.5"/);
  });

  it("draws every billed interval and no invented overnight curve", () => {
    const pts = svg.match(/<polyline points="([^"]+)"/)[1].trim().split(" ");
    expect(pts).toHaveLength(52);
    expect(svg.match(/<polyline/g)).toHaveLength(1);
  });

  it("spends the accent once, on the peak above the held level", () => {
    expect(svg.match(/var\(--signal\)/g)).toHaveLength(1);
    expect(svg).toContain('clip-path="url(#dayshaved)"');
    // plot height 70, y(v) = 1 + (1 - v) * 68, so held 0.375 sits at 43.5
    expect(svg).toContain('<clipPath id="dayshaved"><rect x="0" y="0" width="302" height="43.5"/>');
  });

  it("marks the overnight maximum on both sides of the window and says it is not billed", () => {
    expect(svg.match(/stroke-dasharray="2 2"/g)).toHaveLength(2);
    expect(svg).toContain("not billed");
  });

  it("names the month, the billed peak and the held level for a screen reader", () => {
    expect(svg).toMatch(/aria-label="[^"]*July[^"]*400 kW[^"]*150 kW/);
  });

  it("says so plainly when there is no day, and never draws NaN", () => {
    const empty = daySVG({ ...ROW, day_kw: [] }, DAY_AXIS, 302, 84);
    expect(empty).toContain("No day profile");
    expect(empty).not.toContain("NaN");
    expect(daySVG(DAY_ROW, undefined, 302, 84)).toContain("No day profile");
  });
});

describe("drawerHTML confidence", () => {
  it("shows the confidence tier and names the predicates that failed", () => {
    const html = drawerHTML(
      { ...DAY_ROW, confidence: "LOW", confidence_reasons: ["within_single_meter_cap"] },
      {},
      DAY_AXIS,
    );
    expect(html).toContain('class="chip lo"');
    expect(html).toContain("within single meter cap");
    expect(html).toContain('class="billed"');
  });
});
