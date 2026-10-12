"""
Integration tests for LogAnalysisAgent.
LLM (AgentExecutor) is mocked; real tool classes run against tmp CSVs.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent import LogAnalysisAgent
from src.state import VerificationStatus


@pytest.fixture
def agent(tmp_data_dir):
    """LogAnalysisAgent wired to tmp_data_dir (no real LLM needed)."""
    return LogAnalysisAgent(data_dir=tmp_data_dir)


@pytest.fixture
def mock_executor():
    """Patch AgentExecutor.invoke to return controlled output."""
    with patch("src.agent.AgentExecutor") as MockExec:
        instance = MagicMock()
        MockExec.return_value = instance
        yield instance


# ── Startup ───────────────────────────────────────────────────────────────────

def test_agent_initialises_without_api_key(tmp_data_dir):
    with patch("src.agent.config.GROQ_API_KEY", ""):
        agent = LogAnalysisAgent(data_dir=tmp_data_dir)
    assert agent._executor is None
    assert len(agent._tools) == 6


def test_agent_has_correct_tool_count(agent):
    assert len(agent._tools) == 6


# ── chat() without LLM ────────────────────────────────────────────────────────

def test_chat_returns_not_ready_without_key(tmp_data_dir):
    with patch("src.agent.config.GROQ_API_KEY", ""):
        agent_no_key = LogAnalysisAgent(data_dir=tmp_data_dir)
    response = agent_no_key.chat("detect anomalies")
    assert "not ready" in response.lower() or "GROQ_API_KEY" in response


# ── run_demo() schema ─────────────────────────────────────────────────────────

def test_run_demo_output_schema(tmp_data_dir, mock_executor):
    mock_executor.invoke.return_value = {"output": "Anomaly detected. Error spike at 15:22. DB pool exhausted."}
    agent  = LogAnalysisAgent(data_dir=tmp_data_dir)
    output = agent.run_demo()
    required = {
        "success", "result", "verification_status",
        "steps_executed", "tools_used", "execution_time_seconds",
        "errors", "metadata",
    }
    assert required.issubset(set(output.keys()))


def test_run_demo_saves_report_json(tmp_data_dir, mock_executor):
    import tempfile
    mock_executor.invoke.return_value = {"output": "Incident report generated successfully."}
    out_dir = Path(tempfile.mkdtemp())
    with patch("src.agent.config.OUTPUT_DIR", out_dir):
        agent  = LogAnalysisAgent(data_dir=tmp_data_dir)
        agent.run_demo()
    assert (out_dir / "report.json").exists()


def test_run_demo_metadata_has_domain(tmp_data_dir, mock_executor):
    mock_executor.invoke.return_value = {"output": "Root cause: DB connection pool exhausted."}
    agent  = LogAnalysisAgent(data_dir=tmp_data_dir)
    output = agent.run_demo()
    assert output["metadata"]["domain"] == "log-analysis"


def test_run_demo_execution_time_non_negative(tmp_data_dir, mock_executor):
    mock_executor.invoke.return_value = {"output": "Analysis complete."}
    agent  = LogAnalysisAgent(data_dir=tmp_data_dir)
    output = agent.run_demo()
    assert output["execution_time_seconds"] >= 0


# ── _verify_layer2() ──────────────────────────────────────────────────────────

def test_layer2_anomaly_keywords_pass(agent):
    assert agent._verify_layer2(
        "detect anomalies in logs",
        "Anomaly score: 94. Error spike detected at 15:22."
    ) is True


def test_layer2_root_cause_keywords_pass(agent):
    assert agent._verify_layer2(
        "what is the root cause",
        "Root cause: DB connection pool exhausted (100/100)"
    ) is True


def test_layer2_runbook_keywords_pass(agent):
    assert agent._verify_layer2(
        "generate runbook",
        "Runbook generated. Step 1: Kill slow query. Step 2: Increase pool."
    ) is True


def test_layer2_short_response_fails(agent):
    assert agent._verify_layer2("detect anomalies", "ok") is False


def test_layer2_empty_response_fails(agent):
    assert agent._verify_layer2("detect anomalies", "") is False


# ── Retry logic ───────────────────────────────────────────────────────────────

def test_retry_exhaustion_returns_failure_message(tmp_data_dir):
    agent = LogAnalysisAgent(data_dir=tmp_data_dir)
    agent._executor = MagicMock()
    agent._executor.invoke.side_effect = RuntimeError("LLM down")

    with patch("src.agent.config.MAX_RETRIES", 2), \
         patch("src.agent.time.sleep"):
        response = agent._invoke_with_retry("detect anomalies")

    assert "Unable to process" in response or "not ready" in response.lower()
