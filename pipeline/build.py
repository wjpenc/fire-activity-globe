"""Harmonize MODIS and VIIRS S-NPP hotspots into monthly 0.1-degree cells. See docs/METHOD.md."""
import argparse
import json
import pathlib
import datetime as dt

import duckdb
import numpy as np
import polars as pl
import pyarrow.parquet as pq

from scan_model import fit_scan, scan_weight_table

ESTIMATOR = "median"  # set from --estimator
METHOD_VERSION = "ratio-v1"
MODIS_MIN_CONF = 30
VIIRS_CONF = "('n', 'h')"  # VIIRS confidence levels kept
MIN_M = 5            # min MODIS detections in a region-month for a ratio sample
MIN_SUM_M = 50       # min MODIS detections per group for the ratio-of-sums
MIN_N = 8            # min region-month samples per group before falling back
MIN_Z = 24           # min MODIS-zero region-months per group for the zero part
ZERO_MODEL = "two_part"  # set from --zero-model
N_BOOT = 300
TRAIN = (2012, 2019)
TEST_START = 2020
SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
          6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
AOIS = {  # approximate province bounding boxes (lat_min, lat_max, lon_min, lon_max)
    "Rio Negro": (-42.0, -37.55, -71.95, -62.8),
    "Chaco": (-28.0, -24.1, -63.4, -58.3),
    "Argentina": (-90, 90, -180, 180),
}
N20_TRAIN = (2018, 2022)
DATE_MODE = "solar"  # set from --date
rng = np.random.default_rng(42)


def day_expr():
    """SQL for local solar date (UTC + lon/15 h) or plain UTC date."""
    if DATE_MODE == "utc":
        return "acq_date::DATE"
    return ("CAST(acq_date::TIMESTAMP + to_minutes(CAST(substr(lpad(acq_time, 4, '0'), 1, 2) AS INT) * 60"
            " + CAST(substr(lpad(acq_time, 4, '0'), 3, 2) AS INT) + CAST(round(longitude::DOUBLE * 4) AS INT)) AS DATE)")


def load(con, raw):
    con.execute(f"""
    CREATE TABLE modis AS
    SELECT latitude AS lat, longitude AS lon, {day_expr()} AS d, acq_date::DATE AS d_utc,
           lpad(acq_time::VARCHAR, 4, '0') AS t, satellite AS sat, scan::DOUBLE AS scan,
           confidence::INT AS conf, frp, daynight, coalesce(nullif(type, ''), 'NRT') AS src_type,
           filename LIKE '%_api.csv' AS from_api
    FROM read_csv('{raw}/modis_*_*.csv', union_by_name=true, all_varchar=true, filename=true)
    WHERE coalesce(nullif(type, ''), 'NRT') IN ('0', 'NRT') AND confidence::INT >= {MODIS_MIN_CONF}
    """)
    for t, pat in (("viirs", "viirs-snpp"), ("n20", "viirs-jpss1")):
        con.execute(f"""
        CREATE TABLE {t} AS
        SELECT latitude::DOUBLE AS lat, longitude::DOUBLE AS lon, {day_expr()} AS d, acq_date::DATE AS d_utc,
               lpad(acq_time::VARCHAR, 4, '0') AS t, confidence AS conf,
               frp::DOUBLE AS frp, daynight, coalesce(nullif(type, ''), 'NRT') AS src_type,
               filename LIKE '%_api.csv' AS from_api
        FROM read_csv('{raw}/{pat}_*_*.csv', union_by_name=true, all_varchar=true, filename=true)
        WHERE coalesce(nullif(type, ''), 'NRT') IN ('0', 'NRT') AND lower(left(confidence, 1)) IN {VIIRS_CONF}
        """)
    con.execute("ALTER TABLE modis ALTER lat TYPE DOUBLE; ALTER TABLE modis ALTER lon TYPE DOUBLE;"
                "ALTER TABLE modis ALTER frp TYPE DOUBLE;")
    for t in ("modis", "viirs", "n20"):
        con.execute(f"""ALTER TABLE {t} ADD COLUMN i100 INT; ALTER TABLE {t} ADD COLUMN j100 INT;
            UPDATE {t} SET i100 = floor(lat*100)::INT, j100 = floor(lon*100)::INT;""")
    # NRT has no type: drop cells SP history flags as volcano or static source
    con.execute(f"""CREATE TABLE static_mask AS
      SELECT DISTINCT floor(latitude::DOUBLE*50)::INT a, floor(longitude::DOUBLE*50)::INT b
      FROM read_csv(['{raw}/modis_*_*.csv', '{raw}/viirs-*_*_*.csv'], union_by_name=true, all_varchar=true)
      WHERE type IN ('1', '2')""")
    # API rows: keep only 0.1-degree cells seen in Argentina country files
    con.execute("""CREATE TABLE country_cells AS
      SELECT DISTINCT fdiv(i100, 10)::INT i, fdiv(j100, 10)::INT j FROM modis WHERE NOT from_api
      UNION SELECT DISTINCT fdiv(i100, 10)::INT, fdiv(j100, 10)::INT FROM viirs WHERE NOT from_api""")
    for t in ("modis", "viirs", "n20"):
        con.execute(f"""DELETE FROM {t} WHERE from_api AND
            (fdiv(i100, 10)::INT, fdiv(j100, 10)::INT) NOT IN (SELECT (i, j) FROM country_cells)""")
    for t in ("modis", "viirs", "n20"):
        con.execute(f"""DELETE FROM {t} WHERE src_type = 'NRT' AND
            (floor(lat*50)::INT, floor(lon*50)::INT) IN (SELECT (a, b) FROM static_mask)""")


