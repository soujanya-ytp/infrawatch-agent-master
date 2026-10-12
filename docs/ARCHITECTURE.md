# Architecture — Log Analysis & Incident Response Agent

## Agent Loop

```
User Question
      │
      ▼
 ┌─────────┐
 │ OBSERVE │  Read question, load data context
 └────┬────┘
      │
      ▼
 ┌────────┐
 │ REASON │  LLM decides which tools to call and in what order
 └────┬───┘
      │
      ▼
 ┌──────┐
 │ PLAN │  Decompose task into ordered execution steps
 └──┬───┘
    │
    ▼
 ┌─────┐
 │ ACT │  Execute tools via LangChain AgentExecutor
 └──┬──┘    ┌─────────────────────────────────────────────────────┐
    │        │ Tool Chain                                          │
    │        │  1. RetrievalTool   → fetch raw record             │
    │        │  2. ProcessingTool  → normalise + enrich            │
    │        │  3. ExecutionTool   → write action (+ rollback reg) │
    │        │  4. VerificationTool→ validate intermediate result  │
    │        │  5. AnalysisTool    → compute risk / score          │
    │        │  6. ReportingTool   → format + Layer 3 verify       │
    │        └─────────────────────────────────────────────────────┘
    │
    ▼
 ┌────────┐
 │ VERIFY │  Layer 2 — agent checks response meets goal semantically
 └────┬───┘
      │
      ├── PASSED ──→ ┌──────────┐
      │               │ COMPLETE │ → save output/report.json
      │               └──────────┘
      │
      └── FAILED ──→ ┌─────────┐     ┌─────────────────────┐
                      │ ITERATE │ ──→ │ retry with backoff  │
                      └─────────┘     │ max 3 attempts      │
                                      │ 2^attempt seconds   │
                                      └──────────┬──────────┘
                                                 │ all retries exhausted
                                                 ▼
                                          ┌──────────┐
                                          │ ROLLBACK │ undo execution writes
                                          └──────────┘
                                                 │
                                                 ▼
                                          ┌────────┐
                                          │ FAILED │
                                          └────────┘
```

---

## 3-Layer Verification

### Layer 1 — Tool-Level (every tool)

```
tool.run(input)
    │
    ├── execute domain logic
    │
    ├── _verify_output(result)
    │       ├── check status != "error"
    │       ├── check required keys present
    │       ├── check type constraints
    │       └── domain-specific checks
    │
    ├── PASSED → return ToolResult(status="success", ...)
    └── FAILED → return ToolResult(status="error", error_message=...)
```

### Layer 2 — Agent-Level (agent.py)

```
response = _invoke_with_retry(question)
    │
    └── _verify_layer2(question, response)
            ├── check response length > minimum
            ├── match question intent to expected keywords in response
            └── PASSED → VerificationStatus.PASSED
                FAILED → VerificationStatus.PARTIAL + record ITERATE step
```

### Layer 3 — End-to-End (reporting_tool.py)

```
reporting_tool.run(query, state)
    │
    ├── state.record_tool(self.__class__.__name__)   ← BEFORE verify
    │
    └── _verify_layer3(state)
            ├── check each name in REQUIRED_TOOLS is in state.tools_used
            ├── PASSED → {"passed": True, "failures": []}
            └── FAILED → {"passed": False, "failures": [missing tools]}
```

---

## Rollback Flow

```
ExecutionTool.run(params, state)
    │
    ├── write row to CSV
    │
    ├── state.register_rollback("csv_row_appended", {"file": ..., "row_id": ...})
    │
    └── return ToolResult(success)

--- if downstream steps fail and all retries exhausted ---

agent._attempt_rollback()
    │
    └── for entry in reversed(state.get_rollback_log()):
            ExecutionTool.rollback(entry["payload"])
                └── re-read CSV, drop row_id, write back
```

---

## State Management

```
AgentState
├── domain               str              config.DOMAIN
├── steps_executed       list[str]        appended by record_step()
├── tools_used           list[str]        appended by record_tool()
├── errors               list[str]        appended by add_error()
├── retries              int              incremented by _invoke_with_retry()
├── verification_status  VerificationStatus  set by agent + Layer 3
├── _start               float            time.time() at construction
└── _rollback_log        list[dict]       appended by register_rollback()

Output schema (to_output_dict / save_output → output/report.json):
{
  "success": bool,
  "result": str,
  "verification_status": "passed|failed|partial|pending",
  "steps_executed": [...],
  "tools_used": [...],
  "execution_time_seconds": float,
  "errors": [...],
  "metadata": {"retries": int, "domain": str}
}
```

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│         Log Analysis & Incident Response Agent           │
│                                                          │
│  ┌──────────┐     ┌───────────────────────────────────┐ │
│  │  CLI /   │────▶│           LogAnalysisAgent         │ │
│  │  Demo    │     │  run_cli()  │  run_demo()          │ │
│  └──────────┘     └─────────────────────────────────── ┘ │
│                            │                             │
│                   ┌────────▼────────┐                    │
│                   │  AgentExecutor  │ (LangChain ReAct)  │
│                   │  + LLM (Groq)   │                    │
│                   └────────┬────────┘                    │
│                            │ dispatches                  │
│          ┌─────────────────┼─────────────────────┐       │
│          ▼                 ▼                     ▼       │
│   ┌────────────┐  ┌──────────────┐  ┌──────────────┐    │
│   │ Retrieval  │  │  Processing  │  │  Execution   │    │
│   │    Tool    │  │    Tool      │  │    Tool      │    │
│   └────────────┘  └──────────────┘  └──────┬───────┘    │
│                                            │ rollback   │
│          ┌─────────────────────────────────┤            │
│          ▼                 ▼               ▼            │
│   ┌────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │Verification│  │   Analysis   │  │  Reporting   │   │
│   │    Tool    │  │    Tool      │  │  Tool + L3   │   │
│   └────────────┘  └──────────────┘  └──────────────┘   │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │                  AgentState                      │  │
│   │  steps_executed │ tools_used │ _rollback_log    │  │
│   └──────────────────────────────────────────────────┘  │
│                                                          │
│   Data: data/*.csv                                       │
│   Output: output/report.json                             │
└──────────────────────────────────────────────────────────┘
```
