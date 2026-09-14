// The page computes nothing. Every figure it draws was handed to it by
// scripts/build_site.py, so what is on screen is provably what the scorer
// produced. The only arithmetic here is scaling a normalised series to pixels.

const SUPPORTED_MAJOR = "1";

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

export function drawerHTML(row, flagMeanings) {
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
  return (
    `<div class="eyebrow">Detail &middot; ${esc(siteName(row))}</div>` +
    `<div class="dayprofile">${sparkSVG(row.window_kw, 300, 60)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Billed demand by month &middot; peak marked</div>` +
    `<dl class="kv">` +
    `<div><dt>Address</dt><dd>${esc(row.site_addr)}, ${esc(row.city)}</dd></div>` +
    `<div><dt>Owner of record</dt><dd>${esc(row.owner)}</dd></div>` +
    `<div><dt>Floor area</dt><dd>${Math.round(row.sqft).toLocaleString("en-US")} sq ft</dd></div>` +
    `<div><dt>Shaveable</dt><dd>${Math.round(row.shaveable_kw)} kW</dd></div>` +
    `<div><dt>Shaved fraction</dt><dd>${(row.shaved_fraction * 100).toFixed(1)}%</dd></div>` +
    `<div><dt>Load shape</dt><dd>${esc(row.archetype)} (${esc(row.source)})</dd></div>` +
    flags +
    `</dl>` +
    `<div class="lineage"><strong>How we got here:</strong> use description ` +
    `"${esc(row.use_desc)}" maps to the ${esc(row.archetype)} archetype, ` +
    `${esc(row.source)}-backed, scaled to ${Math.round(row.sqft).toLocaleString("en-US")} sq ft.` +
    `${source} Estimated, never measured &mdash; get the utility bill before anyone signs.` +
    `</div>`
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
    `<p class="lead">A structured prior over three public assessor fields, not a ` +
    `measurement. It orders a call list. It does not underwrite a project.</p>` +
    `<p>Demand is billed on the greatest fifteen-minute peak between 8 a.m. and ` +
    `9 p.m., Monday to Friday, excluding nine observed holidays. A three-in-the-` +
    `morning spike is free. Everything here is computed inside that window and ` +
    `nowhere else.</p>` +
    `<p>${esc(cov.parcels_total)} parcels screened; ${esc(cov.kept)} carry enough ` +
    `demand charge to be worth a conversation; ${esc(cov.sweet_spot)} sit in the ` +
    `sweet spot &mdash; the expensive G-2 rate plus a spiky shape.</p>` +
    `<h2 style="margin-top:16px">Does the archetype layer earn its place?</h2>` +
    regressionBlock +
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
    `top-ranked rows; the rest show the assessor's use description rather than the ` +
    `owner of record.`;

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
  $("#drawer").innerHTML = drawerHTML(row, (state.method || {}).flag_meanings);

  // The map is a view onto the table, not a picture beside it.
  const classes = parcelSelectionClasses(state.shown, id);
  $$("#map .parcel").forEach((g) => {
    g.setAttribute("class", classes[g.dataset.id] || "parcel");
  });
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
          `a sharp peak, and this list has neither together. That is a real answer, ` +
          `not a failure.`
        : `Every screened parcel in this list fell below 50 kW average demand, so ` +
          `a 250 kW cabinet has no peak worth shaving. That is a real answer, not ` +
          `a failure.`;
    $("#rows").innerHTML = `<tr><td colspan="7"><p class="reason">${why}</p></td></tr>`;
    $("#drawer").innerHTML = "";
  }
}

function applyFilters() {
  const rows = state.lists[state.source] || [];
  state.shown = state.view === "sweet" ? rows.filter((r) => r.sweet_spot) : rows;
  draw();
}

async function boot() {
  let ranked;
  try {
    ranked = await (await fetch("/data/ranked.json")).json();
  } catch (err) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">The ranked list could not be loaded. ` +
      `It is served as static data, so this is a network problem rather than a ` +
      `problem with the data itself.</p></td></tr>`;
    return;
  }
  if (String(ranked.site_schema_version || "").split(".")[0] !== SUPPORTED_MAJOR) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">This page was built for schema ` +
      `${SUPPORTED_MAJOR}.x and the data is ${esc(ranked.site_schema_version)}. ` +
      `Refusing to render rather than draw wrong numbers.</p></td></tr>`;
    return;
  }

  state.lists = ranked.lists;
  state.viewBox = (ranked.map || {}).view_box || "0 0 620 818";
  const c = ranked.counts;
  $("#counts").textContent =
    `${c.parcels_in.toLocaleString()} parcels screened · ` +
    `${c.kept.toLocaleString()} in band · ` +
    `${c.sweet_spot.toLocaleString()} in the sweet spot · ` +
    `showing top ${c.exported.comstock} measured and ${c.exported.modeled} modelled`;
  $("#whysplit").textContent = WHY_SPLIT;
  // The assessor vintage comes from the export's town block, not from the
  // method payload: `score_parcels` output carries no assess_fy -- that field
  // lives on the parcel frame -- so method.coverage.assess_years is empty.
  // Reading it here also shows the vintage before method.json has loaded.
  const fy = (ranked.town || {}).assess_fy;
  $("#vintage").textContent = fy ? `Assessor FY ${fy}` : "Assessor vintage unavailable";
  applyFilters();

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
      `above is unaffected &mdash; it is served as separate static data.</p>`;
  }

  $("#rows").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (tr) select(tr.dataset.id);
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
