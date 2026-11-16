// Vendored libraries so the demo runs offline
import { Plot, d3, parquetReadObjects } from "./vendor/libs.js";
import * as LAYERS from "./layers.js";  // burned area + admin boundaries

// ---------------------------------------------------------------- i18n
const I18N = {
  en: {
    title: "Harmonized fire activity calendar",
    subtitle: "MODIS (2000–) and VIIRS S-NPP (2012–) hotspots on one VIIRS-equivalent scale",
    methodLink: "Method & validation", loading: "Loading data…", aoi: "Area of interest",
    bbox: "Bounding box", south: "South lat", north: "North lat", west: "West lon", east: "East lon",
    draw: "Draw rectangle on map", drawing: "Drag on the map…", pointRadius: "Point + radius",
    pick: "Click a point on map", picking: "Click the map…", polygon: "Polygon",
    drawPoly: "Draw polygon on map", drawingPoly: "Click points, double-click to finish", polyHint: "Click to add points, double-click to finish.", dates: "Date range", from: "From", to: "To",
    run: "Update", country: "Country", results: "Results", search: "Search a country", globalBtn: "Whole world",
    wholeCountry: "Whole country", pickHint: "Click a country on the globe or search for one.",
    allCountries: "All processed countries", processed: "Processed countries",
    globalYearly: "Harmonized hotspots per year, all processed countries",
    globalHint: "The world view sums whole calendar years on a 0.25° grid. Pick a country for monthly detail.",
    noDataFor: n => `No processed FIRMS data for ${n} yet. Pick one of the processed countries below.`,
    noMatch: "No country matches that name.", noPoints: "Hotspot CSV is not available for this country yet.",
    biasLbl: "holdout bias", cellsLbl: "0.25° cell", legendTitle: "Harmonized hotspots per 0.1° cell", legendWorld: "Harmonized hotspots per 0.25° cell",
    globe: "3D", flat: "2D", globeTip: "Switch to flat map", flatTip: "Switch to 3D globe",
    cellHint: "Areas are matched on 0.1° grid cells (cell centre inside the area). Hotspot CSV uses exact coordinates.",
    mapHint: "Dots: harmonized hotspot count per 0.1° cell for the selected dates.",
    calendar: "Burning activity calendar",
    calHint: "Harmonized hotspots (VIIRS S-NPP fire-cell-days equivalent). A white dot marks months estimated from MODIS.",
    anomaly: "Anomaly vs. monthly median",
    anomHint: "log₂((count+1)/(median for that month+1)). +1 = twice the usual, −1 = half.",
    season: "Seasonality", seasHint: "Median per calendar month, band = 25th–75th percentile across years.",
    annual: "Yearly totals", annualHint: "Whiskers: bootstrap 5–95 % range of the MODIS→VIIRS ratio.",
    beforeAfter: "Before / after harmonization",
    baHint: "Raw sensor counts disagree by a large factor; the harmonized series continues across 2012 on one scale.",
    points: "Hotspots in this search",
    pointsHint: "Original FIRMS detections (type 0, MODIS conf ≥ 30, VIIRS nominal/high) with sensor tag and harmonization weight.",
    dlPoints: "Download hotspot CSV", methodTitle: "Method and validation",
    footer: "Data: NASA FIRMS (MODIS C6.1, VIIRS S-NPP 375 m). Not an operational product; see docs/METHOD.md for limits.",
    total: "Harmonized hotspots", range: "range", raw: "Raw detections", current: "Latest month vs. median",
    peakMonth: "Peak fire month", peakYear: "Most active year", month: "Month", year: "Year",
    count: "Harmonized count", anomalyLbl: "Anomaly (log₂)", median: "median",
    harmonized: "Harmonized", modisRaw: "MODIS raw (Terra+Aqua)", viirsRaw: "VIIRS raw pixels",
    viirsFcd: "VIIRS fire-cell-days", src_obs: "VIIRS observed", src_modis: "From MODIS",
    rank: (r, n, m) => `${m} rank #${r} of ${n} years (1 = most fire)`,
    noData: "No hotspots in this area and period.", ready: "Ready.",
    months: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    fetchingPts: "Fetching points…", ptsDone: n => `${n.toLocaleString()} hotspots downloaded.`,
  },
  es: {
    title: "Calendario armonizado de actividad de fuego",
    subtitle: "Focos de calor MODIS (2000–) y VIIRS S-NPP (2012–) en una escala equivalente a VIIRS",
    methodLink: "Método y validación", loading: "Cargando datos…", aoi: "Área de interés",
    bbox: "Rectángulo", south: "Lat sur", north: "Lat norte", west: "Lon oeste", east: "Lon este",
    draw: "Dibujar rectángulo en el mapa", drawing: "Arrastre en el mapa…", pointRadius: "Punto + radio",
    pick: "Elegir punto en el mapa", picking: "Haga clic en el mapa…", polygon: "Polígono",
    drawPoly: "Dibujar polígono en el mapa", drawingPoly: "Clic para vértices, doble clic para cerrar", polyHint: "Clic para agregar vértices, doble clic para cerrar.", dates: "Período", from: "Desde", to: "Hasta",
    run: "Actualizar", country: "País", results: "Resultados", search: "Buscar un país", globalBtn: "Todo el mundo",
    wholeCountry: "País completo", pickHint: "Haga clic en un país del globo o búsquelo.",
    allCountries: "Todos los países procesados", processed: "Países procesados",
    globalYearly: "Focos armonizados por año, todos los países procesados",
    globalHint: "La vista mundial suma años calendario completos en una grilla de 0,25°. Elija un país para ver el detalle mensual.",
    noDataFor: n => `Todavía no hay datos FIRMS procesados para ${n}. Elija uno de los países procesados.`,
    noMatch: "Ningún país coincide con ese nombre.", noPoints: "El CSV de focos aún no está disponible para este país.",
    biasLbl: "sesgo en años de prueba", cellsLbl: "celda de 0,25°", legendTitle: "Focos armonizados por celda de 0,1°", legendWorld: "Focos armonizados por celda de 0,25°",
    globe: "3D", flat: "2D", globeTip: "Cambiar a mapa plano", flatTip: "Cambiar a globo 3D",
    cellHint: "Las áreas se resuelven en celdas de 0,1° (centro de celda dentro del área). El CSV de focos usa coordenadas exactas.",
    mapHint: "Puntos: cantidad armonizada de focos por celda de 0,1° para el período elegido.",
    calendar: "Calendario de actividad de quema",
    calHint: "Focos armonizados (equivalente a celdas-día de fuego VIIRS S-NPP). Un punto blanco marca meses estimados desde MODIS.",
    anomaly: "Anomalía respecto de la mediana mensual",
    anomHint: "log₂((focos+1)/(mediana de ese mes+1)). +1 = el doble de lo habitual, −1 = la mitad.",
    season: "Estacionalidad", seasHint: "Mediana por mes; banda = percentiles 25–75 entre años.",
    annual: "Totales anuales", annualHint: "Bigotes: rango bootstrap 5–95 % de la razón MODIS→VIIRS.",
    beforeAfter: "Antes / después de armonizar",
    baHint: "Los conteos crudos difieren mucho entre sensores; la serie armonizada continúa en 2012 en una sola escala.",
    points: "Focos de esta búsqueda",
    pointsHint: "Detecciones originales de FIRMS (tipo 0, MODIS conf ≥ 30, VIIRS nominal/alta) con sensor y peso de armonización.",
    dlPoints: "Descargar CSV de focos", methodTitle: "Método y validación",
    footer: "Datos: NASA FIRMS (MODIS C6.1, VIIRS S-NPP 375 m). No es un producto operativo; ver docs/METHOD.md.",
    total: "Focos armonizados", range: "rango", raw: "Detecciones crudas", current: "Último mes vs. mediana",
    peakMonth: "Mes de mayor actividad", peakYear: "Año más activo", month: "Mes", year: "Año",
    count: "Focos armonizados", anomalyLbl: "Anomalía (log₂)", median: "mediana",
    harmonized: "Armonizado", modisRaw: "MODIS crudo (Terra+Aqua)", viirsRaw: "VIIRS píxeles crudos",
    viirsFcd: "VIIRS celdas-día", src_obs: "VIIRS observado", src_modis: "Desde MODIS",
    rank: (r, n, m) => `${m}: puesto #${r} de ${n} años (1 = más fuego)`,
    noData: "No hay focos en esta área y período.", ready: "Listo.",
    months: ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"],
    fetchingPts: "Buscando focos…", ptsDone: n => `${n.toLocaleString("es-AR")} focos descargados.`,
  },
};
let lang = "en";
const t = k => I18N[lang][k] ?? I18N.en[k] ?? k;
const fmt = v => (v == null || Number.isNaN(v)) ? "–" :
  Math.round(v).toLocaleString(lang === "es" ? "es-AR" : "en-US");
