"""Held-out tests of method changes against the current ratio-of-sums. See docs/METHOD.md section 10."""
import argparse
import json
import pathlib

import numpy as np
import polars as pl

SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
          6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
MIN_SUM_M, MIN_N = 50, 8  # same thresholds as build.py
MIN_Z = 24               # min zero-MODIS region-months per group for part two
LEVELS = [("r05", ["ri", "rj", "season"]), ("r2", ["ci", "cj", "season"]), ("nat", ["season"]), ("all", [])]


def mk(ym):
    y, m = map(int, ym.split("-"))
    return y * 12 + m - 1


def region_months(cal: pl.DataFrame, vfirst: int, vlast: int):
    """0.5-degree region-months inside the S-NPP overlap, zero-filled on the full grid."""
    c = cal.with_columns(i=(pl.col("lat") * 10).floor().cast(pl.Int32), j=(pl.col("lon") * 10).floor().cast(pl.Int32),
                         k=pl.col("year") * 12 + pl.col("month") - 1).filter(pl.col("k").is_between(vfirst, vlast))
    r = c.group_by(ri=pl.col("i") // 5, rj=pl.col("j") // 5, k=pl.col("k")).agg(
        M=pl.col("modis_count").sum().cast(pl.Float64), T=pl.col("modis_terra_count").sum().cast(pl.Float64),
        V=pl.col("viirs_firecell_days").sum().cast(pl.Float64))
    grid = r.select("ri", "rj").unique().join(pl.DataFrame({"k": list(range(vfirst, vlast + 1))}), how="cross")
    r = grid.join(r, on=["ri", "rj", "k"], how="left").fill_null(0.0)
    return r.with_columns(y=pl.col("k") // 12, m=pl.col("k") % 12 + 1).with_columns(
        season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8),
        ci=pl.col("ri") // 4, cj=pl.col("rj") // 4)


def fit_levels(df: pl.DataFrame, num: str, den: str, ok):
    """Per-level sum(num)/sum(den) tables; ok(group) filters thin groups."""
    out = []
    for lvl, keys in LEVELS:
        g = df.group_by(keys).agg(N=pl.col(num).sum(), D=pl.col(den).sum(), n=pl.len()) if keys else \
            df.select(N=pl.col(num).sum(), D=pl.col(den).sum(), n=pl.len())
        g = g.filter(ok(lvl == "all")).with_columns(**{f"R_{lvl}": pl.col("N") / pl.col("D")})
        out.append((lvl, keys, g.drop("N", "D", "n")))
    return out


def apply_levels(test: pl.DataFrame, tabs, name: str):
    """Attach finest available ratio with fallback, as build.lookup does."""
    t = test
    for lvl, keys, g in tabs:
        t = t.join(g, on=keys, how="left") if keys else t.join(g, how="cross")
    t = t.with_columns(pl.coalesce([f"R_{lvl}" for lvl, _, _ in tabs]).alias(name))
    return t.drop([f"R_{lvl}" for lvl, _, _ in tabs])


def ratio_ok(last):
    return (pl.col("D") >= (1 if last else MIN_SUM_M)) & (pl.col("n") >= (1 if last else MIN_N))


def zero_ok(last):
    return pl.col("D") >= (1 if last else MIN_Z)


def baseline(train, test, mcol="M"):
    """Current method: ratio of sums over region-months with any detection."""
    tr = train.filter((pl.col(mcol) > 0) | (pl.col("V") > 0))
    t = apply_levels(test, fit_levels(tr, "V", mcol, ratio_ok), "R0")
    return t.with_columns(pred_base=pl.col(mcol) * pl.col("R0")).drop("R0")


def two_part(train, test, mcol="M"):
    """Part one: ratio on MODIS>0 months. Part two: mean VIIRS when MODIS=0."""
    pos = train.filter(pl.col(mcol) > 0)
    zer = train.filter(pl.col(mcol) == 0).with_columns(one=pl.lit(1.0))
    t = apply_levels(test, fit_levels(pos, "V", mcol, ratio_ok), "R1")
    t = apply_levels(t, fit_levels(zer, "V", "one", zero_ok), "Z")
    return t.with_columns(pred_2p=pl.when(pl.col(mcol) > 0).then(pl.col(mcol) * pl.col("R1"))
                          .otherwise(pl.col("Z"))).drop("R1", "Z")


FT_LEVELS = [("f05", ["ri", "rj", "ft", "season"]), ("f2", ["ci", "cj", "ft", "season"]),
             ("fnat", ["ft", "season"]), ("ftype", ["ft"]), ("all", [])]


