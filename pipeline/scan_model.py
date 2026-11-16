"""Fit MODIS detection efficiency vs. view angle (Li et al. 2018 binning)."""
import argparse
import json
import pathlib

import duckdb
import numpy as np

RE, H = 6371.0, 705.0  # Earth radius, Terra/Aqua altitude (km)
R = (RE + H) / RE
EDGE_DEG = 55.0
LAT_MAX = -35.0  # north of here adjacent swaths barely overlap


def geometry(theta):
    """Ground distance, along-scan and along-track pixel growth for view angle theta (rad)."""
    beta = np.arcsin(R * np.sin(theta)) - theta
    dbeta = R * np.cos(theta) / np.sqrt(1 - (R * np.sin(theta)) ** 2) - 1
    s = RE * dbeta / H
    slant = np.where(theta > 1e-9, RE * np.sin(beta) / np.maximum(np.sin(theta), 1e-12), H)
    t = slant / H
    return RE * beta, s, t


def scan_weight_table(b1, b2, cap=4.0):
    """MODIS weight 1/eta per FIRMS scan value (0.1 km steps), capped."""
    th = np.radians(np.linspace(0, EDGE_DEG, 2000))
    _, s, t = geometry(th)
    scans = np.round(np.arange(1.0, 4.85, 0.1), 1)
    thv = np.interp(scans, s, th)
    _, sv, tv = geometry(thv)
    A = sv * tv
    eta = np.exp(b1 * (A - 1) + b2 * (A - 1) ** 2)
    return scans, np.minimum(1 / eta, cap)


def fit_scan(raw, verbose=True):
    """Fit eta(A) on real FIRMS MODIS data; returns the JSON-ready result."""
    a = argparse.Namespace(raw=raw)
    th = np.radians(np.linspace(0, EDGE_DEG, 2000))
    d, s, t = geometry(th)
    if verbose: print(f"edge check at {EDGE_DEG} deg: scan {s[-1]:.2f} km x track {t[-1]:.2f} km, ground {d[-1]:.0f} km")

    # Pre-drift years, type 0, conf>=30, one count per 0.01 deg cell-day and scan bin.
    files = sorted(str(f) for f in pathlib.Path(a.raw).glob("modis_*.csv") if "_api" not in f.name)
    df = duckdb.sql(f"""
      SELECT scan::DOUBLE AS scan, count(DISTINCT (floor(latitude::DOUBLE*100), floor(longitude::DOUBLE*100), acq_date)) n
      FROM read_csv({files}, all_varchar=true, union_by_name=true)
      WHERE type='0' AND confidence::INT>=30 AND latitude::DOUBLE > {LAT_MAX}
        AND year(acq_date::DATE) BETWEEN 2012 AND 2020
      GROUP BY 1""").fetchnumpy()
    scan_v, n_v = df["scan"], df["n"].astype(float)
    # FIRMS rounds scan to 0.1 km; density = count / ground width per step
    order = np.argsort(scan_v)
    scan_v, n_v = scan_v[order], n_v[order]
    keep = (scan_v >= 1.0) & (scan_v <= s[-1])
    scan_v, n_v = scan_v[keep], n_v[keep]
    lo = np.interp(np.maximum(scan_v - 0.05, 1.0), s, d)
    hi = np.interp(np.minimum(scan_v + 0.05, s[-1]), s, d)
    dens = n_v / (hi - lo)
    eta = dens / dens[0]
    mid = (lo + hi) / 2
    counts = n_v
    th_mid = np.interp(mid, d, th)
    _, s_mid, t_mid = geometry(th_mid)
    A = s_mid * t_mid
    X = np.column_stack([A - 1, (A - 1) ** 2])
    w = np.sqrt(counts)
    b, *_ = np.linalg.lstsq(X * w[:, None], np.log(eta) * w, rcond=None)
    fit = np.exp(X @ b)
    if verbose: print(f"log eta = {b[0]:.4f}*(A-1) + {b[1]:.5f}*(A-1)^2 ; eta at edge = {fit[-1]:.3f}")

    out = {
        "basis": "Li et al. 2018 view-angle binning; scan-to-angle inversion is proposed, not from a cited source",
        "data": f"FIRMS MODIS country files 2012-2020, type 0, conf>=30, lat > {LAT_MAX}, 0.01 deg cell-days",
        "edge_pixel_km": [round(float(s[-1]), 2), round(float(t[-1]), 2)],
        "equation": "log eta = b1*(A-1) + b2*(A-1)^2, A = pixel area / nadir area",
        "b1": float(b[0]), "b2": float(b[1]),
        "bins": [{"dist_km": float(m), "view_deg": float(v), "A": float(x), "eta_obs": float(e),
                  "eta_fit": float(f), "n": int(c)} for m, v, x, e, f, c in zip(mid, np.degrees(th_mid), A, eta, fit, counts)],
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="web/data")
    a = ap.parse_args()
    out = fit_scan(a.raw)
    pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(a.out) / "scan_model.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
