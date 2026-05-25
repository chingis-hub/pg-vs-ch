CREATE TABLE IF NOT EXISTS yellow_taxi_2025 (
    VendorID                Int32,
    tpep_pickup_datetime    DateTime64(6, 'America/New_York'),
    tpep_dropoff_datetime   DateTime64(6, 'America/New_York'),
    passenger_count         Float64,
    trip_distance           Float64,
    RatecodeID              Float64,
    store_and_fwd_flag      String,
    PULocationID            Int32,
    DOLocationID            Int32,
    payment_type            Int64,
    fare_amount             Float64,
    extra                   Float64,
    mta_tax                 Float64,
    tip_amount              Float64,
    tolls_amount            Float64,
    improvement_surcharge   Float64,
    total_amount            Float64,
    congestion_surcharge    Float64,
    Airport_fee             Float64,
    cbd_congestion_fee      Float64,

    INDEX idx_distance_amount (trip_distance, total_amount)
    TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree()
ORDER BY (PULocationID, toHour(tpep_pickup_datetime));