def fire_type_units(cal: pl.DataFrame, ft: pl.DataFrame, vfirst: int, vlast: int):
    """Region x fire type x month units (MODIS>0 only matter for the ratio part)."""
    c = cal.with_columns(i=(pl.col("lat") * 10).floor().cast(pl.Int32), j=(pl.col("lon") * 10).floor().cast(pl.Int32),
                         k=pl.col("year") * 12 + pl.col("month") - 1).filter(pl.col("k").is_between(vfirst, vlast))
    c = c.join(ft.select("i", "j", "fire_type"), on=["i", "j"], how="left").with_columns(
        ft=pl.col("fire_type").fill_null("other"))
    u = c.group_by(ri=pl.col("i") // 5, rj=pl.col("j") // 5, ft=pl.col("ft"), k=pl.col("k")).agg(
        M=pl.col("modis_count").sum().cast(pl.Float64), V=pl.col("viirs_firecell_days").sum().cast(pl.Float64))
    return u.with_columns(y=pl.col("k") // 12, m=pl.col("k") % 12 + 1).with_columns(
        season=pl.col("m").replace_strict(SEASON, return_dtype=pl.Utf8), ci=pl.col("ri") // 4, cj=pl.col("rj") // 4)


def ft_two_part(units, train_rm, test):
    """Two-part model whose ratio part is stratified by land-cover fire type."""
    tr = units.filter(pl.col("y").is_between(2012, 2019) & (pl.col("M") > 0))
    te = units.filter((pl.col("y") >= 2020) & (pl.col("M") > 0))
    tabs = []
    for lvl, keys in FT_LEVELS:
        g = tr.group_by(keys).agg(N=pl.col("V").sum(), D=pl.col("M").sum(), n=pl.len()) if keys else \
            tr.select(N=pl.col("V").sum(), D=pl.col("M").sum(), n=pl.len())
        g = g.filter(ratio_ok(lvl == "all")).with_columns(**{f"R_{lvl}": pl.col("N") / pl.col("D")})
        tabs.append((lvl, keys, g.drop("N", "D", "n")))
    te = apply_levels(te, tabs, "Rf").with_columns(p=pl.col("M") * pl.col("Rf"))
    reg = te.group_by("ri", "rj", "k").agg(pf=pl.col("p").sum()).with_columns(
        [pl.col(c).cast(test.schema[c]) for c in ("ri", "rj", "k")])
    zer = train_rm.filter(pl.col("M") == 0).with_columns(one=pl.lit(1.0))
    t = apply_levels(test, fit_levels(zer, "V", "one", zero_ok), "Z").join(reg, on=["ri", "rj", "k"], how="left")
    return t.with_columns(pred_ft=pl.when(pl.col("M") > 0).then(pl.col("pf").fill_null(0.0))
                          .otherwise(pl.col("Z"))).drop("Z", "pf")


def metrics(pred, obs):
    pred, obs = np.asarray(pred, float), np.asarray(obs, float)
    err = pred - obs
    rho = float(np.corrcoef(pl.Series(pred).rank().to_numpy(), pl.Series(obs).rank().to_numpy())[0, 1])
    return {"n": int(len(obs)), "MAE": float(np.abs(err).mean()), "bias_pct": float(err.sum() / obs.sum() * 100),
            "spearman": rho}


def score(t: pl.DataFrame, cols):
    nat = t.group_by("k").agg([pl.col(c).sum() for c in ["V", *cols]]).sort("k")
    act = t.filter((pl.col("M") > 0) | (pl.col("V") > 0))
    quiet = nat.filter(pl.col("V") <= nat["V"].quantile(0.25))  # low-fire months
    return {c: {"national_month": metrics(nat[c], nat["V"]), "region_month_all": metrics(t[c], t["V"]),
                "region_month_active": metrics(act[c], act["V"]),
                "national_quiet_quarter_MAE": float((quiet[c] - quiet["V"]).abs().mean())} for c in cols}


def drift_test(rm: pl.DataFrame):
    """Does adding drifted years (2023+) to training hurt prediction of held-out 2020-2022?"""
    test = rm.filter(pl.col("y").is_between(2020, 2022))
    out = {}
    for name, tr in (("train_2012_2019", rm.filter(pl.col("y") <= 2019)),
                     ("train_2012_2019_plus_2023_on", rm.filter((pl.col("y") <= 2019) | (pl.col("y") >= 2023)))):
        t = baseline(tr, test)
        out[name] = score(t, ["pred_base"])["pred_base"]
    for name, tr in (("terra_train_2012_2019", rm.filter(pl.col("y") <= 2019)),
                     ("terra_train_2012_2019_plus_2023_on", rm.filter((pl.col("y") <= 2019) | (pl.col("y") >= 2023)))):
        t = baseline(tr, test, mcol="T").rename({"pred_base": "pred_t"})
        out[name] = score(t, ["pred_t"])["pred_t"]
    yr = rm.group_by("y").agg(pl.col("V").sum(), pl.col("M").sum(), pl.col("T").sum()).sort("y")
    out["national_ratio_by_year"] = {int(r["y"]): {"V_over_M": r["V"] / r["M"], "V_over_Terra": r["V"] / r["T"]}
                                     for r in yr.iter_rows(named=True) if r["M"] > 0 and r["T"] > 0}
    return out


def inner_choice(rm: pl.DataFrame):
    """Pick two-part per country on 2012-15 -> 2016-19 only; test years unseen."""
    tr, va = rm.filter(pl.col("y").is_between(2012, 2015)), rm.filter(pl.col("y").is_between(2016, 2019))
    sc = score(two_part(tr, baseline(tr, va)), ["pred_base", "pred_2p"])
    b, t = sc["pred_base"]["national_month"], sc["pred_2p"]["national_month"]
    ok = t["MAE"] < b["MAE"] and abs(t["bias_pct"]) <= abs(b["bias_pct"]) + 2
    return {"use_two_part": bool(ok), "inner_base": b, "inner_two_part": t}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default="web/data/countries")
    ap.add_argument("--out", default="docs/experiments.json")
    ap.add_argument("--firetype", default="data/ref/firetype_0p1.parquet")
    a = ap.parse_args()
    ftab = pl.read_parquet(a.firetype) if pathlib.Path(a.firetype).exists() else None
    res = {}
    for d in sorted(x for x in pathlib.Path(a.countries).iterdir() if (x / "meta.json").exists()):
        meta = json.loads((d / "meta.json").read_text())
        cov = meta["coverage"]
        vf, vl = mk(cov["viirs_first_full_month"]), mk(cov["viirs_last_full_month"])
        cal = pl.read_parquet(d / "calendar_cells.parquet")
        rm = region_months(cal, vf, vl)
        train, test = rm.filter(pl.col("y").is_between(2012, 2019)), rm.filter(pl.col("y") >= 2020)
        t = two_part(train, baseline(train, test))
        cols = ["pred_base", "pred_2p", "M"]
        if ftab is not None:
            t = ft_two_part(fire_type_units(cal, ftab, vf, vl), train, t)
            cols.insert(2, "pred_ft")
        zshare = float(test.filter(pl.col("M") == 0)["V"].sum() / test["V"].sum())
        res[d.name] = {"viirs_share_in_modis_zero_region_months": zshare,
                       "two_part": score(t, cols), "drift": drift_test(rm), "inner": inner_choice(rm)}
        b, p = res[d.name]["two_part"]["pred_base"], res[d.name]["two_part"]["pred_2p"]
        print(f"{d.name:10s} zero-share {zshare:5.1%} | nat bias {b['national_month']['bias_pct']:+5.1f} -> "
              f"{p['national_month']['bias_pct']:+5.1f} | nat MAE {b['national_month']['MAE']:8.1f} -> "
              f"{p['national_month']['MAE']:8.1f} | reg MAE {b['region_month_all']['MAE']:6.2f} -> "
              f"{p['region_month_all']['MAE']:6.2f} | quiet MAE {b['national_quiet_quarter_MAE']:7.1f} -> "
              f"{p['national_quiet_quarter_MAE']:7.1f}")
        if ftab is not None:
            f = res[d.name]["two_part"]["pred_ft"]
            print(f"{'':10s} fire-type two-part: nat bias {f['national_month']['bias_pct']:+5.1f} | nat MAE "
                  f"{f['national_month']['MAE']:8.1f} | reg MAE {f['region_month_all']['MAE']:6.2f} | quiet MAE "
                  f"{f['national_quiet_quarter_MAE']:7.1f} | rho {f['national_month']['spearman']:.4f} vs "
                  f"{p['national_month']['spearman']:.4f}")
        ic = res[d.name]["inner"]
        ch = p if ic["use_two_part"] else b
        print(f"{'':10s} inner 2016-19 choice: {'two-part' if ic['use_two_part'] else 'ratio of sums'} "
              f"(inner MAE {ic['inner_base']['MAE']:.1f} -> {ic['inner_two_part']['MAE']:.1f}, bias "
              f"{ic['inner_base']['bias_pct']:+.1f} -> {ic['inner_two_part']['bias_pct']:+.1f}) | test with choice: "
              f"bias {ch['national_month']['bias_pct']:+.1f}, MAE {ch['national_month']['MAE']:.1f}")
        dr = res[d.name]["drift"]
        print(f"{'':10s} drift: 2020-22 bias {dr['train_2012_2019']['national_month']['bias_pct']:+5.1f} vs "
              f"+2023on {dr['train_2012_2019_plus_2023_on']['national_month']['bias_pct']:+5.1f} | terra "
              f"{dr['terra_train_2012_2019']['national_month']['bias_pct']:+5.1f} vs "
              f"{dr['terra_train_2012_2019_plus_2023_on']['national_month']['bias_pct']:+5.1f}")
    pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
