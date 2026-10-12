# CLAUDE.md — Agentic Orchestration Hackathon
# Top section: common across ALL agents — do not change.
# Only update the DOMAIN CONTEXT section per agent.

---

## DOMAIN CONTEXT
# ─── UPDATE ONLY THIS SECTION per domain ───

DOMAIN         : log-analysis
AGENT_NAME     : Log Analysis & Incident Response Agent
CLIENT_CONTEXT : Production microservices environment with Docker, Nginx, and
                 application logs. Incident on 2024-01-15 involving DB connection
                 pool exhaustion cascading across api-gateway, checkout-service,
                 db-service, and cache-service.

PRIMARY_USE_CASE:
  Answer natural language questions about log incidents, anomalies, root causes,
  and incident runbooks via a CLI chat loop. Agent decides which tools to call
  based on the question — no manual tool selection needed.

DEMO_SCENARIO:
  User asks 5 questions about a DB connection pool exhaustion incident in sequence:
  1. "Analyze logs from 15:20-15:25 and detect any anomalies or error spikes"
  2. "What is the root cause of the error spike at 15:22?"
  3. "Which services are affected and how are they correlated?"
  4. "Generate an incident runbook for DB connection pool exhaustion affecting api-gateway,checkout-service,db-service"
  5. "Generate a full incident report for time range 15:20-15:25"

# ─────────────────────────────────────────────────────────────

---

## PROJECT CONTEXT

This is a hackathon project for an internal YottaFlex hackathon.
Theme: Autonomous agents with intelligent orchestration across diverse domains.
Each team builds ONE independent agent for ONE domain.

---

## TECH STACK

- Language   : Python 3.10+
- Framework  : LangChain (AgentExecutor with tools)
- LLM        : Groq API — model: llama-3.1-8b-instant
- Data       : Local CSV files only (no external APIs, no cloud, no paid services)
- DB         : No database — flat CSV files in data/
- Testing    : pytest
- Logging    : Python standard logging module

---

## STRICT CONSTRAINTS (from hackathon brief — do not violate)

1. NO paid APIs beyond Groq free tier — everything else runs locally
2. NO AWS / GCP / Azure credentials
3. NO external cloud dependencies
4. Data must come from CSV / JSON files in data/
5. All tools must be runnable on a local development machine
6. Max 2-3 retries per execution step before escalation
7. Every tool must return { status, data, metadata } structure (ToolResult in state.py)
8. All tools must have docstrings: purpose, inputs, outputs, error conditions
9. Comprehensive logging at every decision point — no print() anywhere
10. No data generation scripts — sample data provided directly in data/

---

## REQUIRED ARCHITECTURE PATTERN (from brief — must follow exactly)

### Agent Loop
```
Observe → Reason → Plan → Act → Verify → Iterate
```

### 3-Layer Verification (ALL 3 must be implemented)
- Layer 1 — Tool-level   : each tool validates its own output before returning
- Layer 2 — Agent-level  : agent checks if step result semantically meets the goal
- Layer 3 — End-to-end   : final output reconciled against original task specification

### Retry Logic
- Max retries : 3
- Strategy    : exponential backoff (2^retry seconds)
- On failure  : log error, retry, then escalate with failure status

### Rollback
- Execution tools register rollback entries in AgentState immediately after writes
- On all-retry failure, agent._attempt_rollback() undoes entries in reverse order

---

## FOLDER STRUCTURE

```
agent-loganalysis/
├── CLAUDE.md                        ← this file
├── STANDARDS.md                     ← rules every agent follows
├── SETUP.md                         ← step-by-step local setup
├── PROGRESS.md                      ← phase tracking
├── README.md                        ← overview, tools, data sources, testing
├── requirements.txt                 ← pinned dependencies
├── .env.example                     ← env variable template (no real values)
├── .gitignore                       ← venv, .env, pycache, output/ excluded
│
├── src/
│   ├── __init__.py
│   ├── agent.py                     ← AgentExecutor + run_cli() + run_demo()
│   ├── config.py                    ← loads .env, typed config constants
│   ├── llm_provider.py              ← Groq via LangChain abstraction
│   ├── state.py                     ← AgentState, AgentStep, ToolResult
│   └── tools/
│       ├── __init__.py
│       ├── retrieval_tool.py        ← Category: Retrieval
│       ├── processing_tool.py       ← Category: Processing
│       ├── execution_tool.py        ← Category: Execution  (+ rollback)
│       ├── verification_tool.py     ← Category: Verification  ← REQUIRED
│       ├── analysis_tool.py         ← Category: Analysis
│       └── reporting_tool.py        ← Category: Reporting  (+ Layer 3)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  ← shared pytest fixtures, mock data
│   ├── test_tools.py                ← unit tests for all 6 tools
│   └── test_agent.py                ← integration tests (LLM mocked only)
│
├── data/
│   ├── logs.csv                     ← 25-row incident timeline (primary)
│   └── expected_output.json         ← what a correct demo run produces
│
├── output/                          ← gitignored; report.json written here
│
└── docs/
    ├── ARCHITECTURE.md              ← loop flow, tool sequence, verification layers
    └── DATA_SCHEMA.md               ← column definitions for every CSV
```