def coverage(con):
    q = lambda t: con.execute(f"SELECT min(d), max(d), count(*) FROM {t}").fetchall()[0]
    cov = {"modis": q("modis"), "viirs": q("viirs"), "n20": q("n20")}
    cov["aqua_first"] = con.execute("SELECT min(d) FROM modis WHERE sat='Aqua'").fetchall()[0][0]
    cov["terra_last"] = con.execute("SELECT max(d) FROM modis WHERE sat='Terra'").fetchall()[0][0]
    cov["aqua_last"] = con.execute("SELECT max(d) FROM modis WHERE sat='Aqua'").fetchall()[0][0]
    return cov


def month_key(d):
    return d.year * 12 + d.month - 1


def full_months(first: dt.date, last: dt.date):
    """Month keys fully covered between first and last date."""
    a = month_key(first) + (0 if first.day == 1 else 1)
    nxt = (last + dt.timedelta(days=1))
    b = month_key(last) - (0 if nxt.month != last.month else 1)
    return a, b


def monthly_cells(con, sw):
    """0.1-degree monthly counts for all sensors; sw = scan weight table."""
    con.register("sw", sw)
    con.execute("""
    CREATE TABLE m_cell AS
    SELECT (fdiv(i100, 10)::INT) AS i, (fdiv(j100, 10)::INT) AS j, year(d) AS y, month(d) AS m,
           count(*) AS modis_n, count(*) FILTER (WHERE sat='Terra') AS terra_n,
           count(*) FILTER (WHERE sat='Aqua') AS aqua_n, sum(coalesce(sw.w, 4.0)) AS modis_w
    FROM modis LEFT JOIN sw ON sw.scan = round(modis.scan, 1) GROUP BY ALL""")
    con.execute("""
    CREATE TABLE n_cell AS
    SELECT (fdiv(i100, 10)::INT) AS i, (fdiv(j100, 10)::INT) AS j, year(d) AS y, month(d) AS m,
           count(DISTINCT (i100, j100, d)) AS n20_fcd
    FROM n20 GROUP BY ALL""")
    con.execute("""
    CREATE TABLE v_cell AS
    SELECT (fdiv(i100, 10)::INT) AS i, (fdiv(j100, 10)::INT) AS j, year(d) AS y, month(d) AS m,
           count(DISTINCT (i100, j100, d)) AS viirs_fcd, count(*) AS viirs_px
    FROM viirs GROUP BY ALL""")
    con.execute("""
    CREATE TABLE cells AS
    SELECT i, j, y, m, coalesce(modis_n,0) modis_n, coalesce(terra_n,0) terra_n,
           coalesce(aqua_n,0) aqua_n, coalesce(modis_w,0) modis_w,
           coalesce(viirs_fcd,0) viirs_fcd, coalesce(viirs_px,0) viirs_px, coalesce(n20_fcd,0) n20_fcd
    FROM m_cell FULL JOIN v_cell USING (i,j,y,m) FULL JOIN n_cell USING (i,j,y,m)""")


def region_pairs(con, years, vfirst, vlast, terra=False, mcol=None, vcol="viirs_fcd"):
    """Region-month (0.5 deg) predictor M vs S-NPP target V inside the overlap."""
    mcol = mcol or ("terra_n" if terra else "modis_n")
    df = con.sql(f"""
      SELECT (fdiv(i, 5)::INT) ri, (fdiv(j, 5)::INT) rj, y, m, sum({mcol})::DOUBLE mod_n, sum({vcol})::DOUBLE vir_n
      FROM cells WHERE y BETWEEN {years[0]} AND {years[1]}
        AND (y*12+m-1) BETWEEN {vfirst} AND {vlast}
      GROUP BY ALL""").pl().rename({"mod_n": "M", "vir_n": "V"})
    return df.with_columns(season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8))


def grid_pairs(con, years, vfirst, vlast, mcol="modis_n"):
    """Region-months on the full grid (zeros kept) for regions active in the overlap."""
    a, b = max(vfirst, years[0] * 12), min(vlast, years[1] * 12 + 11)
    df = con.sql(f"""
      WITH r AS (SELECT DISTINCT fdiv(i, 5)::INT ri, fdiv(j, 5)::INT rj FROM cells WHERE (y*12+m-1) BETWEEN {vfirst} AND {vlast}),
      k AS (SELECT range AS k FROM range({a}, {b + 1})),
      p AS (SELECT fdiv(i, 5)::INT ri, fdiv(j, 5)::INT rj, y*12+m-1 k, sum({mcol})::DOUBLE M, sum(viirs_fcd)::DOUBLE V
            FROM cells WHERE (y*12+m-1) BETWEEN {a} AND {b} GROUP BY ALL)
      SELECT ri, rj, k, coalesce(M, 0) M, coalesce(V, 0) V FROM r CROSS JOIN k LEFT JOIN p USING (ri, rj, k)
    """).pl()
    return df.with_columns(y=pl.col("k") // 12, m=pl.col("k") % 12 + 1).with_columns(
        season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8))


