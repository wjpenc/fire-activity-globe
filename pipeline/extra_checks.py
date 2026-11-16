"""Extra validation from the action plan: year splits, low-confidence run, drift, static cells."""
import argparse
import json
import pathlib

import duckdb
import numpy as np
import polars as pl

import build as B


def setup(raw, modis_conf=30, viirs_conf="('n', 'h')"):
    B.MODIS_MIN_CONF, B.VIIRS_CONF = modis_conf, viirs_conf
    con = duckdb.connect()
    B.load(con, raw)
    cov = B.coverage(con)
    vfirst, vlast = B.full_months(cov["viirs"][0], cov["viirs"][1])
    B.monthly_cells(con, pl.DataFrame({"scan": [0.0], "w": [1.0]}).to_arrow())
    return con, vfirst, vlast


def score(con, train_years, test_years, vfirst, vlast):
    """Ratio-of-sums region x season vs single national ratio, scored on test years."""
    tr = B.region_pairs(con, train_years, vfirst, vlast)
    te = B.region_pairs(con, test_years, vfirst, vlast)
    keys = te.select("ri", "rj", "season").unique()
    ratios = B.fit_ratios(tr, "sum")
    rt = B.ratio_table(ratios, keys).select("ri", "rj", "season", "R")
    nat = float(tr["V"].sum() / tr["M"].sum())
    te = te.join(rt, on=["ri", "rj", "season"]).with_columns(
        p=pl.col("M") * pl.col("R"), s=pl.col("M") * nat)
    out = {}
    for aoi, (la0, la1, lo0, lo1) in B.AOIS.items():
        sub = te.filter((pl.col("ri") / 2 >= la0) & ((pl.col("ri") + 1) / 2 <= la1 + 0.5) &
                        (pl.col("rj") / 2 >= lo0) & ((pl.col("rj") + 1) / 2 <= lo1 + 0.5))
        V = sub["V"].sum()
        out[aoi] = {"bias_pct": round((sub["p"].sum() - V) / max(V, 1) * 100, 1),
                    "national_ratio_bias_pct": round((sub["s"].sum() - V) / max(V, 1) * 100, 1),
                    "raw_modis_bias_pct": round((sub["M"].sum() - V) / max(V, 1) * 100, 1)}
    act = te.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    out["region_month_MAE"] = round(float((act["p"] - act["V"]).abs().mean()), 2)
    out["region_month_MAE_national"] = round(float((act["s"] - act["V"]).abs().mean()), 2)
    return out


def loyo(con, vfirst, vlast, last_year):
    """Leave one overlap year out: fit on the rest, test on that year."""
    res = {}
    for y in range(2012, last_year + 1):
        con.execute("CREATE OR REPLACE TABLE cells_all AS SELECT * FROM cells")
        con.execute(f"CREATE OR REPLACE TABLE cells AS SELECT * FROM cells_all WHERE y <> {y}")
        tr = B.region_pairs(con, (2012, last_year), vfirst, vlast)
        con.execute("CREATE OR REPLACE TABLE cells AS SELECT * FROM cells_all")
        te = B.region_pairs(con, (y, y), vfirst, vlast)
        keys = te.select("ri", "rj", "season").unique()
        rt = B.ratio_table(B.fit_ratios(tr, "sum"), keys).select("ri", "rj", "season", "R")
        nat = float(tr["V"].sum() / tr["M"].sum())
        te = te.join(rt, on=["ri", "rj", "season"]).with_columns(p=pl.col("M") * pl.col("R"))
        row = {}
        for aoi, (la0, la1, lo0, lo1) in B.AOIS.items():
            sub = te.filter((pl.col("ri") / 2 >= la0) & ((pl.col("ri") + 1) / 2 <= la1 + 0.5) &
                            (pl.col("rj") / 2 >= lo0) & ((pl.col("rj") + 1) / 2 <= lo1 + 0.5))
            V = sub["V"].sum()
            row[aoi] = round((sub["p"].sum() - V) / max(V, 1) * 100, 1)
        row["Argentina_national_ratio"] = round((te["M"].sum() * nat - te["V"].sum()) / te["V"].sum() * 100, 1)
        res[y] = row
    return res


