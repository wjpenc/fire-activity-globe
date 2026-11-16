# Build notes (earlier README, kept for rebuild details)

NASA Space Apps Challenge 2026: *Harmonization of MODIS and VIIRS Hotspots* (CONAE). Version 2.

One consistent monthly hotspot series from 2000 to today. MODIS (Terra 2000+, Aqua 2002+) and
VIIRS S-NPP (2012+) are put on a single **VIIRS-equivalent** scale, validated on held-out years, and
shown in a static web app on a 3D globe. Five countries are processed so far (Argentina, Australia,
Brazil, Canada, United States); the pipeline runs on any FIRMS country file. Search or click a country,
or draw a box, polygon or point + radius inside it, pick dates, and
get a month × year burning-activity calendar, anomalies, seasonality, yearly totals, the latest month
vs. its historical median, and CSV/PNG/SVG downloads. English/Spanish toggle.

* Method, validation numbers and known weak spots: [docs/METHOD.md](METHOD.md)
* What we cut and what comes next: [docs/CUT_LIST.md](CUT_LIST.md)
* Action plan for the full method (fire types, clear looks, gap filling): [docs/ACTION_PLAN.pdf](ACTION_PLAN.pdf)
* How to check our FIRMS facts yourself: [docs/VERIFY_FIRMS.md](VERIFY_FIRMS.md)

## Run it locally (VS Code)

1. Unzip into `~/Desktop/NASA-SPACE-APPS` and open that folder in VS Code (File > Open Folder).
2. Open the VS Code terminal (Terminal > New Terminal) and run:

```bash
cd web
python3 -m http.server 8000
```

3. Open http://localhost:8000 in Chrome or Safari. Stop the server with Ctrl+C.

The data is already built, so no install is needed to view the app. It must be served over
HTTP; double-clicking `index.html` will not load the data. Libraries are vendored in
`web/vendor/`, so only the map imagery needs internet (NASA GIBS Blue Marble and OpenStreetMap, both keyless).

## The interface (v8)

A full-screen 3D globe (toggle **2D / 3D**, top left of the map; the globe turns flat as you zoom in).
By default it shows hotspots for every processed country (`web/data/global_q025_year.parquet`, 0.25° ×
year). Search for a country, click it, or pick it from the country dropdown: the globe flies there, the border is outlined, and only that
country's 0.1° cells show. Area tools (box, point + radius, polygon) work inside the selected country. For Argentina, preset
buttons set approximate Río Negro and Chaco boxes. All UI corners are square.
Results float in a panel on the right: drag it by its top bar, collapse it with the caret.
Colours are colourblind-safe: a light-to-dark yellow-orange-red ramp for hotspots, and Okabe-Ito
colours plus dash patterns for the chart lines. Borders: Natural Earth 1:50m (public domain).

## Layers (v8): burned area and boundaries

The **Layers** box (top left of the map) toggles:

* **Hotspots**: the harmonized FIRMS dots (as before).
* **Burned area**: NASA monthly burned area, Nov 2000 to Dec 2025 (same end as the hotspots), on the same 0.1° grid (0.25° x year in the world view),
  as blue squares. Pick the product: **MODIS MCD64A1** v061 (Nov 2000 onward) or **VIIRS VNP64A1**
  v002 (Mar 2012 onward). The results panel adds a **Burned area** card: totals per product,
  a monthly time series of both, a month x year calendar, CSV/PNG/SVG downloads.
* **Provinces / states** (Natural Earth admin-1, every country) and **Departments / counties**
  (geoBoundaries admin-2, built for the ten processed countries). With a boundary layer on, click a
  unit: it is outlined, the map flies to it and every result (hotspots and burned area) is for that
  unit. The area-type bar shows **Province / dept.** with its name.

Burned area and boundaries are matched on 0.1° cell centres, like the hotspots, so a very small
department (under roughly 100 km²) can contain no cell; the card says so when that happens.
What geoBoundaries calls admin-2 differs by country (Argentina 525 departments, US 3,233 counties,
but Italy 20 and Greece 14 units).

### Merging into another build

Copy `web/layers.js`, `pipeline/burned_area.py`, `pipeline/boundaries.py`, the `web/data` files above
plus `web/data/burned_*` and `web/data/ref/admin*`, and the v8 block at the end of `web/style.css`.
In `web/app.js` and `web/index.html`, every hook is a one- or two-line change marked `layers`
(search for "layers").

