// Extra map layers: burned area (MCD64A1, VNP64A1) and admin-1/admin-2 boundaries.
// app.js calls initLayers once, then onCountry and onUpdate; see the hooks marked "layers".

const TXT = {
  en: {
    layers: "Layers", hotspots: "Hotspots", burned: "Burned area", adm1: "Provinces / states", adm2: "Departments / counties",
    modis: "MODIS MCD64A1", viirs: "VIIRS VNP64A1", both: "Both",
    legend: "Burned area per 0.1° cell (km²)", legendWorld: "Burned area per 0.25° cell (km²)",
    card: "Burned area", cardWorld: "Burned area per year, processed countries",
    hint: "Sum of 500 m pixels with a burn date in that month (MCD64A1 v061 from Nov 2000, VNP64A1 v002 from Mar 2012). Cells matched by 0.1° centre, like hotspots.",
    worldHint: "Whole calendar years on a 0.25° grid, processed countries only.",
    calTitle: "Burned area calendar", total: "Burned area", unmapped: "Unmapped land",
    unmappedHint: "Land the algorithm could not map (cloud, missing data) in this country and period.",
    month: "Month", km2: "km²", none: "Burned area not built for this country yet. Run pipeline/burned_area.py.",
    noneWorld: "Burned area not built yet. Run pipeline/burned_area.py, then --world.",
    region: "Province / dept.", regionHint: "Turn on a boundary layer and click a province or department.",
    smallRegion: "No 0.1° cell centre falls inside this unit; it is too small for the grid.",
    noData: n => `${n}: no processed hotspot data for this country yet.`, adm2None: "No department layer for this country yet.",
    overlap: "in VIIRS months", perMonth: "km² / month", perYear: "km² / year", src: "Sources", cells: n => `${n.toLocaleString()} cells`,
  },
  es: {
    layers: "Capas", hotspots: "Focos de calor", burned: "Área quemada", adm1: "Provincias / estados", adm2: "Departamentos / condados",
    modis: "MODIS MCD64A1", viirs: "VIIRS VNP64A1", both: "Ambos",
    legend: "Área quemada por celda de 0,1° (km²)", legendWorld: "Área quemada por celda de 0,25° (km²)",
    card: "Área quemada", cardWorld: "Área quemada por año, países procesados",
    hint: "Suma de píxeles de 500 m con fecha de quema en ese mes (MCD64A1 v061 desde nov 2000, VNP64A1 v002 desde mar 2012). Celdas por centro de 0,1°, igual que los focos.",
    worldHint: "Años calendario completos en grilla de 0,25°, solo países procesados.",
    calTitle: "Calendario de área quemada", total: "Área quemada", unmapped: "Tierra sin mapear",
    unmappedHint: "Tierra que el algoritmo no pudo mapear (nubes, datos faltantes) en este país y período.",
    month: "Mes", km2: "km²", none: "Área quemada aún no generada para este país. Ejecute pipeline/burned_area.py.",
    noneWorld: "Área quemada aún no generada. Ejecute pipeline/burned_area.py y luego --world.",
    region: "Provincia / depto.", regionHint: "Active una capa de límites y haga clic en una provincia o departamento.",
    smallRegion: "Ningún centro de celda de 0,1° cae dentro de esta unidad; es muy chica para la grilla.",
    noData: n => `${n}: todavía no hay focos procesados para este país.`, adm2None: "Aún no hay capa de departamentos para este país.",
    overlap: "en meses VIIRS", perMonth: "km² / mes", perYear: "km² / año", src: "Fuentes", cells: n => `${n.toLocaleString("es-AR")} celdas`,
  },
};
// Okabe-Ito pair for the two products; dashes as a second cue
const PROD = { MCD64A1: { color: "#56B4E9", dash: null }, VNP64A1: { color: "#E69F00", dash: "6,3" } };
const EMPTY = { type: "FeatureCollection", features: [] };

