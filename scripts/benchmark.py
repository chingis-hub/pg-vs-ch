"""
Runs query_postgres.sql and query_clickhouse.sql each 3 times and prints execution times.
Usage: python benchmark.py
"""
import time
import statistics
from pathlib import Path
import psycopg2
import clickhouse_connect

ROOT = Path(__file__).parent.parent

PG   = dict(host="localhost", port=5432, dbname="taxidb", user="postgres", password="postgres")
CH   = dict(host="localhost", port=8123, username="default", password="")
RUNS = 3


def bench_postgres(query: str) -> list[float]:
    conn = psycopg2.connect(**PG)
    conn.autocommit = True
    cur = conn.cursor()
    times = []
    for i in range(RUNS):
        t0 = time.perf_counter()
        cur.execute(query)
        cur.fetchall()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        print(f"  run {i + 1}: {elapsed:.3f}s")
    cur.close()
    conn.close()
    return times


def bench_clickhouse(query: str) -> list[float]:
    client = clickhouse_connect.get_client(**CH)
    times = []
    for i in range(RUNS):
        t0 = time.perf_counter()
        client.query(query)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        print(f"  run {i + 1}: {elapsed:.3f}s")
    return times


def print_results(pg_times: list[float], ch_times: list[float]):
    w = 56
    print("\n" + "=" * w)
    header = f"{'':16}" + "".join(f"{'Run '+str(i+1):>9}" for i in range(RUNS)) + f"{'Avg':>9}{'Min':>9}"
    print(header)
    print("-" * w)

    def row(label, times):
        cols = "".join(f"{t:>9.3f}" for t in times)
        return f"{label:<16}{cols}{statistics.mean(times):>9.3f}{min(times):>9.3f}"

    print(row("PostgreSQL", pg_times))
    print(row("ClickHouse", ch_times))
    print("=" * w)
    print("(seconds)")

    ratio = statistics.mean(pg_times) / statistics.mean(ch_times)
    faster, slower = ("ClickHouse", "PostgreSQL") if ratio > 1 else ("PostgreSQL", "ClickHouse")
    print(f"\n{faster} is {max(ratio, 1/ratio):.1f}x faster on average")


if __name__ == "__main__":
    with open(ROOT / "sql" / "query_postgres.sql") as f:
        pg_query = f.read().strip()
    with open(ROOT / "sql" / "query_clickhouse.sql") as f:
        ch_query = f.read().strip()

    print("=== PostgreSQL ===")
    pg_times = bench_postgres(pg_query)

    print("\n=== ClickHouse ===")
    ch_times = bench_clickhouse(ch_query)

    print_results(pg_times, ch_times)