def drift(con):
    """Mean local solar overpass time (h) per year, daytime, Terra and Aqua."""
    df = con.sql("""
      SELECT sat, year(d_utc) y,
             avg(((substr(t,1,2)::INT*60 + substr(t,3,2)::INT + lon*4 + 1440) % 1440) / 60.0) h,
             count(*) n
      FROM modis WHERE daynight = 'D' AND year(d_utc) <= 2026 GROUP BY ALL ORDER BY sat, y""").pl()
    return {s: {int(r["y"]): round(r["h"], 2) for r in g.iter_rows(named=True)}
            for (s,), g in df.group_by(["sat"])}


def year_round(con, first=2012, last=2025):
    """0.1-degree cells with VIIRS fire in >= 10 months of every overlap year."""
    df = con.sql(f"""
      WITH ym AS (SELECT fdiv(i100, 10)::INT i, fdiv(j100, 10)::INT j, year(d) y, count(DISTINCT month(d)) nm,
                         count(DISTINCT d) nd
                  FROM viirs WHERE year(d) BETWEEN {first} AND {last} GROUP BY ALL)
      SELECT i, j, min(nm) min_months, avg(nd) mean_days, count(*) AS n_years
      FROM ym GROUP BY ALL HAVING count(*) = {last - first + 1} AND min(nm) >= 10
      ORDER BY mean_days DESC""").pl()
    tot = con.sql(f"SELECT count(*) FROM viirs WHERE year(d) BETWEEN {first} AND {last}").fetchall()[0][0]
    cells = [(r["i"], r["j"]) for r in df.iter_rows(named=True)]
    share = 0
    if cells:
        con.register("yr", df.select("i", "j").to_arrow())
        share = con.sql(f"""SELECT count(*) FROM viirs v JOIN yr ON fdiv(v.i100, 10)::INT = yr.i AND fdiv(v.j100, 10)::INT = yr.j
                            WHERE year(d) BETWEEN {first} AND {last}""").fetchall()[0][0] / tot
    return {"n_cells": len(cells), "share_of_viirs_detections_pct": round(share * 100, 2),
            "cells": [{"lat": round((i + 0.5) / 10, 2), "lon": round((j + 0.5) / 10, 2),
                       "min_months": int(r["min_months"]), "mean_fire_days": round(r["mean_days"], 1)}
                      for (i, j), r in zip(cells, df.iter_rows(named=True))][:15]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="web/data/extra_checks.json")
    a = ap.parse_args()
    res = {}
    con, vf, vl = setup(a.raw)
    last = (vl // 12) - (1 if vl % 12 != 11 else 0)
    print("year splits ...")
    res["split_2012_2018_test_2019_2021"] = score(con, (2012, 2018), (2019, 2021), vf, vl)
    res["split_2012_2019_test_2020_on"] = score(con, (2012, 2019), (2020, 2100), vf, vl)
    print("leave one year out ...")
    res["leave_one_year_out_bias_pct"] = loyo(con, vf, vl, 2025)
    print("drift and year-round cells ...")
    res["overpass_local_hour_day"] = drift(con)
    res["year_round_cells"] = year_round(con)
    print("low-confidence run ...")
    con2, vf2, vl2 = setup(a.raw, 0, "('n', 'h', 'l')")
    res["low_conf_included_split_2012_2019"] = score(con2, (2012, 2019), (2020, 2100), vf2, vl2)
    q = "SELECT (SELECT count(*) FROM modis), (SELECT count(*) FROM viirs)"
    res["detections_default"], res["detections_low_conf"] = con.execute(q).fetchall()[0], con2.execute(q).fetchall()[0]
    pathlib.Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
