# Method, validation and weak spots

Build: `ratio-sum-count-solar-v2` (v2, see §0), first written for `ratio-sum-v1`, run 2026-11-15 on NASA FIRMS data for Argentina. Every number below comes
from `pipeline/build.py` output (`web/data/meta.json`); rerun the pipeline to reproduce it.

## v7.1 grid fix and accuracy caveat

**Grid fix (v7.1).** DuckDB's `//` on integers truncates toward zero; polars `//` floors. In earlier
builds, detections with negative latitude or longitude were put one 0.1° cell toward zero (so cell 0 was
0.2° wide), and the 0.5° ratio was fitted with truncated keys but looked up with floored ones. All SQL
now uses `fdiv()` (floor). Every country was rebuilt. Holdout bias moved little, because validation
used one key consistently; the map cells and the MODIS-era calendar values are what changed most.

| Country | Bias % before fix | Bias % after fix | Step factor before → after |
|---|---|---|---|
| Argentina | +4.2 | +3.9 (test to 2026-10); +5.2 (test to 2025-12, see below) | 1.02 → 1.05 |
| Australia | −2.6 | −2.6 | 1.03 → 1.03 |
| United States | −3.1 | −3.8 | 0.82 → 0.79 |
| Brazil | +7.8 | +7.9 | 1.09 → 1.10 |
| Canada | +11.9 | +12.8 | 1.22 → 1.21 |

§9 shows the rebuilt numbers. The Argentina tables in §0–§8 come from the v4 build, before the fix.
After the fix, Río Negro is −3.1 % (was −3.4 %) and Chaco is +6.7 % (was +6.8 %).

**Data ends in December 2025 (all countries).** Will chose a static app with data through 2025. Argentina's
2026 FIRMS API data (SP and NRT) was removed and Argentina was rebuilt from country files 2000–2025, like the
other countries. Its holdout is now 2020–2025: bias +5.2 % (Río Negro −3.5 %, Chaco +7.4 %; raw MODIS −48.3 %),
2012 step factor 1.05. The NOAA-20 tie is still validated (2023–2025, bias +0.8 %), but the app no longer uses it
because S-NPP covers every month shown. Sections 0–8 describe the earlier Argentina build with 2026 data and are
kept as a record. The July 2026 Río Negro analysis (§7) and the 2026 caveats are not in the app.

**Accuracy caveat.** These numbers say how close MODIS × ratio comes to what VIIRS S-NPP observed in
2020 onward, summed over months and areas. They do not say how many fires actually burned. Both
sensors miss fires under cloud, under canopy, between overpasses and below their detection limits. One
month in one small area can be off by much more than the national bias, as the MAE columns show. The
MODIS-era ratio assumes the VIIRS:MODIS relationship of 2012 onward also held in 2000–2011. Use the
calendar for relative patterns (seasons, anomalies, trends on one scale), not as a census of fires.

## 0. What changed in v2 (all on real FIRMS data, validated on held-out years)

| Change | Result | Used in production? |
|---|---|---|
| Local solar date (UTC + lon/15 h) for daily fire-cells | Metrics nearly unchanged (Argentina bias +4.2 %, Río Negro −3.4 %, Chaco +6.8 %) | Yes (default, `--date solar`) |
| NOAA-20 → S-NPP tie (fire-cell-days, ratio of sums per 0.5° region × season) | Test 2023–2026-10: national bias +1.4 % (raw NOAA-20 +2.7 %), Spearman 0.98 at national monthly scale; Río Negro +6.9 % (raw +5.1 %), Chaco +1.2 % | Yes, for months after S-NPP's last full month (only Nov 2026 so far) |
| MODIS scan-angle weights 1/η (cap 4) | Worse than plain counts: national bias +7.1 % vs +4.2 %, region-month RMSE 28.5 vs 22.2 | No (`--modis-weight scan` to enable) |
| Aqua-only MODIS reference (afternoon orbit) | Worse than Terra + Aqua: national +7.4 %, Chaco +10.9 %, Río Negro −7.8 % | No (validated only) |

