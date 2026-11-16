# Cut list (what we deliberately left out, and what is next)

## Done in v2

* NOAA-20 → S-NPP tie: built, validated, used after S-NPP ended (METHOD.md §0).
* Scan-angle weights: built and validated; worse on holdout, so off by default.
* Aqua-only reference: validated; worse than Terra + Aqua, so not used.
* Local solar date: now the default.

## Still open

Ordered by how much it would improve the product.

| # | Item | Why cut today | Effort |
|---|---|---|---|
| 1 | **NOAA-20/21 as the post-S-NPP reference.** S-NPP stopped on 2026-11-02 (FIRMS data_availability + Earthdata banner). Fit a NOAA-20 → S-NPP ratio on 2018–2026 overlap so the VIIRS-equivalent scale continues. Today, months after the last full S-NPP month fall back to MODIS × ratio. | Needs another download set and a second validation | 0.5 day |
| 2 | **Model-based zeros.** When MODIS sees 0 in a cell-month we predict 0, but VIIRS often sees small fires there. A hurdle / zero-inflated model (Method 3) would fix the low bias in sparse regions such as Patagonia. | Time | 1 day |
| 3 | **Land-cover strata** (MODIS MCD12Q1) instead of 0.5° boxes for the ratio regions. | Extra data source | 0.5 day |
| 4 | **Diurnal/overpass terms.** Use Aqua-only MODIS (same ~13:30 overpass as VIIRS) as an alternative reference and compare. | Time | 2 h |
| 5 | **NRT backend** (FastAPI + scheduled FIRMS API pull) so the latest days update without a rebuild. | Static MVP agreed first | 0.5–1 day |
| 6 | ~~Province/department polygons~~ **Done in v8.** Natural Earth admin-1 everywhere, geoBoundaries admin-2 for the five countries; click to select. | | |
| 7 | ~~Burned-area layer~~ **Done in v8.** MCD64A1 v061 + VNP64A1 v002 on the 0.1° grid for the five countries. Not yet: the rest of the world, and a MODIS-to-VIIRS burned-area harmonization. | | |
| 8 | **More validation regions** outside Argentina (Brazilian Cerrado, boreal Canada, Mediterranean) as the brief suggests. | Country file downloads + compute | 2 h each |
| 9 | Sub-0.1° AOI accuracy for the calendar (it matches whole 0.1° cells). The hotspot CSV is already exact. | Fine for province-scale use | 2 h |
| 10 | ~~Polygon drawing~~ **Done in v3.** Click vertices, double-click to finish. | | |
| 11 | ~~SVG export alongside PNG~~ **Done in v3.** Each chart has an SVG button. | | |

## From the second handoff (HANDOFF_PROMPT.md), cut for time and why

| Item | Status | Why |
|---|---|---|
| VNP14 / VJ114 750 m "MODIS-replica" bridge | Cut | Not in FIRMS. Needs LP DAAC download (Earthdata login) and HDF processing. |
| Aqua-only MODIS reference | Validated in v2, not used | Worse than Terra+Aqua on holdout. |
| Apply scan-angle 1/η weights | Validated in v2, not used | Worse than plain counts on holdout. |
| NOAA-20 → S-NPP intercalibration | Done in v2 | See METHOD.md §0. |
| Wildland vs agricultural split | Cut | Needs land cover (MCD12Q1) and a persistence rule. |
| Synthetic simulator + truth recovery | Cut | We use real FIRMS data and real holdout validation instead. |
| Local solar date instead of UTC date | Done in v2 | Default. |
| Multi-page site, new colour spec | Cut | Kept the tested single page; cividis is colourblind-safe. |
| Era markers | Done | Calendar and before/after chart. |

## Changed from the plan, and why

* **DuckDB-WASM → hyparquet in the browser.** DuckDB-WASM 1.29 loads its Parquet extension from
  extensions.duckdb.org at runtime; in our offline test it failed ("function signature mismatch").
  A live demo cannot depend on that, so the app reads Parquet with hyparquet (small, pure JS) and
  aggregates in JavaScript (≈600k rows in about 1 s). The pipeline still uses DuckDB.
* **Median ratio → ratio of sums for production.** Both were validated (METHOD.md). The median ratio
  underestimated Río Negro by about 45 % on held-out years because it discards months where MODIS
  saw few fires; the ratio of sums cut that bias to about 2 % and removed the 2012 step in
  Río Negro. Both stay in `build.py` (`--estimator`).
* **Libraries vendored** in `web/vendor/` so the demo works without CDNs.
