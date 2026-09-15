import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
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

import { lookup, lookupHTML, parseQuery, similarity } from "../public/app.js";

const ADDRESS_CASES = JSON.parse(
  readFileSync(new URL("../tests/fixtures/address_cases.json", import.meta.url), "utf8"),
);

describe("parseQuery", () => {
  it("parses every shared case exactly as the Python index builder does", () => {
    for (const c of ADDRESS_CASES.cases) {
      expect(parseQuery(c.query, ADDRESS_CASES.towns, ADDRESS_CASES.abbreviations), c.query)
        .toEqual({ street: c.street, town: c.town });
    }
  });
});

describe("similarity", () => {
  it("is 1 for identical strings and 0 for strings sharing nothing", () => {
    expect(similarity("385 PLANTATION ST", "385 PLANTATION ST")).toBe(1);
    expect(similarity("ABC", "XYZ")).toBe(0);
  });
});

const INDEX = {
  index_schema_version: "1.0.0",
  towns: ["WORCESTER"],
  abbreviations: ADDRESS_CASES.abbreviations,
  statuses: {
    ranked: "On the ranked list.",
    below_floor: "Screened out: under the floor. That is a finding, not a missing row.",
    no_floor_area: "No floor area.",
  },
  entries: [
    { key: "385 PLANTATION ST", addr: "385 PLANTATION ST", loc_id: "F_1", status: "ranked",
      list: "modeled", rank: 1, source: "modeled", archetype: "university", sqft: 1628495,
      avg_12mo_kw: 3957.7, rate_class: "G-3", annual_savings_usd: 31440, confidence: "MED" },
    { key: "70 JAMES ST", addr: "70 JAMES ST", loc_id: "F_2", status: "below_floor",
      list: "", rank: null, source: "comstock", archetype: "warehouse", sqft: 2000,
      avg_12mo_kw: 12, rate_class: "G-2", annual_savings_usd: 400, confidence: "HIGH" },
    { key: "10 ELBRIDGE ST", addr: "10 ELBRIDGE ST", loc_id: "F_3", status: "no_floor_area",
      list: "", rank: null, source: "comstock", archetype: "warehouse", sqft: null,
      avg_12mo_kw: 0, rate_class: "G-2", annual_savings_usd: 0, confidence: "LOW" },
  ],
};

describe("lookup", () => {
  it("finds an exact match whatever form the address was pasted in", () => {
    const r = lookup(INDEX, "385 Plantation Street, Worcester, MA 01605");
    expect(r.kind).toBe("exact");
    expect(r.matches.map((m) => m.loc_id)).toEqual(["F_1"]);
  });

  it("offers the nearest address for a typo, and calls it approximate", () => {
    const r = lookup(INDEX, "385 Plantaton St");
    expect(r.kind).toBe("approximate");
    expect(r.matches[0].loc_id).toBe("F_1");
  });

  it("recognises an address in a town that is not covered", () => {
    const r = lookup(INDEX, "12 Main St, Springfield, MA");
    expect(r.kind).toBe("outside");
    expect(r.town).toBe("SPRINGFIELD");
  });

  it("returns none when nothing is close", () => {
    expect(lookup(INDEX, "9999 Nowhere Rd").kind).toBe("none");
  });

  it("does nothing for an empty query", () => {
    expect(lookup(INDEX, "   ").kind).toBe("empty");
  });
});

describe("lookupHTML", () => {
  it("says an uncovered town was not screened, which differs from screened out", () => {
    const html = lookupHTML(lookup(INDEX, "12 Main St, Springfield"), INDEX);
    expect(html).toContain("SPRINGFIELD");
    expect(html).toMatch(/not been screened/);
    expect(html).toContain("WORCESTER");
  });

  it("labels fuzzy matches as approximate", () => {
    expect(lookupHTML(lookup(INDEX, "385 Plantaton St"), INDEX)).toMatch(/approximate/i);
  });

  it("makes a ranked match a button that knows its list, and a screened-out one a statement", () => {
    const ranked = lookupHTML(lookup(INDEX, "385 Plantation St"), INDEX);
    expect(ranked).toMatch(/<button[^>]*class="hit"[^>]*data-id="F_1"[^>]*data-list="modeled"/);
    expect(ranked).toContain("Rank 1");

    const out = lookupHTML(lookup(INDEX, "70 James Street"), INDEX);
    expect(out).not.toContain("<button");
    expect(out).toContain("That is a finding, not a missing row.");
  });

  it("escapes the address, which came from an assessor record", () => {
    const evil = { ...INDEX, entries: [{ ...INDEX.entries[1], key: "1 X ST",
      addr: '<img src=x onerror="alert(1)">' }] };
    const html = lookupHTML(lookup(evil, "1 X St"), evil);
    expect(html).not.toContain("<img");
  });

  it("says what the index holds when nothing matches", () => {
    const html = lookupHTML(lookup(INDEX, "9999 Nowhere Rd"), INDEX);
    expect(html).toContain("3 addressed parcels");
    expect(html).toMatch(/residential/);
  });
});