function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  $("search").placeholder = t("search");
  $("lang").textContent = lang === "en" ? "ES" : "EN";
}

// ---------------------------------------------------------------- state
const $ = id => document.getElementById(id);
// Sensor eras; sources: FIRMS data_availability and NOAA S-NPP cessation notice
const ERAS = [
  { y: 2002, label: "+Aqua (Jul 2002)", short: "+Aqua" }, { y: 2012, label: "+VIIRS S-NPP (Jan 2012)", short: "+VIIRS" },
  { y: 2018, label: "+NOAA-20 (tied to S-NPP)", short: "+NOAA-20" }, { y: 2021, label: "MODIS orbit drift", short: "MODIS drift" },
  { y: 2026, label: "S-NPP ends 2 Nov 2026", short: "S-NPP ends" },
];
// Countries with processed FIRMS data; geo = Natural Earth country name
const COUNTRIES = {
  argentina: { name: "Argentina", geo: "Argentina", box: [-55.2, -21.7, -73.6, -53.5] },
  australia: { name: "Australia", geo: "Australia", box: [-44, -10, 112, 154] },
  brazil: { name: "Brazil", geo: "Brazil", box: [-34, 5.3, -74, -34.8] },
  canada: { name: "Canada", geo: "Canada", box: [41.7, 72, -141, -52.6] },
  usa: { name: "United States", geo: "United States of America", box: [24.5, 49.5, -125, -66.9] },
  spain: { name: "Spain", geo: "Spain", box: [35.9, 43.8, -9.4, 4.4] },
  portugal: { name: "Portugal", geo: "Portugal", box: [36.9, 42.2, -9.6, -6.2] },
  italy: { name: "Italy", geo: "Italy", box: [36.6, 47.1, 6.6, 18.6] },
  greece: { name: "Greece", geo: "Greece", box: [34.8, 41.8, 19.3, 29.7] },
  turkey: { name: "Turkey", geo: "Turkey", box: [35.8, 42.1, 25.6, 44.8] },
};
const BY_GEO = Object.fromEntries(Object.entries(COUNTRIES).map(([k, c]) => [c.geo, k]));
const ALIASES = { usa: "United States of America", us: "United States of America", "united states": "United States of America",
  uk: "United Kingdom", "estados unidos": "United States of America", brasil: "Brazil", "canadá": "Canada" };
const dir = k => `data/countries/${k}/`;
let SEL = null;  // selected country key; null = world view
let userDates = false, LAST;  // keep the user's own date choice across countries
let meta, lastRows = [], WORLD, GLOBAL;
const METAS = {}, CALS = new Map();
const status = (msg, err = false) => { const s = $("status"); s.textContent = msg; s.classList.toggle("err", err); };

// ---------------------------------------------------------------- data (Parquet, read in the browser)
let CAL; // columnar arrays for the selected country, one entry per cell-month
const pointCache = new Map();
async function readParquet(url, columns) {
  const file = await (await fetch(url)).arrayBuffer();
  return parquetReadObjects({ file, columns });
}
async function loadCal(k) {
  if (CALS.has(k)) return CALS.get(k);
  const rows = await readParquet(dir(k) + "calendar_cells.parquet", ["lat", "lon", "year", "month", "harmonized_count",
    "count_low", "count_high", "modis_count", "viirs_firecell_days", "viirs_pixels", "source_mix"]);
  const n = rows.length, f = () => new Float64Array(n);
  const C = { n, lat: f(), lon: f(), k: new Int32Array(n), h: f(), lo: f(), hi: f(), modis: f(), vfcd: f(), vpx: f(), est: new Uint8Array(n) };
  rows.forEach((r, i) => {
    C.lat[i] = r.lat; C.lon[i] = r.lon; C.k[i] = Number(r.year) * 12 + Number(r.month) - 1;
    C.h[i] = r.harmonized_count; C.lo[i] = r.count_low; C.hi[i] = r.count_high;
    C.modis[i] = Number(r.modis_count); C.vfcd[i] = Number(r.viirs_firecell_days); C.vpx[i] = Number(r.viirs_pixels);
    C.est[i] = r.source_mix.startsWith("MODIS") ? 1 : 0;
  });
  if (METAS[k].zero_model?.type === "two_part") C.Z = await loadZero(k, C);
  CALS.set(k, C);
  return C;
}
const SEAS = m => [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 0][m];  // month index 0-11 -> DJF MAM JJA SON
const reg = (lat, lon) => Math.floor(Math.floor(lat * 10 + 1e-6) / 5) * 4000 + Math.floor(Math.floor(lon * 10 + 1e-6) / 5) + 2000;
async function loadZero(k, C) {  // two-part model: expected VIIRS where MODIS saw nothing
  const SN = { DJF: 0, MAM: 1, JJA: 2, SON: 3 };
  const [rates, share] = await Promise.all([
    readParquet(dir(k) + "zero_rates.parquet", ["ri", "rj", "season", "z", "z_lo", "z_hi", "zt", "zt_lo", "zt_hi"]),
    readParquet(dir(k) + "zero_share.parquet", ["lat", "lon", "season", "share"])]);
  const R = new Map();
  for (const r of rates) R.set((Number(r.ri) * 4000 + Number(r.rj) + 2000) * 4 + SN[r.season], [r.z, r.z_lo, r.z_hi, r.zt, r.zt_lo, r.zt_hi]);
  const S = share.map(r => ({ lat: r.lat, lon: r.lon, key: reg(r.lat, r.lon) * 4 + SN[r.season], share: r.share }));
  const c = METAS[k].coverage, vf = ym(c.viirs_first_full_month), hasM = new Set();
  for (let i = 0; i < C.n; i++) if (C.k[i] < vf && C.modis[i] > 0) hasM.add(reg(C.lat[i], C.lon[i]) * 1200 + C.k[i] - 1990 * 12);
  const mf = c.modis_first.slice(0, 10), mk0 = ym(mf.slice(0, 7)) + (mf.endsWith("-01") ? 0 : 1);
  return { R, S, hasM, vf, mk0, aq: ym(c.aqua_first_full_month) };
}
function addZero(agg, inAoi, k0, k1) {  // adds the zero part to monthly AOI totals
  const Z = CAL.Z, frac = new Map();
  for (const s of Z.S) if (inAoi(s.lat, s.lon)) frac.set(s.key, (frac.get(s.key) ?? 0) + s.share);
  for (let k = Math.max(k0, Z.mk0); k <= Math.min(k1, Z.vf - 1); k++) {
    const sea = SEAS(k % 12), terra = k < Z.aq;
    for (const [key, f] of frac) {
      if (key % 4 !== sea || Z.hasM.has(Math.floor(key / 4) * 1200 + k - 1990 * 12)) continue;
      const r = Z.R.get(key);
      if (!r) continue;
      let a = agg.get(k);
      if (!a) agg.set(k, a = { h: 0, lo: 0, hi: 0, modis: 0, vfcd: 0, vpx: 0 });
      const o = terra ? 3 : 0;
      a.h += f * r[o]; a.lo += f * r[o + 1]; a.hi += f * r[o + 2]; a.zero = (a.zero ?? 0) + f * r[o];
    }
  }
}
async function loadGlobal() {  // 0.25-degree x year totals for every processed country
  const rows = await readParquet("data/global_q025_year.parquet", ["lat", "lon", "y", "h"]);
  const n = rows.length;
  GLOBAL = { n, lat: new Float64Array(n), lon: new Float64Array(n), y: new Int16Array(n), h: new Float64Array(n) };
  rows.forEach((r, i) => { GLOBAL.lat[i] = r.lat; GLOBAL.lon[i] = r.lon; GLOBAL.y[i] = Number(r.y); GLOBAL.h[i] = r.h; });
}