NOAA-20 and S-NPP fire-cell-days are almost the same in Argentina (raw NOAA-20 is within
3 % nationally), so the tie is a small correction. That supports VIIRS fire-cell-days as a stable
unit across VIIRS platforms. The tables in §3 and §4 below are the v1 run. The live numbers for v2
are in the app's Method panel and `web/data/meta.json`.

## 1. Data

| | MODIS C6.1 (Terra + Aqua) | VIIRS S-NPP 375 m |
|---|---|---|
| Source | FIRMS country files 2000–2025; FIRMS API 2026 (SP to Aug 31, then NRT) | FIRMS country files 2012–2025; FIRMS API 2026 (SP to Jul 31, then NRT) |
| Coverage used | 2000-11-01 → 2026-11-15 | 2012-01-20 → 2026-11-02 (S-NPP stopped) |
| Kept after filters | 1,626,051 detections | 2,624,145 detections |

Filters (same for both, as agreed): `type == 0` (presumed vegetation fire; drops volcanoes,
static land sources such as gas flares and industry, and offshore), MODIS `confidence >= 30`,
VIIRS confidence nominal or high (low dropped).

2026 caveats. NRT rows have no `type` field (10,321 MODIS and 36,143 VIIRS rows). For those we drop
any detection inside a 0.02° cell that the SP archive ever flagged as type 1 or 2. API rows came from
a bounding box, so we keep only 0.1° cells that appear in the Argentina country files.

## 2. Why these choices

**Reference sensor: VIIRS S-NPP only.** It is the only VIIRS platform that covers the whole overlap
with MODIS (2012 onward). Adding NOAA-20 (2018) and NOAA-21 (2023) would add detections each time a
satellite launches, which is exactly the artificial upward trend the challenge asks us to remove.
We harmonize *to* the VIIRS scale because VIIRS is the future of the record and detects the small
fires that matter for early warning.

**MODIS Terra + Aqua, with Terra-only months handled separately.** Using both maximizes MODIS
sensitivity. Aqua starts in July 2002 (first full month 2002-08), so earlier months have only
Terra. Instead of just flagging them, we fit a separate Terra-only ratio on the overlap years and
apply it to 2000-11 → 2002-07. Those months carry the widest uncertainty bands (see §5).

**Grid: 0.1° monthly cells.** About 11 km, small enough to build any province or department
AOI from cells, large enough that monthly counts are not mostly zeros. Precomputing cells is what
makes a static app possible.

**Method 1, VIIRS fire-cell-days.** One fire front can light up several 375 m VIIRS pixels where
MODIS sees one 1 km pixel. We collapse VIIRS detections to unique 0.01° (~1 km) cells per day. In
Argentina this cuts the VIIRS count by 43 % (2,624,145 detections → 1,504,559 fire-cell-days), removing
the part of the VIIRS:MODIS gap that is pure pixel size, before any statistics.

**Method 2, a regional ratio with fallback and bootstrap.** What is left of the gap is sensitivity
and overpass time, and it varies with fire type and region. During the overlap we compute a
VIIRS:MODIS ratio for each 0.5° region × season (DJF, MAM, JJA, SON). If a region-season has too
little data (fewer than 8 region-months, or fewer than 50 MODIS detections), we fall back to 2° ×
season, then national × season, then a single national ratio. Bounds come from 300 bootstrap
resamples of the region-months (5th–95th percentile).

**Ratio of sums for production, not median of ratios.** We validated both, and the result changed
our choice. The median of monthly ratios needs months where MODIS saw at least 5 fires. That
discards exactly the months where MODIS sees little but VIIRS sees a lot, which are common in
Patagonia. So it underestimated Río Negro by 46 % on held-out years. The ratio of sums
(Σ VIIRS / Σ MODIS, a regression through the origin) uses every month with fire. It cut the
Río Negro bias to −4 % and removed the 2012 step there (§4). Nationally the two are similar
(−6.6 % vs +4.2 %). The median variant stays available with `--estimator median`.

