"""MCD12C1 IGBP percentages -> dominant fire type per 0.1-degree cell. Needs pyhdf."""
import argparse

import numpy as np
import polars as pl
from pyhdf.SD import SD

# IGBP class -> fire type; forests split by latitude below
CROP, SAVANNA, FOREST, WETLAND, OTHER = "cropland", "savanna_grass_shrub", "forest", "wetland_peat", "other"
IGBP = {1: FOREST, 2: FOREST, 3: FOREST, 4: FOREST, 5: FOREST, 6: SAVANNA, 7: SAVANNA, 8: SAVANNA, 9: SAVANNA,
        10: SAVANNA, 11: WETLAND, 12: CROP, 13: OTHER, 14: CROP, 15: OTHER, 16: OTHER}
TYPES = [CROP, SAVANNA, FOREST, WETLAND, OTHER]


def forest_zone(lat):
    """Latitude split of forest (proposed, not from a cited source)."""
    a = np.abs(lat)
    return np.where(a < 23.5, "forest_tropical", np.where(a < 50, "forest_temperate", "forest_boreal"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hdf", help="MCD12C1 v061 file")
    ap.add_argument("--out", default="data/ref/firetype_0p1.parquet")
    a = ap.parse_args()
    pct = SD(a.hdf).select("Land_Cover_Type_1_Percent").get().astype(np.float32)  # 3600 x 7200 x 17
    agg = np.zeros((1800, 3600, len(TYPES)), np.float32)
    north = np.abs(89.95 - np.arange(1800) * 0.1) >= 50  # 0.1-degree row centres
    for cls, ft in IGBP.items():
        x = pct[:, :, cls].reshape(1800, 2, 3600, 2).sum((1, 3))
        if cls == 8:  # IGBP woody savanna above 50 degrees is open boreal forest (proposed)
            agg[north, :, TYPES.index(FOREST)] += x[north]
            x = np.where(north[:, None], 0, x)
        agg[:, :, TYPES.index(ft)] += x
    land = agg.sum(2) > 0
    dom = agg.argmax(2)
    r, c = np.nonzero(land)
    i = 899 - r  # row 0 is 90N; i = floor(lat*10)
    j = c - 1800
    lat = (i + 0.5) / 10
    ft = np.array(TYPES)[dom[r, c]]
    ft = np.where(ft == FOREST, forest_zone(lat), ft)
    share = agg[r, c].max(1) / agg[r, c].sum(1)
    df = pl.DataFrame({"i": i.astype(np.int32), "j": j.astype(np.int32), "fire_type": ft,
                       "dominant_share": share.round(3)})
    df.write_parquet(a.out)
    print(df.group_by("fire_type").len().sort("len"))


if __name__ == "__main__":
    main()