// ---------------------------------------------------------------- AOI
const mode = () => document.querySelector("input[name=mode]:checked").value;
let POLY = [];  // polygon vertices as [lon, lat]
function inPoly(lat, lon, P) {  // ray casting point-in-polygon
  let inside = false;
  for (let i = 0, j = P.length - 1; i < P.length; j = i++) {
    const [xi, yi] = P[i], [xj, yj] = P[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function aoiTest() {
  if (mode() === "country") return () => true;  // country files already hold only that country
  if (mode() === "region") return LAYERS.regionTest();  // layers: province or department
  if (mode() === "poly") {
    const P = POLY.slice();
    return P.length >= 3 ? (lat, lon) => inPoly(lat, lon, P) : () => false;
  }
  if (mode() === "bbox") {
    const [s, n, w, e] = ["s", "n", "w", "e"].map(k => +$(k).value);
    const la0 = Math.min(s, n), la1 = Math.max(s, n), lo0 = Math.min(w, e), lo1 = Math.max(w, e);
    return (lat, lon) => lat >= la0 && lat <= la1 && lon >= lo0 && lon <= lo1;
  }
  const la = +$("plat").value, lo = +$("plon").value, km = +$("prad").value, rad = Math.PI / 180;
  return (lat, lon) => {  // great-circle (haversine) distance
    const a = Math.sin((lat - la) * rad / 2) ** 2 + Math.cos(la * rad) * Math.cos(lat * rad) * Math.sin((lon - lo) * rad / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(a)) <= km;
  };
}
function aoiGeojson() {
  if (!SEL || mode() === "country" || mode() === "region") return { type: "FeatureCollection", features: [] };
  if (mode() === "poly") {
    const ring = POLY.length ? [...POLY, POLY[0]] : [];
    return { type: "Feature", geometry: { type: ring.length >= 4 ? "Polygon" : "LineString", coordinates: ring.length >= 4 ? [ring] : ring } };
  }
  if (mode() === "bbox") {
    const [s, n, w, e] = ["s", "n", "w", "e"].map(k => +$(k).value);
    return { type: "Feature", geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } };
  }
  const la = +$("plat").value, lo = +$("plon").value, km = +$("prad").value, pts = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * 2 * Math.PI;
    pts.push([lo + (km / (111.32 * Math.cos(la * Math.PI / 180))) * Math.cos(a), la + (km / 111) * Math.sin(a)]);
  }
  return { type: "Feature", geometry: { type: "Polygon", coordinates: [pts] } };
}
const ym = v => { const [y, m] = v.split("-").map(Number); return y * 12 + m - 1; };

// ---------------------------------------------------------------- map
let map;
const NO_BASE = new URLSearchParams(location.search).get("basemap") === "off";
function initMap() {
  map = new maplibregl.Map({
    container: "map", center: [-60, 0], zoom: 1.6, attributionControl: false,
    style: {
      version: 8,
      projection: { type: "globe" },  // globe blends into flat Web Mercator when zoomed in
      sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
      sources: {
        // Keyless NASA GIBS Blue Marble for the globe; OSM detail when zoomed in
        bm: { type: "raster", tileSize: 256, maxzoom: 8,
          tiles: ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"],
          attribution: "Imagery: NASA GIBS Blue Marble" },
        osm: { type: "raster", tileSize: 256, maxzoom: 19,
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          attribution: "© <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors" },
        countries: { type: "geojson", data: WORLD, attribution: "Borders: Natural Earth" },
      },
      layers: [{ id: "bg", type: "background", paint: { "background-color": "#16324f" } },
        { id: "bm", type: "raster", source: "bm", layout: { visibility: NO_BASE ? "none" : "visible" } },
        { id: "osm", type: "raster", source: "osm", minzoom: 5.5, layout: { visibility: NO_BASE ? "none" : "visible" },
          paint: { "raster-opacity": ["interpolate", ["linear"], ["zoom"], 5.5, 0, 7.5, 0.85], "raster-saturation": -0.4 } },
        { id: "country-fill", type: "fill", source: "countries", paint: { "fill-color": "#ffffff", "fill-opacity": 0.01 } },
        { id: "country-line", type: "line", source: "countries", paint: { "line-color": "rgba(255,255,255,0.35)", "line-width": 0.6 } },
        { id: "sel-line", type: "line", source: "countries", filter: ["==", ["get", "name"], ""],
          paint: { "line-color": "#ffffff", "line-width": 2.2 } }],
    },
  });
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
  if (new URLSearchParams(location.search).has("debug")) window.__map = map;  // for headless tests
  const tileErr = { bm: 0, osm: 0 };  // hide a basemap after repeated tile failures
  map.on("error", e => { if (e.sourceId in tileErr && ++tileErr[e.sourceId] >= 6 && map.getLayer(e.sourceId)) map.setLayoutProperty(e.sourceId, "visibility", "none"); });
  let ll = map.getCenter();  // bottom bar: cursor position and zoom
  const showPos = () => { $("coords").textContent = `${ll.lat.toFixed(3)}°, ${ll.lng.toFixed(3)}° · zoom ${map.getZoom().toFixed(1)}`; };
  map.on("mousemove", e => { ll = e.lngLat; showPos(); }); map.on("zoomend", showPos);
  projCtrl = new ProjCtrl();
  map.addControl(projCtrl, "top-left");
  map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), "top-left");
  // Don't wait for basemap tiles ("load"): the app must still work if tiles are offline.
  return new Promise(res => { const ready = () => {
    if (map.getSource("cells")) return;
    map.addSource("global", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "global", type: "circle", source: "global", paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 1.1, 3, 2.4, 6, 8, 9, 30],
      "circle-color": ["get", "c"], "circle-opacity": 0.95,
      "circle-stroke-color": "rgba(0,0,0,0.45)", "circle-stroke-width": 0.3 } });
    map.addSource("cells", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "cells", type: "circle", source: "cells", paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1.6, 6, 3.5, 9, 10, 12, 16],
      "circle-color": ["get", "c"], "circle-opacity": 1,
      "circle-stroke-color": "rgba(0,0,0,0.55)", "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 3, 0.3, 6, 0.6, 9, 1.2] } });
    map.addSource("aoi", { type: "geojson", data: aoiGeojson() });
    map.addLayer({ id: "aoi-fill", type: "fill", source: "aoi", paint: { "fill-color": "#8ab4f8", "fill-opacity": 0.08 } });
    map.addLayer({ id: "aoi-line", type: "line", source: "aoi", paint: { "line-color": "#8ab4f8", "line-width": 2 } });
    const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    map.on("mousemove", "cells", e => {
      const p = e.features[0].properties;
      pop.setLngLat(e.lngLat).setHTML(`${p.lat}, ${p.lon}<br><b>${fmt(p.h)}</b> ${t("total").toLowerCase()}`).addTo(map);
    });
    map.on("mouseleave", "cells", () => pop.remove());
    map.on("mousemove", "global", e => {
      const p = e.features[0].properties;
      pop.setLngLat(e.lngLat).setHTML(`${t("cellsLbl")} ${p.lat}, ${p.lon}<br><b>${fmt(p.h)}</b> ${t("total").toLowerCase()}`).addTo(map);
    });
    map.on("mouseleave", "global", () => pop.remove());
    map.on("mouseenter", "country-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "country-fill", () => { map.getCanvas().style.cursor = ""; });
    map.moveLayer("sel-line");  // selected country's border above the dots
    setupDraw();
    LAYERS.initLayers({ map, d3, Plot, readParquet, t, fmt, download, toCsv, exportPng, exportSvg, aoiLabel,  // layers
      lang: () => lang, refresh: () => update(), isWhole: () => mode() === "country", isRegion: () => mode() === "region", panelRight, onRegion,
      legendHot: on => { document.querySelector(".legend:not(.legend-burn)").hidden = !on; } });
    res();
  }; map.isStyleLoaded() ? ready() : map.on("styledata", ready); });
}
class ProjCtrl {  // 3D globe / flat map toggle
  onAdd(m) {
    this.el = document.createElement("div"); this.el.className = "maplibregl-ctrl maplibregl-ctrl-group proj-ctrl";
    this.b = document.createElement("button"); this.b.type = "button"; this.el.append(this.b);
    this.globe = true; this.label();
    this.b.onclick = () => { this.globe = !this.globe; m.setProjection({ type: this.globe ? "globe" : "mercator" }); this.label(); };
    return this.el;
  }
  label() { this.b.textContent = this.globe ? t("flat") : t("globe"); this.b.title = this.globe ? t("globeTip") : t("flatTip"); }
  onRemove() { this.el.remove(); }
}
let projCtrl;
function syncMode() { $("toolbar").dataset.mode = mode(); }
function setupDraw() {
  let drawing = false, start = null, picking = false, lastDraw = 0;
  $("draw").onclick = () => {
    drawing = !drawing; picking = false;
    $("draw").classList.toggle("active", drawing);
    $("draw").textContent = drawing ? t("drawing") : t("draw");
    drawing ? map.dragPan.disable() : map.dragPan.enable();
    document.querySelector("input[value=bbox]").checked = true; syncMode();
  };
  $("pick").onclick = () => {
    picking = true; $("pick").textContent = t("picking");
    document.querySelector("input[value=radius]").checked = true; syncMode();
  };
  map.on("mousedown", e => { if (drawing) start = e.lngLat; });
  map.on("mousemove", e => {
    if (!drawing || !start) return;
    setBbox(start.lat, e.lngLat.lat, start.lng, e.lngLat.lng, false);
  });
  map.on("mouseup", e => {
    if (!drawing || !start) return;
    setBbox(start.lat, e.lngLat.lat, start.lng, e.lngLat.lng, false);
    start = null; drawing = false; map.dragPan.enable(); lastDraw = Date.now();
    $("draw").classList.remove("active"); $("draw").textContent = t("draw");
    update();
  });
  let poly = false;
  $("drawpoly").onclick = () => {
    poly = true; drawing = false; picking = false; POLY = [];
    document.querySelector("input[value=poly]").checked = true; syncMode();
    $("drawpoly").classList.add("active"); $("drawpoly").textContent = t("drawingPoly");
    map.doubleClickZoom.disable();
    map.getSource("aoi").setData(aoiGeojson());
  };
  map.on("dblclick", e => {
    if (!poly) return;
    e.preventDefault();
    poly = false; map.doubleClickZoom.enable();
    $("drawpoly").classList.remove("active"); $("drawpoly").textContent = t("drawPoly");
    POLY = POLY.filter((p, i) => i === 0 || p[0] !== POLY[i - 1][0] || p[1] !== POLY[i - 1][1]);
    $("polyinfo").textContent = `${POLY.length} pts`;
    if (POLY.length >= 3) update();
  });
  map.on("click", e => {
    if (poly) {
      POLY.push([+e.lngLat.lng.toFixed(3), +e.lngLat.lat.toFixed(3)]);
      map.getSource("aoi").setData(aoiGeojson());
      return;
    }
    if (!picking) {
      if (drawing || Date.now() - lastDraw < 500) return;
      if (LAYERS.handleClick(e)) return;  // layers: province or department click
      const f = map.queryRenderedFeatures(e.point, { layers: ["country-fill"] })[0];
      if (f && f.properties.name !== COUNTRIES[SEL]?.geo) chooseCountry(f.properties.name);
      return;
    }
    picking = false; $("pick").textContent = t("pick");
    $("plat").value = e.lngLat.lat.toFixed(3); $("plon").value = e.lngLat.lng.toFixed(3);
    update();
  });
}
function setBbox(a, b, c, d, fit = true) {
  $("s").value = Math.min(a, b).toFixed(2); $("n").value = Math.max(a, b).toFixed(2);
  $("w").value = Math.min(c, d).toFixed(2); $("e").value = Math.max(c, d).toFixed(2);
  map?.getSource("aoi")?.setData(aoiGeojson());
  if (fit && map) map.fitBounds([[Math.min(c, d), Math.min(a, b)], [Math.max(c, d), Math.max(a, b)]], { padding: 30 });
}

