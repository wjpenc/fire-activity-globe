# Demo script (about 4 minutes)

Before you start: run `cd web && python3 -m http.server 8000`, open http://localhost:8000,
and wait for the globe and the results panel to fill. Only the map imagery needs internet (NASA Blue
Marble and OpenStreetMap, both keyless). If imagery fails, the globe turns plain blue and everything
else still works. To hide imagery on purpose, open http://localhost:8000/?basemap=off.

## Screen layout (v8)

The app opens on a 3D globe showing harmonized hotspots for every processed country (0.25° cells,
summed over whole years). The top bar holds the country search, **Whole world**, the area tools (once a
country is picked), dates and **Update**. Results float in a panel on the right: drag its top bar to
move it; the caret collapses it. **2D / 3D** (top left) switches globe and flat map; the globe also
turns flat as you zoom in. **Method & validation** (top right) opens the validation tables.
The **Layers** box (top left, below the zoom buttons) switches hotspots, burned area (MODIS or VIIRS),
provinces/states and departments/counties on and off.
Next to the search box, a **country dropdown** lists the five processed countries. With Argentina
selected, **Río Negro**, **Chaco** and **Argentina** buttons appear. They set an approximate province
box, or go back to the whole country.

## What the map shows (if asked)

Each dot is a grid cell with fire in the selected dates: 0.25° cells in the world view, 0.1° cells
(about 11 km) once a country is picked. Colour is the harmonized hotspot total, pale yellow (few) to
dark red (many). The ramp only gets darker, so it reads the same with any type of colour blindness.
The white line is the selected country's border. A blue outline is a box, circle or polygon you drew.
Blue squares (when **Burned area** is on) are NASA's monthly burned area in each 0.1° cell, light
(little) to dark blue (a lot). Thin white lines are provinces; dashed lines are departments.

## 1. The problem (30 s)

**Say:** "Two NASA satellites have watched every fire on Earth for 25 years: MODIS since 2000, VIIRS
since 2012. VIIRS has sharper eyes, so when it arrived, fire counts appeared to jump. Nothing changed
on the ground. In every country we tested, raw MODIS sees about half of what VIIRS sees. Stitch them
together and you get a fake upward trend."

**Click:** nothing yet. Let the globe turn under the cursor.

## 2. What we did (60 s)

**Say:** "We put the whole record on the VIIRS scale, in two steps. First, VIIRS splits one fire into
several small pixels, so we count fire-cell-days: one 1 km cell on fire on one day counts once.
Second, for the gap that is left, we learn a VIIRS-to-MODIS ratio for each half-degree region and
season from the years both satellites flew, and apply it back to 2000, with a bootstrap range.
Where MODIS saw nothing in a month, we add the average VIIRS count for such months, because VIIRS
often still sees small fires there.
The same pipeline runs on any NASA FIRMS country file. So far we have run five."

**Click:** type **Brazil** in the search box and press Enter. The globe pulls back, turns and zooms in;
the border lights up and the panel shows Brazil.

## 3. A country's burning calendar (60 s)

**Say:** "This is Brazil's burning-activity calendar: months across, years down. You can see the
August to October fire season and how it shifts year to year. Hover a cell to see whether it is
observed VIIRS or MODIS times the ratio, with its range."

**Click:** point at **Latest month vs. median**, then scroll to **Before / after harmonization**.
"The orange harmonized line runs straight through 2012. No fake jump."

## 4. Any area, any format (40 s)

**Click:** click **Canada** on the globe. Then **Polygon**, **Draw polygon on map**, click 4 to 5
points, double-click to finish. Click **CSV** on the calendar and **SVG** on a chart. Click **ES**.

**Say:** "Click any country, or draw a box, a circle or a polygon inside it. Everything downloads as
CSV, PNG or SVG, in English or Spanish. It is a static site, so it runs on GitHub Pages with no server."

## 4b. Burned area and provinces (40 s)

**Click:** search **Argentina**. In **Layers**, tick **Burned area** and **Provinces / states**, untick
**Hotspots**. Click Córdoba. Scroll the panel to **Burned area**.

