# Synthetic Data Generator

Purpose: bootstrap training / evaluation data for the ML modules before
enough real production traffic accumulates. Detailed in paper §VI-A.

**Not implemented yet** — placeholder for Phase 2. Planned output:

- 30 days of one-minute-interval metric records per registered service
- Diurnal + weekly seasonality with Gaussian noise on baseline traffic
- Anomaly injection: response times × factor for fixed-duration windows
- Failure injection: elevated error rate + P99 latency in 15-min blocks
- Ground-truth labels for evaluation (RMSE/MAPE, precision/recall)

Emits records via one of:
1. Direct writes to Postgres (`metrics` table)
2. Kafka producer on `metrics` topic (exercises the full ingestion path)

CLI target once implemented:
```
python -m synthetic_data.generate --services 5 --days 30 --emit kafka
```
