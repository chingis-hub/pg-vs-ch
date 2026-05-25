"""
Downloads yellow_tripdata_2024-02.parquet and loads it into PostgreSQL and ClickHouse.
Usage:
  python load_data.py          # load both
  python load_data.py pg       # PostgreSQL only
  python load_data.py ch       # ClickHouse only
"""
import sys
import time
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import clickhouse_connect
from pathlib import Path

ROOT      = Path(__file__).parent.parent
DATA_URL  = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-02.parquet"
DATA_FILE = ROOT / "yellow_tripdata_2024-02.parquet"

PG = dict(host="localhost", port=5432, dbname="taxidb", user="postgres", password="postgres")
CH = dict(host="localhost", port=8123, username="default", password="")

COLS = [
    "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance", "RatecodeID", "store_and_fwd_flag",
    "PULocationID", "DOLocationID", "payment_type", "fare_amount",
    "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
    "total_amount", "congestion_surcharge", "Airport_fee", "cbd_congestion_fee",
]


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download():
    if Path(DATA_FILE).exists():
        print(f"  already exists: {DATA_FILE}")
        return
    print(f"  {DATA_URL}")
    resp = requests.get(DATA_URL, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    done = 0
    with open(DATA_FILE, "wb") as f:
        for chunk in resp.iter_content(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total}%  ({done >> 20}/{total >> 20} MB)", end="", flush=True)
    print()


# ---------------------------------------------------------------------------
# Read + normalize
# ---------------------------------------------------------------------------

ROW_LIMIT = 5_000  # set to None to load all rows


def read_parquet() -> pd.DataFrame:
    print(f"  reading {DATA_FILE} ...")
    df = pd.read_parquet(DATA_FILE)
    if ROW_LIMIT:
        df = df.iloc[:ROW_LIMIT]
        print(f"  limited to {ROW_LIMIT:,} rows")

    # cbd_congestion_fee was added in 2025 — fill with 0 for 2024 data
    for col in COLS:
        if col not in df.columns:
            print(f"  missing column '{col}' — filling with 0")
            df[col] = 0.0

    df = df[COLS].copy()

    df["store_and_fwd_flag"] = df["store_and_fwd_flag"].fillna("N").astype(str).str[:1]

    for col in df.select_dtypes("float").columns:
        df[col] = df[col].fillna(0.0)

    for col in ["VendorID", "PULocationID", "DOLocationID"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["payment_type"] = pd.to_numeric(df["payment_type"], errors="coerce").fillna(0).astype(int)

    print(f"  {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

def load_postgres(df: pd.DataFrame):
    print("  connecting to PostgreSQL...")
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()

    with open(ROOT / "sql" / "postgres_schema.sql") as f:
        cur.execute(f.read())
    conn.commit()

    sql = f"INSERT INTO yellow_taxi_2025 ({', '.join(COLS)}) VALUES %s"
    chunk_size = 50_000
    n = len(df)
    t0 = time.perf_counter()

    for i in range(0, n, chunk_size):
        rows = list(df.iloc[i : i + chunk_size].itertuples(index=False, name=None))
        execute_values(cur, sql, rows)
        conn.commit()
        elapsed = time.perf_counter() - t0
        pct = min(i + chunk_size, n) * 100 // n
        print(f"\r  {pct}%  {min(i + chunk_size, n):,}/{n:,}  ({elapsed:.0f}s)", end="", flush=True)

    print()
    print("  ANALYZE + CREATE INDEX ...")
    cur.execute("ANALYZE yellow_taxi_2025")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_distance ON yellow_taxi_2025(trip_distance)")
    conn.commit()
    cur.close()
    conn.close()
    print(f"  done in {time.perf_counter() - t0:.1f}s")


# ---------------------------------------------------------------------------
# ClickHouse
# ---------------------------------------------------------------------------

def load_clickhouse(df: pd.DataFrame):
    print("  connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CH)

    with open(ROOT / "sql" / "clickhouse_schema.sql") as f:
        client.command(f.read())

    ch_df = df.copy()
    for col in ["VendorID", "PULocationID", "DOLocationID"]:
        ch_df[col] = ch_df[col].astype("int32")
    ch_df["payment_type"] = ch_df["payment_type"].astype("int64")

    # ensure timezone-aware datetimes so ClickHouse receives correct UTC offset
    for col in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        if pd.api.types.is_datetime64_any_dtype(ch_df[col]):
            if ch_df[col].dt.tz is None:
                ch_df[col] = ch_df[col].dt.tz_localize("UTC")

    t0 = time.perf_counter()
    print(f"  inserting {len(ch_df):,} rows...")
    client.insert_df("yellow_taxi_2025", ch_df)
    print(f"  done in {time.perf_counter() - t0:.1f}s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print("=== Download ===")
    download()

    print("=== Read parquet ===")
    df = read_parquet()

    if target in ("all", "pg", "postgres"):
        print("=== Load PostgreSQL ===")
        load_postgres(df)

    if target in ("all", "ch", "clickhouse"):
        print("=== Load ClickHouse ===")
        load_clickhouse(df)

    print("=== Done ===")
