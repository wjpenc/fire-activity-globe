"""Monthly burned area (MODIS MCD64A1 + VIIRS VNP64A1) aggregated to the app's 0.1-degree grid.

Source products (NASA LP DAAC, Earthdata login required):
  MCD64A1 v061, doi:10.5067/MODIS/MCD64A1.061 (Giglio et al.), Nov 2000 onward
  VNP64A1 v002, doi:10.5067/VIIRS/VNP64A1.002, Mar 2012 onward
Both are 500 m sinusoidal tiles; 'Burn Date' > 0 marks a burned pixel in that month.

Auth (never written to disk by this script):
  EARTHDATA_TOKEN env var (bearer token from https://urs.earthdata.nasa.gov/profile), or
  earthaccess login (~/.netrc or interactive prompt) when no token is set.

Usage:
  EARTHDATA_TOKEN=... python pipeline/burned_area.py --country argentina
  python pipeline/burned_area.py --world      # 0.25 deg x year layer from all built countries
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import pathlib
import re
import sys
import tempfile
import time
import urllib.parse

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import shapely
from pyhdf.SD import SD

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
PRODUCTS = {
    "MCD64A1": {"version": "061", "doi": "10.5067/MODIS/MCD64A1.061", "start": "2000-11-01"},
    "VNP64A1": {"version": "002", "doi": "10.5067/VIIRS/VNP64A1.002", "start": "2012-03-01"},
}
# Same keys and Natural Earth names as COUNTRIES in web/app.js
COUNTRIES = {"argentina": "Argentina", "australia": "Australia", "brazil": "Brazil",
             "canada": "Canada", "usa": "United States of America", "spain": "Spain", "portugal": "Portugal",
             "italy": "Italy", "greece": "Greece", "turkey": "Turkey"}
R_EARTH = 6371007.181          # MODIS sinusoidal sphere radius (m), from file StructMetadata
PIX = 463.31271653             # 500 m grid pixel size (m)
PIX_KM2 = PIX * PIX / 1e6      # equal-area projection, so every pixel has this area
X0, Y0 = -20015109.354, 10007554.677  # sinusoidal grid upper-left corner (m)
NAME_RE = re.compile(r"\.A(\d{4})(\d{3})\.h(\d\d)v(\d\d)\.(\d{3})\.")


# ---------------------------------------------------------------- auth and search
def session():
    s = requests.Session()
    tok = os.environ.get("EARTHDATA_TOKEN")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
        return s
    import earthaccess  # falls back to ~/.netrc or an interactive prompt
    earthaccess.login(persist=False)
    return earthaccess.get_requests_https_session()


def search(product, bbox, t0, t1):
    """All granule download URLs for a product, bbox (w,s,e,n) and date range."""
    w, s, e, n = bbox
    q = {"short_name": product, "version": PRODUCTS[product]["version"], "page_size": 2000,
         "temporal": f"{t0}T00:00:00Z,{t1}T23:59:59Z", "bounding_box": f"{w},{s},{e},{n}"}
    out, after = [], None
    while True:
        h = {"CMR-Search-After": after} if after else {}
        r = requests.get(CMR, params=q, headers=h, timeout=120)
        r.raise_for_status()
        ents = r.json()["feed"]["entry"]
        for ent in ents:
            urls = [l["href"] for l in ent.get("links", []) if l["href"].startswith("https") and l["href"].endswith(".hdf")]
            if urls:
                out.append(urls[0])
        after = r.headers.get("CMR-Search-After")
        if not ents or not after:
            break
    # Some granules' CMR time span overlaps the next month; keep files whose own month is in range
    def month_start(u):
        y, d = NAME_RE.search(u).groups()[:2]
        return (dt.date(int(y), 1, 1) + dt.timedelta(int(d) - 1)).isoformat()
    return sorted(u for u in set(out) if t0 <= month_start(u) <= t1)


# ---------------------------------------------------------------- geometry
def country_geom(name, geo="web/data/ref/countries.geojson"):
    feats = json.load(open(geo))["features"]
    f = next((f for f in feats if f["properties"]["name"] == name), None)
    if f is None:
        sys.exit(f"Country '{name}' not found in {geo}")
    g = shapely.geometry.shape(f["geometry"])
    shapely.prepare(g)
    return g


def tile_lonlat(h, v):
    """Pixel-centre lon/lat arrays (2400 x 2400) for sinusoidal tile h, v."""
    i = np.arange(2400)
    x = X0 + (h * 2400 + i + 0.5) * PIX
    y = Y0 - (v * 2400 + i + 0.5) * PIX
    lat = np.degrees(y / R_EARTH)[:, None] * np.ones((1, 2400))
    lon = np.degrees(x[None, :] / (R_EARTH * np.cos(np.radians(lat))))
    return lon, lat


def country_tiles(geom, step=0.05):
    """Sinusoidal tiles (h, v) touching the country, from a dense point sample."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    xy = [np.asarray(p.exterior.coords) for p in polys]
    w, s, e, n = geom.bounds
    gx, gy = np.meshgrid(np.arange(w, e + step, step), np.arange(s, n + step, step))
    gx, gy = gx.ravel(), gy.ravel()
    m = shapely.contains_xy(geom, gx, gy)
    xy.append(np.c_[gx[m], gy[m]])
    lon, lat = np.concatenate(xy).T
    x = R_EARTH * np.radians(lon) * np.cos(np.radians(lat))
    y = R_EARTH * np.radians(lat)
    h = np.floor((x - X0) / (2400 * PIX)).astype(int)
    v = np.floor((Y0 - y) / (2400 * PIX)).astype(int)
    return set(zip(h.tolist(), v.tolist()))