let C, map, INDEX = {}, GEO = null, REGION = null;
const S = { hot: true, burned: false, prod: "MCD64A1", adm1: false, adm2: false };
const BA = new Map(), BMETA = new Map();
let BWORLD;  // undefined = not tried, null = missing
const tx = k => (TXT[C.lang()] ?? TXT.en)[k] ?? TXT.en[k];
const fmtA = v => v == null ? "–" : v < 10 ? (+v).toFixed(1) : C.fmt(v);

// ---------------------------------------------------------------- data
async function tryJson(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch { return null; } }
let BIDX = { countries: [], world: false };  // which burned-area files exist
async function tryParquet(url, columns) { try { return await C.readParquet(url, columns); } catch { return null; } }
async function loadBurned(key) {
  if (BA.has(key)) return BA.get(key);
  const rows = BIDX.countries.includes(key) && await tryParquet(`data/countries/${key}/burned_area.parquet`, ["lat", "lon", "year", "month", "product", "burned_km2"]);
  let D = null;
  if (rows) {
    const n = rows.length;
    D = { n, lat: new Float64Array(n), lon: new Float64Array(n), k: new Int32Array(n), p: new Uint8Array(n), a: new Float64Array(n) };
    rows.forEach((r, i) => {
      D.lat[i] = r.lat; D.lon[i] = r.lon; D.k[i] = Number(r.year) * 12 + Number(r.month) - 1;
      D.p[i] = r.product === "VNP64A1" ? 1 : 0; D.a[i] = r.burned_km2;
    });
    BMETA.set(key, await tryJson(`data/countries/${key}/burned_meta.json`));
  }
  BA.set(key, D);
  return D;
}
async function loadBurnedWorld() {
  if (BWORLD !== undefined) return BWORLD;
  const rows = BIDX.world && await tryParquet("data/burned_q025_year.parquet", ["lat", "lon", "y", "product", "km2"]);
  BWORLD = rows ? rows.map(r => ({ lat: r.lat, lon: r.lon, y: Number(r.y), p: r.product, a: r.km2 })) : null;
  return BWORLD;
}
const admCache = new Map();
async function loadAdmin(path) {
  if (!admCache.has(path)) admCache.set(path, await tryJson(`data/ref/${path}`) ?? EMPTY);
  return admCache.get(path);
}

