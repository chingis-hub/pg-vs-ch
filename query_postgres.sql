SELECT
    PULocationID,
    EXTRACT(HOUR FROM tpep_pickup_datetime)::INT AS hour,
    COUNT(*)                                     AS trips,
    AVG(trip_distance)                           AS avg_distance,
    SUM(total_amount)                            AS revenue
FROM yellow_taxi_2025
WHERE trip_distance > 1
  AND total_amount > 5
GROUP BY PULocationID, hour
ORDER BY revenue DESC;
