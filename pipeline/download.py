"""Download FIRMS yearly country CSVs for MODIS and VIIRS S-NPP. Usage in README."""
import argparse
import datetime as dt
import pathlib
import time
import urllib.error
import urllib.request

BASE = "https://firms.modaps.eosdis.nasa.gov/data/country"
SENSORS = {"modis": 2000, "viirs-snpp": 2012, "viirs-jpss1": 2018}  # viirs-jpss1 = NOAA-20


def fetch(url: str, dest: pathlib.Path, tries: int = 6) -> str:
    for i in range(tries):
        try:
            tmp = dest.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.rename(dest)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "missing"
            err = str(e)
        except Exception as e:  # connection resets happen; retry with backoff
            err = str(e)
        time.sleep(2 * (i + 1))
    return f"failed ({err})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="Argentina")
    ap.add_argument("--out", default="data/raw")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    this_year = dt.date.today().year
    for sensor, start in SENSORS.items():
        for year in range(start, this_year + 1):
            name = f"{sensor}_{year}_{args.country}.csv"
            dest = out / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"have    {name}")
                continue
            status = fetch(f"{BASE}/{sensor}/{year}/{name}", dest)
            print(f"{status:8s}{name}")


if __name__ == "__main__":
    main()