// ---------------------------------------------------------------- geometry
function ringsOf(g) { return g.type === "Polygon" ? g.coordinates : g.type === "MultiPolygon" ? g.coordinates.flat() : []; }
function bboxOf(g) {
  let s = 90, n = -90, w = 180, e = -180;
  for (const r of ringsOf(g)) for (const [x, y] of r) { s = Math.min(s, y); n = Math.max(n, y); w = Math.min(w, x); e = Math.max(e, x); }
  return [s, n, w, e];
}
function inRings(lat, lon, rings) {  // even-odd over all rings, so holes work
  let inside = false;
  for (const P of rings) for (let i = 0, j = P.length - 1; i < P.length; j = i++) {
    const [xi, yi] = P[i], [xj, yj] = P[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
const square = (lat, lon, h) => [[[lon - h, lat - h], [lon + h, lat - h], [lon + h, lat + h], [lon - h, lat + h], [lon - h, lat - h]]];

// ---------------------------------------------------------------- map layers and control
export function initLayers(ctx) {
  C = ctx; map = ctx.map;
  const below = map.getLayer("global") ? "global" : undefined;
  map.addSource("burned", { type: "geojson", data: EMPTY, attribution: "Burned area: NASA LP DAAC MCD64A1, VNP64A1" });
  map.addLayer({ id: "burned", type: "fill", source: "burned", layout: { visibility: "none" },
    paint: { "fill-color": ["get", "c"], "fill-opacity": 0.8 } }, below);
  for (const lv of ["adm1", "adm2"]) {
    map.addSource(lv, { type: "geojson", data: EMPTY, attribution: lv === "adm1" ? "Admin-1: Natural Earth" : "Admin-2: geoBoundaries" });
    map.addLayer({ id: `${lv}-fill`, type: "fill", source: lv, layout: { visibility: "none" }, paint: { "fill-color": "#fff", "fill-opacity": 0.01 } });
    map.addLayer({ id: `${lv}-line`, type: "line", source: lv, layout: { visibility: "none" },
      paint: { "line-color": lv === "adm1" ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.6)", "line-width": lv === "adm1" ? 1.2 : 0.8,
        "line-dasharray": lv === "adm1" ? [1, 0] : [3, 2] } });
  }
  map.addSource("region", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "region-line", type: "line", source: "region", paint: { "line-color": "#ffffff", "line-width": 3.2 } });
  map.addLayer({ id: "region-halo", type: "line", source: "region", paint: { "line-color": "#000", "line-width": 1, "line-offset": -2, "line-opacity": 0.6 } });
  map.moveLayer("sel-line");
  const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
  for (const lv of ["adm2", "adm1"]) {
    map.on("mousemove", `${lv}-fill`, e => {
      if (lv === "adm1" && S.adm2 && GEO?.adm2) return;
      if (map.queryRenderedFeatures(e.point, { layers: ["cells", "global"] }).length) return;
      map.getCanvas().style.cursor = "pointer";
      pop.setLngLat(e.lngLat).setText(e.features[0].properties.name).addTo(map);
    });
    map.on("mouseleave", `${lv}-fill`, () => { pop.remove(); map.getCanvas().style.cursor = ""; });
  }
  map.on("mousemove", "burned", e => {
    if (map.queryRenderedFeatures(e.point, { layers: ["cells", "global"] }).length) return;
    const p = e.features[0].properties;
    pop.setLngLat(e.lngLat).setHTML(`${p.lat}, ${p.lon}<br><b>${fmtA(p.a)} km²</b> ${tx("burned").toLowerCase()}`).addTo(map);
  });
  map.on("mouseleave", "burned", () => pop.remove());
  map.addControl(new LayerCtrl(), "top-left");
  addLegend();
}
class LayerCtrl {
  onAdd() {
    const el = this.el = document.createElement("div");
    el.className = "maplibregl-ctrl layer-ctrl"; el.id = "layer-ctrl";
    el.innerHTML = `<button type="button" class="lc-head" aria-expanded="true"><span data-lt="layers"></span></button>
      <div class="lc-body">
        <label><input type="checkbox" id="lc-hot" checked><span data-lt="hotspots"></span></label>
        <label><input type="checkbox" id="lc-burned"><span data-lt="burned"></span></label>
        <div class="lc-sub" id="lc-prods">
          <label><input type="radio" name="lc-prod" value="MCD64A1" checked><span data-lt="modis"></span></label>
          <label><input type="radio" name="lc-prod" value="VNP64A1"><span data-lt="viirs"></span></label>
        </div>
        <label><input type="checkbox" id="lc-adm1"><span data-lt="adm1"></span></label>
        <label><input type="checkbox" id="lc-adm2"><span data-lt="adm2"></span></label>
        <p class="lc-note" id="lc-note" hidden></p>
      </div>`;
    const q = s => el.querySelector(s);
    q(".lc-head").onclick = () => { const c = el.classList.toggle("collapsed"); q(".lc-head").setAttribute("aria-expanded", String(!c)); };
    q("#lc-hot").onchange = e => { S.hot = e.target.checked; for (const l of ["cells", "global"]) map.setLayoutProperty(l, "visibility", S.hot ? "visible" : "none"); C.legendHot(S.hot); };
    q("#lc-burned").onchange = e => { S.burned = e.target.checked; C.refresh(); };
    el.querySelectorAll("input[name=lc-prod]").forEach(r => r.onchange = () => { S.prod = r.value; C.refresh(); });
    q("#lc-adm1").onchange = e => { S.adm1 = e.target.checked; showAdmin(); };
    q("#lc-adm2").onchange = e => { S.adm2 = e.target.checked; showAdmin(); };
    for (const ev of ["mousedown", "click", "dblclick", "wheel"]) el.addEventListener(ev, e => e.stopPropagation());
    applyText(el);
    return el;
  }
  onRemove() { this.el.remove(); }
}
function addLegend() {
  const lg = document.createElement("div");
  lg.className = "legend legend-burn"; lg.id = "legend-burn"; lg.hidden = true;
  lg.innerHTML = `<span id="lb-title"></span><div class="ramp ramp-burn"></div><div class="ramp-lbl"><span>0</span><span id="lb-max">–</span></div>`;
  document.querySelector(".stage").append(lg);
}
export function applyText(root = document) {
  root.querySelectorAll("[data-lt]").forEach(el => { el.textContent = tx(el.dataset.lt); });
  const h = document.querySelector(".mode-region .hint");
  if (h && REGION) h.textContent = `${REGION.name}${REGION.type ? ` (${REGION.type})` : ""}`;
}
function note(msg) { const n = document.getElementById("lc-note"); if (!n) return; n.hidden = !msg; n.textContent = msg || ""; }

// ---------------------------------------------------------------- boundaries
export async function loadIndex() {
  [INDEX, BIDX] = await Promise.all([tryJson("data/ref/admin_index.json").then(x => x ?? {}),
    tryJson("data/burned_index.json").then(x => x ?? BIDX)]);
}
export function onCountry(geoName) {
  GEO = geoName ? INDEX[geoName] ?? null : null;
  clearRegion();
  showAdmin();
}
async function showAdmin() {
  const want = { adm1: S.adm1 && GEO?.adm1, adm2: S.adm2 && GEO?.adm2 };
  note(S.adm2 && GEO && !GEO.adm2 ? tx("adm2None") : "");
  for (const lv of ["adm1", "adm2"]) {
    const vis = want[lv] ? "visible" : "none";
    map.getSource(lv).setData(want[lv] ? await loadAdmin(GEO[lv]) : EMPTY);
    map.setLayoutProperty(`${lv}-fill`, "visibility", vis);
    map.setLayoutProperty(`${lv}-line`, "visibility", vis);
  }
}
// Click on a province or department: returns true when it handled the click
export function handleClick(e) {
  const lv = S.adm2 && GEO?.adm2 ? "adm2" : S.adm1 && GEO?.adm1 ? "adm1" : null;
  if (!lv) return false;
  const f = map.queryRenderedFeatures(e.point, { layers: [`${lv}-fill`] })[0];
  if (!f) return false;
  const src = (admCache.get(GEO[lv])?.features ?? []).find(x => x.properties.id === f.properties.id) ?? f;
  REGION = { name: f.properties.name, type: f.properties.type, level: lv, geometry: src.geometry, rings: ringsOf(src.geometry), box: bboxOf(src.geometry) };
  map.getSource("region").setData({ type: "Feature", geometry: src.geometry, properties: {} });
  const [s, n, w, ee] = REGION.box;
  map.fitBounds([[w, s], [ee, n]], { padding: { top: 60, bottom: 60, left: 60, right: C.panelRight() }, duration: 1600, maxZoom: 9 });
  applyText();
  C.onRegion(REGION);
  return true;
}
export function clearRegion() { REGION = null; map?.getSource("region")?.setData(EMPTY); if (C) applyText(); }
export const region = () => REGION;
export function regionTest() {
  if (!REGION) return () => false;
  const [s, n, w, e] = REGION.box, R = REGION.rings;
  return (lat, lon) => lat >= s && lat <= n && lon >= w && lon <= e && inRings(lat, lon, R);
}
function regionHasCell() {  // any 0.1-degree cell centre inside the selected unit?
  const [s, n, w, e] = REGION.box, test = regionTest();
  for (let la = Math.floor(s * 10) / 10 + 0.05; la <= n; la += 0.1)
    for (let lo = Math.floor(w * 10) / 10 + 0.05; lo <= e; lo += 0.1) if (test(+la.toFixed(2), +lo.toFixed(2))) return true;
  return false;
}
export const regionLabel = () => REGION ? REGION.name.replace(/[^\p{L}\p{N}]+/gu, "_") : "region";

// ---------------------------------------------------------------- burned area: map + panel
function colorScale(vals) {
  const max = C.d3.quantile(vals.sort(C.d3.ascending), 0.99) || 1;
  const s = C.d3.scaleSequentialSqrt(t => C.d3.interpolatePuBu(0.25 + 0.75 * t)).domain([0, max]).clamp(true);
  return { s, max };
}
function setLegend(on, title, max) {
  const lg = document.getElementById("legend-burn");
  lg.hidden = !on;
  if (on) { document.getElementById("lb-title").textContent = `${title} · ${S.prod}`; document.getElementById("lb-max").textContent = "≥ " + fmtA(max); }
}
// Called by app.js update(); o = { key, geo, k0, k1, inAoi } or { world: [y0, y1] }
let SEQ = 0;  // newest call wins when the user switches quickly
export async function onUpdate(o) {
  const my = ++SEQ;
  if (o.world) return updateWorld(o.world, my);
  const card = ensureCard("burn-card", "country-view", "#pts-card");
  card.classList.add("loading");  // dim old numbers while the new country loads
  const D = await loadBurned(o.key);
  if (my !== SEQ) return;
  card.classList.remove("loading");
  if (!D) {
    map.getSource("burned").setData(EMPTY); setLegend(false);
    map.setLayoutProperty("burned", "visibility", "none");
    card.querySelector(".bc-body").innerHTML = `<p class="hint">${tx("none")}</p>`;
    return;
  }
  const pi = S.prod === "VNP64A1" ? 1 : 0, cell = new Map(), mon = new Map();
  for (let i = 0; i < D.n; i++) {
    const k = D.k[i];
    if (k < o.k0 || k > o.k1) continue;
    if (D.p[i] === pi) {
      const ck = D.lat[i] * 10000 + D.lon[i];
      const c = cell.get(ck);
      c ? c.a += D.a[i] : cell.set(ck, { lat: D.lat[i], lon: D.lon[i], a: D.a[i] });
    }
    if (!o.inAoi(D.lat[i], D.lon[i])) continue;
    let r = mon.get(k);
    if (!r) mon.set(k, r = [0, 0]);
    r[D.p[i]] += D.a[i];
  }
  const cells = [...cell.values()], { s, max } = colorScale(cells.map(c => c.a));
  map.getSource("burned").setData({ type: "FeatureCollection", features: S.burned ? cells.map(c => ({ type: "Feature",
    geometry: { type: "Polygon", coordinates: square(c.lat, c.lon, 0.05) }, properties: { a: +c.a.toFixed(2), c: s(c.a), lat: c.lat, lon: c.lon } })) : [] });
  map.setLayoutProperty("burned", "visibility", S.burned ? "visible" : "none");
  setLegend(S.burned, tx("legend"), max);
  renderCard(card, o, mon, BMETA.get(o.key));
}
function monthRows(o, mon, meta) {
  const P = meta?.products ?? {}, ym = s => { const [y, m] = s.split("-").map(Number); return y * 12 + m - 1; };
  const span = p => P[p] ? [ym(P[p].first), ym(P[p].last)] : [Infinity, -Infinity];
  const sp = [span("MCD64A1"), span("VNP64A1")], rows = [];
  for (let k = o.k0; k <= o.k1; k++) {
    const v = mon.get(k) ?? [0, 0], year = Math.floor(k / 12), month = (k % 12) + 1;
    // null outside a product's record, so gaps are not drawn as zero
    rows.push({ k, year, month, date: new Date(Date.UTC(year, month - 1, 15)),
      MCD64A1: k >= sp[0][0] && k <= sp[0][1] ? v[0] : null, VNP64A1: k >= sp[1][0] && k <= sp[1][1] ? v[1] : null });
  }
  return rows;
}
function renderCard(card, o, mon, meta) {
  const { Plot, d3 } = C, M = C.t("months"), rows = monthRows(o, mon, meta), body = card.querySelector(".bc-body");
  const sum = p => d3.sum(rows, r => r[p] ?? 0), has = p => rows.some(r => r[p] != null);
  const overlap = d3.sum(rows, r => r.VNP64A1 != null ? r.MCD64A1 ?? 0 : 0);  // same months as VIIRS
  const um = (meta?.unmapped_monthly ?? []).filter(u => { const k = u.y * 12 + u.m - 1; return k >= o.k0 && k <= o.k1; });
  const umTxt = ["MCD64A1", "VNP64A1"].filter(has).map(p => `${p} ${fmtA(d3.sum(um.filter(u => u.product === p), u => u.km2))} km²`).join(" · ");
  const W = Math.max(340, body.clientWidth || 480);
  body.innerHTML = `<div class="kpis">${["MCD64A1", "VNP64A1"].map(p => `<div class="kpi"><div class="k">${tx("total")} · ${p}</div>
      <div class="v">${has(p) ? fmtA(sum(p)) : "–"} <span class="d">km²</span></div><div class="d">${has(p) ? `${meta.products[p].first} → ${meta.products[p].last}` : ""}${p === "MCD64A1" && has("VNP64A1") ? ` · ${fmtA(overlap)} km² ${tx("overlap")}` : ""}</div></div>`).join("")}</div>
    ${REGION && C.isRegion() && !regionHasCell() ? `<p class="notice">${tx("smallRegion")}</p>` : ""}
    <p class="hint">${tx("hint")}</p><div id="bseries" class="chart"></div>
    <div class="card-h"><h2>${tx("calTitle")} · ${S.prod}</h2></div><div id="bcal" class="chart"></div>
    <p class="hint" title="${tx("unmappedHint")}">${tx("unmapped")} (${C.isWhole() ? "" : "country, "}${tx("unmappedHint").toLowerCase()}): ${umTxt || "–"}</p>
    <p class="hint">${tx("src")}: Giglio et al., MCD64A1 v061 (doi:10.5067/MODIS/MCD64A1.061); VNP64A1 v002 (doi:10.5067/VIIRS/VNP64A1.002); NASA LP DAAC.${meta ? ` Built ${meta.built_utc}.` : ""}</p>`;
  const long = rows.flatMap(r => ["MCD64A1", "VNP64A1"].filter(p => r[p] != null).map(p => ({ date: r.date, p, v: r[p] })));
  document.getElementById("bseries").append(Plot.plot({
    width: W, height: 230, marginLeft: 60, style: { fontSize: "11px" },
    x: { label: null, type: "utc" }, y: { label: tx("perMonth"), grid: true },
    color: { legend: true, domain: Object.keys(PROD), range: Object.values(PROD).map(p => p.color) },
    marks: [...Object.entries(PROD).map(([p, st]) => Plot.lineY(long.filter(d => d.p === p), { x: "date", y: "v", stroke: "p", strokeWidth: 1.4, strokeDasharray: st.dash })),
      Plot.ruleY([0])],
  }));
  const cal = rows.filter(r => r[S.prod] != null), years = [...new Set(cal.map(r => r.year))];
  if (cal.length) document.getElementById("bcal").append(Plot.plot({
    width: W, height: years.length * 15 + 70, marginLeft: 40, marginTop: 30, padding: 0.06, style: { fontSize: "11px" },
    x: { label: null, tickFormat: m => M[m - 1], axis: "top", domain: d3.range(1, 13) }, y: { label: null, domain: years, tickFormat: String },
    color: { type: "sqrt", interpolate: t => d3.interpolatePuBu(0.15 + 0.85 * t), legend: true, label: `km² (${S.prod})`, width: Math.min(320, W - 20), ticks: 4, tickFormat: d => fmtA(d) },
    marks: [Plot.cell(cal, { x: "month", y: "year", fill: r => r[S.prod], inset: 0.5, title: r => `${M[r.month - 1]} ${r.year}: ${fmtA(r[S.prod])} km²` })],
  }));
  card.querySelector("[data-bcsv]").onclick = () => C.download(`burned_area_${C.aoiLabel()}.csv`, C.toCsv(rows.map(r => ({
    year: r.year, month: r.month, MCD64A1_km2: r.MCD64A1?.toFixed(3) ?? "", VNP64A1_km2: r.VNP64A1?.toFixed(3) ?? "" })),
    ["year", "month", "MCD64A1_km2", "VNP64A1_km2"]));
}
function ensureCard(id, parentId, beforeSel) {
  let card = document.getElementById(id);
  if (!card) {
    card = document.createElement("article");
    card.className = "card"; card.id = id;
    card.innerHTML = `<div class="card-h"><h2 class="bc-title"></h2><div class="dl"><button data-png="${id}-c">PNG</button><button data-svg="${id}-c">SVG</button>${id === "burn-card" ? `<button data-bcsv>CSV</button>` : ""}</div></div>
      <div class="bc-body" id="${id}-c"></div>`;
    const parent = document.getElementById(parentId), before = parent.querySelector(beforeSel);
    before ? parent.insertBefore(card, before) : parent.append(card);
    card.querySelector("[data-png]").onclick = () => C.exportPng(`${id}-c`);
    card.querySelector("[data-svg]").onclick = () => C.exportSvg(`${id}-c`);
  }
  card.querySelector(".bc-title").textContent = id === "burn-card" ? tx("card") : tx("cardWorld");
  return card;
}
async function updateWorld([y0, y1], my) {
  const card = ensureCard("burn-world", "global-view", null), body = card.querySelector(".bc-body");
  const W = await loadBurnedWorld();
  if (my !== SEQ) return;
  if (!W) {
    map.getSource("burned").setData(EMPTY); setLegend(false);
    body.innerHTML = `<p class="hint">${tx("noneWorld")}</p>`;
    return;
  }
  const cell = new Map(), byY = [];
  for (const r of W) {
    if (r.y < y0 || r.y > y1) continue;
    byY.push(r);
    if (r.p !== S.prod) continue;
    const ck = r.lat * 10000 + r.lon, c = cell.get(ck);
    c ? c.a += r.a : cell.set(ck, { lat: r.lat, lon: r.lon, a: r.a });
  }
  const cells = [...cell.values()], { s, max } = colorScale(cells.map(c => c.a));
  map.getSource("burned").setData({ type: "FeatureCollection", features: S.burned ? cells.map(c => ({ type: "Feature",
    geometry: { type: "Polygon", coordinates: square(c.lat, c.lon, 0.125) }, properties: { a: +c.a.toFixed(1), c: s(c.a), lat: c.lat, lon: c.lon } })) : [] });
  map.setLayoutProperty("burned", "visibility", S.burned ? "visible" : "none");
  setLegend(S.burned, tx("legendWorld"), max);
  const ys = C.d3.rollups(byY, v => C.d3.sum(v, r => r.a), r => r.y, r => r.p).flatMap(([y, ps]) => ps.map(([p, a]) => ({ y, p, a })));
  const Wd = Math.max(340, body.clientWidth || 480);
  body.innerHTML = `<p class="hint">${tx("worldHint")}</p>`;
  // grouped bars: one column per product inside each year
  body.append(C.Plot.plot({ width: Wd, height: 230, marginLeft: 70, style: { fontSize: "11px" },
    fx: { label: null, tickFormat: d => d % 5 === 0 ? String(d) : "", padding: 0.1 }, x: { axis: null, domain: Object.keys(PROD) },
    y: { label: tx("perYear"), grid: true }, color: { legend: true, domain: Object.keys(PROD), range: Object.values(PROD).map(p => p.color) },
    marks: [C.Plot.barY(ys, { fx: "y", x: "p", y: "a", fill: "p", title: d => `${d.y} ${d.p}: ${C.fmt(d.a)} km²` }), C.Plot.ruleY([0])] }));
}
export const burnedOn = () => S.burned;