class TileCache:
    """Per tile: in-country mask and 0.1-degree cell index, computed once."""

    def __init__(self, geom):
        self.geom, self.c = geom, {}

    def get(self, h, v):
        if (h, v) not in self.c:
            lon, lat = tile_lonlat(h, v)
            ok = np.abs(lon) <= 180
            inside = np.zeros(lon.shape, bool)
            inside[ok] = shapely.contains_xy(self.geom, lon[ok], lat[ok])
            ci = np.floor(lat * 10).astype(np.int32)  # cell row, centre = (ci + 0.5) / 10
            cj = np.floor(lon * 10).astype(np.int32)
            self.c[(h, v)] = (inside, ci, cj)
        return self.c[(h, v)]


# ---------------------------------------------------------------- per-granule work
def read_burn_date(path):
    sd = SD(str(path))
    a = sd.select("Burn Date").get()
    sd.end()
    return a


def aggregate(url, path, tiles, product):
    """Burned and unmapped km2 per 0.1-degree cell for one monthly tile."""
    y, doy, h, v, ver = NAME_RE.search(url).groups()
    d = dt.date(int(y), 1, 1) + dt.timedelta(int(doy) - 1)
    inside, ci, cj = tiles.get(int(h), int(v))
    a = read_burn_date(path)
    rows = []
    for kind, m in (("burned", (a > 0) & inside), ("unmapped", (a == -1) & inside)):
        if not m.any():
            continue
        key = ci[m].astype(np.int64) * 10000 + cj[m]  # cj in [-1800, 1800)
        u, cnt = np.unique(key, return_counts=True)
        for k, c in zip(u, cnt):
            i, j = int(np.floor_divide(k + 5000, 10000)), int(k - np.floor_divide(k + 5000, 10000) * 10000)
            rows.append((round((i + 0.5) / 10, 2), round((j + 0.5) / 10, 2), d.year, d.month, product, ver, kind, c * PIX_KM2))
    # Burn dates outside the file's month would break the monthly sum; report them
    bd = a[(a > 0) & inside]
    m0 = (d.replace(day=1) - dt.date(d.year, 1, 1)).days + 1
    m1 = ((d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.date(d.year, 1, 1)).days
    off = int(((bd < m0) | (bd > m1)).sum())
    return rows, off


def fetch(sess, url, tmp):
    p = pathlib.Path(tmp) / url.rsplit("/", 1)[1]
    for k in range(5):
        try:
            with sess.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(p, "wb") as f:
                    for ch in r.iter_content(1 << 20):
                        f.write(ch)
            return p
        except Exception as e:  # retry network errors with backoff
            if k == 4:
                raise
            print(f"  retry {url.rsplit('/', 1)[1]}: {type(e).__name__}", flush=True)
            time.sleep(2 ** k)


# ---------------------------------------------------------------- country build
SCHEMA = pa.schema([("lat", pa.float64()), ("lon", pa.float64()), ("year", pa.int16()), ("month", pa.int8()),
                    ("product", pa.string()), ("version", pa.string()), ("kind", pa.string()), ("km2", pa.float32())])


def build_country(key, name, products, y0, y1, workers, cache_root):
    geom = country_geom(name)
    w, s, e, n = geom.bounds
    tiles = TileCache(geom)
    want = country_tiles(geom)
    print(f"{name}: {len(want)} sinusoidal tiles", flush=True)
    cache = pathlib.Path(cache_root) / key
    cache.mkdir(parents=True, exist_ok=True)
    done_f = cache / "done.txt"
    done = set(done_f.read_text().split()) if done_f.exists() else set()
    sess = session()
    info = {}
    for prod in products:
        t0 = max(f"{y0}-01-01", PRODUCTS[prod]["start"])
        t1 = min(f"{y1}-12-31", dt.date.today().isoformat())
        urls = [u for u in search(prod, (w, s, e, n), t0, t1)
                if tuple(int(g) for g in NAME_RE.search(u).groups()[2:4]) in want]
        todo = [u for u in urls if u.rsplit("/", 1)[1] not in done]
        print(f"{prod}: {len(urls)} granules for {name} {t0}..{t1}, {len(todo)} to process", flush=True)
        info[prod] = {"granules": len(urls)}
        off_total, t_start = 0, time.time()
        with tempfile.TemporaryDirectory() as tmp, cf.ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(fetch, sess, u, tmp): u for u in todo}
            buf, names = [], []
            for i, fu in enumerate(cf.as_completed(futs), 1):
                u = futs[fu]
                p = fu.result()
                rows, off = aggregate(u, p, tiles, prod)
                p.unlink()
                off_total += off
                buf.extend(rows)
                names.append(u.rsplit("/", 1)[1])
                if len(names) >= 200 or i == len(todo):  # checkpoint so a rerun resumes
                    part = cache / f"part_{prod}_{int(time.time() * 1000)}.parquet"
                    pq.write_table(pa.Table.from_pylist([dict(zip(SCHEMA.names, r)) for r in buf], schema=SCHEMA), part)
                    with open(done_f, "a") as f:
                        f.write("\n".join(names) + "\n")
                    buf, names = [], []
                    rate = i / (time.time() - t_start)
                    print(f"  {prod} {i}/{len(todo)} ({rate:.1f}/s, ~{(len(todo) - i) / rate / 60:.0f} min left)", flush=True)
        info[prod]["burn_dates_outside_month_px"] = off_total
        print(f"  {prod}: {off_total} burned pixels dated outside their file's month", flush=True)
    return info


