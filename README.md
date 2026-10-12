# Log Analysis & Incident Response Agent

Autonomous agent for the YottaFlex Agentic Orchestration Hackathon.
Domain: **log-analysis** | Framework: LangChain + Groq (llama-3.1-8b-instant)

---

## Quick Start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY and set GROQ_MODEL=llama-3.1-8b-instant
python -m src.agent --demo    # automated demo (no manual input)
python -m src.agent           # interactive CLI
pytest tests/ -v              # run all tests
```

---

## Purpose

Ingests logs from Docker, Nginx, and application sources, detects anomalies and
error spikes in a batch time window, correlates failures across microservices,
identifies the root cause, predicts recurrence, and auto-generates an incident
response runbook — cutting MTTR dramatically.

---

## Use Cases

1. **Anomaly detection** — detect error rate spikes from 2/min to 180/min in a 5-minute log window
2. **Root cause analysis** — trace a cascade (api-gateway → checkout-service → db-service) to its origin
3. **Service correlation** — identify which services share failing request_ids
4. **Recurrence prediction** — estimate minutes until next occurrence if unresolved
5. **Runbook generation** — auto-generate step-by-step fix commands with rollback steps

---

## Tool Overview

| Tool | Category | Input | Output |
|---|---|---|---|
| `LogRetrieverTool` | Retrieval | log_id / service / time range / 'all' | logs list |
| `LogNormalizeTool` | Processing | logs dict | enriched logs + patterns |
| `RunbookGeneratorTool` | Execution | root_cause + services | runbook + rollback |
| `LogOutputVerifierTool` | Verification | result + spec_name | pass/fail + failures |
| `AnomalyAnalysisTool` | Analysis | time range / service | anomaly score + root cause |
| `IncidentReportTool` | Reporting | time range / 'all' | full report + Layer 3 |

---

## Data Sources

| File | Rows | Description |
|---|---|---|
| `data/logs.csv` | 25 | Incident timeline 15:20–15:24, DB pool exhaustion cascade |

All data is local CSV — no external APIs, no cloud dependencies.

---

## Example Workflows

### 1. Detect anomalies
```
> Analyze logs from 15:20-15:25 and detect any anomalies or error spikes

Response: Anomaly score 94 (CRITICAL). Error rate spiked from 2/min to 18/min
at 15:22. Repeating patterns: DB connection pool exhausted, connection timeout.
```

### 2. Root cause
```
> What is the root cause of the error spike at 15:22?

Response: Root cause — db-service: DB connection pool exhausted (100/100)
triggered by slow query_id=4821 in checkout-service.
```

### 3. Service correlation
```
> Which services are affected and how are they correlated?

Response: api-gateway → checkout-service → db-service → cache-service.
Correlation via shared request_ids REQ004-REQ010.
```

### 4. Generate runbook
```
> Generate an incident runbook for DB connection pool exhaustion

Response: Runbook RB001 generated:
  1. Kill slow query: KILL QUERY 4821;
  2. Increase pool: SET global max_connections=200;
  3. Restart checkout-service
  4. Add circuit breaker
  5. Monitor error rate
```

### 5. Full incident report
```
> Generate a full incident report for time range 15:20-15:25

Response: Incident report — 17 errors across 5 services. Layer 3: PASSED.
Post-mortem: increase pool, add circuit breaker, add slow query alerting.
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full agent loop diagram,
3-layer verification flow, rollback sequence, and component diagram.

**Loop:** Observe → Reason → Plan → Act → Verify → Iterate

**Verification:**
- Layer 1: each tool validates its own output (`_verify_output`)
- Layer 2: agent checks response satisfies question intent (`_verify_layer2`)
- Layer 3: reporting tool confirms all 6 required tools ran (`_verify_layer3`)

**Retry:** exponential backoff, max 3 retries, rollback on exhaustion.

---

## Testing

```bash
pytest tests/ -v              # all tests
pytest tests/test_tools.py -v # tool unit tests only
pytest tests/test_agent.py -v # integration tests only
```

**44 tests — all passing.**

---

## Output

After `--demo` run, `output/report.json` contains:

```json
{
  "success": true,
  "result": "Demo complete — 5/5 questions answered",
  "verification_status": "passed",
  "steps_executed": ["observe", "reason", "plan", "act", "verify", "complete"],
  "tools_used": ["LogRetrieverTool", "LogNormalizeTool", "RunbookGeneratorTool",
                 "LogOutputVerifierTool", "AnomalyAnalysisTool", "IncidentReportTool"],
  "execution_time_seconds": 45.2,
  "errors": [],
  "metadata": {"retries": 0, "domain": "log-analysis"}
}
```

---

## Project Structure

```
agent-loganalysis/
├── src/agent.py              ← LogAnalysisAgent, orchestration loop, run_demo()
├── src/config.py             ← domain constants, anomaly thresholds
├── src/state.py              ← AgentState, ToolResult
├── src/tools/                ← 6 tool files (all categories)
├── tests/                    ← 44 unit + integration tests
├── data/logs.csv             ← 25-row incident timeline
├── data/expected_output.json ← reference output from real demo run
├── output/                   ← report.json (gitignored)
└── docs/                     ← ARCHITECTURE.md, DATA_SCHEMA.md
```
