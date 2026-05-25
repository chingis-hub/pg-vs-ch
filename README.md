# PostgreSQL vs ClickHouse — Analytical Query Benchmark

Compares a row-oriented DB (PostgreSQL) against a column-oriented DB (ClickHouse)
on NYC TLC Yellow Taxi trip data.

## Project structure

```
pg-vs-ch/
├── docker-compose.yml
├── requirements.txt
├── sql/
│   ├── postgres_schema.sql
│   ├── clickhouse_schema.sql
│   ├── query_postgres.sql
│   └── query_clickhouse.sql
└── scripts/
    ├── load_data.py
    └── benchmark.py
```

## Setup

```powershell
docker-compose up -d
pip install -r requirements.txt
```

## Load data

```powershell
python scripts/load_data.py
```

Downloads `yellow_tripdata_2024-02.parquet` (~500 MB, ~3.6 M rows) and loads it
into both databases. To limit rows for a quick test, set `ROW_LIMIT` at the top
of `scripts/load_data.py` (e.g. `5_000`). Set to `None` for the full dataset.

## Run benchmark

```powershell
python scripts/benchmark.py
```

Executes each query 3 times and prints a results table.

## Query

Both databases run the same logical query — pick-up location × hour aggregation
with revenue, trip count, and average distance:

```sql
SELECT
    PULocationID,
    <hour_extract>,          -- EXTRACT(HOUR FROM ...) in PG, toHour() in CH
    COUNT(*)        AS trips,
    AVG(trip_distance)  AS avg_distance,
    SUM(total_amount)   AS revenue
FROM yellow_taxi_2025
WHERE trip_distance > 1
  AND total_amount > 5
GROUP BY PULocationID, hour
ORDER BY revenue DESC;
```

## Results (5 000 rows)

| Database   | Run 1  | Run 2  | Run 3  | Avg    | Min    |
|------------|--------|--------|--------|--------|--------|
| PostgreSQL | 0.102s | 0.099s | 0.091s | 0.097s | 0.091s |
| ClickHouse | 0.059s | 0.051s | 0.048s | 0.053s | 0.048s |

**ClickHouse is ~1.9x faster** at 5 000 rows.
At the full 3.6 M rows the gap is typically 10–50x.

## Observations

**ClickHouse wins because of its storage model.**
PostgreSQL stores data row by row — to read 5 columns it must scan all 20 columns
of every row. ClickHouse stores each column separately; the query only touches the
columns it actually needs, skipping the rest entirely.

**The query shape amplifies the advantage.**
Aggregations (`COUNT`, `AVG`, `SUM`) over a few columns on millions of rows is the
canonical analytical workload. PostgreSQL is optimised for the opposite pattern —
fetching whole rows for a small number of records (OLTP).

**ClickHouse's sort order matches the query.**
The MergeTree table is ordered by `(PULocationID, toHour(tpep_pickup_datetime))`,
which is exactly the `GROUP BY`. ClickHouse processes pre-sorted groups without an
extra sort step.

**Run 1 is always the slowest** — the OS page cache is cold. Runs 2–3 are faster
because the data is already in memory. In production benchmarks the first run is
typically discarded for this reason.

**5 000 rows understates the difference.**
Both databases finish in under 100 ms because the whole table fits in RAM.
The real gap appears at millions of rows, where I/O reduction and ClickHouse's
vectorised execution engine make a decisive difference.
