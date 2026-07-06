# ML Service

Python FastAPI subsystem serving the five predictive modules described in
Section IV of the paper.

## Modules

| Path | Module | Algorithm |
|---|---|---|
| `POST /predict/traffic` | Traffic forecasting | XGBoost Regressor |
| `POST /predict/failure` | Failure prediction | XGBoost Classifier |
| `POST /predict/anomaly` | Anomaly detection | Isolation Forest |
| `POST /score/health` | Composite health score | Weighted linear combination |
| `POST /alerts/prioritize` | Alert prioritization | Random Forest |

Contract of record: `../docs/api-contracts/ml-service-openapi.yaml`.

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

## Layout

```
app/
├── main.py                # FastAPI app + router wiring
├── config.py              # pydantic-settings
├── modules/               # one subpackage per predictive module
│   ├── traffic/
│   ├── failure/
│   ├── anomaly/
│   ├── health/
│   └── alerts/
├── features/              # lag / rolling / cyclical encoders
├── kafka/                 # predictions producer
├── clients/               # Analytics Service HTTP client
├── models/                # joblib artifacts (gitignored)
└── schemas.py             # pydantic models mirroring the OpenAPI spec
```