**Quantile mapping as the comparison method.** It is the standard bias-correction alternative,
and it preserves ranks. It does worse here (§3). It is also not additive: mapping each cell and then
summing an AOI is not the same as mapping the AOI total. That makes it a poor fit for an app where
users draw arbitrary areas. A ratio is additive, so cell-level harmonized counts sum correctly to any
AOI.

**Final series.** Months with S-NPP data (2012-02 → 2026-10) use the *observed* VIIRS fire-cell-days.
All other months use MODIS × ratio. The ratios used for production are refit on all overlap years
(2012–2026); the holdout below uses ratios fit on 2012–2019 only.

## 3. Holdout validation (train 2012–2019, test 2020-01 → 2026-10)

Predict VIIRS fire-cell-days from MODIS alone in the test years and compare with what VIIRS
actually saw. Bias % = Σ(predicted − observed) / Σ observed. Peak-month = share of region-years
(with ≥ 20 VIIRS fire-cell-days) where the predicted busiest month equals the observed one.

**0.5° region-months (n = 42,653 with any fire):**

| Method | MAE | RMSE | Bias % | Spearman | Peak-month |
|---|---|---|---|---|---|
| **Ratio of sums, region × season (production)** | 7.19 | 22.1 | **+4.2** | 0.73 | 64 % |
| Median ratio, region × season | 6.91 | 19.0 | −6.6 | 0.74 | 64 % |
| Quantile mapping | 7.36 | 29.1 | −13.9 | 0.74 | 63 % |
| Single national ratio | 7.19 | 20.5 | −15.2 | 0.73 | 66 % |
| Raw MODIS, no harmonization | 9.38 | 29.4 | −48.8 | 0.73 | 66 % |

**Monthly totals for the areas the calendar shows (n = 82 months):**

| Area | Method | MAE | RMSE | Bias % | Spearman | Peak-month |
|---|---|---|---|---|---|---|
| Río Negro (box) | **Ratio of sums** | 89.9 | 119.3 | **−4.2** | 0.86 | 57 % |
| | Median ratio | 161.1 | 183.3 | −45.7 | 0.87 | 86 % |
| | Quantile mapping | 115.3 | 204.6 | −24.9 | 0.83 | 14 % |
| | Raw MODIS | 219.6 | 246.4 | −63.4 | 0.88 | 86 % |
| Chaco (box) | **Ratio of sums** | 288.4 | 518.3 | +6.8 | 0.99 | 86 % |
| | Median ratio | 335.8 | 593.6 | +4.7 | 0.99 | 100 % |
| | Quantile mapping | 336.4 | 821.8 | −5.7 | 0.99 | 86 % |
| | Raw MODIS | 1027.8 | 1552.7 | −41.0 | 0.99 | 86 % |
| Argentina | **Ratio of sums** | 1051.5 | 1820.0 | +4.2 | 0.99 | 100 % |
| | Median ratio | 1186.0 | 1488.7 | −6.6 | 0.98 | 100 % |
| | Quantile mapping | 1535.8 | 3183.5 | −13.9 | 0.98 | 86 % |
| | Raw MODIS | 4521.2 | 6003.8 | −48.8 | 0.99 | 100 % |

(Peak-month at area level is over only 7 test years, so one year moves it by 14 points.)

How to read it: harmonization removes almost all of the ~49 % level gap between raw MODIS and VIIRS.
The timing information (Spearman 0.86–0.99 at area level) is already in MODIS and is kept.
Area-level errors are within ±7 % in total for all three areas with the production method.

## 4. Step check at the 2012 sensor switch