### Rebuild burned area (needs a free NASA Earthdata login)

```bash
pip install -r requirements.txt
# Token from https://urs.earthdata.nasa.gov/profile (Generate Token). Never commit it.
export EARTHDATA_TOKEN=paste_your_token_here
python pipeline/burned_area.py --country argentina            # about 8 min, ~5,000 tiles
python pipeline/burned_area.py --country brazil --years 2019-2020   # quick partial test
python pipeline/burned_area.py --world                         # world-view layer from all countries
```

Without `EARTHDATA_TOKEN` the script asks for your Earthdata username and password (via
`earthaccess`) and keeps them in memory only. Tiles are downloaded one at a time, reduced to 0.1°
cells and deleted, so disk use stays small. Progress is cached in `data/raw/burned/<country>/`, so a
rerun resumes. Outputs: `web/data/countries/<key>/burned_area.parquet` and `burned_meta.json`,
`web/data/burned_q025_year.parquet`, and `web/data/burned_index.json` (which files exist).

### Rebuild boundaries (no login)

```bash
python pipeline/boundaries.py --adm2 ARG,AUS,BRA,CAN,USA,ESP,PRT,ITA,GRC,TUR   # admin-1 everywhere + admin-2
python pipeline/boundaries.py --adm2 CHL,BOL,PRY    # add admin-2 for more countries (ISO3 codes)
```

Outputs `web/data/ref/admin1/<A3>.geojson`, `admin2/<A3>.geojson` and `admin_index.json`
(source and licence per country, shown in the map attribution).

## Rebuild the data from NASA FIRMS

Requires Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Yearly country files (no key): MODIS 2000+, VIIRS S-NPP 2012+, NOAA-20 2018+
#    Any FIRMS country name works (Argentina, Brazil, United_States, ...)
python pipeline/download.py --country Brazil --out data/raw/Brazil

# 2. Optional: current year from the FIRMS API (the shipped app stops at Dec 2025).
#    Free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
FIRMS_MAP_KEY=your_key python pipeline/fetch_api.py --year 2026 --out data/raw/Brazil

# 3. Filter, grid, harmonize, validate, export for the app (about 1 minute per country)
python pipeline/build.py --raw data/raw/Brazil --out web/data/countries/brazil

# 3b. Rebuild the world-view layer from every processed country
python pipeline/global_layer.py

# 4. Scan-angle diagnostic (MODIS detection efficiency vs. view angle)
python pipeline/scan_model.py --raw data/raw/Brazil --out web/data/countries/brazil

# 4b. v8 method tests across all built countries (two-part, fire types, drift)
python pipeline/experiments.py --countries web/data/countries --out docs/experiments.json
#     Land-cover fire types need MCD12C1 (Earthdata login) and pyhdf:
#     python pipeline/landcover.py MCD12C1.A2016001.061.*.hdf --out data/ref/firetype_0p1.parquet
#     Day/night test: python pipeline/daynight.py argentina=data/raw/Argentina

