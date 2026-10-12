# Data Schema — Log Analysis & Incident Response Agent

All data lives in `data/`. No external databases. No data generation scripts.

---

## logs.csv

25 records covering a real DB connection pool exhaustion incident on 2024-01-15,
from normal operation (15:20) through cascade failure (15:24).

| Column | Type | Description | Example |
|---|---|---|---|
| log_id | string | Unique log entry identifier | "LOG001" |
| timestamp | string | ISO datetime YYYY-MM-DD HH:MM:SS | "2024-01-15 15:22:08" |
| service | string | Originating microservice name | "db-service" |
| source | string | Log source type | "application" / "nginx" / "docker" |
| level | string | Severity: INFO / WARN / ERROR / CRITICAL | "CRITICAL" |
| error_code | integer | HTTP or domain error code | 500 |
| message | string | Human-readable log message | "DB connection pool exhausted: active=100 max=100" |
| request_id | string | Correlation ID across services | "REQ005" |
| host | string | Host that emitted the log | "db-node-01" |
| duration_ms | integer | Operation duration in milliseconds | 0 |

### Notes

- `keep_default_na=False` required on all `pd.read_csv()` calls — empty `error_code` and `message` fields must stay as empty strings, not NaN.
- RUNBOOK rows (`level=RUNBOOK`) are written by `RunbookGeneratorTool` and removed on rollback. Strip these rows when reading purely for analysis.
- `request_id` is the primary correlation key: same request_id across multiple services indicates a cross-service cascade.
- `duration_ms=0` on CRITICAL db-service rows indicates the pool was fully blocked (no query completed).

### Services

| Service | Host | Role |
|---|---|---|
| api-gateway | app-node-01 | Nginx reverse proxy, entry point |
| checkout-service | app-node-02 | Business logic, calls db-service |
| db-service | db-node-01 | PostgreSQL adapter, connection pool |
| cache-service | cache-node-01 | Redis adapter |
| auth-service | auth-node-01 | JWT validation |

### Incident Timeline

| Time | Level | Event |
|---|---|---|
| 15:20 | INFO | Normal traffic — pool at ~0% |
| 15:21 | WARN | Pool reaches 85%, slow query detected (1850ms) |
| 15:22:00 | ERROR | First timeout — checkout-service upstream unresponsive |
| 15:22:08 | CRITICAL | Pool exhausted 100/100, 47 requests waiting |
| 15:22:32 | CRITICAL | Pool still exhausted, 89 waiting, query still blocking |
| 15:23:00 | CRITICAL | Health check fails + 134 waiting, DB kills slow query |
| 15:24:00 | ERROR | Circuit breaker OPEN — api-gateway stops forwarding |

---

## expected_output.json

Reference output produced by a successful `python -m src.agent --demo` run.

```json
{
  "success": true,
  "result": "Demo complete — 5/5 questions answered",
  "verification_status": "passed",
  "steps_executed": ["observe", "reason", "plan", "act", "verify", "complete"],
  "tools_used": [
    "LogRetrieverTool",
    "LogNormalizeTool",
    "RunbookGeneratorTool",
    "LogOutputVerifierTool",
    "AnomalyAnalysisTool",
    "IncidentReportTool"
  ],
  "execution_time_seconds": 45.2,
  "errors": [],
  "metadata": {
    "retries": 0,
    "domain": "log-analysis"
  }
}
```

---

## Sample Data Design Notes

- 25 records — all in one service-cascade incident (realistic, not random)
- CRITICAL logs present → always triggers `risk_level=HIGH` regardless of score
- `request_id` linking: REQ004-REQ010 span multiple services → correlation test
- Pool exhaustion language: `"pool exhausted (100/100)"` in 3+ rows → pattern detection fires
- Slow query `query_id=4821` repeated in WARN + CRITICAL rows → root cause traceable
