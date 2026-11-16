"""Day/night check: separate day and night ratios vs the pooled ratio, held-out years."""
import argparse
import json
import pathlib

import duckdb
import numpy as np
import polars as pl

import build
from experiments import LEVELS, apply_levels, ratio_ok, metrics


def region_dn(con, vfirst, vlast):
    """0.5-degree region-months with MODIS and VIIRS split by day/night."""
    con.execute("""CREATE TABLE vd AS SELECT i100 // 10 i, j100 // 10 j, year(d) y, month(d) m,
        count(DISTINCT (i100, j100, d)) v,
        count(DISTINCT (i100, j100, d)) FILTER (WHERE daynight = 'D') vd,
        count(DISTINCT (i100, j100, d)) FILTER (WHERE daynight = 'N') vn
        FROM viirs GROUP BY ALL""")
    con.execute("""CREATE TABLE md AS SELECT i100 // 10 i, j100 // 10 j, year(d) y, month(d) m,
        count(*) FILTER (WHERE daynight = 'D') md, count(*) FILTER (WHERE daynight = 'N') mn,
        count(*) FILTER (WHERE daynight = 'N' AND sat = 'Aqua') mn_aqua
        FROM modis GROUP BY ALL""")
    df = con.sql(f"""SELECT i // 5 ri, j // 5 rj, y, m, sum(coalesce(md,0))::DOUBLE Md, sum(coalesce(mn,0))::DOUBLE Mn,
        sum(coalesce(mn_aqua,0))::DOUBLE Mn_aqua,
        sum(coalesce(v,0))::DOUBLE V, sum(coalesce(vd,0))::DOUBLE Vd, sum(coalesce(vn,0))::DOUBLE Vn
        FROM md FULL JOIN vd USING (i, j, y, m) WHERE (y*12+m-1) BETWEEN {vfirst} AND {vlast} GROUP BY ALL""").pl()
    return df.with_columns(M=pl.col("Md") + pl.col("Mn"), k=pl.col("y") * 12 + pl.col("m") - 1,
                           season=pl.col("m").replace_strict(build.SEASON, return_dtype=pl.Utf8),
                           ci=pl.col("ri") // 4, cj=pl.col("rj") // 4)


def fit(df, num, den):
    tr = df.filter((pl.col(den) > 0) | (pl.col(num) > 0))
    out = []
    for lvl, keys in LEVELS:
        g = tr.group_by(keys).agg(N=pl.col(num).sum(), D=pl.col(den).sum(), n=pl.len()) if keys else \
            tr.select(N=pl.col(num).sum(), D=pl.col(den).sum(), n=pl.len())
        out.append((lvl, keys, g.filter(ratio_ok(lvl == "all")).with_columns(
            **{f"R_{lvl}": pl.col("N") / pl.col("D")}).drop("N", "D", "n")))
    return out


def run(raw):
    con = duckdb.connect()
    build.load(con, raw)
    cov = build.coverage(con)
    vf, vl = build.full_months(cov["viirs"][0], cov["viirs"][1])
    df = region_dn(con, vf, vl)
    tr, te = df.filter(pl.col("y").is_between(2012, 2019)), df.filter(pl.col("y") >= 2020)
    te = apply_levels(te, fit(tr, "V", "M"), "R").with_columns(pred_pooled=pl.col("M") * pl.col("R")).drop("R")
    te = apply_levels(te, fit(tr, "Vd", "Md"), "Rd")
    te = apply_levels(te, fit(tr, "Vn", "Mn"), "Rn")
    # Vd + Vn double-counts cell-days seen day and night; scale back to V
    te = apply_levels(te, fit(tr.with_columns(S=pl.col("Vd") + pl.col("Vn")), "V", "S"), "c")
    te = te.with_columns(pred_split=(pl.col("Md") * pl.col("Rd") + pl.col("Mn") * pl.col("Rn")) * pl.col("c"))
    nat = te.group_by("k").agg(pl.col("V", "pred_pooled", "pred_split").sum())
    act = te.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    yr = df.group_by("y").agg(pl.col("Md", "Mn", "Mn_aqua", "V", "Vd", "Vn").sum()).sort("y")
    diag = {int(r["y"]): {"modis_night_share": r["Mn"] / (r["Md"] + r["Mn"]),
                          "viirs_night_share": r["Vn"] / (r["Vd"] + r["Vn"]),
                          "ratio_day": r["Vd"] / max(r["Md"], 1), "ratio_night": r["Vn"] / max(r["Mn"], 1)}
            for r in yr.iter_rows(named=True)}
    return {"national_month": {c: metrics(nat[c], nat["V"]) for c in ("pred_pooled", "pred_split")},
            "region_month_active": {c: metrics(act[c], act["V"]) for c in ("pred_pooled", "pred_split")},
            "by_year": diag}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+", help="name=raw_dir pairs")
    ap.add_argument("--out", default="docs/daynight.json")
    a = ap.parse_args()
    res = {}
    for pair in a.raw:
        name, raw = pair.split("=")
        r = res[name] = run(raw)
        n, g = r["national_month"], r["region_month_active"]
        print(f"{name:10s} nat bias {n['pred_pooled']['bias_pct']:+5.1f} -> {n['pred_split']['bias_pct']:+5.1f} | "
              f"nat MAE {n['pred_pooled']['MAE']:8.1f} -> {n['pred_split']['MAE']:8.1f} | reg MAE "
              f"{g['pred_pooled']['MAE']:6.2f} -> {g['pred_split']['MAE']:6.2f}")
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