def fit_zero(grid: pl.DataFrame):
    """Part two: mean VIIRS fire-cell-days in region-months where MODIS saw nothing."""
    z = grid.filter(pl.col("M") == 0).with_columns(ci=pl.col("ri") // 4, cj=pl.col("rj") // 4)
    levels = {"r05": ["ri", "rj", "season"], "r2": ["ci", "cj", "season"], "nat": ["season"], "all": []}
    out = {}
    for lvl, keys in levels.items():
        tab = {}
        for k, g in (z.group_by(keys) if keys else [((), z)]):
            k = k if isinstance(k, tuple) else (k,)
            v = g["V"].to_numpy()
            if len(v) < (1 if lvl == "all" else MIN_Z):
                continue
            if len(v) <= 20000:
                boots = v[rng.integers(0, len(v), size=(N_BOOT, len(v)))].mean(1)
                lo, hi = np.percentile(boots, 5), np.percentile(boots, 95)
            else:  # large groups: normal approximation of the mean
                se = v.std() / np.sqrt(len(v))
                lo, hi = max(v.mean() - 1.645 * se, 0), v.mean() + 1.645 * se
            tab[k] = (float(v.mean()), float(lo), float(hi), len(v))
        out[lvl] = tab
    return out


def fit_ratios(pairs: pl.DataFrame, estimator: str = "median", pos_only: bool = False):
    """VIIRS:MODIS ratio per stratum with fallback levels and bootstrap 5-95% bounds."""
    p = pairs.with_columns(ci=(pl.col("ri") // 4), cj=(pl.col("rj") // 4))  # 2-degree
    if estimator == "median":
        p = p.filter(pl.col("M") >= MIN_M).with_columns(r=pl.col("V") / pl.col("M"))
    elif pos_only:  # two-part model: ratio only where MODIS saw something
        p = p.filter(pl.col("M") > 0)
    else:
        p = p.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    levels = {"r05": ["ri", "rj", "season"], "r2": ["ci", "cj", "season"],
              "nat": ["season"], "all": []}
    out = {}
    for lvl, keys in levels.items():
        groups = p.group_by(keys) if keys else [((), p)]
        tab = {}
        for k, g in groups:
            k = k if isinstance(k, tuple) else (k,)
            last = lvl == "all"
            if estimator == "median":
                r = g["r"].to_numpy()
                if len(r) < (1 if last else MIN_N):
                    continue
                idx = rng.integers(0, len(r), size=(N_BOOT, len(r)))
                boots = np.median(r[idx], axis=1)
                est = float(np.median(r))
            else:
                M, V = g["M"].to_numpy(), g["V"].to_numpy()
                if M.sum() < (1 if last else MIN_SUM_M) or len(M) < (1 if last else MIN_N):
                    continue
                idx = rng.integers(0, len(M), size=(N_BOOT, len(M)))
                ms = M[idx].sum(1)  # drop resamples below the estimate's own MODIS threshold
                boots = np.where(ms >= (1 if last else MIN_SUM_M), V[idx].sum(1) / np.maximum(ms, 1e-9), np.nan)
                est = float(V.sum() / M.sum())
            tab[k] = (est, float(np.nanpercentile(boots, 5)), float(np.nanpercentile(boots, 95)), len(g))
        out[lvl] = tab
    return out


def lookup(ratios, ri, rj, season):
    for lvl, key in (("r05", (ri, rj, season)), ("r2", (ri // 4, rj // 4, season)),
                     ("nat", (season,)), ("all", ())):
        if key in ratios[lvl]:
            return (*ratios[lvl][key], lvl)
    raise KeyError


def ratio_table(ratios, keys: pl.DataFrame):
    rows = []
    for ri, rj, season in keys.iter_rows():
        r, lo, hi, n, lvl = lookup(ratios, ri, rj, season)
        rows.append((ri, rj, season, r, lo, hi, n, lvl))
    return pl.DataFrame(rows, schema=["ri", "rj", "season", "R", "R_lo", "R_hi", "R_n", "R_level"],
                        orient="row")


def quantile_map(train: pl.DataFrame, test: pl.DataFrame):
    """Empirical quantile mapping MODIS->VIIRS per 0.5-deg region (2-deg fallback)."""
    def fit(df, keys):
        d = {}
        for k, g in df.group_by(keys):
            if g.height >= 24:
                d[k] = (np.sort(g["M"].to_numpy()), np.sort(g["V"].to_numpy()))
        return d
    tr = train.with_columns(ci=pl.col("ri") // 4, cj=pl.col("rj") // 4)
    f05, f2 = fit(tr, ["ri", "rj"]), fit(tr, ["ci", "cj"])
    fall = (np.sort(tr["M"].to_numpy()), np.sort(tr["V"].to_numpy()))
    preds = []
    for ri, rj, M in test.select("ri", "rj", "M").iter_rows():
        ms, vs = f05.get((ri, rj)) or f2.get((ri // 4, rj // 4)) or fall
        if M == 0:
            preds.append(0.0)
            continue
        p = (np.searchsorted(ms, M, side="left") + np.searchsorted(ms, M, side="right")) / 2 / len(ms)
        preds.append(float(np.quantile(vs, min(max(p, 0), 1))))
    return np.array(preds)


def metrics(pred, obs):
    pred, obs = np.asarray(pred, float), np.asarray(obs, float)
    err = pred - obs
    rp = pl.Series(pred).rank().to_numpy()
    ro = pl.Series(obs).rank().to_numpy()
    rho = float(np.corrcoef(rp, ro)[0, 1]) if len(obs) > 2 else float("nan")
    return {"n": int(len(obs)), "MAE": float(np.mean(np.abs(err))),
            "RMSE": float(np.sqrt(np.mean(err ** 2))), "bias": float(np.mean(err)),
            "bias_pct": float(err.sum() / max(obs.sum(), 1e-9) * 100), "spearman": rho}


def peak_agreement(df, pred_col):
    """Share of region-years where predicted peak month == observed peak month."""
    agg = df.filter(pl.col("V").sum().over(["ri", "rj", "y"]) >= 20)
    if agg.height == 0:
        return None
    pk = agg.group_by(["ri", "rj", "y"]).agg(
        pl.col("m").sort_by("V").last().alias("pv"),
        pl.col("m").sort_by(pred_col).last().alias("pp"))
    return float((pk["pv"] == pk["pp"]).mean())


def validate(con, cov, vfirst, vlast):
    train = region_pairs(con, TRAIN, vfirst, vlast)
    test = region_pairs(con, (TEST_START, 2100), vfirst, vlast)
    ratios = fit_ratios(train, "median")
    keys = test.select("ri", "rj", "season").unique()
    rt = ratio_table(ratios, keys)
    rs = ratio_table(fit_ratios(train, "sum"), keys).select(
        "ri", "rj", "season", pl.col("R").alias("Rs"), pl.col("R_level").alias("Rs_level"))
    test = test.join(rt, on=["ri", "rj", "season"]).join(rs, on=["ri", "rj", "season"]).with_columns(
        ratio_pred=pl.col("M") * pl.col("R"), sum_pred=pl.col("M") * pl.col("Rs"))
    nat = ratios["all"][()][0]
    test = test.with_columns(qm_pred=pl.Series(quantile_map(train, test)),
                             single_pred=pl.col("M") * nat)
    for name, mcol in (("scan_pred", "modis_w"), ("aqua_pred", "aqua_n")):
        tr = region_pairs(con, TRAIN, vfirst, vlast, mcol=mcol)
        te = region_pairs(con, (TEST_START, 2100), vfirst, vlast, mcol=mcol)
        r = ratio_table(fit_ratios(tr, "sum"), keys).select("ri", "rj", "season", pl.col("R").alias("Rv"))
        te = te.join(r, on=["ri", "rj", "season"]).select("ri", "rj", "y", "m", (pl.col("M") * pl.col("Rv")).alias(name))
        test = test.join(te, on=["ri", "rj", "y", "m"], how="left").with_columns(pl.col(name).fill_null(0.0))
    # two-part model on the zero-filled grid, so MODIS-zero months get a prediction
    gtr, gte = grid_pairs(con, TRAIN, vfirst, vlast), grid_pairs(con, (TEST_START, 2100), vfirst, vlast)
    gk = gte.select("ri", "rj", "season").unique()
    r1 = ratio_table(fit_ratios(gtr, "sum", pos_only=True), gk).select("ri", "rj", "season", pl.col("R").alias("R1"))
    zt = ratio_table(fit_zero(gtr), gk).select("ri", "rj", "season", pl.col("R").alias("Z"))
    gte = gte.join(r1, on=["ri", "rj", "season"]).join(zt, on=["ri", "rj", "season"]).with_columns(
        tp_pred=pl.when(pl.col("M") > 0).then(pl.col("M") * pl.col("R1")).otherwise(pl.col("Z")))
    pcols = [c for c in test.columns if c.endswith("_pred")]
    test = gte.select("ri", "rj", "y", "m", "season", "M", "V", "tp_pred").join(
        test.select("ri", "rj", "y", "m", *pcols), on=["ri", "rj", "y", "m"], how="left").with_columns(
        [pl.col(c).fill_null(0.0) for c in pcols])
    active = test.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    res = {"train_years": list(TRAIN), "test_years": [TEST_START, int(test["y"].max())],
           "region_month_0p5deg": {}, "aoi_monthly": {}, "notes": []}
    for name, col in (("median_ratio_region_season", "ratio_pred"),
                      ("sum_ratio_region_season", "sum_pred"), ("two_part_ratio_plus_zero", "tp_pred"),
                      ("sum_ratio_scan_weighted", "scan_pred"),
                      ("sum_ratio_aqua_only", "aqua_pred"), ("quantile_mapping", "qm_pred"),
                      ("single_national_ratio", "single_pred"), ("raw_modis_unscaled", "M")):
        m = metrics(active[col], active["V"])
        m["peak_month_agreement"] = peak_agreement(active, col)
        res["region_month_0p5deg"][name] = m
    # AOI-level monthly series (what the calendar actually shows)
    for aoi, (la0, la1, lo0, lo1) in AOIS.items():
        sub = test.filter((pl.col("ri") / 2 >= la0) & ((pl.col("ri") + 1) / 2 <= la1 + 0.5) &
                          (pl.col("rj") / 2 >= lo0) & ((pl.col("rj") + 1) / 2 <= lo1 + 0.5))
        s = sub.group_by(["y", "m"]).agg(pl.col("V").sum(), pl.col("M").sum(), pl.col("ratio_pred").sum(),
                                         pl.col("sum_pred").sum(), pl.col("tp_pred").sum(), pl.col("scan_pred").sum(),
                                         pl.col("aqua_pred").sum(), pl.col("qm_pred").sum()).sort(["y", "m"])
        s = s.with_columns(ri=pl.lit(0), rj=pl.lit(0))
        res["aoi_monthly"][aoi] = {
            name: {**metrics(s[col], s["V"]), "peak_month_agreement": peak_agreement(s, col)}
            for name, col in (("median_ratio_region_season", "ratio_pred"),
                              ("sum_ratio_region_season", "sum_pred"), ("two_part_ratio_plus_zero", "tp_pred"),
                              ("sum_ratio_scan_weighted", "scan_pred"), ("sum_ratio_aqua_only", "aqua_pred"),
                              ("quantile_mapping", "qm_pred"), ("raw_modis_unscaled", "M"))}
    lvl_counts = rt.group_by("R_level").len().to_dicts()
    res["fallback_levels_used_in_test"] = {d["R_level"]: d["len"] for d in lvl_counts}
    return res, test


def validate_n20(con, nfirst, vlast):
    """NOAA-20 to S-NPP ratio: train 2018-2022, test 2023+, both fire-cell-days."""
    tr = region_pairs(con, N20_TRAIN, nfirst, vlast, mcol="n20_fcd")
    te = region_pairs(con, (N20_TRAIN[1] + 1, 2100), nfirst, vlast, mcol="n20_fcd")
    keys = te.select("ri", "rj", "season").unique()
    r = ratio_table(fit_ratios(tr, "sum"), keys)
    te = te.join(r, on=["ri", "rj", "season"]).with_columns(pred=pl.col("M") * pl.col("R"))
    act = te.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    res = {"train_years": list(N20_TRAIN), "test_years": [N20_TRAIN[1] + 1, int(te["y"].max())],
           "region_month_0p5deg": {"n20_ratio_region_season": {**metrics(act["pred"], act["V"]),
                                                               "peak_month_agreement": peak_agreement(act, "pred")},
                                   "raw_n20_unscaled": metrics(act["M"], act["V"])},
           "aoi_monthly": {}}
    for aoi, (la0, la1, lo0, lo1) in AOIS.items():
        sub = te.filter((pl.col("ri") / 2 >= la0) & ((pl.col("ri") + 1) / 2 <= la1 + 0.5) &
                        (pl.col("rj") / 2 >= lo0) & ((pl.col("rj") + 1) / 2 <= lo1 + 0.5))
        s = sub.group_by(["y", "m"]).agg(pl.col("V").sum(), pl.col("M").sum(), pl.col("pred").sum())
        res["aoi_monthly"][aoi] = {"n20_ratio_region_season": metrics(s["pred"], s["V"]),
                                   "raw_n20_unscaled": metrics(s["M"], s["V"])}
    return res


def step_check(nat_year: pl.DataFrame, vstart_year: int):
    """Harmonized jump across 2012 divided by raw MODIS jump; 1.0 means no step."""
    d = {r["y"]: r for r in nat_year.iter_rows(named=True)}
    pre = [vstart_year - 2, vstart_year - 1]
    post = [vstart_year + 1, vstart_year + 2]  # skip the partial switch year
    if not all(y in d for y in pre + post):
        return None
    H = lambda ys: sum(d[y]["harmonized"] for y in ys)
    M = lambda ys: sum(d[y]["modis"] for y in ys)
    return {"pre_years": pre, "post_years": post,
            "harmonized_post_over_pre": H(post) / H(pre),
            "raw_modis_post_over_pre": M(post) / M(pre),
            "step_artifact_factor": (H(post) / H(pre)) / (M(post) / M(pre))}


def zero_tables(con, vfirst, vlast, mcol):
    """Zero-part rates per region x season (all MODIS and Terra-only) and cell shares."""
    g = grid_pairs(con, (2012, 2100), vfirst, vlast, mcol)
    gt = grid_pairs(con, (2012, 2100), vfirst, vlast, "terra_n")
    keys = g.select("ri", "rj").unique().join(pl.DataFrame({"season": ["DJF", "MAM", "JJA", "SON"]}), how="cross")
    za = ratio_table(fit_zero(g), keys).select("ri", "rj", "season", pl.col("R").alias("z"),
                                               pl.col("R_lo").alias("z_lo"), pl.col("R_hi").alias("z_hi"),
                                               pl.col("R_level").alias("z_level"))
    zt = ratio_table(fit_zero(gt), keys).select("ri", "rj", "season", pl.col("R").alias("zt"),
                                                pl.col("R_lo").alias("zt_lo"), pl.col("R_hi").alias("zt_hi"))
    rates = za.join(zt, on=["ri", "rj", "season"])
    cv = con.sql(f"""SELECT i, j, fdiv(i, 5)::INT ri, fdiv(j, 5)::INT rj, y*12+m-1 k, m, viirs_fcd::DOUBLE v FROM cells
                     WHERE (y*12+m-1) BETWEEN {vfirst} AND {vlast} AND viirs_fcd > 0""").pl().with_columns(
        season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8))
    cz = cv.join(g.filter(pl.col("M") == 0).select("ri", "rj", "k"), on=["ri", "rj", "k"], how="semi")
    seasons = pl.DataFrame({"season": ["DJF", "MAM", "JJA", "SON"]})
    anyc = con.sql("SELECT DISTINCT i, j, fdiv(i, 5)::INT ri, fdiv(j, 5)::INT rj, 1.0 v FROM cells").pl()
    # share priority: VIIRS in MODIS-zero months, all VIIRS same season, all VIIRS, any active cell
    cand = pl.concat([
        cz.group_by("i", "j", "ri", "rj", "season").agg(pl.col("v").sum()).with_columns(p=pl.lit(1)),
        cv.group_by("i", "j", "ri", "rj", "season").agg(pl.col("v").sum()).with_columns(p=pl.lit(2)),
        cv.group_by("i", "j", "ri", "rj").agg(pl.col("v").sum()).join(seasons, how="cross")
          .select("i", "j", "ri", "rj", "season", "v").with_columns(p=pl.lit(3)),
        anyc.join(seasons, how="cross").select("i", "j", "ri", "rj", "season", "v").with_columns(p=pl.lit(4)),
    ], how="vertical_relaxed")
    cand = cand.filter(pl.col("p") == pl.col("p").min().over("ri", "rj", "season"))
    share = cand.with_columns(share=pl.col("v") / pl.col("v").sum().over("ri", "rj", "season")).select(
        lat=((pl.col("i") + 0.5) / 10).round(2), lon=((pl.col("j") + 0.5) / 10).round(2),
        season="season", share=pl.col("share").round(5)).filter(pl.col("share") > 0)
    return rates.sort("ri", "rj", "season"), share.sort("lat", "lon", "season")


def compact_points(path):
    """Rewrite a points file small: scaled ints with delta encoding, dictionary strings."""
    import pyarrow as pa
    import pyarrow.compute as pc
    t = pq.read_table(path)
    i32 = lambda c, f: pc.cast(pc.round(pc.multiply(t[c], f)), pa.int32())
    out = pa.table({"lat_e4": i32("lat", 1e4), "lon_e4": i32("lon", 1e4), "acq_date": t["acq_date"],
                    "acq_time": pc.cast(t["acq_time"], pa.int16()), "sensor": t["sensor"],
                    "confidence": pc.cast(t["confidence"], pa.string()), "frp_e1": i32("frp", 10),
                    "daynight": t["daynight"], "harm_weight": t["harm_weight"]})
    pq.write_table(out, path, row_group_size=20000, data_page_version="1.0", compression="snappy",
                   use_dictionary=["acq_date", "acq_time", "sensor", "confidence", "daynight", "harm_weight"],
                   column_encoding={c: "PLAIN" for c in ("lat_e4", "lon_e4", "frp_e1")})


def zero_year_totals(cells: pl.DataFrame, rates: pl.DataFrame, vfirst: int, aqua_first: int, m_first: int):
    """Zero part per year for months before S-NPP (region-months with no MODIS)."""
    reg = rates.select("ri", "rj").unique()
    ks = pl.DataFrame({"mk": list(range(m_first, vfirst))}).with_columns(
        y=pl.col("mk") // 12, season=(pl.col("mk") % 12 + 1).replace_strict(SEASON, return_dtype=pl.Utf8))
    pos = cells.filter(pl.col("modis_n") > 0).select(ri=pl.col("i") // 5, rj=pl.col("j") // 5, mk="mk").unique()
    g = reg.join(ks, how="cross").join(pos, on=["ri", "rj", "mk"], how="anti").join(rates, on=["ri", "rj", "season"])
    g = g.with_columns(z=pl.when(pl.col("mk") < aqua_first).then(pl.col("zt")).otherwise(pl.col("z")))
    return {int(r["y"]): float(r["z"]) for r in g.group_by("y").agg(pl.col("z").sum()).iter_rows(named=True)}


def finite(o):
    """Replace NaN/inf with None so browsers can parse the JSON."""
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, dict):
        return {k: finite(v) for k, v in o.items()}
    if isinstance(o, list):
        return [finite(v) for v in o]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="web/data")
    ap.add_argument("--estimator", choices=["median", "sum"], default="sum",
                    help="production ratio estimator (both are always validated)")
    ap.add_argument("--date", choices=["solar", "utc"], default="solar", help="day boundary for cell-days")
    ap.add_argument("--modis-weight", choices=["count", "scan"], default="count",
                    help="production MODIS input: raw counts or scan-angle weighted")
    ap.add_argument("--zero-model", choices=["two_part", "none"], default="two_part",
                    help="two_part adds expected VIIRS for months MODIS saw nothing")
    args = ap.parse_args()
    global ESTIMATOR, METHOD_VERSION, DATE_MODE, ZERO_MODEL
    ESTIMATOR, DATE_MODE, ZERO_MODEL = args.estimator, args.date, args.zero_model
    METHOD_VERSION = f"ratio-{ESTIMATOR}-{args.modis_weight}-{DATE_MODE}-{ZERO_MODEL}-v3"
    two = ZERO_MODEL == "two_part"
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    print("loading CSVs ...")
    load(con, args.raw)
    cov = coverage(con)
    print("coverage", cov)
    vfirst, vlast = full_months(cov["viirs"][0], cov["viirs"][1])
    aqua_first_full = full_months(cov["aqua_first"], cov["aqua_last"])[0]
    nfirst, nlast = full_months(cov["n20"][0], cov["n20"][1]) if cov["n20"][2] else (None, None)
    print("fitting scan-angle model ...")
    scan = fit_scan(args.raw, verbose=False)
    sc, w = scan_weight_table(scan["b1"], scan["b2"])
    monthly_cells(con, pl.DataFrame({"scan": sc, "w": w}).to_arrow())

    print("validating (train 2012-2019, test 2020+) ...")
    val, _ = validate(con, cov, vfirst, vlast)
    val_n20 = validate_n20(con, nfirst, min(vlast, nlast)) if nfirst else None

    print("fitting production ratios on full overlap ...")
    mcol = "modis_w" if args.modis_weight == "scan" else "modis_n"
    all_pairs = region_pairs(con, (2012, 2100), vfirst, vlast, mcol=mcol)
    ratios = fit_ratios(all_pairs, ESTIMATOR, pos_only=two)
    ratios_t = fit_ratios(region_pairs(con, (2012, 2100), vfirst, vlast, terra=True), ESTIMATOR, pos_only=two)
    ratios_n = fit_ratios(region_pairs(con, (2018, 2100), nfirst, min(vlast, nlast), mcol="n20_fcd"), "sum") if nfirst else None

    cells = con.sql("SELECT * FROM cells").pl().with_columns(
        ri=pl.col("i") // 5, rj=pl.col("j") // 5,
        season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8),
        mk=pl.col("y") * 12 + pl.col("m") - 1)
    keys = cells.select("ri", "rj", "season").unique()
    rt = ratio_table(ratios, keys)
    rtt = ratio_table(ratios_t, keys).rename(
        {"R": "Rt", "R_lo": "Rt_lo", "R_hi": "Rt_hi", "R_n": "Rt_n", "R_level": "Rt_level"})
    cells = cells.join(rt, on=["ri", "rj", "season"]).join(rtt, on=["ri", "rj", "season"])
    if ratios_n:
        rtn = ratio_table(ratios_n, keys).select("ri", "rj", "season", pl.col("R").alias("Rn"),
                                                 pl.col("R_lo").alias("Rn_lo"), pl.col("R_hi").alias("Rn_hi"))
        cells = cells.join(rtn, on=["ri", "rj", "season"])
    else:
        cells = cells.with_columns(Rn=pl.lit(0.0), Rn_lo=pl.lit(0.0), Rn_hi=pl.lit(0.0))
    n20_last_mk = (cov["n20"][1].year * 12 + cov["n20"][1].month - 1) if nfirst else -1

    terra_only = pl.col("mk") < aqua_first_full
    viirs_ok = (pl.col("mk") >= vfirst) & (pl.col("mk") <= vlast)
    n20_ok = (pl.col("mk") > vlast) & (pl.col("mk") <= n20_last_mk)
    Mx = pl.when(terra_only).then(pl.col("terra_n")).otherwise(pl.col(mcol))
    R = pl.when(terra_only).then(pl.col("Rt")).otherwise(pl.col("R"))
    Rlo = pl.when(terra_only).then(pl.col("Rt_lo")).otherwise(pl.col("R_lo"))
    Rhi = pl.when(terra_only).then(pl.col("Rt_hi")).otherwise(pl.col("R_hi"))
    N = pl.col("n20_fcd").cast(pl.Float64)
    V = pl.col("viirs_fcd").cast(pl.Float64)
    cells = cells.with_columns(
        harmonized_count=pl.when(viirs_ok).then(V).when(n20_ok).then(N * pl.col("Rn")).otherwise(Mx * R),
        count_low=pl.when(viirs_ok).then(V).when(n20_ok).then(N * pl.col("Rn_lo")).otherwise(Mx * Rlo),
        count_high=pl.when(viirs_ok).then(V).when(n20_ok).then(N * pl.col("Rn_hi")).otherwise(Mx * Rhi),
        source_mix=pl.when(viirs_ok).then(pl.lit("VIIRS_SNPP_observed"))
        .when(n20_ok).then(pl.lit("VIIRS_NOAA20_x_ratio"))
        .when(terra_only).then(pl.lit("MODIS_Terra_only_x_ratio"))
        .otherwise(pl.lit("MODIS_TerraAqua_x_ratio")),
        ratio_level=pl.when(viirs_ok | n20_ok).then(pl.lit("")).otherwise(
            pl.when(terra_only).then(pl.col("Rt_level")).otherwise(pl.col("R_level"))),
    ).with_columns(
        cell_id=pl.format("{}_{}", pl.col("i"), pl.col("j")),
        lat=((pl.col("i") + 0.5) / 10).round(2), lon=((pl.col("j") + 0.5) / 10).round(2),
        method_version=pl.lit(METHOD_VERSION),
    )
    calendar = cells.select(
        "cell_id", "lat", "lon", pl.col("y").alias("year"), pl.col("m").alias("month"),
        pl.col("harmonized_count").round(2), pl.col("count_low").round(2),
        pl.col("count_high").round(2), "source_mix", "method_version",
        pl.col("modis_n").alias("modis_count"), pl.col("terra_n").alias("modis_terra_count"),
        pl.col("viirs_fcd").alias("viirs_firecell_days"), pl.col("viirs_px").alias("viirs_pixels"),
        pl.col("n20_fcd").alias("noaa20_firecell_days"), pl.col("modis_w").round(2).alias("modis_scan_weighted"),
        "ratio_level").filter(
        (pl.col("harmonized_count") > 0) | (pl.col("modis_count") > 0) | (pl.col("viirs_pixels") > 0)
    ).sort(["lat", "lon", "year", "month"])
    # pyarrow, plain types, snappy: readable by hyparquet in the browser
    pq.write_table(calendar.to_arrow(compat_level=pl.CompatLevel.oldest()), out / "calendar_cells.parquet",
                   compression="snappy", row_group_size=50_000, data_page_version="1.0")
    print("calendar rows", calendar.height)
    zinfo = None
    if two:  # small tables; the app adds the zero part to area totals
        rates, share = zero_tables(con, vfirst, vlast, mcol)
        for name, df in (("zero_rates.parquet", rates), ("zero_share.parquet", share)):
            pq.write_table(df.to_arrow(compat_level=pl.CompatLevel.oldest()), out / name,
                           compression="snappy", data_page_version="1.0")
        zinfo = {"regions": rates.select("ri", "rj").unique().height, "share_rows": share.height,
                 "levels": {d["z_level"]: d["len"] for d in rates.group_by("z_level").len().to_dicts()},
                 "applies_to": "months before the S-NPP overlap where a 0.5-degree region has no MODIS detection"}

    # Point-level table with harmonization weight (sum of weights == harmonized count)
    con.register("rt", rt.to_arrow())
    con.register("rtt", rtt.to_arrow())
    con.execute(f"""
    CREATE TABLE pts AS
    WITH v AS (SELECT *, count(*) OVER (PARTITION BY i100, j100, d) AS dup FROM viirs)
    SELECT round(lat,4) lat, round(lon,4) lon, d_utc AS acq_date, t AS acq_time,
           'VIIRS_SNPP' AS sensor, conf AS confidence, frp, daynight,
           CASE WHEN (year(d)*12+month(d)-1) BETWEEN {vfirst} AND {vlast} THEN round(1.0/dup, 4) ELSE 0 END AS harm_weight
    FROM v
    UNION ALL
    SELECT round(lat,4), round(lon,4), d_utc, t, 'MODIS_' || sat, conf::VARCHAR, frp, daynight,
           CASE WHEN (year(d)*12+month(d)-1) BETWEEN {vfirst} AND {vlast} THEN 0
                WHEN (year(d)*12+month(d)-1) < {aqua_first_full}
                     THEN CASE WHEN sat='Terra' THEN round(rtt.Rt,4) ELSE 0 END
                ELSE round(rt.R * {"coalesce(sw.w, 4.0)" if args.modis_weight == "scan" else "1"}, 4) END
    FROM modis LEFT JOIN sw ON sw.scan = round(modis.scan, 1)
    JOIN rt ON rt.ri = fdiv(i100, 50)::INT AND rt.rj = fdiv(j100, 50)::INT AND rt.season =
      CASE WHEN month(d) IN (12,1,2) THEN 'DJF' WHEN month(d) IN (3,4,5) THEN 'MAM'
           WHEN month(d) IN (6,7,8) THEN 'JJA' ELSE 'SON' END
    JOIN rtt ON rtt.ri = rt.ri AND rtt.rj = rt.rj AND rtt.season = rt.season
    """)
    if ratios_n:
        con.register("rtn", rtn.to_arrow())
        con.execute(f"""
        INSERT INTO pts
        WITH v AS (SELECT *, count(*) OVER (PARTITION BY i100, j100, d) AS dup FROM n20
                   WHERE (year(d)*12+month(d)-1) > {vlast})
        SELECT round(lat,4), round(lon,4), d_utc, t, 'VIIRS_NOAA20', conf, frp, daynight, round(rtn.Rn / dup, 4)
        FROM v JOIN rtn ON rtn.ri = fdiv(i100, 50)::INT AND rtn.rj = fdiv(j100, 50)::INT AND rtn.season =
          CASE WHEN month(d) IN (12,1,2) THEN 'DJF' WHEN month(d) IN (3,4,5) THEN 'MAM'
               WHEN month(d) IN (6,7,8) THEN 'JJA' ELSE 'SON' END""")
    pdir = out / "points"
    pdir.mkdir(exist_ok=True)
    years = [r[0] for r in con.execute("SELECT DISTINCT year(acq_date) FROM pts ORDER BY 1").fetchall()]
    for y in years:
        con.execute(f"""COPY (SELECT * FROM pts WHERE year(acq_date)={y} ORDER BY lat, lon, acq_date)
            TO '{pdir}/points_{y}.parquet' (FORMAT PARQUET, COMPRESSION SNAPPY, ROW_GROUP_SIZE 20000)""")
        compact_points(pdir / f"points_{y}.parquet")

    # National + AOI annual series for docs / step check
    nat = cells.group_by("y").agg(harmonized=pl.col("harmonized_count").sum(),
                                  modis=pl.col("modis_n").sum(), viirs=pl.col("viirs_fcd").sum(),
                                  viirs_px=pl.col("viirs_px").sum()).sort("y")
    vstart_year = (vfirst // 12)
    if two:  # step check must include the zero part, as the app does
        mf = full_months(cov["modis"][0], cov["modis"][1])[0]
        zy = zero_year_totals(cells, rates, vfirst, aqua_first_full, mf)
        nat = nat.with_columns(harmonized=pl.col("harmonized") + pl.col("y").replace_strict(zy, default=0.0))
    val["step_check_national"] = step_check(nat, vstart_year)
    aoi_series = {}
    for aoi, (la0, la1, lo0, lo1) in AOIS.items():
        s = cells.filter(pl.col("lat").is_between(la0, la1) & pl.col("lon").is_between(lo0, lo1)) \
            if aoi != "Argentina" else cells
        yr = s.group_by("y").agg(harmonized=pl.col("harmonized_count").sum(),
                                 low=pl.col("count_low").sum(), high=pl.col("count_high").sum(),
                                 modis=pl.col("modis_n").sum(), viirs=pl.col("viirs_fcd").sum(),
                                 viirs_px=pl.col("viirs_px").sum()).sort("y")
        aoi_series[aoi] = yr.to_dicts()
        if aoi != "Argentina":
            val.setdefault("step_check_aoi", {})[aoi] = step_check(yr, vstart_year)

    meta = {
        "method_version": METHOD_VERSION,
        "estimator": ESTIMATOR,
        "built_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "NASA FIRMS country yearly CSVs, https://firms.modaps.eosdis.nasa.gov/country/",
        "coverage": {"modis_first": str(cov["modis"][0]), "modis_last": str(cov["modis"][1]),
                     "modis_rows_kept": cov["modis"][2],
                     "viirs_first": str(cov["viirs"][0]), "viirs_last": str(cov["viirs"][1]),
                     "viirs_rows_kept": cov["viirs"][2],
                     "aqua_first": str(cov["aqua_first"]), "terra_last": str(cov["terra_last"]),
                     "aqua_last": str(cov["aqua_last"]),
                     "viirs_first_full_month": f"{vfirst // 12}-{vfirst % 12 + 1:02d}",
                     "viirs_last_full_month": f"{vlast // 12}-{vlast % 12 + 1:02d}",
                     "aqua_first_full_month": f"{aqua_first_full // 12}-{aqua_first_full % 12 + 1:02d}"},
        "filters": {"type": 0, "modis_confidence_min": MODIS_MIN_CONF, "viirs_confidence": ["n", "h"]},
        "params": {"grid_deg": 0.1, "viirs_dedupe_deg": 0.01, "ratio_region_deg": 0.5,
                   "fallbacks": ["0.5deg x season", "2deg x season", "national x season", "all"],
                   "min_modis_per_sample": MIN_M, "min_samples": MIN_N, "bootstrap": N_BOOT,
                   "bounds": "5th-95th percentile of bootstrap median"},
        "national_ratio_by_season": {k[0]: v[0] for k, v in ratios["nat"].items()},
        "national_ratio_all": ratios["all"][()][0],
        "validation": val,
        "validation_noaa20": val_n20,
        "scan_model": {"b1": scan["b1"], "b2": scan["b2"], "weight_cap": 4.0},
        "date_mode": DATE_MODE, "modis_weight": args.modis_weight,
        "zero_model": {"type": ZERO_MODEL, **(zinfo or {})},
        "noaa20": {"first": str(cov["n20"][0]), "last": str(cov["n20"][1]), "rows_kept": cov["n20"][2]},
        "point_years": years,
        "last_date": str(max(cov["modis"][1], cov["viirs"][1])),
        "last_month": (lambda k: f"{k // 12}-{k % 12 + 1:02d}")(
            full_months(cov["modis"][0], max(cov["modis"][1], cov["viirs"][1]))[1]),
        "nrt_rows": {t: con.execute(f"SELECT count(*) FROM {t} WHERE src_type='NRT'").fetchall()[0][0]
                     for t in ("modis", "viirs", "n20")},
        "aoi_annual": aoi_series,
    }
    (out / "meta.json").write_text(json.dumps(finite(meta), indent=1, default=str))
    (out / "scan_model.json").write_text(json.dumps(finite(scan), indent=1))
    print(json.dumps({"validation": val, "validation_noaa20": val_n20}, indent=1, default=str))


if __name__ == "__main__":
    main()
