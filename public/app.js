// The page computes nothing. Every figure it draws was handed to it by
// scripts/build_site.py, so what is on screen is provably what the scorer
// produced. The only arithmetic here is scaling a normalised series to pixels.

// 2: the page loads index.json, then one ranked payload per town.
const SUPPORTED_MAJOR = "2";

export function fmtMoney(n) {
  return "$" + Math.round(Number(n) || 0).toLocaleString("en-US");
}

export function chipClass(conf) {
  return conf === "HIGH" ? "hi" : conf === "MED" ? "med" : "lo";
}

function esc(value) {
  return String(value == null ? "" : value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

// A 12-point series, already normalised to its own max by the build. The peak
// dot is the only place --signal is spent here; the line and the area fill are
// neutral, per the accent discipline in DESIGN.md.
export function sparkSVG(values, w, h) {
  const a = (values || []).map((v) => Number(v) || 0);
  if (a.length === 0) return `<svg class="spark" width="${w}" height="${h}"></svg>`;
  const n = a.length;
  const max = Math.max(...a);
  const scale = max > 0 ? 1 / max : 0;
  const x = (i) => ((i / Math.max(1, n - 1)) * (w - 2) + 1).toFixed(1);
  const y = (v) => (h - 1 - v * scale * (h - 4)).toFixed(1);

  let peak = 0;
  for (let i = 1; i < n; i++) if (a[i] > a[peak]) peak = i;

  const pts = a.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `M1,${h - 1} L${pts.split(" ").join(" L")} L${w - 1},${h - 1} Z`;

  return (
    `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">` +
    `<path d="${area}" fill="var(--ink-2)" opacity=".16"/>` +
    `<polyline points="${pts}" fill="none" stroke="var(--ink-2)" stroke-width="1.1" stroke-linejoin="round"/>` +
    `<circle cx="${x(peak)}" cy="${y(a[peak])}" r="1.9" fill="var(--signal)"/>` +
    `</svg>`
  );
}

// The towns the build produced, in the order it produced them. The first is
// the default. Rendered here rather than baked into index.html so adding a
// municipality is a build change and not an HTML edit.
export function townButtonsHTML(towns, currentSlug) {
  return (towns || [])
    .map(
      (t) =>
        `<button type="button" data-slug="${esc(t.slug)}" ` +
        `aria-pressed="${String(t.slug === currentSlug)}">${esc(t.name)}</button>`,
    )
    .join("");
}

// Every figure here was counted by the pipeline. The page only formats them.
export function countsLine(counts) {
  const c = counts || {};
  const ex = c.exported || {};
  return (
    `${Number(c.parcels_in || 0).toLocaleString()} parcels screened · ` +
    `${Number(c.kept || 0).toLocaleString()} in band · ` +
    `${Number(c.sweet_spot || 0).toLocaleString()} in the sweet spot · ` +
    `showing top ${ex.comstock} measured and ${ex.modeled} modelled`
  );
}

// An unresolved row shows what the assessor actually recorded, never the
// holding company dressed up as an occupant.
function siteName(row) {
  return row.occupant ? row.occupant : row.use_desc || row.archetype;
}

export function rowHTML(row) {
  const rate = row.rate_class === "G-2" ? "g2" : "g3";
  return (
    `<tr data-id="${esc(row.loc_id)}" tabindex="0" role="button" ` +
    `aria-label="${esc(siteName(row))}, estimated saving ${fmtMoney(row.annual_savings_usd)} a year">` +
    `<td class="rank">${row.rank}</td>` +
    `<td><div class="who">${esc(siteName(row))}</div>` +
    `<div class="where">${esc(row.site_addr)} &middot; ` +
    `<span class="src">${esc(String(row.source).toUpperCase())}</span></div></td>` +
    `<td>${sparkSVG(row.window_kw, 68, 22)}</td>` +
    `<td class="r kw">${Number(row.peak_to_avg).toFixed(1)}&times;<br>` +
    `${Math.round(row.peak_kw)}/${Math.round(row.avg_12mo_kw)} kW</td>` +
    `<td class="r"><span class="rate ${rate}">${esc(row.rate_class)}</span></td>` +
    `<td class="r money">${fmtMoney(row.annual_savings_usd)}</td>` +
    `<td><span class="chip ${chipClass(row.confidence)}">${esc(row.confidence)}</span></td>` +
    `</tr>`
  );
}

// D4: the argument is never behind a click. The selected row expands in place.
export function reasonRowHTML(row) {
  const flags = (row.flags || [])
    .map((f) => `<span class="eyebrow">${esc(f.replace(/_/g, " "))}</span>`)
    .join("");
  return (
    `<tr class="leadreason"><td colspan="7">` +
    `<p class="reason">${esc(row.reason)}</p>` +
    `<div class="mini">` +
    `<span class="eyebrow">${esc(row.use_desc)}</span>` +
    `<span class="eyebrow">Shaveable ${Math.round(row.shaveable_kw)} kW</span>` +
    `<span class="eyebrow">${Math.round(row.sqft).toLocaleString("en-US")} sq ft</span>` +
    flags +
    `</div></td></tr>`
  );
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function hh(hour) {
  return String(hour).padStart(2, "0") + ":00";
}

// The worst billed day, on a 24-hour axis. Every value arrives normalised to
// one shared scale by site_data.day_profile, and the tariff's hours arrive in
// `axis`, so this only maps hours and 0-1 values to pixels. The shaved peak is
// the load drawn a second time in --signal and clipped to the region above the
// held line: a shape, not a subtraction.
export function daySVG(row, axis, w, h) {
  const a = ((row && row.day_kw) || []).map((v) => Number(v) || 0);
  if (!a.length || !axis) {
    return `<p class="dayempty">No day profile for this site.</p>`;
  }
  const pad = 1;
  const ph = h - 14; // plot height; the bottom 14px carry the hour labels
  const x = (hour) => (pad + (hour / 24) * (w - 2 * pad)).toFixed(1);
  const y = (v) => (pad + (1 - v) * (ph - 2)).toFixed(1);

  const start = axis.window_start_hour;
  const end = axis.window_end_hour;
  const step = axis.step_hours;
  const base = (ph - pad).toFixed(1);
  const pts = a.map((v, i) => `${x(start + i * step)},${y(v)}`);
  const lastX = x(start + (a.length - 1) * step);
  const area = `M${x(start)},${base} L${pts.join(" L")} L${lastX},${base} Z`;
  const held = y(Number(row.day_held) || 0);
  const night = y(Number(row.day_offpeak) || 0);

  const month = MONTHS[(row.peak_day_month || 0) - 1] || "";
  const peakKw = (row.monthly_billed_demand_kw || [])[(row.peak_day_month || 0) - 1];
  const label =
    `Worst billed day${month ? " in " + month : ""}: billed peak ` +
    `${Math.round(Number(peakKw) || 0)} kW, held to ` +
    `${Math.round(Number(row.peak_day_held_kw) || 0)} kW. The shaded band is the ` +
    `billed ${hh(start)} to ${hh(end)} window; the dashed line outside it is the ` +
    `overnight maximum, which is not billed.`;

  const tick = (hour, anchor) =>
    `<text x="${x(hour)}" y="${h - 2}" text-anchor="${anchor}" font-size="9" ` +
    `font-family="var(--mono)" fill="var(--ink-3)">${hh(hour)}</text>`;

  return (
    `<svg class="day" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" ` +
    `aria-label="${esc(label)}">` +
    `<defs><clipPath id="dayshaved"><rect x="0" y="0" width="${w}" height="${held}"/></clipPath></defs>` +
    `<rect class="billed" x="${x(start)}" y="0" ` +
    `width="${(((end - start) / 24) * (w - 2 * pad)).toFixed(1)}" height="${ph}" ` +
    `fill="var(--ink-2)" opacity=".05"/>` +
    `<line x1="${x(0)}" y1="${night}" x2="${x(start)}" y2="${night}" ` +
    `stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="2 2"/>` +
    `<line x1="${x(end)}" y1="${night}" x2="${x(24)}" y2="${night}" ` +
    `stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="2 2"/>` +
    `<path d="${area}" fill="var(--ink-2)" opacity=".16"/>` +
    `<path d="${area}" fill="var(--signal)" opacity=".55" clip-path="url(#dayshaved)"/>` +
    `<polyline points="${pts.join(" ")}" fill="none" stroke="var(--ink-2)" ` +
    `stroke-width="1.1" stroke-linejoin="round"/>` +
    `<line x1="${x(start)}" y1="${held}" x2="${lastX}" y2="${held}" ` +
    `stroke="var(--ink)" stroke-width="1" stroke-dasharray="3 2"/>` +
    tick(0, "start") + tick(start, "middle") + tick(end, "middle") + tick(24, "end") +
    `</svg>`
  );
}

// The siting screen is a screen-out, never a green light. Every number here was
// computed by the build; the page only chooses which sentence to show.
export function sitingText(row, rule) {
  const r = rule || {};
  const run = Math.round(Number(row && row.wall_run_ft) || 0);
  const clearance = r.clearance_ft != null ? `${r.clearance_ft} ft` : "the required";
  if (row && row.siting === "clear") {
    return (
      `Longest wall with ${clearance} of parcel-side clearance: ${run} ft, facing ` +
      `${row.wall_facing} (${row.wall_bearing_deg}°). Not a green light: the screen ` +
      `cannot see loading docks, fire lanes, egress or where the service entrance is.`
    );
  }
  if (row && row.siting === "screened_out") {
    return (
      `Screened out: the longest wall with ${clearance} of clearance to the parcel ` +
      `line runs ${run} ft, under the ${r.min_wall_run_ft} ft two cabinets need. ` +
      `Stated as a finding.`
    );
  }
  if (row && row.siting === "no_roofprint") {
    return (
      `Not assessed: no roofprint sits on this parcel. The building's roof is mapped ` +
      `mostly on a neighbouring lot, so its walls cannot be attributed here.`
    );
  }
  return `Not assessed: there is no parcel polygon to measure against.`;
}

// Hatched in ink, never the accent. Hidden until its parcel is selected: at town
// scale a median wall is two or three units long, and 172 of them at once are noise.
export function wallHTML(row) {
  if (!row || !row.wall) return "";
  return (
    `<path class="wall" data-id="${esc(row.loc_id)}" d="${esc(row.wall)}" fill="none" ` +
    `stroke="var(--ink)" stroke-width="2.4" stroke-dasharray="1.2 0.8" ` +
    `stroke-linecap="butt" pointer-events="none"/>`
  );
}

export function drawerHTML(row, flagMeanings, dayAxis, sitingRule) {
  const flags = (row.flags || [])
    .map(
      (f) =>
        `<div><dt>${esc(f.replace(/_/g, " "))}</dt>` +
        `<dd>${esc((flagMeanings || {})[f] || "")}</dd></div>`,
    )
    .join("");
  const source = row.occupant_source
    ? ` Occupant verified at <a href="${esc(row.occupant_source)}" rel="noopener">` +
      `${esc(row.occupant_source)}</a>.`
    : " Occupant not yet resolved; the name shown is the assessor's use description.";
  const failed = (row.confidence_reasons || []).map((r) => r.replace(/_/g, " ")).join(" · ");
  const month = MONTHS[(row.peak_day_month || 0) - 1];
  return (
    `<div class="eyebrow">Detail &middot; ${esc(siteName(row))}</div>` +
    `<div class="dayprofile">${daySVG(row, dayAxis, 302, 84)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Worst billed day` +
    `${month ? " &middot; " + esc(month) : ""} &middot; shaded = billed window ` +
    `&middot; accent = what the battery removes</div>` +
    `<div class="dayprofile">${sparkSVG(row.window_kw, 302, 36)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Billed demand by month &middot; peak marked</div>` +
    `<dl class="kv">` +
    `<div><dt>Address</dt><dd>${esc(row.site_addr)}, ${esc(row.city)}</dd></div>` +
    `<div><dt>Owner of record</dt><dd>${esc(row.owner)}</dd></div>` +
    `<div><dt>Floor area</dt><dd>${Math.round(row.sqft).toLocaleString("en-US")} sq ft</dd></div>` +
    `<div><dt>Shaveable</dt><dd>${Math.round(row.shaveable_kw)} kW</dd></div>` +
    `<div><dt>Shaved fraction</dt><dd>${(row.shaved_fraction * 100).toFixed(1)}%</dd></div>` +
    `<div><dt>Load shape</dt><dd>${esc(row.archetype)} (${esc(row.source)})</dd></div>` +
    `<div><dt>Confidence</dt><dd><span class="chip ${chipClass(row.confidence)}">` +
    `${esc(row.confidence)}</span>${failed ? " failed: " + esc(failed) : ""}</dd></div>` +
    `<div><dt>Siting</dt><dd>${esc(sitingText(row, sitingRule))}</dd></div>` +
    flags +
    `</dl>` +
    `<div class="lineage"><strong>How we got here:</strong> use description ` +
    `"${esc(row.use_desc)}" maps to the ${esc(row.archetype)} archetype, ` +
    `${esc(row.source)}-backed, scaled to ${Math.round(row.sqft).toLocaleString("en-US")} sq ft.` +
    `${source} An estimate from public records. Get the utility bill before anyone signs.` +
    `</div>`
  );
}

// The MECOLS class-shape check. Every figure, including the percentage and both
// normalised shapes, arrives from calibration.py; this only lays them out.
function calShapeSVG(rate, r) {
  const w = 240;
  const h = 60;
  const x = (i) => (4 + (i / 11) * (w - 8)).toFixed(1);
  const y = (v) => (h - 4 - (Number(v) || 0) * (h - 8)).toFixed(1);
  const line = (vals) => (vals || []).map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    `<figure class="calshape"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" ` +
    `aria-label="${esc(rate)}: monthly billed peak, this tool against MECOLS, each ` +
    `normalised to its own annual maximum.">` +
    `<polyline points="${line(r.peak_shape_mecols)}" fill="none" stroke="var(--ink-3)" ` +
    `stroke-width="1.1" stroke-dasharray="3 2"/>` +
    `<polyline points="${line(r.peak_shape_ours)}" fill="none" stroke="var(--ink-2)" stroke-width="1.4"/>` +
    `</svg><figcaption class="eyebrow">${esc(rate)} &middot; solid = this tool &middot; ` +
    `dashed = MECOLS</figcaption></figure>`
  );
}

export function calibrationHTML(cal) {
  if (!cal || cal.status || !cal.by_rate) {
    return (
      `<p>${esc((cal && cal.status) ||
        "The class-shape check has not been run, so there is no result to report yet.")}</p>`
    );
  }
  const c = cal.criterion || {};
  const rates = Object.keys(cal.by_rate);
  const rows = rates
    .map((rate) => {
      const r = cal.by_rate[rate];
      return (
        `<tr><td>${esc(rate)}</td><td class="v r">${esc(r.n_parcels)}</td>` +
        `<td class="v r">${esc(r.months_hour_ok)} of 12</td>` +
        `<td class="v r">${esc(r.months_load_factor_ok)} of 12</td>` +
        `<td>${r.passes ? "Passes" : "Does not pass"}</td></tr>`
      );
    })
    .join("");
  return (
    `<p>The ComStock-backed rows, summed by rate class, against National Grid's ` +
    `published class average load shapes for ${esc(cal.year)}. Declared before the ` +
    `first run: hour of the monthly billed peak within &plusmn;${esc(c.hour_tolerance_h)} h ` +
    `in at least ${esc(c.months_required)} of 12 months, and monthly load factor within ` +
    `&plusmn;${esc(c.load_factor_tolerance_pct)}% in all 12. A modest sanity check, too ` +
    `weak to validate the model.</p>` +
    `<div class="tablewrap"><table class="assum"><thead><tr><th>Rate</th>` +
    `<th class="r">Parcels</th><th class="r">Hour of peak</th>` +
    `<th class="r">Load factor</th><th>Result</th></tr></thead>` +
    `<tbody>${rows}</tbody></table></div>` +
    rates.map((rate) => calShapeSVG(rate, cal.by_rate[rate])).join("")
  );
}

export function methodHTML(payload) {
  const cov = payload.coverage || {};
  const occ = payload.occupants || {};
  const reg = payload.regression || {};

  const assumptions = (payload.assumptions || [])
    .map(
      (a) =>
        `<tr><td>${esc(a.note || a.key)}</td>` +
        `<td class="v r">${esc(a.value)}</td>` +
        `<td class="s">${esc(a.provenance)} &middot; ${esc(a.source)}</td></tr>`,
    )
    .join("");

  // The payload shape is {ceiling, by_source: {comstock: {...}, modeled: {...}}},
  // one row per ranked list. Read it, never assert a figure: an earlier
  // revision of the Python side printed "~1.000 by construction" above a table
  // showing 0.878, and a method page that contradicts its own numbers is the
  // one thing this artifact cannot afford.
  const bySource = (reg && reg.by_source) || {};
  const regressionRows = Object.keys(bySource)
    .map((name) => {
      const r = bySource[name];
      if (r.skipped)
        return (
          `<tr><td>${esc(name)}</td><td class="v r">${esc(r.n)}</td>` +
          `<td class="v r">&mdash;</td><td class="v r">&mdash;</td></tr>`
        );
      return (
        `<tr><td>${esc(name)}</td><td class="v r">${esc(r.n)}</td>` +
        `<td class="v r">${r.r2_size_and_rate.toFixed(3)}</td>` +
        `<td class="v r">${r.r2_with_archetype.toFixed(3)}</td></tr>`
      );
    })
    .join("");
  const verdicts = Object.keys(bySource)
    .filter((name) => !bySource[name].skipped)
    .map((name) => {
      const r = bySource[name];
      return r.archetype_adds_little
        ? `<p><strong>${esc(name)}: the archetype layer is adding little.</strong> ` +
            `Size and rate class alone explain ${r.r2_size_and_rate.toFixed(3)}, above the ` +
            `${Number(reg.ceiling).toFixed(2)} threshold declared before the numbers were ` +
            `computed. Read this list as close to a size sort.</p>`
        : `<p><strong>${esc(name)}: the archetype layer adds spread.</strong> ` +
            `Size and rate class alone explain ${r.r2_size_and_rate.toFixed(3)}; the load ` +
            `shape accounts for the rest of the ordering.</p>`;
    })
    .join("");

  const regressionBlock = reg.status
    ? `<p>${esc(reg.status)}</p>`
    : `<div class="tablewrap"><table class="assum"><thead><tr>` +
      `<th>List</th><th class="r">n</th>` +
      `<th class="r">R&sup2; vs size &times; rate</th>` +
      `<th class="r">R&sup2; vs size &times; rate &times; archetype</th>` +
      `</tr></thead><tbody>${regressionRows}</tbody></table></div>` +
      verdicts +
      `<p>The second column is high because the score is a deterministic ` +
      `function of exactly three public assessor fields and nothing else. It ` +
      `falls short of 1.000 because this fit is linear in floor area within an ` +
      `archetype and the scorer is not: the shaveable kilowatts come from a ` +
      `root-find against a fixed energy budget and a 250 kW power cap, so a ` +
      `site large enough to saturate the cap stops scaling with its floor area. ` +
      `That kink is what separates this from a size sort.</p>`;

  const prose =
    `<h2>What this is</h2>` +
    `<p class="lead">A structured prior over three public assessor fields. Nothing ` +
    `here has seen a meter, so it can order a call list and cannot underwrite a ` +
    `project.</p>` +
    `<p>Demand is billed on the greatest fifteen-minute peak between 8 a.m. and ` +
    `9 p.m., Monday to Friday, excluding nine observed holidays. A three-in-the-` +
    `morning spike is free. Everything here is computed inside that window and ` +
    `nowhere else.</p>` +
    `<p>${esc(cov.parcels_total)} parcels screened; ${esc(cov.kept)} carry enough ` +
    `demand charge to be worth a conversation; ${esc(cov.sweet_spot)} sit in the ` +
    `sweet spot: the expensive G-2 rate plus a spiky shape.</p>` +
    ((payload.towns || []).length
      ? `<p>Covers ${(payload.towns || [])
          .map((t) => `${esc(t.name)} (assessor FY ${esc(t.assess_fy)})`)
          .join(", ")}.</p>`
      : "") +
    `<h2 style="margin-top:16px">Does the archetype layer earn its place?</h2>` +
    regressionBlock +
    `<h2 style="margin-top:16px">Does the aggregate look like National Grid's classes?</h2>` +
    calibrationHTML(payload.calibration) +
    `<h2 style="margin-top:16px">Every assumption, and where it came from</h2>` +
    `<p style="margin-bottom:8px">This table is rendered from the same file the ` +
    `scorer imports, so the published numbers cannot drift from the computed ones.</p>` +
    `<div class="tablewrap"><table class="assum">` +
    `<thead><tr><th>Assumption</th><th class="r">Value</th><th>Source</th></tr></thead>` +
    `<tbody>${assumptions}</tbody></table></div>`;

  const limitations = (payload.limitations || [])
    .map((l) => `<li>${esc(l.statement)}</li>`)
    .join("");
  const gaps = (payload.known_gaps || [])
    .map((g) => `<li>${esc(g.statement)}</li>`)
    .join("");

  const cannot =
    `<h2>What this cannot tell you</h2><ul>${limitations}</ul>` +
    `<h2 style="margin-top:14px">Specified and not yet built</h2><ul>${gaps}</ul>`;

  const foot =
    `Lineage: ${Object.values(payload.lineage || {}).map(esc).join(" &middot; ")}. ` +
    `Occupant names hand-resolved for ${esc(occ.top_n_resolved)} of ${esc(occ.top_n)} ` +
    `top-ranked rows. The rest show the assessor's use description, because the ` +
    `owner of record is usually a holding company.`;

  return { prose, cannot, foot };
}

//: Fill opacity floor and ceiling. A parcel at the floor must still be
//: visible -- an invisible row is a row the reader cannot click.
const FILL_MIN = 0.16;
const FILL_MAX = 0.78;

export function parcelHTML(row, maxSaving) {
  const share = maxSaving > 0 ? Number(row.annual_savings_usd) / maxSaving : 0;
  const opacity = (FILL_MIN + (FILL_MAX - FILL_MIN) * Math.min(1, Math.max(0, share)))
    .toFixed(3);
  const stroke = row.rate_class === "G-2" ? "var(--g2)" : "var(--g3)";
  return (
    `<g class="parcel" data-id="${esc(row.loc_id)}" tabindex="0" role="button" ` +
    `aria-label="${esc(siteName(row))}, rate ${esc(row.rate_class)}, estimated ` +
    `saving ${fmtMoney(row.annual_savings_usd)} a year">` +
    `<path class="pfill" d="${esc(row.path)}" fill="var(--signal)" ` +
    `fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.1"/>` +
    `</g>`
  );
}

export function mapSVG(rows, viewBox, maxSaving) {
  const drawn = (rows || []).filter((r) => r.path);
  if (!drawn.length) {
    return (
      `<svg class="mapsvg" viewBox="${esc(viewBox)}" role="img" ` +
      `aria-label="No mapped parcel in this view."></svg>` +
      `<p class="whysplit">No mapped parcel in this view. The ranked list is ` +
      `unaffected; only the drawing has nothing to show.</p>`
    );
  }
  return (
    `<svg class="mapsvg" viewBox="${esc(viewBox)}" role="img" ` +
    `aria-label="Worcester parcels, shaded by estimated annual demand-charge ` +
    `saving and outlined by rate class.">` +
    `<g id="parcels">${drawn.map((r) => parcelHTML(r, maxSaving)).join("")}</g>` +
    `<g id="walls">${drawn.map(wallHTML).join("")}</g>` +
    `</svg>`
  );
}

export function parcelSelectionClasses(rows, selectedId) {
  const drawn = (rows || []).filter((r) => r.path);
  const out = {};
  const anySelected = selectedId != null;
  for (const row of drawn) {
    const on = row.loc_id === selectedId;
    out[row.loc_id] = on ? "parcel on" : anySelected ? "parcel dim" : "parcel";
  }
  return out;
}

// ---------------------------------------------------------------------------
// address lookup. parseQuery is src/shave/addresses.py parse_query in
// JavaScript; both are tested against tests/fixtures/address_cases.json, and
// the abbreviation table comes from the index rather than living here.
// ---------------------------------------------------------------------------

const SUPPORTED_INDEX_MAJOR = "1";
const STATE_TOKENS = new Set(["MA", "MASS", "MASSACHUSETTS"]);
const ZIPPISH = /^\d{4,5}$/;
//: A fuzzy candidate must share at least this share of trigrams to be offered.
const APPROX_MIN = 0.4;
const APPROX_MAX_RESULTS = 5;

function addrTokens(text) {
  return String(text || "").toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
}

export function parseQuery(query, towns, abbrev) {
  const text = typeof query === "string" ? query : "";
  const cut = text.indexOf(",");
  let street = addrTokens(cut < 0 ? text : text.slice(0, cut));
  let town = [];
  if (cut >= 0) {
    town = addrTokens(text.slice(cut + 1)).filter((t) => !STATE_TOKENS.has(t) && !ZIPPISH.test(t));
  } else {
    while (
      street.length > 1 &&
      (STATE_TOKENS.has(street[street.length - 1]) || ZIPPISH.test(street[street.length - 1]))
    ) {
      street.pop();
    }
    for (const name of towns || []) {
      const words = addrTokens(name);
      const tail = street.slice(street.length - words.length);
      if (street.length > words.length && words.every((w, i) => tail[i] === w)) {
        street = street.slice(0, street.length - words.length);
        town = words;
        break;
      }
    }
  }
  const map = abbrev || {};
  return {
    street: street.map((t) => (Object.hasOwn(map, t) ? map[t] : t)).join(" "),
    town: town.join(" "),
  };
}

function trigrams(s) {
  const padded = `  ${s} `;
  const out = new Set();
  for (let i = 0; i + 3 <= padded.length; i++) out.add(padded.slice(i, i + 3));
  return out;
}

export function similarity(a, b) {
  const A = trigrams(a);
  const B = trigrams(b);
  let shared = 0;
  for (const t of A) if (B.has(t)) shared++;
  const union = A.size + B.size - shared;
  return union ? shared / union : 0;
}

export function lookup(index, query) {
  const q = parseQuery(query, index.towns, index.abbreviations);
  if (!q.street) return { kind: "empty", matches: [], town: q.town };
  if (q.town && !index.towns.includes(q.town)) {
    return { kind: "outside", matches: [], town: q.town };
  }
  const exact = index.entries.filter((e) => e.key === q.street);
  if (exact.length) return { kind: "exact", matches: exact, town: q.town };
  const near = index.entries
    .map((e) => ({ e, s: similarity(q.street, e.key) }))
    .filter((c) => c.s >= APPROX_MIN)
    .sort((a, b) => b.s - a.s || (a.e.key < b.e.key ? -1 : a.e.key > b.e.key ? 1 : 0))
    .slice(0, APPROX_MAX_RESULTS)
    .map((c) => c.e);
  return { kind: near.length ? "approximate" : "none", matches: near, town: q.town };
}

function hitHTML(entry, index) {
  const sentence = (index.statuses || {})[entry.status] || "";
  const listName = entry.list === "modeled" ? "Modeled industrial" : "ComStock-backed";
  const facts = [
    entry.archetype ? `${esc(entry.archetype)} (${esc(entry.source)})` : "",
    entry.sqft != null ? `${Number(entry.sqft).toLocaleString("en-US")} sq ft` : "",
    entry.rate_class ? `rate ${esc(entry.rate_class)}` : "",
    entry.status !== "ranked" && entry.annual_savings_usd
      ? `estimated ${fmtMoney(entry.annual_savings_usd)}/yr`
      : "",
  ].filter(Boolean).join(" &middot; ");
  const body =
    `<div class="addr">${esc(entry.addr)}</div>` +
    `<div class="status">${entry.status === "ranked"
      ? `Rank ${esc(entry.rank)} &middot; ${esc(listName)} &middot; ` +
        `${fmtMoney(entry.annual_savings_usd)}/yr &middot; open it in the list`
      : esc(sentence)}</div>` +
    (facts ? `<div class="status">${facts}</div>` : "");
  // Only a ranked parcel has a row to jump to. Anything else is a statement.
  return entry.status === "ranked"
    ? `<li><button type="button" class="hit" data-id="${esc(entry.loc_id)}" ` +
        `data-town="${esc(entry.town || "")}" ` +
        `data-list="${esc(entry.list)}">${body}</button></li>`
    : `<li><div class="hit">${body}</div></li>`;
}

export function lookupHTML(result, index) {
  const towns = (index.towns || []).map(esc).join(", ");
  if (result.kind === "empty") return "";
  if (result.kind === "outside") {
    return (
      `<p class="reason">That address is in ${esc(result.town)}. This screen ` +
      `covers ${towns}, and has not processed ${esc(result.town)} yet, so ` +
      `there is no answer for it here.</p>`
    );
  }
  if (result.kind === "none") {
    return (
      `<p class="reason">No screened parcel matches that address. The index holds ` +
      `the assessor's own site addresses for ${index.entries.length.toLocaleString("en-US")} ` +
      `addressed parcels in ${towns}, commercial and industrial only; a residential ` +
      `parcel, or a building recorded under a different street number, will not ` +
      `appear.</p>`
    );
  }
  const head =
    result.kind === "exact"
      ? `<div class="eyebrow">Exact match</div>`
      : `<div class="eyebrow">No exact match &middot; nearest addresses, approximate, so check the street number</div>`;
  return `${head}<ul class="hits">${result.matches.map((e) => hitHTML(e, index)).join("")}</ul>`;
}

// ---------------------------------------------------------------------------
// wiring. Everything above is pure and tested; everything below touches the DOM.
// ---------------------------------------------------------------------------

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

// Two lists, never merged. `source` selects which one is on screen.
const state = {
  lists: { comstock: [], modeled: [] },
  shown: [],
  method: null,
  selected: null,
  source: "comstock",
  view: "all",
  viewBox: "0 0 620 818",
  dayAxis: null,
  sitingRule: null,
  towns: [],
  town: null,
};

const WHY_SPLIT =
  "ComStock-backed and modelled-industrial rows are ranked separately and never " +
  "against each other. A ComStock magnitude comes from a measured timeseries; a " +
  "modelled one comes from a published intensity and a load factor derived from a " +
  "declared shape. Comparing their dollars would claim an accuracy the second one " +
  "does not have.";

function select(id) {
  state.selected = id;
  $$("#rows tr.leadreason").forEach((tr) => tr.remove());
  $$("#rows tr").forEach((tr) => {
    tr.classList.toggle("on", tr.dataset.id === id);
    tr.classList.toggle("lead", tr.dataset.id === id);
  });
  const row = state.shown.find((r) => r.loc_id === id);
  if (!row) return;
  const tr = $(`#rows tr[data-id="${CSS.escape(id)}"]`);
  if (tr) tr.insertAdjacentHTML("afterend", reasonRowHTML(row));
  $("#drawer").innerHTML = drawerHTML(
    row, (state.method || {}).flag_meanings, state.dayAxis, state.sitingRule,
  );

  // The map is a view onto the table, not a picture beside it.
  const classes = parcelSelectionClasses(state.shown, id);
  $$("#map .parcel").forEach((g) => {
    g.setAttribute("class", classes[g.dataset.id] || "parcel");
  });
  $$("#map .wall").forEach((w) => w.classList.toggle("on", w.dataset.id === id));
}

function draw() {
  const maxSaving = state.shown.reduce(
    (m, r) => Math.max(m, Number(r.annual_savings_usd) || 0), 0,
  );
  $("#map").innerHTML = mapSVG(state.shown, state.viewBox, maxSaving);
  if (state.shown.length) {
    $("#rows").innerHTML = state.shown.map(rowHTML).join("");
    select(state.shown[0].loc_id);
  } else {
    // State the finding this filter actually produced. Blaming the demand
    // floor when the sweet-spot filter is what emptied the list would be a
    // confident, wrong explanation -- worse than no explanation at all.
    const why =
      state.view === "sweet"
        ? `No ${state.source === "comstock" ? "ComStock-backed" : "modelled-industrial"} ` +
          `site here is both on the expensive G-2 rate and spiky enough to clear ` +
          `1.4x its own average. The sweet spot is where an expensive tariff meets ` +
          `a sharp peak, and it needs both.`
        : `Every screened parcel in this list fell below 50 kW average demand, so ` +
          `a 250 kW cabinet has no peak worth shaving.`;
    $("#rows").innerHTML = `<tr><td colspan="7"><p class="reason">${why}</p></td></tr>`;
    $("#drawer").innerHTML = "";
  }
}

function applyFilters() {
  const rows = state.lists[state.source] || [];
  state.shown = state.view === "sweet" ? rows.filter((r) => r.sweet_spot) : rows;
  draw();
}

// One town's payload. The map frame, the day axis and the siting rule are all
// per-town, so switching town replaces them together rather than patching one.
async function loadTown(slug) {
  const ranked = await (await fetch(`/data/towns/${slug}/ranked.json`)).json();
  if (String(ranked.site_schema_version || "").split(".")[0] !== SUPPORTED_MAJOR) {
    throw new Error(`payload schema ${ranked.site_schema_version} is not supported`);
  }
  return ranked;
}

function applyTown(ranked) {
  state.lists = ranked.lists;
  state.viewBox = (ranked.map || {}).view_box || "0 0 620 818";
  state.dayAxis = ranked.day_axis || null;
  state.sitingRule = ranked.siting_rule || null;
  state.town = ranked.town || null;
  state.selected = null;
  $("#counts").textContent = countsLine(ranked.counts);
  // The assessor vintage comes from the export's town block, not from the
  // method payload: `score_parcels` output carries no assess_fy -- that field
  // lives on the parcel frame -- so method.coverage.assess_years is empty.
  // Reading it here also shows the vintage before method.json has loaded.
  const fy = (ranked.town || {}).assess_fy;
  $("#vintage").textContent = fy
    ? `${ranked.town.name} · Assessor FY ${fy}`
    : "Assessor vintage unavailable";
  applyFilters();
}

function townFailureHTML(slug) {
  return (
    `<tr><td colspan="7"><p class="reason">The ranked list for ${esc(slug)} ` +
    `could not be loaded. It is served as static data, so the likely cause is ` +
    `the network. Try again in a moment.</p></td></tr>`
  );
}

async function switchTown(slug) {
  $$("#towns button").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.slug === slug)),
  );
  try {
    applyTown(await loadTown(slug));
  } catch (err) {
    $("#rows").innerHTML = townFailureHTML(slug);
    $("#drawer").innerHTML = "";
  }
}