def export_country(key, cache_root, out_dir, info, until):
    """Merge cached parts into one compact file the browser reads."""
    import duckdb
    cache = pathlib.Path(cache_root) / key
    files = sorted(str(p) for p in cache.glob("part_*.parquet"))
    if not files:
        sys.exit("No cached parts; run the download first.")
    uy, um_ = (int(x) for x in until.split("-"))
    # last month exported, to match the hotspot record
    parts = f"(SELECT * FROM read_parquet({files}) WHERE \"year\"::INT * 100 + \"month\" <= {uy * 100 + um_})"
    q = f"""SELECT lat, lon, "year"::SMALLINT AS year, "month"::TINYINT AS month, product,
              round(sum(km2) FILTER (WHERE kind = 'burned'), 4)::FLOAT AS burned_km2,
              round(coalesce(sum(km2) FILTER (WHERE kind = 'unmapped'), 0), 4)::FLOAT AS unmapped_km2
            FROM {parts} GROUP BY ALL HAVING sum(km2) FILTER (WHERE kind = 'burned') > 0
            ORDER BY product, year, month, lat, lon"""
    t = duckdb.sql(q).arrow().read_all()
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # data page v1 keeps the file readable by the browser Parquet reader
    pq.write_table(t, out / "burned_area.parquet", compression="snappy", data_page_version="1.0")
    # Monthly unmapped totals per product (land the algorithm could not map)
    um = duckdb.sql(f"""SELECT product, "year"::INT AS y, "month"::INT AS m, round(sum(km2), 1) AS km2
            FROM {parts} WHERE kind = 'unmapped' GROUP BY ALL ORDER BY ALL""").fetchall()
    rng = duckdb.sql(f"""SELECT product, any_value(version), min("year"::INT*100+"month"), max("year"::INT*100+"month")
            FROM {parts} GROUP BY product""").fetchall()
    meta = {"built_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "grid_deg": 0.1,
            "pixel_km2": round(PIX_KM2, 6), "clip": "pixel centre inside Natural Earth 1:50m country polygon",
            "products": {p: {**PRODUCTS[p], "version_seen": v, "first": f"{a // 100}-{a % 100:02d}",
                             "last": f"{b // 100}-{b % 100:02d}", **info.get(p, {})} for p, v, a, b in rng},
            "unmapped_monthly": [{"product": p, "y": y, "m": m, "km2": k} for p, y, m, k in um]}
    old = out / "burned_meta.json"
    meta["until"] = until
    if old.exists() and not info:  # export-only run keeps earlier granule counts
        prev = json.loads(old.read_text())["products"]
        for p in meta["products"]:
            meta["products"][p] = {**prev.get(p, {}), **meta["products"][p]}
    (out / "burned_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"{t.num_rows:,} cell-months -> {out / 'burned_area.parquet'}")
    update_index(out.parent.parent, country=out.name)


def update_index(data_dir, country=None, world=None):
    """web/data/burned_index.json tells the app which files exist (avoids 404s)."""
    p = pathlib.Path(data_dir) / "burned_index.json"
    idx = json.loads(p.read_text()) if p.exists() else {"countries": [], "world": False}
    if country and country not in idx["countries"]:
        idx["countries"] = sorted(idx["countries"] + [country])
    if world is not None:
        idx["world"] = world
    p.write_text(json.dumps(idx))


def build_world(countries_dir, out):
    import duckdb
    files = sorted(str(f) for f in pathlib.Path(countries_dir).glob("*/burned_area.parquet"))
    if not files:
        sys.exit("No country burned_area.parquet files yet.")
    q = f"""SELECT round(floor(lat*4)/4 + 0.125, 3)::DOUBLE AS lat, round(floor(lon*4)/4 + 0.125, 3)::DOUBLE AS lon,
               "year"::SMALLINT AS y, product, round(sum(burned_km2), 3)::FLOAT AS km2
            FROM read_parquet({files}) GROUP BY ALL ORDER BY product, y, lat, lon"""
    t = duckdb.sql(q).arrow().read_all()
    pq.write_table(t, out, compression="snappy", data_page_version="1.0")
    print(f"{len(files)} countries, {t.num_rows:,} rows -> {out}")
    update_index(pathlib.Path(out).parent, world=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", help="app key (argentina, usa, ...) or a Natural Earth country name")
    ap.add_argument("--products", default="MCD64A1,VNP64A1")
    ap.add_argument("--years", default="2000-2026", help="e.g. 2019-2020 for a quick test")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cache", default="data/raw/burned")
    ap.add_argument("--out", help="default web/data/countries/<key>")
    ap.add_argument("--until", default="2025-12", help="last month exported (hotspots end Dec 2025)")
    ap.add_argument("--export-only", action="store_true", help="rebuild output from the cache, no download")
    ap.add_argument("--world", action="store_true", help="build web/data/burned_q025_year.parquet")
    a = ap.parse_args()
    if a.world:
        return build_world("web/data/countries", "web/data/burned_q025_year.parquet")
    if not a.country:
        ap.error("--country or --world is required")
    key = a.country if a.country in COUNTRIES else a.country.lower().replace(" ", "_")
    name = COUNTRIES.get(key, a.country)
    y0, y1 = (int(x) for x in a.years.split("-"))
    info = {} if a.export_only else build_country(key, name, a.products.split(","), y0, y1, a.workers, a.cache)
    export_country(key, a.cache, a.out or f"web/data/countries/{key}", info, a.until)


if __name__ == "__main__":
    main()