// ---------------------------------------------------------------- analysis
async function update() {
  status(t("loading")); syncMode();
  map.getSource("aoi").setData(aoiGeojson());
  if (!SEL) return renderGlobal();
  map.getSource("global").setData({ type: "FeatureCollection", features: [] });
  $("global-view").hidden = true; $("country-view").hidden = false;
  $("panel-sub").textContent = `${COUNTRIES[SEL].name} · ${mode() === "country" ? t("wholeCountry") : mode() === "region" ? LAYERS.region()?.name ?? "–" : aoiLabel().replace(/_/g, " ")} · ${$("d0").value} → ${$("d1").value}`;
  const inAoi = aoiTest(), k0 = ym($("d0").value), k1 = ym($("d1").value);
  const agg = new Map(), cellTot = new Map();
  for (let i = 0; i < CAL.n; i++) {
    const k = CAL.k[i];
    if (k < k0 || k > k1) continue;
    const ck = CAL.lat[i] * 1000 + CAL.lon[i];
    let c = cellTot.get(ck);
    if (!c) cellTot.set(ck, c = { lat: CAL.lat[i], lon: CAL.lon[i], h: 0 });
    c.h += CAL.h[i];
    if (!inAoi(CAL.lat[i], CAL.lon[i])) continue;
    let r = agg.get(k);
    if (!r) agg.set(k, r = { h: 0, lo: 0, hi: 0, modis: 0, vfcd: 0, vpx: 0 });
    r.h += CAL.h[i]; r.lo += CAL.lo[i]; r.hi += CAL.hi[i];
    r.modis += CAL.modis[i]; r.vfcd += CAL.vfcd[i]; r.vpx += CAL.vpx[i];
  }
  if (CAL.Z) addZero(agg, inAoi, k0, k1);
  const rows = [...agg.values()];
  // fill all months in range with zeros so medians and the calendar are honest
  const lastK = ym(meta.last_month), byK = agg;
  const vf = ym(meta.coverage.viirs_first_full_month), vl = ym(meta.coverage.viirs_last_full_month);
  lastRows = [];
  for (let k = k0; k <= Math.min(k1, lastK); k++) {
    const r = byK.get(k) ?? { h: 0, lo: 0, hi: 0, modis: 0, vfcd: 0, vpx: 0 };
    lastRows.push({ ...r, year: Math.floor(k / 12), month: (k % 12) + 1, k, est: !(k >= vf && k <= vl) });
  }
  // cells for map
  const cells = [...cellTot.values()].filter(c => c.h > 0);
  const cmax = d3.quantile(cells.map(c => c.h).sort(d3.ascending), 0.99) || 1;
  const col = d3.scaleSequentialSqrt(d3.interpolateYlOrRd).domain([0, cmax]).clamp(true);  // colourblind-safe, light to dark
  $("legend-max").textContent = "≥ " + fmt(cmax); $("legend-title").textContent = t("legendTitle");
  map.getSource("cells").setData({ type: "FeatureCollection", features: cells.map(c => ({
    type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] },
    properties: { h: c.h, c: col(c.h), lat: c.lat, lon: c.lon } })) });
  render();
  status(rows.length ? t("ready") : t("noData"));
  await LAYERS.onUpdate({ key: SEL, k0, k1, inAoi });  // layers: burned area map + card
}

const BA_STYLE = () => [["harmonized", null, 2.8], ["modisRaw", "6,3", 1.6], ["viirsRaw", "2,3", 1.6], ["viirsFcd", "10,3,2,3", 1.6]];
function stats() {
  const R = lastRows;
  const byMonth = d3.range(1, 13).map(m => {
    const v = R.filter(r => r.month === m).map(r => r.h).sort(d3.ascending);
    return { month: m, med: d3.quantile(v, .5) ?? 0, q1: d3.quantile(v, .25) ?? 0, q3: d3.quantile(v, .75) ?? 0, n: v.length };
  });
  const medOf = new Map(byMonth.map(d => [d.month, d.med]));
  R.forEach(r => { r.anom = Math.log2((r.h + 1) / (medOf.get(r.month) + 1)); r.med = medOf.get(r.month); });
  const years = d3.rollups(R, v => ({ h: d3.sum(v, r => r.h), lo: d3.sum(v, r => r.lo), hi: d3.sum(v, r => r.hi),
    modis: d3.sum(v, r => r.modis), vfcd: d3.sum(v, r => r.vfcd), vpx: d3.sum(v, r => r.vpx),
    est: v.some(r => r.est), months: v.length }), r => r.year).map(([year, o]) => ({ year, ...o }));
  return { byMonth, years };
}

