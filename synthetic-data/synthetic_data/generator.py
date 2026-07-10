"""Traffic pattern generator.

Models per-service RPM as a superposition of:
  - Baseline traffic level (per-service constant)
  - Diurnal cycle: sinusoid over 24h with configurable amplitude / phase
  - Weekly cycle: weekday (Mon-Fri) traffic > weekend
  - Gaussian noise on top

Latency and error rate are correlated with load: as load approaches a
service's capacity, P99 grows super-linearly and error rate rises.

Anomaly and failure injections layer on top of the baseline signal so the
ML modules have ground-truth labels to evaluate against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import numpy as np
import pandas as pd


# ─── Service profile ────────────────────────────────────────────
@dataclass
class ServiceProfile:
    """Per-service traffic characteristics."""

    service_id: UUID
    name: str
    baseline_rpm: float = 200.0        # avg requests-per-minute at midday
    diurnal_amplitude: float = 0.6     # peak = baseline * (1 + amp)
    weekend_factor: float = 0.55       # weekend traffic = weekday * factor
    baseline_p99_ms: float = 250.0     # under nominal load
    capacity_rpm: float = 2000.0       # RPM at which the service saturates
    baseline_error_rate: float = 0.008
    noise_std_rpm: float = 0.08        # fractional gaussian noise on RPM


DEFAULT_PROFILES: list[ServiceProfile] = [
    ServiceProfile(
        service_id=UUID("11111111-1111-1111-1111-111111111111"),
        name="payments-api",
        baseline_rpm=350.0,
        capacity_rpm=1800.0,
        baseline_p99_ms=180.0,
    ),
    ServiceProfile(
        service_id=UUID("22222222-2222-2222-2222-222222222222"),
        name="inventory-api",
        baseline_rpm=800.0,
        capacity_rpm=3500.0,
        baseline_p99_ms=140.0,
    ),
    ServiceProfile(
        service_id=UUID("33333333-3333-3333-3333-333333333333"),
        name="orders-api",
        baseline_rpm=250.0,
        capacity_rpm=1200.0,
        baseline_p99_ms=220.0,
    ),
    ServiceProfile(
        service_id=UUID("44444444-4444-4444-4444-444444444444"),
        name="user-api",
        baseline_rpm=180.0,
        capacity_rpm=1500.0,
        baseline_p99_ms=90.0,
    ),
    ServiceProfile(
        service_id=UUID("55555555-5555-5555-5555-555555555555"),
        name="notification-api",
        baseline_rpm=120.0,
        capacity_rpm=800.0,
        baseline_p99_ms=310.0,
    ),
]


# ─── Fault injection ────────────────────────────────────────────
@dataclass
class AnomalyEpisode:
    """A response-time spike lasting ``duration_minutes`` minutes."""

    service_id: UUID
    start: datetime
    duration_minutes: int
    latency_multiplier: float


@dataclass
class FailureEpisode:
    """A sustained failure: elevated error rate + P99 latency."""

    service_id: UUID
    start: datetime
    duration_minutes: int = 15
    error_rate_floor: float = 0.15      # forces error_rate >= 15%
    p99_floor_ms: float = 2500.0        # forces P99 >= 2.5s


@dataclass
class InjectionPlan:
    anomalies: list[AnomalyEpisode] = field(default_factory=list)
    failures: list[FailureEpisode] = field(default_factory=list)


def default_injection_plan(
    profiles: list[ServiceProfile],
    start: datetime,
    days: int,
    seed: int,
    anomaly_rate_per_day: float = 1.0,
    failure_rate_per_day: float = 0.6,
) -> InjectionPlan:
    """Generate a plausible mix of anomalies and failures over the window.

    Failure density was bumped from 0.1/day → 0.6/day per service after the
    first training pass — recall was starved at ~0.22 with only ~500
    positives across 216k rows. The XGBoost failure classifier needs ~2-3k
    positives to lift recall into the 0.5+ range without sacrificing precision.
    """
    rng = np.random.default_rng(seed)
    plan = InjectionPlan()

    for prof in profiles:
        n_anom = rng.poisson(anomaly_rate_per_day * days)
        for _ in range(n_anom):
            offset_min = int(rng.integers(0, days * 24 * 60))
            plan.anomalies.append(
                AnomalyEpisode(
                    service_id=prof.service_id,
                    start=start + timedelta(minutes=offset_min),
                    duration_minutes=int(rng.integers(5, 20)),
                    latency_multiplier=float(rng.uniform(3.0, 6.0)),
                )
            )

        n_fail = rng.poisson(failure_rate_per_day * days)
        for _ in range(n_fail):
            offset_min = int(rng.integers(0, days * 24 * 60))
            plan.failures.append(
                FailureEpisode(
                    service_id=prof.service_id,
                    start=start + timedelta(minutes=offset_min),
                    duration_minutes=int(rng.integers(10, 25)),
                )
            )

    return plan


# ─── Core simulator ─────────────────────────────────────────────
def _diurnal_multiplier(hour_of_day: np.ndarray, amplitude: float) -> np.ndarray:
    # Peak around 14:00 (hour_of_day = 14).
    phase = 2 * np.pi * (hour_of_day - 14.0) / 24.0
    return 1.0 + amplitude * (np.cos(phase))


def _weekly_multiplier(day_of_week: np.ndarray, weekend_factor: float) -> np.ndarray:
    # day_of_week: 0=Mon .. 6=Sun
    return np.where(day_of_week >= 5, weekend_factor, 1.0)


def _load_to_latency(rpm: np.ndarray, prof: ServiceProfile) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute (mean, p95, p99) latency in ms from instantaneous RPM.

    Below 50% capacity latency is flat; above that it climbs super-linearly.
    """
    load = np.clip(rpm / prof.capacity_rpm, 0.0, 1.5)
    stress = np.where(load < 0.5, 0.0, (load - 0.5) ** 2)
    latency_mean = prof.baseline_p99_ms * 0.35 * (1.0 + 3.0 * stress)
    latency_p95 = prof.baseline_p99_ms * 0.70 * (1.0 + 5.0 * stress)
    latency_p99 = prof.baseline_p99_ms * (1.0 + 8.0 * stress)
    return latency_mean, latency_p95, latency_p99


