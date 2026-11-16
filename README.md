# Fire Activity Globe: harmonized MODIS + VIIRS hotspots, 2000-2025

NASA Space Apps Challenge 2026, challenge *Harmonization of MODIS and VIIRS Hotspots* (CONAE).

**Live app:** https://wjpenc.github.io/fire-activity-globe/

NASA's two active-fire records do not line up. MODIS (Terra 2000 onward, Aqua 2002 onward) has
1 km pixels; VIIRS S-NPP (2012 onward) has 375 m pixels and sees many more, smaller fires. Put
end to end, the record shows a false jump in fire activity at 2012. Raw MODIS counts are about
50 % below VIIRS in the same months (-46.5 % to -53.6 % in the five largest countries we tested).

This project puts both sensors on one **VIIRS-equivalent** monthly scale on a 0.1° grid, validates
it on years the model never saw, and shows it in a static web app on a 3D globe.

* Countries: Argentina, Australia, Brazil, Canada, United States, Spain, Portugal, Italy, Greece, Turkey.
* Period: November 2000 to December 2025 (all countries).
* Data source: NASA FIRMS (MODIS Collection 6.1, VIIRS S-NPP 375 m), plus NASA burned area
  (MCD64A1, VNP64A1) as a separate layer.

## What the app does

* Full-screen globe (2D/3D toggle). The world view shows every processed country at 0.25° x year.
* Search, click or pick a country. Draw a box, a polygon, or a point + radius inside it, or click
  a province/state or department/county (boundary layers).
* Results panel: month x year burning-activity calendar, anomalies against the monthly median,
  seasonality, yearly totals with uncertainty bands, latest month against its historical median,
  and a before/after harmonization chart.
* Burned-area card: MODIS MCD64A1 or VIIRS VNP64A1 monthly burned area for the same area.
* Downloads: CSV, PNG, SVG, and a per-detection hotspot CSV for every country.
* English/Spanish toggle. Colourblind-safe colours (yellow-orange-red ramp, Okabe-Ito lines).
* No server, no login, no install. All data is precomputed Parquet read in the browser.

## Method

Full details, every validation table and known weak spots: [docs/METHOD.md](docs/METHOD.md).

1. **Filter.** FIRMS `type == 0` (presumed vegetation fire; drops volcanoes, static sources such as
   gas flares, and offshore), MODIS confidence >= 30, VIIRS confidence nominal or high.
2. **Fair counting unit (VIIRS fire-cell-days).** One fire lights several 375 m VIIRS pixels where
   MODIS sees one 1 km pixel. VIIRS detections are collapsed to unique 0.01° (~1 km) cells per local
   solar day. In Argentina this cuts the VIIRS count by 43 % before any statistics.
3. **Local exchange rate.** In the overlap years, a VIIRS:MODIS ratio of sums (Σ VIIRS / Σ MODIS) is
   fitted per 0.5° region x season (DJF, MAM, JJA, SON). Thin strata (fewer than 8 region-months or
   50 MODIS detections) fall back to 2° x season, then national x season, then one national ratio.
   Before Aqua (2000-11 to 2002-07) a separate Terra-only ratio is used.
4. **Uncertainty.** 300 bootstrap resamples of region-months give a 5th-95th percentile range for
   every converted month. Resamples below the 50-detection minimum are dropped.
5. **Months where MODIS saw nothing (two-part model).** MODIS x ratio is zero there, but VIIRS often
   still sees fire. A second part predicts the mean VIIRS count in MODIS-zero region-months, by 0.5°
   region x season (fallback 2°, then national). It is added to area totals, not drawn as map dots.
6. **Final series.** Months with S-NPP data (2012-02 to 2025-12) use the observed VIIRS
   fire-cell-days. Earlier months use MODIS x ratio plus the zero part. Ratios are additive, so cell
   values sum correctly to any area a user draws.

Tested and **not** used, because they did worse on held-out years: median of ratios, quantile
mapping, a single national ratio, Aqua-only calibration, MODIS scan-angle weights, land-cover fire
types, a day/night split, and excluding orbit-drift years (METHOD.md sections 0, 3, 10).

## Validation

Train 2012-2019, test 2020-2025: predict VIIRS from MODIS alone in the test years and compare with
what VIIRS observed. Bias % = Σ(predicted - observed) / Σ observed. Source: METHOD.md sections 9-10,
`docs/experiments.json`.

| Country | Raw MODIS bias % | Production bias % (two-part) | Monthly MAE before → after two-part | 2012 step factor |
|---|---|---|---|---|
| Argentina | -48.3 | +4.5 | 1044 → 921 | 1.06 |
| Australia | -53.6 | -2.0 | 3354 → 3165 | 1.04 |
| Brazil | -50.9 | +7.4 | 7997 → 7896 | 1.10 |
| Canada | -50.0 | +6.3 | 3624 → 2777 | 1.21 |
| United States | -46.5 | -2.1 | 2423 → 1990 | 0.90 |
| Spain | | +10.8 | 142 → 100 | 1.13 |
| Portugal | | +13.7 | 38 → 36 | 1.09 |
| Italy | | -5.4 | 200 → 175 | 0.97 |
| Greece | | +13.0 | 71 → 55 | 1.02 |
| Turkey | | +1.2 | 338 → 270 | 0.99 |