function render() {
  const { byMonth, years } = stats();
  const R = lastRows, M = t("months");
  // KPIs
  const tot = d3.sum(R, r => r.h), lo = d3.sum(R, r => r.lo), hi = d3.sum(R, r => r.hi);
  const peakM = d3.greatest(byMonth, d => d.med), peakY = d3.greatest(years.filter(y => y.months === 12), d => d.h);
  const cur = R.at(-1);
  let curTxt = "–", curSub = "";
  if (cur) {
    const hist = R.filter(r => r.month === cur.month && r.k < cur.k).map(r => r.h);
    const med = d3.median(hist) ?? 0;
    const rank = 1 + hist.filter(v => v > cur.h).length;
    curTxt = `${fmt(cur.h)} <span class="d">/ ${t("median")} ${fmt(med)}</span>`;
    curSub = `${M[cur.month - 1]} ${cur.year} · ${med ? (cur.h >= med ? "+" : "") + Math.round(100 * (cur.h - med) / med) + "%" : ""}`
      + (hist.length ? ` · ${t("rank")(rank, hist.length + 1, M[cur.month - 1])}` : "");
  }
  $("kpis").innerHTML = [
    [t("total"), fmt(tot), `${t("range")} ${fmt(lo)}–${fmt(hi)}`, true],
    [t("raw"), `${fmt(d3.sum(R, r => r.modis))} <span class="d">MODIS</span>`, `${fmt(d3.sum(R, r => r.vpx))} VIIRS px · ${fmt(d3.sum(R, r => r.vfcd))} VIIRS fire-cell-days`],
    [t("current"), curTxt, curSub, cur && cur.h > (cur.med ?? 0)],
    [t("peakMonth"), peakM ? M[peakM.month - 1] : "–", peakM ? `${t("median")} ${fmt(peakM.med)}` : ""],
    [t("peakYear"), peakY ? peakY.year : "–", peakY ? fmt(peakY.h) : ""],
  ].map(([k, v, d, hot]) => `<div class="kpi ${hot ? "hot" : ""}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const W = Math.max(340, $("cal").clientWidth || 480);
  const yearsList = [...new Set(R.map(r => r.year))];
  const cellH = 15;
  const calOpts = (fill, color, extra = []) => Plot.plot({
    width: W, height: yearsList.length * cellH + 60, marginLeft: 40, marginRight: 84, marginTop: 30, padding: 0.06,
    x: { label: null, tickFormat: m => (W - 124) / 12 < 26 ? M[m - 1][0] : M[m - 1], axis: "top", domain: d3.range(1, 13) },
    y: { label: null, domain: yearsList, tickFormat: d => String(d) },
    color, style: { fontSize: "11px" },
    marks: [Plot.cell(R, { x: "month", y: "year", fill, inset: 0.5,
      title: r => `${M[r.month - 1]} ${r.year}\n${t("count")}: ${fmt(r.h)}${r.est ? ` (${fmt(r.lo)}–${fmt(r.hi)}, ${t("src_modis")})` : ` (${t("src_obs")})`}\nMODIS: ${fmt(r.modis)} · VIIRS px: ${fmt(r.vpx)}\n${t("anomalyLbl")}: ${r.anom.toFixed(2)}` }),
      Plot.text(ERAS.filter(e => yearsList.includes(e.y)), { x: 12, y: "y", text: e => "◂ " + e.short, textAnchor: "start", dx: 14, fill: "currentColor", fontSize: 9 }),
      ...extra],
  });
  const estDots = Plot.dot(R.filter(r => r.est && r.h > 0), { x: "month", y: "year", r: 1.4, fill: "white", stroke: "black", strokeWidth: 0.3 });
  $("cal").replaceChildren(calOpts("h", (new Set(R.map(r => Math.round(r.h))).size >= 20
      ? { scheme: "ylorrd", type: "quantile", n: 9, legend: true, label: t("count") + " (9 quantile classes)", width: Math.min(360, W - 20), tickFormat: d => fmt(d) }
      : { scheme: "ylorrd", type: "linear", legend: true, label: t("count"), width: Math.min(320, W - 20) }), [estDots]));
  $("anom").replaceChildren(calOpts("anom", { scheme: "PuOr", reverse: true, type: "linear", domain: [-4, 4], clamp: true, legend: true, label: t("anomalyLbl"), width: Math.min(320, W - 20) }));

  const half = W;
  $("seas").replaceChildren(Plot.plot({
    width: half, height: 260, marginLeft: 55, style: { fontSize: "11px" },
    x: { label: null, tickFormat: m => M[m - 1], domain: d3.range(1, 13), type: "point" }, y: { label: t("count"), grid: true },
    marks: [Plot.areaY(byMonth, { x: "month", y1: "q1", y2: "q3", fill: "#f28b54", fillOpacity: 0.22 }),
      Plot.lineY(byMonth, { x: "month", y: "med", stroke: "#f28b54", strokeWidth: 2, marker: "circle" }),
      Plot.ruleY([0])],
  }));
  $("annual").replaceChildren(Plot.plot({
    width: half, height: 260, marginLeft: 55, style: { fontSize: "11px" },
    x: { label: null, tickFormat: d => String(d), tickRotate: -45, type: "band" }, y: { label: t("count"), grid: true },
    color: { domain: [t("src_modis"), t("src_obs")], range: ["#cfd3d7", "#D55E00"], legend: true },
    marks: [Plot.barY(years, { x: "year", y: "h", fill: y => y.est ? t("src_modis") : t("src_obs"),
        title: y => `${y.year}: ${fmt(y.h)} (${fmt(y.lo)}–${fmt(y.hi)})${y.months < 12 ? ` · ${y.months} mo` : ""}` }),
      Plot.ruleX(years.filter(y => y.est), { x: "year", y1: "lo", y2: "hi", stroke: "currentColor" }),
      Plot.ruleY([0])],
  }));
  const ba = years.flatMap(y => [
    { year: y.year, s: t("harmonized"), v: y.h }, { year: y.year, s: t("modisRaw"), v: y.modis },
    ...(y.vpx ? [{ year: y.year, s: t("viirsRaw"), v: y.vpx }, { year: y.year, s: t("viirsFcd"), v: y.vfcd }] : [])]);
  $("ba").replaceChildren(Plot.plot({
    width: W, height: 280, marginLeft: 60, style: { fontSize: "11px" },
    x: { label: null, tickFormat: d => String(d) }, y: { label: "hotspots / year", grid: true },
    color: { legend: true, domain: [t("harmonized"), t("modisRaw"), t("viirsRaw"), t("viirsFcd")],
      range: ["#D55E00", "#56B4E9", "#CCCCCC", "#009E73"] },
    marks: [...BA_STYLE().map(([k, dash, w]) => Plot.lineY(ba.filter(d => d.s === t(k)), { x: "year", y: "v", stroke: "s", strokeWidth: w, strokeDasharray: dash, marker: "circle" })),
      Plot.ruleX(ERAS, { x: "y", stroke: "currentColor", strokeOpacity: 0.35, strokeDasharray: "3,3" }),
      Plot.text(ERAS, { x: "y", text: "label", rotate: -90, textAnchor: "end", dx: -2, dy: -4, frameAnchor: "top", fontSize: 9, fill: "currentColor" })],
  }));
}

// ---------------------------------------------------------------- downloads
function download(name, text, type = "text/csv") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const toCsv = (rows, cols) => [cols.join(","), ...rows.map(r => cols.map(c => {
  const v = r[c]; return v == null ? "" : typeof v === "string" && v.includes(",") ? `"${v}"` : v;
}).join(","))].join("\n");
function aoiLabel() {
  if (!SEL) return "world";
  if (mode() === "country") return COUNTRIES[SEL].name.replace(/ /g, "_");
  if (mode() === "region") return `${COUNTRIES[SEL].name.replace(/ /g, "_")}_${LAYERS.regionLabel()}`;  // layers
  if (mode() === "poly") {
    const lats = POLY.map(p => p[1]), lons = POLY.map(p => p[0]);
    return `poly${POLY.length}_${Math.min(...lats).toFixed(2)}_${Math.max(...lats).toFixed(2)}_${Math.min(...lons).toFixed(2)}_${Math.max(...lons).toFixed(2)}`;
  }
  return mode() === "bbox" ? `bbox_${$("s").value}_${$("n").value}_${$("w").value}_${$("e").value}`
    : `pt_${$("plat").value}_${$("plon").value}_${$("prad").value}km`;
}
$("csv-cal").onclick = () => download(`fire_calendar_${aoiLabel()}.csv`, toCsv(lastRows.map(r => ({
  year: r.year, month: r.month, harmonized_count: r.h.toFixed(2), count_low: r.lo.toFixed(2), count_high: r.hi.toFixed(2),
  source: r.est ? "MODIS_x_ratio" : "VIIRS_SNPP_observed", zero_part: (r.zero ?? 0).toFixed(2), modis_count: r.modis, viirs_pixels: r.vpx,
  viirs_firecell_days: r.vfcd, monthly_median: r.med?.toFixed(2), anomaly_log2: r.anom?.toFixed(3),
  method_version: meta.method_version })), ["year", "month", "harmonized_count", "count_low", "count_high", "source",
  "zero_part", "modis_count", "viirs_pixels", "viirs_firecell_days", "monthly_median", "anomaly_log2", "method_version"]));

$("csv-pts").onclick = async () => {
  $("pts-status").textContent = t("fetchingPts");
  const y0 = +$("d0").value.slice(0, 4), y1 = +$("d1").value.slice(0, 4);
  if (!meta.point_years.length) { $("pts-status").textContent = t("noPoints"); return; }
  const ys = meta.point_years.filter(y => y >= y0 && y <= y1);
  if (!ys.length) { $("pts-status").textContent = t("noData"); return; }
  const inAoi = aoiTest(), d0 = $("d0").value, d1 = $("d1").value, rows = [];
  for (const y of ys) {
    const pk = `${SEL}_${y}`;
    if (!pointCache.has(pk)) pointCache.set(pk, await readParquet(`${dir(SEL)}points/points_${y}.parquet`));
    for (const p of pointCache.get(pk)) {
      const d = p.acq_date instanceof Date ? p.acq_date.toISOString().slice(0, 10) : String(p.acq_date).slice(0, 10);
      const mth = d.slice(0, 7);
      const lat = p.lat ?? p.lat_e4 / 1e4, lon = p.lon ?? p.lon_e4 / 1e4;  // compact files store scaled ints
      if (mth < d0 || mth > d1 || !inAoi(lat, lon)) continue;
      rows.push({ latitude: lat.toFixed(4), longitude: lon.toFixed(4), acq_date: d, acq_time: String(p.acq_time).padStart(4, "0"),
        sensor: p.sensor, confidence: p.confidence, frp: p.frp ?? (p.frp_e1 / 10).toFixed(1), daynight: p.daynight, harm_weight: p.harm_weight });
    }
  }
  rows.sort((a, b) => (a.acq_date + a.acq_time).localeCompare(b.acq_date + b.acq_time));
  download(`fire_hotspots_${aoiLabel()}_${$("d0").value}_${$("d1").value}.csv`,
    toCsv(rows, ["latitude", "longitude", "acq_date", "acq_time", "sensor", "confidence", "frp", "daynight", "harm_weight"]));
  $("pts-status").textContent = t("ptsDone")(rows.length);
};

async function exportPng(id) {
  const el = $(id), svgs = [...el.querySelectorAll("svg")];
  const ink = getComputedStyle(document.body).color, bg = getComputedStyle(document.body).backgroundColor;
  const scale = 2, pad = 12;
  const imgs = await Promise.all(svgs.map(svg => new Promise(res => {
    const c = svg.cloneNode(true), r = svg.getBoundingClientRect();
    c.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    c.setAttribute("width", r.width); c.setAttribute("height", r.height);
    c.style.color = ink; c.style.fontFamily = "system-ui, sans-serif";
    const img = new Image();
    img.onload = () => res({ img, w: r.width, h: r.height });
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(c));
  })));
  const title = el.closest(".card").querySelector("h2").textContent;
  const mv = meta?.method_version ?? "global";
  const W = Math.max(...imgs.map(i => i.w)) + 2 * pad, H = imgs.reduce((a, i) => a + i.h + 6, 0) + 2 * pad + 44;
  const cv = document.createElement("canvas"); cv.width = W * scale; cv.height = H * scale;
  const g = cv.getContext("2d"); g.scale(scale, scale); g.fillStyle = bg; g.fillRect(0, 0, W, H);
  g.fillStyle = ink; g.font = "600 15px system-ui, sans-serif"; g.fillText(title, pad, pad + 14);
  g.font = "11px system-ui, sans-serif"; g.fillText(`${aoiLabel()} · ${$("d0").value} → ${$("d1").value} · NASA FIRMS · ${mv}`, pad, pad + 32);
  let y = pad + 44;
  for (const i of imgs) { g.drawImage(i.img, pad, y, i.w, i.h); y += i.h + 6; }
  cv.toBlob(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `${id}_${aoiLabel()}.png`; a.click(); });
}
document.querySelectorAll("[data-png]").forEach(b => b.onclick = () => exportPng(b.dataset.png));

function exportSvg(id) {
  const el = $(id), svgs = [...el.querySelectorAll("svg")], pad = 12, ink = getComputedStyle(document.body).color;
  const esc = x => String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const title = el.closest(".card").querySelector("h2").textContent;
  let y = pad + 44, W = 0, parts = [];
  for (const svg of svgs) {
    const r = svg.getBoundingClientRect(), c = svg.cloneNode(true);
    c.setAttribute("x", pad); c.setAttribute("y", y); c.setAttribute("width", r.width); c.setAttribute("height", r.height);
    c.style.color = ink;
    parts.push(new XMLSerializer().serializeToString(c));
    y += r.height + 6; W = Math.max(W, r.width);
  }
  const out = `<svg xmlns="http://www.w3.org/2000/svg" width="${W + 2 * pad}" height="${y + pad}" style="color:${ink};font-family:system-ui,sans-serif">
<text x="${pad}" y="${pad + 14}" font-size="15" font-weight="600" fill="currentColor">${esc(title)}</text>
<text x="${pad}" y="${pad + 32}" font-size="11" fill="currentColor">${esc(`${aoiLabel()} · ${$("d0").value} → ${$("d1").value} · NASA FIRMS · ${meta?.method_version ?? "global"}`)}</text>
${parts.join("\n")}</svg>`;
  download(`${id}_${aoiLabel()}.svg`, out, "image/svg+xml");
}
document.querySelectorAll("[data-svg]").forEach(b => b.onclick = () => exportSvg(b.dataset.svg));

// ---------------------------------------------------------------- method panel
function renderMethodWorld() {
  const f = x => x == null ? "–" : (+x).toFixed(1);
  const rows = Object.entries(COUNTRIES).map(([k, c]) => {
    const n = METAS[k].validation.aoi_monthly.Argentina, st = METAS[k].validation.step_check_national;
    const tp = n.two_part_ratio_plus_zero, rs = n.sum_ratio_region_season;
    return `<tr><td>${c.name}</td><td>${METAS[k].validation.test_years.join("–")}</td><td>${f(tp?.bias_pct)}</td><td>${f(rs.bias_pct)}</td>
      <td>${f(n.raw_modis_unscaled.bias_pct)}</td><td>${tp ? Math.round(100 * (1 - tp.MAE / rs.MAE)) + "%" : "–"}</td><td>${st ? (+st.step_artifact_factor).toFixed(2) : "–"}</td></tr>`;
  }).join("");
  $("method-body").innerHTML = `<p><b>One method for every country.</b> The same pipeline runs on each NASA FIRMS country file. VIIRS detections
  become unique 0.01° fire-cell-days; a VIIRS:MODIS ratio of sums per 0.5° region × season (fallback 2° → national) carries
  MODIS back to 2000 on the VIIRS scale, with bootstrap 5–95 % bounds. Since v8 a two-part model fits the ratio only on months where MODIS
  saw fire, and adds the average VIIRS count for months where MODIS saw none. Each country is trained on 2012–2019 and tested on later years.</p>
  <table><tr><th>country</th><th>test years</th><th>bias % (two-part, used)</th><th>bias % (ratio of sums, v7)</th><th>bias % (raw MODIS)</th><th>monthly error cut by two-part</th><th>2012 step factor</th></tr>${rows}</table>
  <p>Whole-country monthly series. Bias = Σ(predicted − observed VIIRS) / Σ observed. Monthly error = mean absolute error per month.
  Step factor 1.0 = no artificial jump when VIIRS starts. Select a country to see its full validation. Full write-up: <code>docs/METHOD.md</code>.</p>`;
}
function renderMethod() {
  if (!SEL) return renderMethodWorld();
  const v = meta.validation, c = meta.coverage, f = x => x == null ? "–" : (+x).toFixed(Math.abs(x) < 10 ? 2 : 1);
  const tbl = (obj) => `<table><tr><th>method</th><th>n</th><th>MAE</th><th>RMSE</th><th>bias</th><th>bias %</th><th>Spearman</th><th>peak-month</th></tr>` +
    Object.entries(obj).map(([k, m]) => `<tr><td>${k}</td><td>${m.n}</td><td>${f(m.MAE)}</td><td>${f(m.RMSE)}</td><td>${f(m.bias)}</td><td>${f(m.bias_pct)}</td><td>${f(m.spearman)}</td><td>${m.peak_month_agreement == null ? "–" : Math.round(100 * m.peak_month_agreement) + "%"}</td></tr>`).join("") + `</table>`;
  const sc = v.step_check_national;
  $("method-body").innerHTML = `
  <p><b>Data.</b> NASA FIRMS country file for ${COUNTRIES[SEL].name}. MODIS C6.1 ${c.modis_first} → ${c.modis_last} (${c.modis_rows_kept.toLocaleString()} detections kept),
  VIIRS S-NPP 375 m ${c.viirs_first} → ${c.viirs_last} (${c.viirs_rows_kept.toLocaleString()} kept). Filters: type = 0, MODIS confidence ≥ 30, VIIRS nominal + high.
  Built ${meta.built_utc}.</p>
  <p><b>Method.</b> (1) VIIRS detections collapsed to unique 0.01° fire-cells per day. (2) In the overlap, VIIRS:MODIS ratio of sums per 0.5° region × season
  (fallback 2° → national → all), bootstrap 5–95 % bounds. Months with VIIRS S-NPP use observed VIIRS fire-cell-days; earlier months use MODIS × ratio
  (a Terra-only ratio before Aqua, ${c.aqua_first_full_month}). ${meta.zero_model?.type === "two_part" ? `Two-part model: the ratio is fitted only on region-months
  where MODIS detected fire; for a 0.5° region-month with no MODIS detection, the mean VIIRS count of such months in the overlap (same region × season, fallback 2° → national)
  is added to area totals, spread over cells by where VIIRS saw those fires. It is not drawn as map dots.` : ""} After S-NPP ends, NOAA-20 fire-cell-days × a NOAA-20→S-NPP ratio. National MODIS ratio: <b>${f(meta.national_ratio_all)}</b>.</p>
  <p><b>Holdout validation</b> (train ${v.train_years.join("–")}, test ${v.test_years.join("–")}), 0.5° region-months:</p>${tbl(v.region_month_0p5deg)}
  <p>Region-month rows only count months with a MODIS or VIIRS detection, so they leave out the two-part model's zero-month part. Judge it on the table below.</p>
  <p>Whole-country monthly series (what the calendar shows):</p>
  ${tbl(v.aoi_monthly.Argentina)}
  ${SEL === "argentina" ? ["Rio Negro", "Chaco"].map(n => `<p>${n === "Rio Negro" ? "Río Negro" : n} (approximate province box), monthly:</p>${tbl(v.aoi_monthly[n])}`).join("") : ""}
  ${sc ? `<p><b>2012 step check.</b> Harmonized ${sc.post_years.join("–")} vs ${sc.pre_years.join("–")}: ×${f(sc.harmonized_post_over_pre)};
  raw MODIS (no sensor change): ×${f(sc.raw_modis_post_over_pre)}. Artifact factor ${f(sc.step_artifact_factor)} (1.0 = no artificial step).</p>` : ""}
  ${meta.validation_noaa20 ? `<p><b>NOAA-20 → S-NPP tie</b> (used after S-NPP ended ${c.viirs_last}). Train ${meta.validation_noaa20.train_years.join("–")}, test ${meta.validation_noaa20.test_years.join("–")}, 0.5° region-months:</p>
  ${tbl(meta.validation_noaa20.region_month_0p5deg)}
  <p>Whole country, monthly:</p>${tbl(meta.validation_noaa20.aoi_monthly.Argentina)}` : ""}
  <p>Day boundary: ${meta.date_mode === "solar" ? "local solar date (UTC + longitude/15 h)" : "UTC date"}. MODIS input: ${meta.modis_weight === "scan" ? "scan-angle weighted" : "detection counts"}.</p>
  <div id="scan"></div>
  <p>Full write-up, weak spots and cut list: <code>docs/METHOD.md</code>.</p>`;
  renderScan();
}

async function renderScan() {
  let sm;
  try { sm = await (await fetch(dir(SEL) + "scan_model.json")).json(); } catch { return; }
  const b = sm.bins, fit = d3.range(1, 9.6, 0.1).map(A => ({ A, eta: Math.exp(sm.b1 * (A - 1) + sm.b2 * (A - 1) ** 2) }));
  const el = $("scan");
  el.innerHTML = `<p><b>Scan-angle effect (real MODIS data).</b> ${sm.data}. MODIS pixel grows to ${sm.edge_pixel_km[0]} × ${sm.edge_pixel_km[1]} km at the 55° edge.
  Fit: ${sm.equation}, b1 = ${sm.b1.toFixed(3)}, b2 = ${sm.b2.toFixed(4)}. Detection efficiency at the swath edge is ${Math.round(100 * b.at(-1).eta_fit)}% of nadir.
  Basis: ${sm.basis}. Tested as 1/η weights (cap 4) on held-out years: it did not beat plain counts, so it is not applied (row "sum_ratio_scan_weighted" above).</p>`;
  el.append(Plot.plot({
    width: Math.min(640, el.clientWidth || 640), height: 260, marginLeft: 50, style: { fontSize: "11px" },
    x: { label: "pixel area relative to nadir (A)" }, y: { label: "detection efficiency η", domain: [0, 1.1], grid: true },
    color: { legend: true, domain: ["observed (per FIRMS scan step)", "fitted"], range: ["#2a78d6", "#eb6834"] },
    marks: [Plot.dot(b, { x: "A", y: "eta_obs", r: d => Math.max(1.5, Math.sqrt(d.n) / 30), fill: () => "observed (per FIRMS scan step)", fillOpacity: 0.7,
        title: d => `view ${d.view_deg.toFixed(1)}°, A ${d.A.toFixed(2)}\nη observed ${d.eta_obs.toFixed(2)}, fitted ${d.eta_fit.toFixed(2)}\n${d.n.toLocaleString()} cell-days` }),
      Plot.line(fit, { x: "A", y: "eta", stroke: () => "fitted", strokeWidth: 2 })],
  }));
}

// ---------------------------------------------------------------- world view and country choice
function yearRange() { return [+$("d0").value.slice(0, 4), +$("d1").value.slice(0, 4)]; }
function renderGlobal() {
  const [y0, y1] = yearRange(), tot = new Map(), byYear = new Map();
  for (let i = 0; i < GLOBAL.n; i++) {
    const y = GLOBAL.y[i];
    if (y < y0 || y > y1) continue;
    const key = GLOBAL.lat[i] * 1000 + GLOBAL.lon[i];
    let c = tot.get(key);
    if (!c) tot.set(key, c = { lat: GLOBAL.lat[i], lon: GLOBAL.lon[i], h: 0 });
    c.h += GLOBAL.h[i]; byYear.set(y, (byYear.get(y) ?? 0) + GLOBAL.h[i]);
  }
  const cells = [...tot.values()];
  const cmax = d3.quantile(cells.map(c => c.h).sort(d3.ascending), 0.99) || 1;
  const col = d3.scaleSequentialSqrt(d3.interpolateYlOrRd).domain([0, cmax]).clamp(true);
  $("legend-max").textContent = "≥ " + fmt(cmax);
  $("legend-title").textContent = t("legendWorld");
  map.getSource("global").setData({ type: "FeatureCollection", features: cells.map(c => ({
    type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: { h: Math.round(c.h), c: col(c.h), lat: c.lat, lon: c.lon } })) });
  map.getSource("cells").setData({ type: "FeatureCollection", features: [] });
  $("global-view").hidden = false; $("country-view").hidden = true;
  $("panel-sub").textContent = `${t("allCountries")} · ${y0}–${y1}`;
  const total = d3.sum(cells, c => c.h);
  $("gkpis").innerHTML = `<div class="kpi hot"><div class="k">${t("total")}</div><div class="v">${fmt(total)}</div><div class="d">${y0}–${y1}</div></div>
    <div class="kpi"><div class="k">${t("processed")}</div><div class="v">${Object.keys(COUNTRIES).length}</div><div class="d">${Object.values(COUNTRIES).map(c => c.name).join(", ")}</div></div>`;
  const ys = [...byYear].map(([year, h]) => ({ year, h })).sort((a, b) => a.year - b.year);
  const W = Math.max(340, $("gyear").clientWidth || 480);
  $("gyear").replaceChildren(Plot.plot({ width: W, height: 240, marginLeft: 74, style: { fontSize: "11px" },
    x: { label: null, tickFormat: d => d % 5 === 0 ? String(d) : "", type: "band" }, y: { label: t("count"), grid: true },
    marks: [Plot.barY(ys, { x: "year", y: "h", fill: "#D55E00", title: d => `${d.year}: ${fmt(d.h)}` }), Plot.ruleY([0])] }));
  $("clist").innerHTML = Object.entries(COUNTRIES).map(([k, c]) => {
    const b = METAS[k].validation.region_month_0p5deg.sum_ratio_region_season.bias_pct;
    return `<button class="cbtn" data-geo="${c.geo}"><b>${c.name}</b><span>${t("biasLbl")} ${b >= 0 ? "+" : ""}${b.toFixed(1)} %</span></button>`;
  }).join("");
  $("clist").querySelectorAll("button").forEach(b => b.onclick = () => chooseCountry(b.dataset.geo));
  status(t("ready"));
  LAYERS.onUpdate({ world: [y0, y1] });  // layers: world burned area
}
function geoBox(name) {  // bbox of the largest polygon, so island chains don't span the globe
  const f = WORLD.features.find(x => x.properties.name === name);
  if (!f) return null;
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  const big = polys.reduce((a, p) => p[0].length > a[0].length ? p : a);
  const xs = big[0].map(c => c[0]), ys = big[0].map(c => c[1]);
  return [Math.min(...ys), Math.max(...ys), Math.min(...xs), Math.max(...xs)];
}
function panelRight() {
  const P = $("panel"), open = !P.classList.contains("collapsed");
  return innerWidth > 760 && open ? Math.min(P.offsetWidth + 40, innerWidth / 2) : 40;
}
function onRegion(r) {  // layers: a province or department was clicked
  if (!SEL) { status(`${r.name} · ${t("noDataFor")($("search").value)}`, true); return; }
  document.querySelector("input[value=region]").checked = true; syncMode(); update();
}
function flyToBox([s, n, w, e]) {
  const P = $("panel"), open = !P.classList.contains("collapsed"), wide = innerWidth > 760;
  const right = panelRight();
  const bottom = !wide && open ? Math.min(P.offsetHeight + 20, innerHeight / 2) : 40;
  // flyTo arc: pulls back to show the globe, turns it, then zooms into the country
  map.fitBounds([[w, s], [e, n]], { padding: { top: 40, bottom, left: 60, right }, duration: 3200, curve: 1.6, maxZoom: 6.5, essential: true });
}
function chooseCountry(name) {
  const key = BY_GEO[name];
  LAYERS.onCountry(name);  // layers: load this country's boundaries
  map.setFilter("sel-line", ["==", ["get", "name"], name]);
  const box = key ? COUNTRIES[key].box : geoBox(name);
  if (box) flyToBox(box);
  if (key) return selectCountry(key);
  SEL = null; meta = null; document.body.classList.remove("has-country", "ar"); $("country").value = "";
  $("d0").max = $("d1").max = LAST; if (!userDates) $("d1").value = LAST;
  $("search").value = name;
  $("notice").hidden = false; $("notice").textContent = t("noDataFor")(name);
  update(); renderMethod();
}
async function selectCountry(k) {
  SEL = k; meta = METAS[k]; status(t("loading"));
  $("notice").hidden = true; $("search").value = COUNTRIES[k].name;
  document.body.classList.add("has-country"); document.body.classList.toggle("ar", k === "argentina");
  $("country").value = k;
  document.querySelector("input[value=country]").checked = true; syncMode();
  const [s, n, w, e] = COUNTRIES[k].box; setBbox(s, n, w, e, false);
  $("plat").value = ((s + n) / 2).toFixed(2); $("plon").value = ((w + e) / 2).toFixed(2);
  if (!userDates || $("d1").value > meta.last_month) $("d1").value = meta.last_month;
  $("d0").max = $("d1").max = meta.last_month;
  CAL = await loadCal(k);
  if (SEL !== k) return;  // user picked another country while loading
  renderMethod();
  await update();
}
function goWorld() {
  SEL = null; meta = null; $("search").value = ""; $("notice").hidden = true;
  $("d0").max = $("d1").max = LAST; if (!userDates) $("d1").value = LAST;
  document.body.classList.remove("has-country", "ar"); $("country").value = "";
  map.setFilter("sel-line", ["==", ["get", "name"], ""]);
  LAYERS.onCountry(null);  // layers
  map.flyTo({ zoom: 1.6, duration: 2200, essential: true });
  renderMethod(); update();
}
function onSearch() {
  const q = $("search").value.trim().toLowerCase();
  if (!q) return;
  const names = WORLD.features.map(f => f.properties.name);
  const hit = names.find(n => n.toLowerCase() === (ALIASES[q] ?? q).toLowerCase())
    ?? Object.values(COUNTRIES).find(c => c.name.toLowerCase() === q)?.geo
    ?? names.find(n => n.toLowerCase().startsWith(q));
  hit ? chooseCountry(hit) : status(t("noMatch"), true);
}

// ---------------------------------------------------------------- floating panel
function setupPanel() {
  const P = $("panel"), bar = $("panel-bar"), stage = P.parentElement;
  $("panel-toggle").onclick = () => {
    const c = P.classList.toggle("collapsed");
    $("panel-toggle").setAttribute("aria-expanded", String(!c));
    $("panel-toggle").setAttribute("aria-label", c ? "Expand results" : "Collapse results");
    if (!c && lastRows.length) render();
  };
  let drag = null;  // drag the panel by its top bar
  bar.addEventListener("pointerdown", e => {
    if (e.target.closest("button")) return;
    const r = P.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    drag = { dx: e.clientX - r.left, dy: e.clientY - r.top, sr };
    bar.setPointerCapture(e.pointerId);
  });
  bar.addEventListener("pointermove", e => {
    if (!drag) return;
    const { sr } = drag, w = P.offsetWidth, h = bar.offsetHeight;
    const x = Math.min(Math.max(e.clientX - drag.dx - sr.left, 0), sr.width - w);
    const y = Math.min(Math.max(e.clientY - drag.dy - sr.top, 0), sr.height - h);
    Object.assign(P.style, { left: x + "px", top: y + "px", right: "auto", bottom: "auto", maxHeight: (sr.height - y - 12) + "px" });
  });
  const end = () => { drag = null; };
  bar.addEventListener("pointerup", end); bar.addEventListener("pointercancel", end);
}

// ---------------------------------------------------------------- boot
document.querySelectorAll("input[name=mode]").forEach(r => r.onchange = () => { syncMode(); map.getSource("aoi").setData(aoiGeojson()); if (mode() === "country") update(); });
$("run").onclick = () => { if (SEL && mode() === "bbox") setBbox(+$("s").value, +$("n").value, +$("w").value, +$("e").value); update(); };
$("lang").onclick = () => { lang = lang === "en" ? "es" : "en"; applyI18n(); projCtrl?.label(); LAYERS.applyText(); renderMethod(); if (!SEL) renderGlobal(); else if (lastRows.length) render(); };
$("method-open").onclick = () => $("method").showModal();
$("method-close").onclick = () => $("method").close();
$("global-btn").onclick = goWorld;
for (const [k, c] of Object.entries(COUNTRIES)) $("country").add(new Option(c.name, k));
$("country").addEventListener("change", e => e.target.value ? chooseCountry(COUNTRIES[e.target.value].geo) : goWorld());
const PRESETS = { rionegro: [-42.0, -37.55, -71.95, -62.8], chaco: [-28.0, -24.1, -63.4, -58.3] };  // approximate province boxes
document.querySelectorAll("[data-preset]").forEach(b => b.onclick = () => {
  const p = PRESETS[b.dataset.preset];
  if (!p) { document.querySelector("input[value=country]").checked = true; syncMode(); flyToBox(COUNTRIES.argentina.box); return update(); }
  document.querySelector("input[value=bbox]").checked = true; syncMode();
  setBbox(...p); update();
});
$("search").addEventListener("change", onSearch);
$("search").addEventListener("keydown", e => { if (e.key === "Enter") onSearch(); });
setupPanel();
let resizeT; addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => SEL ? lastRows.length && render() : GLOBAL && renderGlobal(), 200); });

(async () => {
  try {
    const [world] = await Promise.all([fetch("data/ref/countries.geojson").then(r => r.json()), loadGlobal(), LAYERS.loadIndex(),
      ...Object.keys(COUNTRIES).map(async k => { METAS[k] = await (await fetch(dir(k) + "meta.json")).json(); })]);
    WORLD = world;
    $("country-list").innerHTML = WORLD.features.map(f => f.properties.name).sort().map(n => `<option value="${n}">`).join("");
    LAST = Object.values(METAS).map(m => m.last_month).sort().at(-1);
    $("d0").value = "2000-11"; $("d1").value = LAST;
    $("d0").min = $("d1").min = "2000-11"; $("d0").max = $("d1").max = LAST;
    ["d0", "d1"].forEach(id => $(id).addEventListener("change", () => { userDates = true; }));
    applyI18n();
    await initMap();
    renderMethod();
    await update();
  } catch (err) {
    console.error(err);
    status(`Error: ${err.message}. Serve the web/ folder over HTTP (python -m http.server), not file://`, true);
  }
})();