def _load_to_error_rate(rpm: np.ndarray, prof: ServiceProfile, rng: np.random.Generator) -> np.ndarray:
    load = np.clip(rpm / prof.capacity_rpm, 0.0, 1.5)
    stress = np.where(load < 0.7, 0.0, (load - 0.7) * 0.5)
    base = prof.baseline_error_rate + stress
    jitter = rng.normal(0, 0.002, size=rpm.shape)
    return np.clip(base + jitter, 0.0, 1.0)


def simulate_service(
    prof: ServiceProfile,
    start: datetime,
    days: int,
    plan: InjectionPlan,
    seed: int,
) -> pd.DataFrame:
    """Produce a DataFrame of 1-minute metric rows for one service.

    Columns: service_id, window_start, window_end, window_size, request_count,
    rpm, response_time_mean, response_time_p95, response_time_p99,
    error_rate, success_rate, is_anomaly (ground truth), is_failure_window.
    """
    rng = np.random.default_rng(seed + hash(prof.service_id) % 100_000)
    total_minutes = days * 24 * 60

    timestamps = pd.date_range(start=start, periods=total_minutes, freq="1min", tz="UTC")
    hour_of_day = timestamps.hour.values.astype(float)
    day_of_week = timestamps.dayofweek.values.astype(float)

    diurnal = _diurnal_multiplier(hour_of_day, prof.diurnal_amplitude)
    weekly = _weekly_multiplier(day_of_week, prof.weekend_factor)
    noise = rng.normal(1.0, prof.noise_std_rpm, total_minutes)

    rpm = prof.baseline_rpm * diurnal * weekly * noise
    rpm = np.clip(rpm, 1.0, None)

    latency_mean, latency_p95, latency_p99 = _load_to_latency(rpm, prof)
    error_rate = _load_to_error_rate(rpm, prof, rng)

    is_anomaly = np.zeros(total_minutes, dtype=bool)
    is_failure = np.zeros(total_minutes, dtype=bool)

    # ─── Layer anomaly episodes ───────────────────────────────
    for ep in plan.anomalies:
        if ep.service_id != prof.service_id:
            continue
        idx_start = int((ep.start - start).total_seconds() // 60)
        if idx_start < 0 or idx_start >= total_minutes:
            continue
        idx_end = min(total_minutes, idx_start + ep.duration_minutes)
        latency_mean[idx_start:idx_end] *= ep.latency_multiplier
        latency_p95[idx_start:idx_end] *= ep.latency_multiplier
        latency_p99[idx_start:idx_end] *= ep.latency_multiplier
        is_anomaly[idx_start:idx_end] = True

    # ─── Layer failure episodes ───────────────────────────────
    for ep in plan.failures:
        if ep.service_id != prof.service_id:
            continue
        idx_start = int((ep.start - start).total_seconds() // 60)
        if idx_start < 0 or idx_start >= total_minutes:
            continue
        idx_end = min(total_minutes, idx_start + ep.duration_minutes)
        error_rate[idx_start:idx_end] = np.maximum(
            error_rate[idx_start:idx_end], ep.error_rate_floor
        )
        latency_p99[idx_start:idx_end] = np.maximum(
            latency_p99[idx_start:idx_end], ep.p99_floor_ms
        )
        latency_p95[idx_start:idx_end] = np.maximum(
            latency_p95[idx_start:idx_end], ep.p99_floor_ms * 0.7
        )
        is_failure[idx_start:idx_end] = True

    request_count = np.round(rpm).astype(int)
    success_rate = 1.0 - error_rate

    window_start = timestamps.tz_convert("UTC").to_pydatetime()
    window_end = [ts + timedelta(minutes=1) for ts in window_start]

    return pd.DataFrame(
        {
            "service_id": [str(prof.service_id)] * total_minutes,
            "window_start": window_start,
            "window_end": window_end,
            "window_size": ["1m"] * total_minutes,
            "request_count": request_count,
            "rpm": rpm.round(2),
            "response_time_mean": latency_mean.round(2),
            "response_time_p95": latency_p95.round(2),
            "response_time_p99": latency_p99.round(2),
            "error_rate": np.round(error_rate, 4),
            "success_rate": np.round(success_rate, 4),
            "is_anomaly": is_anomaly,
            "is_failure_window": is_failure,
        }
    )
