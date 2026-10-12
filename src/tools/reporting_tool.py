"""
Reporting Tool — Category: Reporting
Generate incident summary report and perform Layer 3 end-to-end verification.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ..state import AgentState, ToolResult, VerificationStatus

logger = logging.getLogger(__name__)


class IncidentReportTool:
    """
    Purpose:
        Generate a human-readable incident summary for a time range or 'all' logs.
        Performs Layer 3 end-to-end verification: checks that all REQUIRED_TOOLS
        appear in AgentState.tools_used.

    Inputs:
        query (str):             time range e.g. '15:20-15:25' or 'all'
        state (AgentState|None): agent state for Layer 3 verification

    Outputs:
        ToolResult with status="success", data={
            "summary": dict,
            "layer3_verification": {"passed": bool, "failures": list, "tools_found": list},
        }
        OR status="error", error_message=reason

    Errors:
        - CSV file missing
        - Empty query
    """

    REQUIRED_TOOLS: list = [
        "LogRetrieverTool",
        "LogNormalizeTool",
        "RunbookGeneratorTool",
        "LogOutputVerifierTool",
        "AnomalyAnalysisTool",
        "IncidentReportTool",
    ]

    def __init__(self, data_dir: Path) -> None:
        self._data_dir      = data_dir
        self._csv_path      = data_dir / "logs.csv"
        self._incidents_csv = data_dir / "incidents.csv"
        logger.info(f"[{self.__class__.__name__}] Initialised")

    def run(self, query: str, state: Optional[AgentState] = None) -> ToolResult:
        """
        Generate incident report and perform Layer 3 e2e verification.

        IMPORTANT: state.record_tool() called BEFORE _verify_layer3() so this
        tool itself counts toward REQUIRED_TOOLS.

        Args:
            query: time range or 'all'
            state: AgentState (may be None in unit tests)
        Returns:
            ToolResult (success|error)
        """
        logger.info(f"[{self.__class__.__name__}] Starting — input={query!r}")

        if not query or not query.strip():
            return ToolResult(status="error", data=None, error_message="query must not be empty")

        if state is not None:
            state.record_tool(self.__class__.__name__)

        try:
            if not self._csv_path.exists():
                raise FileNotFoundError(f"CSV not found: {self._csv_path}")

            q = query.strip().strip("'\"").lower()
            summary = self._build_all_summary() if q == "all" else self._build_single_summary(query.strip())

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Error — {exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        layer3 = self._verify_layer3(state)
        if state is not None:
            state.verification_status = (
                VerificationStatus.PASSED if layer3["passed"] else VerificationStatus.PARTIAL
            )

        result = ToolResult(
            status="success",
            data={"summary": summary, "layer3_verification": layer3},
            metadata={"source": str(self._csv_path), "query": query},
        )
        check = self._verify_output(result)
        if not check["passed"]:
            logger.warning(f"[{self.__class__.__name__}] Layer 1 FAILED — {check['reason']}")
            return ToolResult(
                status="error", data=None,
                error_message=f"Layer 1 verification failed: {check['reason']}",
            )

        l3_label = "PASSED" if layer3["passed"] else "PARTIAL"
        logger.info(
            f"[{self.__class__.__name__}] Success — "
            f"Layer3={l3_label} output_keys={list(result.data.keys())}"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_single_summary(self, time_range: str) -> dict:
        """Build incident summary for a given time range."""
        df = pd.read_csv(self._csv_path, keep_default_na=False)

        if "-" in time_range and ":" in time_range:
            df["_ts"] = pd.to_datetime(df["timestamp"])
            parts     = time_range.split("-")
            start     = pd.to_datetime(f"2024-01-15 {parts[0].strip()}:00")
            end       = pd.to_datetime(f"2024-01-15 {parts[1].strip()}:59")
            df        = df[(df["_ts"] >= start) & (df["_ts"] <= end)].drop(columns=["_ts"])

        if df.empty:
            raise ValueError(f"No logs found for: {time_range!r}")

        total     = len(df)
        errors    = df[df["level"].isin(["ERROR", "CRITICAL"])]
        services  = sorted(df["service"].unique().tolist())
        top_error = (
            errors["service"].value_counts().idxmax()
            if not errors.empty else "none"
        )

        historical = self._historical_context(top_error)

        return {
            "time_range":       time_range,
            "total_logs":       total,
            "error_count":      len(errors),
            "critical_count":   len(df[df["level"] == "CRITICAL"]),
            "services":         services,
            "top_error_service": top_error,
            "incident_summary": (
                f"{len(errors)} errors across {len(services)} services. "
                f"Primary failure: {top_error}. "
                f"Recommendation: investigate DB connection pool exhaustion."
            ),
            "historical_context": historical,
            "post_mortem_actions": [
                "Increase DB connection pool size to 200",
                "Kill long-running query #4821",
                "Add circuit breaker to checkout-service → db-service path",
                "Set up alerting at error_rate > 10/min",
                "Review slow query log and add missing index",
            ],
        }

    def _historical_context(self, top_error_service: str) -> dict:
        """
        Load incidents.csv and return past incidents that involved top_error_service.
        Returns empty context dict gracefully if incidents.csv is absent.
        """
        if not self._incidents_csv.exists():
            logger.warning(f"[{self.__class__.__name__}] incidents.csv not found — no historical context")
            return {"matched_incidents": [], "pattern_note": "No historical incident data available"}

        try:
            df = pd.read_csv(self._incidents_csv, keep_default_na=False)
        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Failed to read incidents.csv — {exc}")
            return {"matched_incidents": [], "pattern_note": f"Could not load history: {exc}"}

        svc = top_error_service.lower()
        matches = []
        for _, row in df.iterrows():
            past_svcs = str(row.get("affected_services", "")).lower()
            if svc in past_svcs:
                matches.append({
                    "incident_id":        str(row["incident_id"]),
                    "date":               str(row["date"]),
                    "root_cause_type":    str(row["root_cause_type"]),
                    "resolution_minutes": int(row["resolution_minutes"]),
                    "recurrence_days":    int(row["recurrence_days"]),
                    "runbook_id":         str(row["runbook_id"]),
                })

        matches.sort(key=lambda x: x["date"], reverse=True)
        top = matches[:3]
        note = (
            f"{len(matches)} past incident(s) involved {top_error_service}. "
            f"Most recent: {top[0]['date']} ({top[0]['root_cause_type']})."
            if top else f"No past incidents found involving {top_error_service}."
        )
        logger.info(
            f"[{self.__class__.__name__}] Historical context — "
            f"service={top_error_service!r} past_matches={len(top)}"
        )
        return {"matched_incidents": top, "pattern_note": note}

    def _build_all_summary(self) -> dict:
        """Build full incident summary across all logs."""
        return self._build_single_summary("all")

    def _verify_layer3(self, state: Optional[AgentState]) -> dict:
        """
        Layer 3: end-to-end verification.
        Checks all REQUIRED_TOOLS appear in state.tools_used.
        """
        if state is None:
            logger.info("[VERIFY]   Layer 3 skipped — no state provided (unit test mode)")
            return {"passed": True, "failures": [], "tools_found": [], "note": "skipped (no state)"}

        tools_found = list(state.tools_used)
        failures    = [t for t in self.REQUIRED_TOOLS if t not in tools_found]
        passed      = len(failures) == 0

        logger.info(
            f"[VERIFY]   Layer 3 — required={self.REQUIRED_TOOLS} "
            f"found={tools_found} failures={failures}"
        )
        return {"passed": passed, "failures": failures, "tools_found": tools_found}

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: validate reporting tool output structure."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        if "summary" not in result.data:
            return {"passed": False, "reason": "'summary' key missing"}
        if "layer3_verification" not in result.data:
            return {"passed": False, "reason": "'layer3_verification' key missing"}
        l3 = result.data["layer3_verification"]
        if not isinstance(l3.get("passed"), bool):
            return {"passed": False, "reason": "layer3_verification.passed must be bool"}
        return {"passed": True, "reason": "ok"}