Raw MODIS in the five Mediterranean countries ranges from -15 % (Portugal) to -67 % (Italy).
The step factor compares 2013-2014 with 2010-2011 in the harmonized series against raw MODIS;
1.0 means no artificial jump at the 2012 sensor switch.

Other checks (Argentina, earlier v4 build, METHOD.md section 8): leave-one-year-out bias within ±5 %
in 12 of 14 years; including low-confidence detections moves bias by at most 1.1 points; the regional ratio beats
a single national ratio in Río Negro (-3.4 % vs -32.1 %).

**What these numbers mean.** They measure how close MODIS x ratio comes to what VIIRS S-NPP saw,
summed over months and areas. They are not a census of fires: both sensors miss fires under cloud,
under canopy, between overpasses and below their detection limits. Results are strongest for
regional trends, seasons and anomalies; one month in one small cell can be off by much more than
the national bias. Canada, Greece, Portugal and Spain have the largest biases. Read
[docs/METHOD.md](docs/METHOD.md) section 5 before relying on a single number.

## Burned area and boundaries

* Burned area: MCD64A1 v061 (Nov 2000 onward) and VNP64A1 v002 (Mar 2012 onward), 500 m, summed
  into the same 0.1° cells, Nov 2000 to Dec 2025. The two products agree closely (monthly
  correlation 0.93-0.998 by country), so neither is rescaled; the app shows both. METHOD.md section 11.
* Admin-1: Natural Earth 1:10m, every country. Admin-2: geoBoundaries, for the ten countries.

## Run locally

Needs only Python 3 (built into macOS). The data is already built.

```bash
cd web
python3 -m http.server 8000
```

Open http://localhost:8000. It must be served over HTTP; opening `index.html` directly will not
load the data. Libraries are vendored in `web/vendor/`; only the map imagery needs internet.

## Rebuild the data

Python 3.10+. Full steps, flags and run times: [docs/BUILD_NOTES.md](docs/BUILD_NOTES.md).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipeline/download.py --country Brazil --out data/raw/Brazil          # FIRMS yearly country files, no key
python pipeline/build.py --raw data/raw/Brazil --out web/data/countries/brazil  # filter, grid, harmonize, validate, export
python pipeline/global_layer.py                                              # world-view layer
python pipeline/experiments.py --countries web/data/countries --out docs/experiments.json
python pipeline/burned_area.py --country brazil                              # needs a free NASA Earthdata login
python pipeline/boundaries.py --adm2 ARG,AUS,BRA,CAN,USA,ESP,PRT,ITA,GRC,TUR
```

Raw FIRMS downloads go to `data/raw/` and are not committed. Never commit a FIRMS MAP_KEY or an
Earthdata token.

## Repository layout

```
web/                    static app (MapLibre GL, Observable Plot, d3, hyparquet; vendored)
web/data/countries/<c>/ calendar_cells.parquet, meta.json, zero_*.parquet, burned_area.parquet, points/
web/data/ref/           country borders, admin-1 and admin-2 boundaries
pipeline/               Python pipeline (download, build, validation, burned area, boundaries)
docs/METHOD.md          method, validation tables, weak spots
docs/CUT_LIST.md        what was cut and what comes next
docs/VERIFY_FIRMS.md    how to check our FIRMS facts yourself
docs/ACTION_PLAN.pdf    plan for the fuller method
docs/BUILD_NOTES.md     detailed rebuild, layer and merge notes (earlier README)
```

Main table, `calendar_cells.parquet`, one row per 0.1° cell x month: `harmonized_count`,
`count_low`, `count_high`, `modis_count`, `viirs_firecell_days`, `ratio_level` (which fallback level
was used), `source_mix`, `method_version`. Point files hold the original FIRMS detections with a
`harm_weight` per point, so summing weights over any area reproduces the harmonized total.

## Data credits and citations

* We acknowledge the use of data and imagery from NASA's Fire Information for Resource Management
  System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Science Data and
  Information System (ESDIS).
* Giglio, L., Justice, C., Boschetti, L., Roy, D. MCD64A1 MODIS/Terra+Aqua Burned Area Monthly L3
  Global 500m SIN Grid V061. NASA LP DAAC. doi:10.5067/MODIS/MCD64A1.061
* VNP64A1 VIIRS/NPP Burned Area Monthly L3 Global 500m SIN Grid V002. NASA LP DAAC.
  doi:10.5067/VIIRS/VNP64A1.002
* MCD12C1 v061 land cover (used only in a rejected test). NASA LP DAAC.
* Li et al. 2018, JGR Atmospheres (MODIS detection loss with scan angle; METHOD.md section 6).
* van der Werf, G. R. et al. 2017, Earth System Science Data 9:697 (fire-type idea tested in section 10.2).
* Runfola, D. et al. 2020, geoBoundaries, PLoS ONE 15(4): e0231866. Licence per country in
  `web/data/ref/admin_index.json`.
* Natural Earth (public domain): country borders 1:50m, admin-1 1:10m.
* Globe imagery: NASA GIBS Blue Marble. Zoomed-in basemap © OpenStreetMap contributors.
  Add `?basemap=off` to the URL to hide both.