async function boot() {
  let index;
  try {
    index = await (await fetch("/data/index.json")).json();
  } catch (err) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">The list of covered towns could ` +
      `not be loaded. It is served as static data, so the likely cause is the ` +
      `network. Try again in a moment.</p></td></tr>`;
    return;
  }
  state.towns = index.towns || [];
  const slug = index.default || (state.towns[0] || {}).slug;
  $("#towns").innerHTML = townButtonsHTML(state.towns, slug);
  $("#whysplit").textContent = WHY_SPLIT;
  await switchTown(slug);

  try {
    state.method = await (await fetch("/data/method.json")).json();
    const m = methodHTML(state.method);
    $("#method-prose").innerHTML = m.prose;
    $("#method-cannot").innerHTML = m.cannot;
    $("#method-foot").innerHTML = m.foot;
    // The drawer's flag explanations only exist once the method payload lands.
    if (state.selected) select(state.selected);
  } catch (err) {
    $("#method-prose").innerHTML =
      `<p class="reason">The method page could not be loaded. The ranked list ` +
      `above is unaffected, because it is served as separate static data.</p>`;
  }

  $("#rows").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (tr) select(tr.dataset.id);
  });
  $("#towns").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-slug]");
    if (b && b.getAttribute("aria-pressed") !== "true") switchTown(b.dataset.slug);
  });
  $("#rows").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const tr = e.target.closest("tr[data-id]");
    if (tr) {
      e.preventDefault();
      select(tr.dataset.id);
    }
  });

  $("#map").addEventListener("click", (e) => {
    const g = e.target.closest(".parcel");
    if (!g) return;
    select(g.dataset.id);
    const tr = $(`#rows tr[data-id="${CSS.escape(g.dataset.id)}"]`);
    if (tr) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      tr.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
  });
  $("#map").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const g = e.target.closest(".parcel");
    if (!g) return;
    e.preventDefault();
    select(g.dataset.id);
  });

  const sources = { "src-cs": "comstock", "src-md": "modeled" };
  const views = { "view-all": "all", "view-sweet": "sweet" };
  Object.keys(sources).forEach((id) =>
    $("#" + id).addEventListener("click", () => {
      state.source = sources[id];
      Object.keys(sources).forEach((k) =>
        $("#" + k).setAttribute("aria-pressed", String(k === id)),
      );
      $("#listsrc").textContent = $("#" + id).textContent;
      applyFilters();
    }),
  );
  Object.keys(views).forEach((id) =>
    $("#" + id).addEventListener("click", () => {
      state.view = views[id];
      Object.keys(views).forEach((k) =>
        $("#" + k).setAttribute("aria-pressed", String(k === id)),
      );
      applyFilters();
    }),
  );

  // The address index loads on the first search, never with the page, so the
  // ranked list's first paint does not wait for it.
  let addressIndex = null;
  async function loadAddressIndex() {
    if (addressIndex) return addressIndex;
    const idx = await (await fetch("/data/addresses.json")).json();
    if (String(idx.index_schema_version || "").split(".")[0] !== SUPPORTED_INDEX_MAJOR) {
      throw new Error(`address index ${idx.index_schema_version} not supported`);
    }
    addressIndex = idx;
    return idx;
  }

  // A ranked match opens in the list it belongs to, and in the town it is in.
  // The lists are never merged and the towns are never merged, so the toggles
  // move to that row rather than the row joining this view.
  async function jumpTo(list, id, town) {
    if (town && state.town && town !== state.town.slug) await switchTown(town);
    $(list === "modeled" ? "#src-md" : "#src-cs").click();
    $("#view-all").click();
    select(id);
    const tr = $(`#rows tr[data-id="${CSS.escape(id)}"]`);
    if (tr) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      tr.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
      tr.focus({ preventScroll: true });
    }
  }

  $("#lookup").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#addr");
    const out = $("#lookup-result");
    input.setAttribute("aria-busy", "true");
    out.innerHTML = `<p class="whysplit">Loading the address index&hellip;</p>`;
    try {
      const idx = await loadAddressIndex();
      out.innerHTML = lookupHTML(lookup(idx, input.value), idx);
    } catch (err) {
      out.innerHTML =
        `<p class="reason">The address index could not be loaded. The ranked list ` +
        `and the map are unaffected, because they are served as separate static data.</p>`;
    } finally {
      input.removeAttribute("aria-busy");
    }
  });
  $("#lookup-result").addEventListener("click", (e) => {
    const hit = e.target.closest("button.hit[data-id]");
    if (hit) jumpTo(hit.dataset.list, hit.dataset.id, hit.dataset.town);
  });

  $$(".tab").forEach((t) =>
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => {
        const on = x === t;
        x.setAttribute("aria-selected", String(on));
        $("#" + x.getAttribute("aria-controls")).hidden = !on;
      });
    }),
  );
}

if (typeof document !== "undefined" && document.getElementById("rows")) boot();