If harmonization worked, the series should not jump when it switches from MODIS × ratio to observed
VIIRS. We compare 2013–2014 with 2010–2011 (skipping the switch year) in the harmonized series and
in raw MODIS, which has no sensor change. The artifact factor is the harmonized change divided by
the MODIS change; 1.0 means no artificial step.

| Area | Harmonized change | Raw MODIS change | Artifact factor (sums) | Artifact factor (median) |
|---|---|---|---|---|
| Argentina | ×0.754 | ×0.738 | **1.02** | 1.13 |
| Río Negro (box) | ×1.258 | ×1.318 | **0.95** | 1.74 |
| Chaco (box) | ×0.703 | ×0.696 | **1.01** | 1.02 |

With the median ratio, Río Negro showed a false 74 % jump at 2012. This is the main reason we
switched estimators.

## 5. Weak spots (please read before trusting a number)

1. **MODIS zeros stay zero.** If MODIS saw nothing in a cell-month, the pre-2012 estimate is 0,
   even though VIIRS would often have caught small fires there. Sparse regions are therefore
   biased low month by month, even when totals look right. Fix: a hurdle / zero-inflated model
   (cut list #2).
2. **Terra-only months (2000-11 → 2002-07) are the least certain.** The Terra-only ratio is about
   5 VIIRS fire-cell-days per Terra detection nationally (vs about 1.9 for Terra + Aqua). The
   2001 peak in the Río Negro box (30,550, bootstrap range 24,240–44,417) rests on 6,257 Terra
   detections. Treat that year's level as indicative.
3. **The bands are only the ratio uncertainty.** They don't include MODIS detection noise or the
   choice of region size, and summing cell bounds over an AOI assumes fully correlated errors
   (conservative).
4. **Fallbacks are common.** In the test set only 711 of 3,989 region-seasons had enough data for
   their own 0.5° ratio; 2,058 used the 2° ratio and 1,220 the national one.
5. **AOIs are matched on 0.1° cells** (cell centre inside the box or circle). The presets are
   approximate province bounding boxes, not boundaries. For example, the Río Negro box also covers
   parts of Neuquén, La Pampa and Chubut. The hotspot CSV uses exact coordinates.
6. **S-NPP ended on 2026-11-02.** November 2026 onward is MODIS × ratio, and November is a partial
   month, so the app's "latest month" is October 2026. Continuing the VIIRS scale needs a NOAA-20
   → S-NPP tie (cut list #1). MODIS is also near end of life; when it stops, the method still
   stands for history, but new months must come from VIIRS.
7. **2026 mixes SP and NRT processing.** NRT has no `type` field, so we mask static sources using
   SP history. A new static source that appeared in 2026 would not be masked.
8. **One country only.** We validated on Argentina, using Chaco (savanna/agricultural burning,
   high counts) as a contrast to Río Negro (sparse Patagonian steppe and forest). Other biomes
   need their own validation.

## 6. Scan-angle effect (diagnostic, real data)

MODIS pixels grow from 1 × 1 km at nadir to about 4.8 × 2.0 km at the 55° swath edge, so small
fires are missed off-nadir (Li et al. 2018, JGR Atmospheres, report a ~67 % drop in MODIS fire
counts from nadir to edge). We measured this on the real Argentina record.

* **Inverting FIRMS `scan` to view angle** with MODIS geometry (h = 705 km, Re = 6371 km) is
  *(proposed, not from a cited source)*. Our geometry reproduces 4.83 × 2.01 km at 55°.
* **Efficiency η.** For a fixed place, overpasses sample cross-track ground distance about uniformly,
  so detections per km of ground distance should be flat if detection did not degrade. η is
  observed density over nadir density, per 0.1 km FIRMS `scan` step. We used 2012–2020 (before the
  orbit drift), type 0, confidence ≥ 30, 0.01° cell-days, and latitudes north of 35° S, where
  adjacent swaths barely overlap.
* **Fit:** log η = −0.471·(A−1) + 0.0303·(A−1)², where A is pixel area relative to nadir.
  η is 0.16 at the edge, a steeper drop than the ~67 % in Li et al. 2018. Part of that may be
  remaining swath overlap or the uniform-sampling assumption.
* **Not yet applied** to the harmonized series. The ratio calibration already absorbs the average
  scan loss per region-season. A 1/η weight (clipped at 4) needs its own holdout validation
  before we use it. See CUT_LIST.md.

## 7. About the July 2026 Río Negro fire

We looked for it in the data, and we're reporting what we found rather than what we expected. In
the Río Negro box, July 2026 has 97 harmonized hotspots, *below* the July median of 200
(2001–2025). July 2026 detections are scattered: the largest cluster is 48 VIIRS detections around
38.5–38° S, 69–68.5° W, which is near the Neuquén border. So a single large July fire doesn't
stand out at province scale in the S-NPP and MODIS records. If the event was small, short-lived,
cloud-covered during overpasses, or at a specific locality, use point + radius around it and the
hotspot CSV. The app is designed for exactly that use.

## 8. Extra checks from the action plan (v4)

The full plan is in [ACTION_PLAN.pdf](ACTION_PLAN.pdf). This section runs its quick checks.

Run with `python pipeline/extra_checks.py --raw data/raw --out web/data/extra_checks.json`.
All use the production ratio of sums, 0.5° region × season. Bias % = Σ(pred − obs) / Σ obs.

**Other train/test splits.**

| Split | Río Negro | Chaco | Argentina | Argentina, single national ratio | Raw MODIS (Argentina) |
|---|---|---|---|---|---|
| Train 2012–2018, test 2019–2021 (plan's split) | −9.6 | +6.9 | +3.9 | −4.7 | −48.7 |
| Train 2012–2019, test 2020–2026-10 (ours) | −3.4 | +6.8 | +4.2 | −4.6 | −48.8 |

The regional ratio beats the single national ratio in Río Negro (−9.6 vs −31.8, and −3.4 vs −32.1).
Nationally both are within about ±5 %.

**Leave one year out (2012–2025).** Argentina bias stays within ±5 % in 12 of 14 years
(range −5.0 to +11.2). Río Negro is within ±12 % in 11 of 14 years. The outliers are 2020 (−20.8),
2023 (+10.6) and 2024 (+58.5). 2024 is also the worst national year (+11.2) and coincides with
Aqua's drift (below), so later years are less certain.

**Low-confidence detections included** (MODIS conf ≥ 0, VIIRS l/n/h; +5 % MODIS, +10 % VIIRS
detections). Holdout bias moves from +4.2 to +3.7 (Argentina), −3.4 to −4.0 (Río Negro), and
+6.8 to +5.7 (Chaco). The cutoff is not driving the result.

**Orbit drift (mean local solar time of daytime MODIS detections over Argentina).** Aqua is
13.9 h from 2002 to 2022, then 14.2 (2023), 14.5 (2024), 15.1 (2025), 15.8 (2026). Terra is
10.2 h until 2020, then 10.0 (2022), 9.5 (2024), 8.6 (2026). Our training years (2012–2019) are
before the drift. Months from 2023 on mix in a drifted MODIS look; the regional ratio absorbs
part of it, but the drift is not modelled. *(Mean detection time is a proxy for overpass time,
proposed, not from a cited source.)*

**Year-round burning cells.** No 0.1° cell has VIIRS fire in ≥ 10 months of every year
2012–2025. The type-0 filter already removes the persistent static sources, so a second mask is not
needed for Argentina.

**Not done from the plan** (see CUT_LIST.md): day/night split corrections, clear-look rates and
gap filling (need MYD14A1 / VNP14A1), land-cover fire types (MCD12Q1), swath-level angle cutoff,
two-part zero model, leave-one-region-out, MODIS-equivalent forward record, FRP record.

## 9. Other countries (v5)

The same pipeline, unchanged, run on four more FIRMS country files (MODIS 2000–2025, S-NPP
2012–2025, NOAA-20 2018–2025; no 2026 API pull). Holdout: train 2012–2019, test 2020–2025.
Bias % at 0.5° region-month level, Σ(pred − obs) / Σ obs.

Rebuilt in v7.1 after the grid fix (see top).

| Country | Ratio of sums (production) | Median ratio | Single national ratio | Raw MODIS | Step artifact factor 2012 |
|---|---|---|---|---|---|
| Argentina (2020–2025) | +5.2 | −6.1 | −14.2 | −48.3 | 1.05 |
| Australia | −2.6 | −5.5 | −7.7 | −53.6 | 1.03 |
| United States | −3.8 | −25.9 | −30.1 | −46.5 | 0.79 |
| Brazil | +7.9 | +3.9 | +1.2 | −50.9 | 1.10 |
| Canada | +12.8 | −8.4 | −23.3 | −50.0 | 1.21 |

Reading it: harmonization removes the ~50 % MODIS gap everywhere. In Canada and the US the 2012
step check is less clean. Boreal and western US fire years swing a lot, so 2010–2011 vs 2013–2014
mixes real change with any artifact. In Brazil the single national ratio does slightly better on
total bias; regional strata matter less there. Canada's +12.8 % is the weakest result; boreal fires
are large and long, which is where the action plan's fire-type corrections should help most.

v5 change: bootstrap resamples with zero MODIS detections are dropped. Before, they produced
huge upper bounds in sparse strata. Estimates are unchanged; only the upper bounds shrink.
The Argentina data in v5 is the v4 build.

Not done: the rest of the planet. Country files total tens of GB; the pipeline runs one country at a
time (`build.py --raw <country folder>`). Each country needs about 1 minute and 2–4 GB of RAM;
run them one at a time.


## 10. v8 method tests (held-out 2020 onward, 10 countries)

Rule fixed before testing: adopt a change only if, on held-out years, whole-country monthly MAE and
0.5° region-month MAE both improve in most countries, and no country's |bias| gets worse by more than
2 points. All numbers are from `pipeline/experiments.py` (`docs/experiments.json`) and `build.py` meta.

### 10.1 Two-part model for months where MODIS saw nothing (adopted)

MODIS × ratio is zero when MODIS saw nothing, but VIIRS often still sees fire there. Part one fits the
ratio only on region-months with MODIS > 0. Part two predicts the mean VIIRS count over MODIS-zero
region-months in the overlap, by 0.5° region × season (fallback 2° → national; at least 24 months per group).
In the app, part two is added to area totals and spread over cells by where VIIRS saw those fires
(`zero_rates.parquet`, `zero_share.parquet`). It is not drawn as map dots.
The bridge thread found the same gap independently: in Río Negro, 19.4 % of VIIRS fire falls in
MODIS-zero region-months, and VNP14 750 m recovers only 4 % of it (docs in the bridge build).

| Country | VIIRS in MODIS-zero months | Bias % ratio of sums → two-part | Monthly MAE ratio of sums → two-part |
|---|---|---|---|
| Argentina | 5.1 % | +5.2 → +4.5 | 1044 → 921 |
| Australia | 2.4 % | −2.6 → −2.0 | 3354 → 3165 |
| Brazil | 2.7 % | +7.9 → +7.4 | 7997 → 7896 |
| Canada | 2.8 % | +12.8 → +6.3 | 3624 → 2777 |
| United States | 14.0 % | −3.8 → −2.1 | 2423 → 1990 |
| Spain | 24.3 % | +8.9 → +10.8 | 142 → 100 |
| Portugal | 11.4 % | +5.3 → +13.7 | 38 → 36 |
| Italy | 18.3 % | −12.5 → −5.4 | 200 → 175 |
| Greece | 22.3 % | +12.1 → +13.0 | 71 → 55 |
| Turkey | 15.6 % | +1.0 → +1.2 | 338 → 270 |

Monthly MAE improves in 10 of 10 countries, and region-month MAE (full grid) in 8 of 10; Australia
and Portugal are about unchanged or slightly worse. Bias improves in 6 of 10. Portugal breaks the
2-point rule (+8.4 points), on a small base: its monthly MAE is 36 detections.
A per-country choice made only on 2012–15 → 2016–19 did not help: it kept two-part for Portugal and
dropped it for Greece, the opposite of what the test years favour. So it is not used.
Spearman correlation of the monthly series is unchanged (±0.005). Months with very little fire get worse
in Brazil, Italy, Spain, Portugal and Greece, because the zero part adds a small expected value every month.

### 10.2 Land-cover fire types (not adopted)

MCD12C1 v061 2016 (0.05°, IGBP percentages, LP DAAC) → dominant fire type per 0.1° cell: cropland,
savanna/grass/shrub, tropical/temperate/boreal forest (latitude split at 23.5° and 50°), wetland, other
(`pipeline/landcover.py`). The latitude split, and counting IGBP woody savanna north of 50° as boreal forest, are
(proposed, not from a cited source); the fire-type idea follows GFED4s partitioning (van der Werf et al.
2017, ESSD 9:697). The ratio part was stratified by fire type within each region (fallback 2° → national
→ type → all). Compared with two-part alone, it cut bias in Argentina, Brazil, Canada, Greece and Spain.
It did worse on monthly MAE in Australia and the United States, and US bias went from −2.1 % to −4.6 %.
It fails the rule. One land-cover year (2016) is used for all years, which is a limit.

### 10.3 Day/night split (not adopted)

Separate day and night ratios (night VIIRS:MODIS ≈ 3.5, day ≈ 1.8 in Argentina) with an overlap correction
(`pipeline/daynight.py`). Worse than one pooled ratio: Argentina bias +4.2 → +6.1 %, MAE 1060 → 1229;
Canada +11.9 → +16.9 %. Night share is stable from year to year, so pooling loses little and the split adds noise.

### 10.4 Orbit drift (not adopted)

Terra and Aqua drift after 2022. Test: does adding 2023 onward to the training years hurt predictions of the
held-out 2020–2022? Mixed: it helped in Argentina, Australia, Canada, Spain and Greece, and hurt in Brazil
and the United States (all-MODIS ratio). VIIRS:Terra did rise in 2025–26 in Argentina (7.0 and 9.1 vs about 5.3
before) and the United States. No consistent gain, so production keeps fitting on the whole overlap. Revisit when
Terra ends.

### 10.5 Clear-sky observation rates (not done)

This needs per-overpass cloud and observation counts. The MODIS CMG fire product (MOD14CMH / MYD14CMH) has
cloud-corrected fire pixels and mean cloud fraction per 0.5° per month. It is served from the UMD SFTP server
in the MODIS fire user guide, not from Earthdata/CMR, and the cloud build machine cannot reach it.

### 10.6 Other v8 changes

- Bootstrap: a resample counts only if its MODIS sum meets the same minimum (50) as the estimate. This
  narrows the extreme upper bounds in sparse strata. Estimates are unchanged.
- Mediterranean validation: Spain, Portugal, Italy, Greece and Turkey (FIRMS country files 2000–2025),
  same pipeline. Raw MODIS is −15 % (Portugal) to −67 % (Italy) against VIIRS.
- 2012 step factor, including the zero part as the app shows it: Argentina 1.06, Australia 1.04, Brazil 1.10,
  Canada 1.21, United States 0.90, Spain 1.13, Portugal 1.09, Italy 0.97, Greece 1.02, Turkey 0.99
  (v7.1 without the zero part: Argentina 1.05, United States 0.79, Canada 1.21). The Río Negro and Chaco
  box step checks in meta.json still leave out the zero part.
- Hotspot CSV for all 10 countries. Point files are stored compact: lat/lon × 10⁴ and FRP × 10 as
  integers, about 30 % smaller.

## 11. Burned area and boundary layers

**What it is.** NASA's monthly burned-area products, shown next to the hotspots, not merged with
them. MCD64A1 v061 (MODIS Terra + Aqua, Nov 2000 onward, doi:10.5067/MODIS/MCD64A1.061) and
VNP64A1 v002 (VIIRS S-NPP, Mar 2012 onward, doi:10.5067/VIIRS/VNP64A1.002), both 500 m sinusoidal
tiles from NASA LP DAAC. Built for the ten processed countries, Nov 2000 to Dec 2025 (same end as the
hotspots). 57,398 monthly tiles were downloaded and reduced (`pipeline/burned_area.py`).

**How.** For each monthly tile, a pixel counts as burned when `Burn Date` > 0 (the file's own
valid range is 0 to 366; -1 unmapped, -2 water). Every pixel of the equal-area grid covers
463.31² m = 0.2147 km². Pixels are kept when their centre falls inside the Natural Earth 1:50m country
polygon, then summed into the app's 0.1° cells (same centres as the hotspot cells). No burn date
fell outside its file's month in any country. Land the algorithm could not map (`Burn Date` = -1) is
summed separately and shown in the card for the whole country.

**MODIS vs VIIRS in the overlap (Mar 2012 to Dec 2025, whole country, monthly totals).**

| Country | MCD64A1 km² | VNP64A1 km² | VIIRS vs MODIS | Monthly correlation | MCD64A1 mean per year 2001–2025, km² |
|---|---|---|---|---|---|
| Argentina | 433,416 | 420,600 | −3.0 % | 0.933 | 37,505 |
| Australia | 5,928,343 | 5,600,013 | −5.5 % | 0.995 | 472,235 |
| Brazil | 2,319,745 | 2,089,807 | −9.9 % | 0.998 | 181,477 |
| Canada | 461,117 | 515,028 | +11.7 % | 0.985 | 25,731 |
| United States | 462,556 | 461,778 | −0.2 % | 0.979 | 32,731 |
| Spain | 15,347 | 15,326 | −0.1 % | 0.997 | 1,157 |
| Portugal | 16,516 | 16,011 | −3.1 % | 0.997 | 1,245 |
| Italy | 10,088 | 11,152 | +10.6 % | 0.943 | 891 |
| Greece | 8,036 | 7,851 | −2.3 % | 0.992 | 650 |
| Turkey | 71,593 | 88,524 | +23.6 % | 0.941 | 5,440 |

Correlation uses months with any burned area. Unlike the hotspots, the two burned-area products
already agree closely, so we do not rescale either one; the app shows both and lets you pick. Turkey,
Canada and Italy are where they differ most (VIIRS higher), so treat those as two separate
estimates.

**Limits.**
* Both products miss small fires (well under one 500 m pixel, about 21 ha), so they report less
  than national statistics where small agricultural fires dominate. The hotspots catch many of these.
* Matching uses 0.1° cell centres, like the hotspots. A province or department is the set of cells
  whose centres fall inside it, so edges are approximate, and units under about 100 km² can contain
  no cell at all (the card says so).
* VNP64A1 depends on S-NPP, which stopped on 2 Nov 2026; it does not affect this 2025 build.
* Only the ten processed countries are built. Each new country needs one run of
  `pipeline/burned_area.py` (a NASA Earthdata login, about 10 to 25 minutes).

**Boundaries.** Admin-1 (provinces, states) comes from Natural Earth 1:10m (public domain) for every
country. Admin-2 comes from geoBoundaries gbOpen (Runfola et al. 2020), with the licence recorded per
country in `web/data/ref/admin_index.json`. geoBoundaries' "ADM2" level is not the same kind of unit
everywhere (Argentina 525 departments, US 3,233 counties, Italy 20 units, Greece 14 units). Admin-1
and admin-2 come from different sources, so their lines can differ slightly.