---

## TOOL OVERVIEW (6 tools — all categories required by brief)

| File | Class Name | Category | Input | Output |
|---|---|---|---|---|
| retrieval_tool.py   | LogRetrieverTool         | Retrieval     | log_id / service / time range | logs list |
| processing_tool.py  | LogNormalizeTool         | Processing    | logs dict                     | enriched logs + patterns |
| execution_tool.py   | RunbookGeneratorTool     | Execution     | root_cause + services         | runbook + rollback |
| verification_tool.py| LogOutputVerifierTool    | Verification  | result + spec_name            | pass/fail + failures |
| analysis_tool.py    | AnomalyAnalysisTool      | Analysis      | time range / service          | anomaly score + root cause |
| reporting_tool.py   | IncidentReportTool       | Reporting     | time range / 'all'            | full report + Layer 3 |

---

## DATA SCHEMA

### logs.csv
log_id (string), timestamp (datetime), service (string), source (string),
level (INFO|WARN|ERROR|CRITICAL|RUNBOOK), error_code (int), message (string),
request_id (string), host (string), duration_ms (int)

No secondary CSV — single log file contains all incident data.

---

## STANDARD OUTPUT SCHEMA (required by brief)

```json
{
  "success": true,
  "result": "<human readable summary>",
  "verification_status": "passed | failed | partial",
  "steps_executed": ["observe", "reason", "plan", "act", "verify", "complete"],
  "tools_used": ["Tool1", "Tool2"],
  "execution_time_seconds": 2.34,
  "errors": [],
  "metadata": {
    "retries": 0,
    "domain": "log-analysis"
  }
}
```

---

## STATE MANAGEMENT (state.py)

- `AgentState`         — central object passed through entire loop
- `AgentStep`          — enum: IDLE, OBSERVE, REASON, PLAN, ACT, VERIFY, ITERATE, COMPLETE, FAILED
- `VerificationStatus` — enum: PENDING, PASSED, FAILED, PARTIAL
- `ToolResult`         — { status, data, metadata, error_message }

Every tool receives data as input and returns a ToolResult.
No tool modifies AgentState directly — only agent.py does.
Execution tools register rollback entries via state.register_rollback().

---

## HOW TO RUN

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add GROQ_API_KEY to .env

# Interactive CLI
python src/agent.py

# Automated demo (no manual input — required by brief)
python src/agent.py --demo

# Run tests
pytest tests/ -v
```

---

## TESTING REQUIREMENTS

### test_tools.py
- One happy path test per tool (6 tools × 1 = 6 minimum)
- One failure test per tool (6 tools × 1 = 6 minimum)
- Rollback test for execution tool
- Layer 3 pass/fail tests for reporting tool
- Use conftest.py fixtures — never read real CSVs in unit tests

### test_agent.py
- Mock ONLY at the LLM boundary (AgentExecutor.invoke)
- Real tool classes run against tmp CSV files
- Test run_demo() produces correct output schema
- Test run_demo() saves report.json
- 3+ natural language question scenarios
- Entity not found error case
- Retry logic test

---

## EVALUATION CRITERIA (optimise for these)

| Criterion | Weight |
|---|---|
| Architecture | 25% |
| Tool Implementation | 25% |
| Verification | 20% |
| Code Quality | 15% |
| Demo | 15% |

---

## DEMO SCRIPT (for presentation)

1. Show folder structure
2. Run `python src/agent.py --demo` — automated run, no typing required
3. Point out each log line maps to Observe/Reason/Plan/Act/Verify
4. Show output/report.json — verify all 8 required fields present
5. Run `pytest tests/ -v` — show all passing
6. Run `python src/agent.py` — live CLI for Q&A if time allows
