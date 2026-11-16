"""Province/state (admin-1) and department/county (admin-2) boundaries for the app.

Sources:
  admin-1: Natural Earth 1:10m states and provinces (public domain), every country.
  admin-2: geoBoundaries gbOpen ADM2, simplified (Runfola et al. 2020, PLoS ONE 15(4): e0231866);
           license varies by country and is stored per country in the index.

Output (web/data/ref/):
  admin1/<A3>.geojson, admin2/<A3>.geojson, admin_index.json (country name -> files, source, license)

Usage:
  python pipeline/boundaries.py                       # admin-1 for all, admin-2 for processed countries
  python pipeline/boundaries.py --adm2 ARG,CHL,BOL    # add admin-2 for more countries (ISO3)
"""
import argparse
import json
import pathlib
import re

import requests
import shapely
from shapely.geometry import mapping, shape

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
GB_API = "https://www.geoboundaries.org/api/current/gbOpen/{iso}/ADM2/"
PROCESSED = "ARG,AUS,BRA,CAN,USA,ESP,PRT,ITA,GRC,TUR"


def get_json(url, cache):
    p = pathlib.Path(cache) / re.sub(r"[^A-Za-z0-9_.-]", "_", url.split("://")[1])[-120:]
    if not p.exists():
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
    return json.loads(p.read_text())


def lfs_url(u):
    """github.com/<o>/<r>/raw/<ref>/<path> -> media.githubusercontent.com (Git LFS files)."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/raw/([^/]+)/(.+)", u)
    return f"https://media.githubusercontent.com/media/{m[1]}/{m[2]}/{m[3]}/{m[4]}" if m else u


def slim(geom, tol, nd):
    """Simplify and round coordinates to keep files small."""
    g = shapely.make_valid(shape(geom)).simplify(tol, preserve_topology=True)
    g = shapely.set_precision(g, 10 ** -nd)
    if g.is_empty:
        return None
    if g.geom_type == "GeometryCollection":
        polys = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        if not polys:
            return None
        g = shapely.union_all(polys)
    return mapping(g)


def write_fc(path, feats):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="web/data/ref")
    ap.add_argument("--cache", default="data/raw/boundaries")
    ap.add_argument("--adm2", default=PROCESSED, help="ISO3 list for admin-2 (geoBoundaries)")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    idx_p = out / "admin_index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.exists() else {}

    # Country names as the app knows them (Natural Earth 1:50m) -> ISO-style A3 code
    adm0 = get_json(NE + "ne_50m_admin_0_countries.geojson", a.cache)["features"]
    app_names = {f["properties"]["name"] for f in json.load(open(out / "countries.geojson"))["features"]}
    a3_of = {f["properties"]["NAME"]: f["properties"]["ADM0_A3"] for f in adm0 if f["properties"]["NAME"] in app_names}
    iso_of = {f["properties"]["ADM0_A3"]: f["properties"]["ISO_A3_EH"] for f in adm0}

    # admin-1: Natural Earth, every country
    adm1 = get_json(NE + "ne_10m_admin_1_states_provinces.geojson", a.cache)["features"]
    by_a3 = {}
    for f in adm1:
        p = f["properties"]
        g = slim(f["geometry"], 0.01, 3)
        if g:
            by_a3.setdefault(p["adm0_a3"], []).append({"type": "Feature", "geometry": g, "properties": {
                "id": p["adm1_code"], "name": p["name"] or p["name_en"] or p["adm1_code"], "type": p["type_en"] or "",
                "iso": p["iso_3166_2"] or ""}})
    for name, a3 in a3_of.items():
        if a3 not in by_a3:
            continue
        write_fc(out / "admin1" / f"{a3}.geojson", by_a3[a3])
        e = idx.setdefault(name, {})
        e.update({"a3": a3, "iso3": iso_of.get(a3, a3), "adm1": f"admin1/{a3}.geojson", "adm1_n": len(by_a3[a3]),
                  "adm1_source": "Natural Earth 1:10m admin-1 (public domain)"})

    # admin-2: geoBoundaries gbOpen, chosen countries
    by_iso = {}  # prefer the country whose own code is the ISO code (AUS, not Ashmore)
    for n, e in idx.items():
        if "iso3" in e and (e["iso3"] not in by_iso or e["a3"] == e["iso3"]):
            by_iso[e["iso3"]] = n
    for iso in [x.strip().upper() for x in a.adm2.split(",") if x.strip()]:
        name = by_iso.get(iso)
        if not name:
            print(f"{iso}: no matching country in countries.geojson, skipped")
            continue
        try:
            m = requests.get(GB_API.format(iso=iso), timeout=120).json()
            gj = get_json(lfs_url(m["simplifiedGeometryGeoJSON"]), a.cache)
        except Exception as ex:
            print(f"{iso}: geoBoundaries ADM2 unavailable ({ex})")
            continue
        feats = []
        for i, f in enumerate(gj["features"]):
            p = f["properties"]
            g = slim(f["geometry"], 0.005, 3)
            if g:
                feats.append({"type": "Feature", "geometry": g, "properties": {
                    "id": p.get("shapeID") or f"{iso}-{i}", "name": p.get("shapeName") or "", "type": m.get("boundaryCanonical") or "ADM2"}})
        a3 = idx[name]["a3"]
        write_fc(out / "admin2" / f"{a3}.geojson", feats)
        idx[name].update({"adm2": f"admin2/{a3}.geojson", "adm2_n": len(feats), "adm2_label": m.get("boundaryCanonical") or "",
                          "adm2_source": f"geoBoundaries gbOpen ADM2 ({m.get('boundarySource', '')}), build {m.get('buildDate', '')}",
                          "adm2_license": m.get("boundaryLicense", "")})
        print(f"{iso}: {len(feats)} admin-2 units, {m.get('boundaryLicense')}")
    idx_p.write_text(json.dumps(dict(sorted(idx.items())), indent=0, ensure_ascii=False))
    print(f"admin-1 for {sum(1 for e in idx.values() if 'adm1' in e)} countries -> {out}")


if __name__ == "__main__":
    main()
