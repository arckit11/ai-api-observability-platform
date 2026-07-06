# Synthetic Data Generator

Standalone tool that produces 30 days of realistic 1-minute API telemetry
per service, with anomaly + failure injection for evaluation. Written to
the platform's Postgres `metrics` table (or CSV for offline use).

Detailed in the accompanying paper §VI-A.

## Traffic model

For each configured service, one-minute RPM is a superposition of:

- Baseline traffic level (per-service constant)
- Diurnal cycle — cosine over 24h, peaking around 14:00
- Weekly cycle — Mon-Fri at full traffic, weekends scaled down
- Gaussian noise on top

Latency and error rate are derived from load: below 50% capacity latency
is flat; above that, P99 grows super-linearly. Error rate lifts once load
exceeds 70% capacity.

## Fault injection

- **Anomaly episodes** — response times multiplied by 3-6× for 5-20 min windows,
  Poisson-sampled at ~0.5 events / service / day
- **Failure episodes** — error rate forced ≥ 15% and P99 latency ≥ 2.5s for
  15-min blocks, Poisson-sampled at ~0.1 events / service / day

Ground-truth labels (`is_anomaly`, `is_failure_window`) are written to
`out/labels.csv` alongside the metrics for evaluation.

## Install

```bash
cd synthetic-data
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use

```bash
# 30 days into the platform Postgres (default)
synth generate --days 30

# 7 days for a quick smoke test, custom seed
synth generate --days 7 --seed 1

# CSV output instead of Postgres
synth generate --days 7 --out csv --path out/metrics.csv

# Clean up synthetic rows before regenerating
synth clear --since 2026-01-01
```

## Default service inventory

Five services are registered on first run (`owner = 'synthetic'`):

| Name | Baseline RPM | Capacity RPM | Baseline P99 |
|---|---:|---:|---:|
| payments-api      |   350 |  1800 | 180 ms |
| inventory-api     |   800 |  3500 | 140 ms |
| orders-api        |   250 |  1200 | 220 ms |
| user-api          |   180 |  1500 |  90 ms |
| notification-api  |   120 |   800 | 310 ms |