**Say:** "Hotspots tell you where fire was seen; burned area tells you how much land actually burned.
These are NASA's own monthly burned-area products, MODIS since 2000 and VIIRS since 2012, on the same
grid. Click any province or department and everything recalculates for it: Córdoba lost about
31,500 square kilometres to fire between 2000 and 2025 (MODIS). Switch to VIIRS to compare the two sensors."

## 5. Does it work? (50 s)

**Click:** **Whole world**, then **Method & validation**. Close it with ×.

**Say:** "Every country is trained on 2012 to 2019 and tested on later years the model never saw.
Bias against what VIIRS actually saw: Australia −2.0 %, United States −2.1 %, Argentina +4.5 %,
Canada +6.3 %, Brazil +7.4 %. We added five Mediterranean countries as a check: Italy −5 %, Turkey +1 %,
but Spain, Greece and Portugal run 11 to 14 % high on small fire counts. Raw MODIS was about −50 % everywhere."

## 6. Honest limits and next steps (30 s)

**Say:** "Four limits. Ten countries are processed so far; the rest of the planet is the same
pipeline run one country at a time. Months where MODIS saw nothing get an average VIIRS value, which
fixes the low bias in sparse areas but adds a little to very quiet months. MODIS orbits have drifted since
2023; we tested dropping those years and it did not help consistently. And the data ends in December 2025;
S-NPP stopped in November 2026, so extending it means tying NOAA-20 to the S-NPP scale, which we have validated. We also tested day/night ratios and land-cover fire types; neither
beat the current method on held-out years, so neither is used."

---

## Likely questions

**Is burned area harmonized like the hotspots?**
No. We show both NASA products side by side and do not rescale either. In the years both exist
they are close (see METHOD.md section 11), but they are separate estimates.

**Where do the boundaries come from?**
Provinces/states: Natural Earth (public domain). Departments/counties: geoBoundaries, which records
each country's own source and licence; we show them in the map credits.

**Why a ratio of sums and not a median ratio?**
"We tested both. The median needs months where MODIS saw at least 5 fires, which throws away exactly
the months where VIIRS sees much more. It underestimated Río Negro by 46 % and created a false 74 % jump
at 2012. The ratio of sums uses every month and cut that bias to about 4 %."

**Why not merge all VIIRS satellites?**
"Each new satellite adds more looks, so counts would rise with every launch. That is the same fake trend
we are removing. S-NPP is the one reference. NOAA-20 is only used after S-NPP stopped, tied to it on
2018 to 2022 and tested on 2023 onward (+1.4 % nationally)."

**Why not quantile mapping?**
"We tested it: −14 % bias, versus +4 %. It also does not add up. Mapping each cell and summing an area
gives a different answer than mapping the area total. A ratio adds up correctly for any shape a user draws."

**What about viewing angle and the Aqua-only calibration?**
"Both are measured and validated. Downweighting off-nadir MODIS pixels and using Aqua alone both scored
worse on held-out years, so they are off. The results are documented."

**What about orbit drift?**
"Aqua's local overpass time over Argentina is 13.9 h until 2022, then 14.5 h in 2024 and 15.8 h in 2026.
We train before the drift. Recent months carry that caveat."

**Does the confidence cutoff matter?**
"We reran with low-confidence detections included. The bias moved by at most about 1 point."

**Why only five countries so far?**
"We piloted on Argentina because this is CONAE's challenge. Then we ran the same pipeline, unchanged,
on Canada, Australia and the United States, trained on 2012 to 2019 and tested on 2020 to 2025.
Bias versus what VIIRS saw: Australia −2.6 %, United States −3.8 %, Canada +12.8 %. Raw MODIS was
about −50 % in all three. Brazil: +7.9 %.
The whole planet is tens of gigabytes and runs one country at a time; that is the next step."

Demo option: the **Country** dropdown next to the search box picks a processed country directly.
Since v8 every country has the hotspot CSV.

**Can you verify the data?**
"Everything comes from public NASA FIRMS country files and the FIRMS API. docs/VERIFY_FIRMS.md lists the
URLs, and one command rebuilds every number."