# 5. Extra checks from the action plan (splits, leave-one-year-out, drift, low confidence)
python pipeline/extra_checks.py --raw data/raw/Argentina --out web/data/extra_checks.json
```

Since v8 `build.py` uses the two-part zero model by default (`--zero-model none` gives the v7 method)
and also writes `zero_rates.parquet` and `zero_share.parquet`. `build.py` prints the validation metrics and writes them to `web/data/countries/<name>/meta.json`, which the app's
"Method & validation" panel reads. `--estimator median` switches the production ratio to the
median-of-ratios variant (both are always validated).

## Adding a country

Processed so far: Argentina, Australia, Brazil, Canada, United States, Spain, Portugal, Italy, Greece, Turkey (`web/data/countries/<name>/`).
To add one, run steps 1, 3 and 3b above for it, then add one line to `COUNTRIES` in `web/app.js`
with its Natural Earth name (as in `web/data/ref/countries.geojson`) and a bounding box. Run one
country at a time (Brazil needs about 4 GB of RAM). Validation for each country is in METHOD.md
sections 9 and 10. Every country has the per-detection hotspot CSV (since v8).

## Deploy on GitHub Pages

The app is plain static files in `web/`. Either set Pages to serve from a `docs/`-style folder, or
push `web/` to a `gh-pages` branch:

```bash
git subtree push --prefix web origin gh-pages
```

Data size is about 875 MB (ten countries' calendars and hotspot files, plus the world layer). That is under the GitHub Pages limit of 1 GB but close to it; adding more countries' hotspot files needs another host.

## Repository layout

```
pipeline/download.py   FIRMS country CSV downloader (MODIS, VIIRS S-NPP)
pipeline/fetch_api.py  FIRMS API fetch for the current year (SP first, then NRT)
pipeline/build.py      filter → grid → harmonize → validate → export (one country)
pipeline/global_layer.py world-view layer from all processed countries
pipeline/scan_model.py MODIS scan-angle detection-efficiency fit
pipeline/extra_checks.py extra validation from the action plan (METHOD.md section 8)
pipeline/burned_area.py  MCD64A1 + VNP64A1 monthly burned area -> 0.1 deg cells (Earthdata login)
pipeline/boundaries.py   Natural Earth admin-1 + geoBoundaries admin-2 for the app
web/layers.js            burned-area and boundary layers (hooks in app.js are marked "layers")
pipeline/experiments.py  v8 held-out method comparisons (METHOD.md section 10)
pipeline/landcover.py    MCD12C1 -> fire type per 0.1 deg cell
pipeline/daynight.py     day/night ratio test
web/                   static app (MapLibre GL 5 globe, Observable Plot, d3, hyparquet)
web/data/countries/<name>/  per country: calendar_cells.parquet, meta.json, scan_model.json, zero_*.parquet, points/
web/data/global_q025_year.parquet  world-view layer
web/data/ref/countries.geojson     Natural Earth 1:50m borders
docs/                  METHOD.md, CUT_LIST.md, VERIFY_FIRMS.md
```

## Output tables

`web/data/countries/<name>/calendar_cells.parquet`, one row per 0.1° cell × month:
`cell_id, lat, lon, year, month, harmonized_count, count_low, count_high, source_mix, method_version,
modis_count, modis_terra_count, viirs_firecell_days, viirs_pixels, ratio_level`

`web/data/countries/<name>/points/points_YYYY.parquet`, original detections:
`lat_e4, lon_e4 (degrees × 10⁴), acq_date, acq_time, sensor, confidence, frp_e1 (MW × 10), daynight, harm_weight`.
The app's CSV export converts them back to degrees and MW.
`harm_weight` is each point's contribution to the harmonized count (VIIRS: 1 / pixels in its
0.01° cell that day; MODIS before VIIRS: the regional ratio; MODIS during VIIRS months: 0), so
summing weights over an area reproduces the harmonized total.

## Data credit

We acknowledge the use of data and imagery from NASA's Fire Information for Resource Management
System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Science Data and
Information System (ESDIS). Country borders: Natural Earth 1:50m (public domain).
Burned area: Giglio, L., Justice, C., Boschetti, L., Roy, D. MCD64A1 MODIS/Terra+Aqua Burned Area
Monthly L3 Global 500m SIN Grid V061, doi:10.5067/MODIS/MCD64A1.061; VNP64A1 VIIRS/NPP Burned Area
Monthly L3 Global 500m SIN Grid V002, doi:10.5067/VIIRS/VNP64A1.002; both distributed by NASA EOSDIS
LP DAAC. Admin-1: Natural Earth 1:10m states and provinces (public domain). Admin-2: geoBoundaries
(Runfola, D. et al. 2020, PLoS ONE 15(4): e0231866), licence per country as recorded by
geoBoundaries: Argentina, Brazil CC BY 3.0 IGO; Australia, Greece CC BY 4.0; Canada Open Government
Licence Canada 2.0; United States public domain; Portugal CC0 1.0; Italy CC BY 3.0; Spain INE data
licence; Turkey ODbL 1.0 (also in `web/data/ref/admin_index.json`). Globe imagery: NASA GIBS Blue Marble (gibs.earthdata.nasa.gov). Zoomed-in basemap © OpenStreetMap contributors (tile.openstreetmap.org). Add `?basemap=off` to the URL to hide both.