import { sitingText, wallHTML } from "../public/app.js";

const RULE = { clearance_ft: 10, min_wall_run_ft: 13.1 };

describe("sitingText", () => {
  it("states a clear run with its direction and says it is not a green light", () => {
    const text = sitingText(
      { siting: "clear", wall_run_ft: 288.7, wall_bearing_deg: 228, wall_facing: "SW" }, RULE,
    );
    expect(text).toContain("289 ft");
    expect(text).toContain("SW");
    expect(text).toContain("228°");
    expect(text).toContain("10 ft");
    expect(text).toMatch(/not a green light/i);
  });

  it("states a screen-out as a finding, with the threshold it failed", () => {
    const text = sitingText({ siting: "screened_out", wall_run_ft: 0 }, RULE);
    expect(text).toMatch(/^Screened out/);
    expect(text).toContain("0 ft");
    expect(text).toContain("13.1 ft");
  });

  it("says a parcel with no roofprint was not assessed, and why", () => {
    const text = sitingText({ siting: "no_roofprint", wall_run_ft: null }, RULE);
    expect(text).toMatch(/^Not assessed/);
    expect(text).toMatch(/neighbouring/);
  });

  it("never prints undefined or NaN for a row without a result", () => {
    const text = sitingText({}, undefined);
    expect(text).toMatch(/^Not assessed/);
    expect(text).not.toMatch(/undefined|NaN/);
  });
});

describe("wallHTML", () => {
  it("draws a hidden, unclickable mark only when the row has a wall", () => {
    const html = wallHTML({ loc_id: "A", wall: "M1,2L3,4" });
    expect(html).toContain('class="wall"');
    expect(html).toContain('data-id="A"');
    expect(html).toContain('pointer-events="none"');
    expect(html).not.toContain("var(--signal)");
    expect(wallHTML({ loc_id: "B", wall: "" })).toBe("");
  });

  it("escapes the path it was handed", () => {
    expect(wallHTML({ loc_id: "A", wall: '"><script>' })).not.toContain("<script>");
  });
});

describe("drawerHTML siting", () => {
  it("carries the siting sentence", () => {
    const html = drawerHTML(
      { ...ROW, siting: "screened_out", wall_run_ft: 0 }, {}, undefined, RULE,
    );
    expect(html).toContain("<dt>Siting</dt>");
    expect(html).toContain("Screened out");
  });
});

import { calibrationHTML } from "../public/app.js";

const CAL = {
  year: 2025,
  criterion: { hour_tolerance_h: 1, months_required: 9, load_factor_tolerance_pct: 15, load_factor_months_required: 12 },
  by_rate: {
    "G-2": { n_parcels: 380, months_hour_ok: 10, months_load_factor_ok: 12, passes: true,
             peak_shape_ours: Array(12).fill(0.9), peak_shape_mecols: Array(12).fill(0.8) },
    "G-3": { n_parcels: 148, months_hour_ok: 7, months_load_factor_ok: 11, passes: false,
             peak_shape_ours: Array(12).fill(1), peak_shape_mecols: Array(12).fill(1) },
  },
};

describe("calibrationHTML", () => {
  it("states the declared criterion and both results plainly, pass or not", () => {
    const html = calibrationHTML(CAL);
    expect(html).toContain("10 of 12");
    expect(html).toContain("7 of 12");
    expect(html).toContain("Passes");
    expect(html).toContain("Does not pass");
    expect(html).toContain("15%");
    expect(html).toMatch(/not validation/);
  });

  it("says an unrun check is unreported, not failed", () => {
    const html = calibrationHTML({ status: "not run: file missing. The result is unreported, not failed." });
    expect(html).toContain("unreported, not failed");
    expect(html).not.toContain("<table");
  });

  it("draws two lines per rate and never spends the accent", () => {
    const html = calibrationHTML(CAL);
    expect(html.match(/<polyline/g)).toHaveLength(4);
    expect(html).not.toContain("var(--signal)");
  });
});

describe("methodHTML towns", () => {
  it("names every covered town with its own assessor year", () => {
    const { prose } = methodHTML({
      ...METHOD,
      towns: [
        { name: "Worcester", slug: "worcester", assess_fy: 2026 },
        { name: "Fall River", slug: "fall-river", assess_fy: 2026 },
        { name: "Lowell", slug: "lowell", assess_fy: 2026 },
      ],
    });
    expect(prose).toContain("Worcester (assessor FY 2026)");
    expect(prose).toContain("Fall River (assessor FY 2026)");
    expect(prose).toContain("Lowell (assessor FY 2026)");
  });
});
