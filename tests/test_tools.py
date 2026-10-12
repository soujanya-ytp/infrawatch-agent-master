"""
Unit tests for all 6 tools.
Pattern: one happy-path test + one failure test per tool.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.tools.retrieval_tool    import LogRetrieverTool
from src.tools.processing_tool   import LogNormalizeTool
from src.tools.execution_tool    import RunbookGeneratorTool
from src.tools.verification_tool import LogOutputVerifierTool
from src.tools.analysis_tool     import AnomalyAnalysisTool
from src.tools.reporting_tool    import IncidentReportTool
from src.state import AgentState


# ── LogRetrieverTool ──────────────────────────────────────────────────────────

class TestLogRetrieverTool:

    def test_fetch_all_success(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        assert res.data["count"] == 3
        assert isinstance(res.data["logs"], list)

    def test_fetch_by_log_id_success(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("LOG001")
        assert res.status == "success"
        assert res.data["count"] == 1
        assert res.data["logs"][0]["log_id"] == "LOG001"

    def test_fetch_by_service_success(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("db-service")
        assert res.status == "success"
        assert res.data["logs"][0]["service"] == "db-service"

    def test_fetch_by_time_range_success(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("15:20-15:25")
        assert res.status == "success"
        assert res.data["count"] >= 1

    def test_fetch_nonexistent_returns_error(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("nonexistent-service")
        assert res.status == "error"
        assert res.error_message is not None

    def test_fetch_empty_query_returns_error(self, tmp_data_dir):
        tool = LogRetrieverTool(data_dir=tmp_data_dir)
        res  = tool.run("")
        assert res.status == "error"


# ── LogNormalizeTool ──────────────────────────────────────────────────────────

class TestLogNormalizeTool:

    def test_normalize_success(self, tmp_data_dir, sample_logs_payload):
        tool = LogNormalizeTool(data_dir=tmp_data_dir)
        res  = tool.run(sample_logs_payload)
        assert res.status == "success"
        assert res.data["count"] == 3
        assert "error_category" in res.data["logs"][0]
        assert "time_bucket"    in res.data["logs"][0]
        assert "is_error"       in res.data["logs"][0]

    def test_normalize_classifies_pool_exhausted(self, tmp_data_dir, sample_high_risk_record):
        tool    = LogNormalizeTool(data_dir=tmp_data_dir)
        payload = {"logs": [sample_high_risk_record], "count": 1}
        res     = tool.run(payload)
        assert res.status == "success"
        enriched = res.data["logs"][0]
        assert enriched["error_category"] == "pool_exhausted"
        assert enriched["is_error"] is True

    def test_normalize_classifies_info_as_none(self, tmp_data_dir, sample_primary_record):
        tool    = LogNormalizeTool(data_dir=tmp_data_dir)
        payload = {"logs": [sample_primary_record], "count": 1}
        res     = tool.run(payload)
        assert res.status == "success"
        assert res.data["logs"][0]["error_category"] == "none"
        assert res.data["logs"][0]["is_error"] is False

    def test_normalize_empty_logs_returns_error(self, tmp_data_dir):
        tool = LogNormalizeTool(data_dir=tmp_data_dir)
        res  = tool.run({"logs": [], "count": 0})
        assert res.status == "error"

    def test_normalize_missing_logs_key_returns_error(self, tmp_data_dir):
        tool = LogNormalizeTool(data_dir=tmp_data_dir)
        res  = tool.run({"data": "bad"})
        assert res.status == "error"


# ── RunbookGeneratorTool ──────────────────────────────────────────────────────

class TestRunbookGeneratorTool:

    def test_generate_runbook_success(self, tmp_data_dir):
        tool = RunbookGeneratorTool(data_dir=tmp_data_dir)
        res  = tool.run(
            root_cause="DB connection pool exhausted",
            services="api-gateway,checkout-service,db-service",
        )
        assert res.status == "success"
        assert res.data["runbook_id"].startswith("RB")
        assert len(res.data["fix_steps"]) > 0
        assert res.data["root_cause"] == "DB connection pool exhausted"

    def test_generate_runbook_registers_rollback(self, tmp_data_dir):
        tool  = RunbookGeneratorTool(data_dir=tmp_data_dir)
        state = AgentState(domain="log-analysis")
        res   = tool.run(root_cause="DB connection pool exhausted", state=state)
        assert res.status == "success"
        log = state.get_rollback_log()
        assert len(log) == 1
        assert log[0]["action"] == "csv_row_appended"
        assert log[0]["payload"]["row_id"] == res.data["runbook_id"]

    def test_rollback_removes_row(self, tmp_data_dir):
        import pandas as pd
        tool  = RunbookGeneratorTool(data_dir=tmp_data_dir)
        state = AgentState(domain="log-analysis")
        res   = tool.run(root_cause="DB connection pool exhausted", state=state)
        rb_id = res.data["runbook_id"]

        tool.rollback(state.get_rollback_log()[0]["payload"])
        df = pd.read_csv(tmp_data_dir / "logs.csv", keep_default_na=False)
        assert rb_id not in df["log_id"].values

    def test_empty_root_cause_returns_error(self, tmp_data_dir):
        tool = RunbookGeneratorTool(data_dir=tmp_data_dir)
        res  = tool.run(root_cause="")
        assert res.status == "error"


# ── LogOutputVerifierTool ─────────────────────────────────────────────────────

class TestLogOutputVerifierTool:

    def test_verify_log_record_passes(self, tmp_data_dir, sample_primary_record):
        tool = LogOutputVerifierTool(data_dir=tmp_data_dir)
        res  = tool.run(sample_primary_record, "log_record")
        assert res.status == "success"
        assert res.data["passed"] is True
        assert res.data["checks_run"] > 0

    def test_verify_anomaly_analysis_passes(self, tmp_data_dir):
        tool   = LogOutputVerifierTool(data_dir=tmp_data_dir)
        result = {
            "anomaly_score":          94,
            "risk_level":             "HIGH",
            "root_cause":             "DB connection pool exhausted",
            "affected_services":      ["db-service"],
            "spike_detected_at":      "2024-01-15 15:22:00",
            "matched_past_incidents": [],
            "historical_match_count": 0,
        }
        res = tool.run(result, "anomaly_analysis")
        assert res.status == "success"
        assert res.data["passed"] is True

    def test_verify_missing_key_fails(self, tmp_data_dir):
        tool   = LogOutputVerifierTool(data_dir=tmp_data_dir)
        result = {"log_id": "LOG001"}  # missing required keys
        res    = tool.run(result, "log_record")
        assert res.status == "success"
        assert res.data["passed"] is False
        assert len(res.data["failures"]) > 0

    def test_verify_unknown_spec_returns_error(self, tmp_data_dir):
        tool = LogOutputVerifierTool(data_dir=tmp_data_dir)
        res  = tool.run({}, "nonexistent_spec")
        assert res.status == "error"

    def test_verify_none_result_returns_error(self, tmp_data_dir):
        tool = LogOutputVerifierTool(data_dir=tmp_data_dir)
        res  = tool.run(None, "log_record")
        assert res.status == "error"

    def test_verify_json_string_input(self, tmp_data_dir, sample_primary_record):
        import json
        tool = LogOutputVerifierTool(data_dir=tmp_data_dir)
        res  = tool.run(json.dumps(sample_primary_record), "log_record")
        assert res.status == "success"
        assert res.data["passed"] is True


# ── AnomalyAnalysisTool ───────────────────────────────────────────────────────

class TestAnomalyAnalysisTool:

    def test_analyse_all_success(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        d = res.data
        assert d["risk_level"] in ("HIGH", "MEDIUM", "LOW")
        assert 0 <= d["anomaly_score"] <= 100
        assert isinstance(d["reasons"], list)
        assert "spike_detected_at" in d

    def test_analyse_detects_critical_as_high_risk(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        assert res.data["risk_level"] == "HIGH"
        assert res.data["escalated"] is True

    def test_analyse_identifies_db_root_cause(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        assert "db" in res.data["root_cause_service"].lower() or \
               "pool" in res.data["root_cause"].lower()

    def test_analyse_empty_query_returns_error(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("")
        assert res.status == "error"

    def test_analyse_no_matching_service_returns_error(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("nonexistent-service")
        assert res.status == "error"

    def test_analyse_returns_matched_past_incidents(self, tmp_data_dir):
        tool = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        assert "matched_past_incidents" in res.data
        assert "historical_match_count" in res.data
        assert isinstance(res.data["matched_past_incidents"], list)
        assert isinstance(res.data["historical_match_count"], int)

    def test_analyse_matches_pool_exhausted_incidents(self, tmp_data_dir):
        tool    = AnomalyAnalysisTool(data_dir=tmp_data_dir)
        res     = tool.run("all")
        matches = res.data["matched_past_incidents"]
        assert res.data["historical_match_count"] >= 1
        types   = [m["root_cause_type"] for m in matches]
        assert "pool_exhausted" in types

    def test_analyse_no_incidents_csv_still_succeeds(self, tmp_path):
        primary_path = tmp_path / "logs.csv"
        from tests.conftest import SAMPLE_PRIMARY_RECORDS, _write_csv
        _write_csv(primary_path, SAMPLE_PRIMARY_RECORDS)
        tool = AnomalyAnalysisTool(data_dir=tmp_path)
        res  = tool.run("all")
        assert res.status == "success"
        assert res.data["matched_past_incidents"] == []
        assert res.data["historical_match_count"] == 0


# ── IncidentReportTool ────────────────────────────────────────────────────────

class TestIncidentReportTool:

    def test_report_all_success(self, tmp_data_dir):
        tool = IncidentReportTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        assert "summary" in res.data
        assert "layer3_verification" in res.data

    def test_report_layer3_skipped_without_state(self, tmp_data_dir):
        tool = IncidentReportTool(data_dir=tmp_data_dir)
        res  = tool.run("all", state=None)
        assert res.status == "success"
        l3 = res.data["layer3_verification"]
        assert l3["passed"] is True
        assert "skipped" in l3.get("note", "")

    def test_report_layer3_fails_with_empty_state(self, tmp_data_dir):
        tool  = IncidentReportTool(data_dir=tmp_data_dir)
        state = AgentState(domain="log-analysis")
        state.record_tool("IncidentReportTool")  # only this tool recorded
        res   = tool.run("all", state=state)
        assert res.status == "success"
        l3 = res.data["layer3_verification"]
        assert l3["passed"] is False
        assert len(l3["failures"]) > 0

    def test_report_layer3_passes_with_all_tools(self, tmp_data_dir):
        tool  = IncidentReportTool(data_dir=tmp_data_dir)
        state = AgentState(domain="log-analysis")
        for t in IncidentReportTool.REQUIRED_TOOLS:
            state.record_tool(t)
        res   = tool.run("all", state=state)
        assert res.status == "success"
        assert res.data["layer3_verification"]["passed"] is True

    def test_report_empty_query_returns_error(self, tmp_data_dir):
        tool = IncidentReportTool(data_dir=tmp_data_dir)
        res  = tool.run("")
        assert res.status == "error"

    def test_report_includes_historical_context(self, tmp_data_dir):
        tool = IncidentReportTool(data_dir=tmp_data_dir)
        res  = tool.run("all")
        assert res.status == "success"
        summary = res.data["summary"]
        assert "historical_context" in summary
        hctx = summary["historical_context"]
        assert "matched_incidents" in hctx
        assert "pattern_note" in hctx
        assert isinstance(hctx["matched_incidents"], list)

    def test_report_historical_context_no_incidents_csv(self, tmp_path):
        from tests.conftest import SAMPLE_PRIMARY_RECORDS, _write_csv
        _write_csv(tmp_path / "logs.csv", SAMPLE_PRIMARY_RECORDS)
        tool = IncidentReportTool(data_dir=tmp_path)
        res  = tool.run("all")
        assert res.status == "success"
        hctx = res.data["summary"]["historical_context"]
        assert hctx["matched_incidents"] == []
