# STANDARDS.md — Shared Rules for All Hackathon Agents

These rules apply to EVERY agent regardless of domain. Do not modify.

---

## Code Standards

### Naming
- Tool classes: `{Domain}{Action}Tool` — e.g. `PatientRecordFetchTool`, `TradeExecutorTool`
- No abbreviations in class names — full descriptive names only

### Type Safety
- Type hints on ALL function signatures — parameters and return types
- Use `Optional[X]` not `X | None` for Python 3.10 compatibility

### Logging
- No `print()` anywhere — use `logging.getLogger(__name__)`
- Log format: `%(asctime)s  %(levelname)-8s  %(message)s`
- Log at start of every tool call: `[ToolName] Starting — input={value!r}`
- Log at success: `[ToolName] Success — output={value}`
- Log at error: `[ToolName] Error — input={value!r} error={exc}`
- Log every decision point in agent loop: `[OBSERVE]`, `[REASON]`, `[PLAN]`, `[ACT]`, `[VERIFY]`

### Error Handling
- Tools NEVER raise — catch all exceptions, return `ToolResult(status="error", ...)`
- Agent NEVER crashes on a single bad question — log and continue
- Retry with exponential backoff: `time.sleep(2 ** attempt)`, max 3 attempts

### Data Access
- Always use `keep_default_na=False` in `pd.read_csv()` — prevents "None" → NaN
- Never hardcode file paths — use `config.DATA_DIR / "file.csv"`
- Never write CSVs outside of Execution-category tools

---

## Architecture Standards

### Tool Output
Every tool MUST return a `ToolResult`:
```python
ToolResult(
    status="success",    # or "error"
    data=<payload>,
    metadata={"source": str, ...},
    error_message=None,  # or reason string on error
)
```

### Layer 1 Verification
Every tool MUST implement `_verify_output(result: ToolResult) -> dict`:
```python
{"passed": bool, "reason": str}
```
Call it before returning success, return error ToolResult if it fails.

### Layer 2 Verification
Agent MUST implement `_verify_layer2(question, response) -> bool`.
Domain-specific keyword checks — not just length check.

### Layer 3 Verification
Reporting tool MUST implement `_verify_layer3(state) -> dict`.
Record self in `state.tools_used` BEFORE calling `_verify_layer3`.

### Rollback
Execution tools MUST call `state.register_rollback(action, payload)` immediately after any CSV write.
Agent MUST implement `_attempt_rollback()` called when all retries exhausted.

### Output File
Agent MUST save `output/report.json` after every `run_demo()` call.
Output MUST match the standard schema (see CLAUDE.md).

---

## Testing Standards

- Unit tests: use `conftest.py` fixtures only — no real CSV reads
- Integration tests: mock ONLY at `AgentExecutor.invoke` — tool code runs real
- One happy-path test per tool
- One failure test per tool
- Rollback test for execution tool
- Layer 3 pass/fail tests for reporting tool
- `run_demo()` output schema test
- `run_demo()` saves report.json test

---

## Demo Standards

- `python src/agent.py --demo` must run to completion without any keyboard input
- All 5 demo questions send programmatically
- Agent produces `output/report.json` at end
- `pytest tests/ -v` must show all tests passing before demo
