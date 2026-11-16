"""Build the world-view layer: 0.25-degree x year totals for every processed country."""
import argparse
import pathlib

import duckdb
import pyarrow.parquet as pq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default="web/data/countries")
    ap.add_argument("--out", default="web/data/global_q025_year.parquet")
    a = ap.parse_args()
    files = sorted(str(f) for f in pathlib.Path(a.countries).glob("*/calendar_cells.parquet"))
    q = f"""SELECT round(floor(lat*4)/4 + 0.125, 3)::DOUBLE AS lat, round(floor(lon*4)/4 + 0.125, 3)::DOUBLE AS lon,
               "year"::INT AS y, sum(harmonized_count)::DOUBLE AS h
            FROM read_parquet({files}) GROUP BY ALL HAVING sum(harmonized_count) > 0 ORDER BY y, lat, lon"""
    t = duckdb.sql(q).arrow().read_all()
    # data page v1 keeps the file readable by the browser Parquet reader
    pq.write_table(t, a.out, compression="snappy", data_page_version="1.0")
    print(f"{len(files)} countries, {t.num_rows:,} rows -> {a.out}")


if __name__ == "__main__":
    main()
