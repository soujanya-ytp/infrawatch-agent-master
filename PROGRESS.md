# PROGRESS.md — {{AGENT_NAME}}

## Phase 1: Setup & Data    — ⬜ Not started
## Phase 2: Tools           — ⬜ Not started
## Phase 3: Agent           — ⬜ Not started
## Phase 4: Tests           — ⬜ Not started
## Phase 5: Docs & Check    — ⬜ Not started

---

## Phase 1 Checklist — Setup & Data

- [ ] Fill DOMAIN and AGENT_NAME in `config.py` and `CLAUDE.md`
- [ ] Rename agent class in `src/agent.py`
- [ ] Define `requirements.txt` (base already present — add domain deps)
- [ ] Copy `.env.example` → `.env`, add GROQ_API_KEY
- [ ] Create `data/{{primary_data_file}}.csv` — 25 realistic records
- [ ] Create `data/{{secondary_data_file}}.csv` — 25 records
- [ ] Verify data includes: demo entity, high-risk entity, threshold-trigger entity
- [ ] Update `conftest.py` SAMPLE_* constants with real domain data

---

## Phase 2 Checklist — Tools

- [ ] `retrieval_tool.py` — implement `run()` and `_verify_output()`
- [ ] `processing_tool.py` — implement `run()` and `_verify_output()`
- [ ] `execution_tool.py` — implement `run()`, `rollback()`, `_verify_output()`
- [ ] `verification_tool.py` — define `SPECS`, implement `run()`, `_verify_output()`
- [ ] `analysis_tool.py` — implement `run()`, `_compute_risk()`, `_apply_escalation()`, `_count_metric()`
- [ ] `reporting_tool.py` — implement `_build_single_summary()`, `_build_all_summary()`
- [ ] Set `REQUIRED_TOOLS` in `reporting_tool.py` to real class names
- [ ] Smoke test each tool manually (can use `python -c "..."`)

---

## Phase 3 Checklist — Agent

- [ ] Implement `_build_tools()` — 6 `@tool` wrappers
- [ ] Implement `_verify_layer2()` — domain keyword map
- [ ] Fill `DEMO_QUESTIONS` with 5 real domain questions
- [ ] Fill `REQUIRED_TOOLS` in `agent.py` to match class names
- [ ] Wire `_attempt_rollback()` to dispatch to execution tool's `rollback()`
- [ ] Test `python src/agent.py` starts without GROQ_API_KEY error
- [ ] Test `python src/agent.py --demo` runs all 5 questions

---

## Phase 4 Checklist — Tests

- [ ] Remove `@pytest.mark.skip` from all tests one-by-one as tools are implemented
- [ ] Fill in TODO test bodies in `test_tools.py`
- [ ] Fill in TODO test bodies in `test_agent.py`
- [ ] Run `pytest tests/ -v` — all tests pass
- [ ] Verify rollback test passes
- [ ] Verify Layer 3 pass/fail tests pass
- [ ] Verify `run_demo()` output schema test passes

---

## Phase 5 Checklist — Docs & Final Check

- [ ] Run `python src/agent.py --demo` with real GROQ_API_KEY
- [ ] Copy output from `output/report.json` into `data/expected_output.json`
- [ ] Update `README.md` use cases and example workflows with real domain content
- [ ] Update `docs/DATA_SCHEMA.md` with actual column names and types
- [ ] Confirm all 8 output schema fields present in report.json
- [ ] Run final `pytest tests/ -v` — all pass
- [ ] Rehearse demo script (5 min max):
  1. Show folder structure
  2. `pytest tests/ -v` → all green
  3. `python src/agent.py --demo` → show logs
  4. Open `output/report.json` → show all fields
  5. `python src/agent.py` → live Q&A if time allows
