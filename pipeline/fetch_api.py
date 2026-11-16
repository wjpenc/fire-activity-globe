"""Fetch the current year from the FIRMS area API. Needs FIRMS_MAP_KEY."""
import argparse
import csv
import datetime as dt
import io
import os
import pathlib
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://firms.modaps.eosdis.nasa.gov/api"
CACHE = None
PAIRS = {"modis": ("MODIS_SP", "MODIS_NRT"), "viirs-snpp": ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"),
         "viirs-jpss1": ("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT")}


def get(url, tries=12):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read().decode()
        except Exception as e:
            err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url.split('/api/')[1].split('/')[0]}: {err}")


def availability(key):
    txt = get(f"{API}/data_availability/csv/{key}/ALL")
    rows = list(csv.DictReader(io.StringIO(txt)))
    return {r["data_id"]: (dt.date.fromisoformat(r["min_date"]), dt.date.fromisoformat(r["max_date"]))
            for r in rows}


def fetch_range(key, source, start, end, bbox, days=1, workers=8):
    """Fetch [start, end] in chunks of `days` (1-day chunks answer fastest), in parallel."""
    chunks, d = [], start
    while d <= end:
        n = min(days, (end - d).days + 1)
        chunks.append((d, n))
        d += dt.timedelta(days=n)

    def one(c):
        d, n = c
        cache = CACHE / f"{source}_{bbox}_{d.isoformat()}_{n}.csv"
        if cache.exists():
            return cache.read_text()
        txt = get(f"{API}/area/csv/{key}/{source}/{bbox}/{n}/{d.isoformat()}")
        if not txt.startswith("latitude"):
            raise RuntimeError(f"{source} {d}: {txt[:200]}")
        cache.write_text(txt)  # resume support: chunks are cached
        return txt

    rows, header = [], None
    with ThreadPoolExecutor(workers) as ex:
        for (d, n), txt in zip(chunks, ex.map(one, chunks)):
            lines = txt.strip().splitlines()
            header = header or lines[0]
            rows += lines[1:]
            if d.day == 1:
                print(f"  {source} {d}: {len(lines) - 1} rows", flush=True)
    return header, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=dt.date.today().year)
    ap.add_argument("--bbox", default="-73.6,-55.2,-53.5,-21.7",
                    help="west,south,east,north. Argentina by default; build.py keeps only cells "
                         "that appear in the Argentina country files, which removes neighbours.")
    ap.add_argument("--name", default="Argentina")
    ap.add_argument("--sensors", default="modis,viirs-snpp,viirs-jpss1")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--key", default=os.environ.get("FIRMS_MAP_KEY"))
    a = ap.parse_args()
    if not a.key:
        raise SystemExit("Set FIRMS_MAP_KEY or pass --key")
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    global CACHE
    CACHE = out / ".api_cache"
    CACHE.mkdir(exist_ok=True)
    av = availability(a.key)
    print("data_availability:", {k: [str(x) for x in v] for k, v in av.items()})
    y0, y1 = dt.date(a.year, 1, 1), min(dt.date(a.year, 12, 31), dt.date.today())
    for sensor, (sp, nrt) in PAIRS.items():
        if sensor not in a.sensors.split(","):
            continue
        header, rows, cur = None, [], y0
        if sp in av and av[sp][1] >= y0:
            h, r = fetch_range(a.key, sp, y0, min(av[sp][1], y1), a.bbox)
            header, rows, cur = h, r, min(av[sp][1], y1) + dt.timedelta(days=1)
        if nrt in av and cur <= y1:
            h, r = fetch_range(a.key, nrt, max(cur, av[nrt][0]), min(av[nrt][1], y1), a.bbox)
            if header and h and h != header:
                # align NRT columns to SP header by name (NRT lacks `type`)
                hs, hn = header.split(","), h.split(",")
                idx = [hn.index(c) if c in hn else None for c in hs]
                r = [",".join(v.split(",")[i] if i is not None else "" for i in idx) for v in r]
            header = header or h
            rows += r
        if not header:
            print(f"no data for {sensor} {a.year}")
            continue
        dest = out / f"{sensor}_{a.year}_{a.name}_api.csv"
        dest.write_text(header + "\n" + "\n".join(rows) + "\n")
        print(f"wrote {dest} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
