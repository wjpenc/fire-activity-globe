# How to verify our FIRMS facts yourself

Every data claim in the app and in METHOD.md can be checked on NASA's own FIRMS site. These are the
checks we ran on 2026-11-15, what we saw, and how you repeat them in a few minutes.

## 1. The yearly country files exist and need no login

Open https://firms.modaps.eosdis.nasa.gov/country/ and pick a year, *Argentina* and a sensor. The
files download from this pattern (what `pipeline/download.py` uses):

```
https://firms.modaps.eosdis.nasa.gov/data/country/modis/2020/modis_2020_Argentina.csv
https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2020/viirs-snpp_2020_Argentina.csv
```

What we saw: MODIS files for 2000–2025 and VIIRS S-NPP files for 2012–2025 download fine. Both
`.../2026/..._2026_Argentina.csv` files return **404**: the current year is not published as a
country file yet, so 2026 comes from the API (step 3).

## 2. The columns and the `type` field

Open any CSV. Header lines we saw:

```
MODIS: latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,type
VIIRS: latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight,type
```

* MODIS `confidence` is 0–100; VIIRS `confidence` is `l` / `n` / `h`.
* `type`: 0 = presumed vegetation fire, 1 = active volcano, 2 = other static land source,
  3 = offshore. The definitions are in the FIRMS FAQ and attribute descriptions on
  earthdata.nasa.gov (search the FIRMS FAQ for "type"). In the Argentina MODIS files we found
  type 0: 1,680,407 rows, type 1: 4, type 2: 31,936, type 3: 69.

Reproduce our filter on one file (needs `pip install duckdb`):

```bash
python -c "import duckdb; print(duckdb.sql(\"SELECT count(*), count(*) FILTER (WHERE type=0 AND confidence>=30) FROM read_csv('data/raw/modis_2020_Argentina.csv')\").fetchall())"
# we got: 124,094 rows, 113,716 kept
python -c "import duckdb; print(duckdb.sql(\"SELECT count(*), count(*) FILTER (WHERE type=0 AND confidence IN ('n','h')) FROM read_csv('data/raw/viirs-snpp_2020_Argentina.csv')\").fetchall())"
# we got: 448,313 rows, 400,953 kept
```

## 3. What each sensor's archive covers right now (needs your MAP_KEY)

Open in a browser (replace `KEY`):

```
https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/KEY/ALL
```

What it said on 2026-11-15:

| source | from | to |
|---|---|---|
| MODIS_SP | 2000-11-01 | 2026-08-31 |
| MODIS_NRT | 2026-09-01 | 2026-11-15 |
| VIIRS_SNPP_SP | 2012-01-20 | 2026-07-31 |
| VIIRS_SNPP_NRT | 2026-08-01 | **2026-11-02** |
| VIIRS_NOAA20_SP / NRT | 2018-04-01 | 2026-07-31 / 2026-11-15 |
| VIIRS_NOAA21_SP / NRT | 2023-03-01 | 2026-07-31 / 2026-11-15 |

So: **MODIS is still delivering data in late 2026** (NRT up to today), and **VIIRS S-NPP stops on
2026-11-02**. SP (science quality, has `type`) ends in July/August 2026; later days are NRT
(no `type` field).

## 4. Suomi NPP has stopped

The FIRMS page on Earthdata, https://www.earthdata.nasa.gov/data/tools/firms, shows the banner
"Suomi NPP is no longer delivering new data. Users must transition to alternative products." It
links to a notice about new Suomi NPP observations ceasing on November 2, 2026, which matches the
`VIIRS_SNPP_NRT` end date above. This is why our reference sensor (S-NPP) needs a successor
calibration (NOAA-20/21) after October 2026; see CUT_LIST.md.

## 5. Spot-check the hotspots on the FIRMS map

1. In the app, choose Río Negro, set the dates to the month you want (e.g. July 2026), and click
   **Download hotspot CSV**.
2. Open https://firms.modaps.eosdis.nasa.gov/map/, go to the same place and dates, and turn on the
   MODIS and VIIRS S-NPP layers.
3. The points should line up one to one with the CSV (same dates, positions and sensors). Points
   flagged as static sources (type 2) or low confidence are in FIRMS but not in our CSV, by design.

## 6. The VIIRS:MODIS ratio is a property of the data, not a parameter we chose

The "Before / after harmonization" chart shows, per year, raw MODIS detections, raw VIIRS pixels
and VIIRS fire-cell-days for the same area. You can recompute any of those from the CSVs with the
filters in step 2. Our fitted national ratio (VIIRS fire-cell-days per MODIS detection) is printed
in the app's Method panel and in `web/data/meta.json`.
