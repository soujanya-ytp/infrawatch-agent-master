"""
Execution Tool — Category: Execution
Generate and persist an incident runbook entry to logs.csv. Registers rollback.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ..state import AgentState, ToolResult

logger = logging.getLogger(__name__)


def _next_runbook_id(df: pd.DataFrame) -> str:
    existing = [r for r in df["log_id"].tolist() if str(r).startswith("RB")]
    return f"RB{str(len(existing) + 1).zfill(3)}"


def _build_fix_steps(root_cause: str) -> list:
    rc = root_cause.lower()
    if "pool" in rc or "connection" in rc:
        return [
            "1. Kill slow query: KILL QUERY 4821;",
            "2. Increase DB connection pool: SET global max_connections=200;",
            "3. Restart checkout-service to flush stale connection handles",
            "4. Add circuit breaker between checkout-service and db-service",
            "5. Monitor error rate: watch -n5 'ss -s | grep ESTAB'",
        ]
    if "memory" in rc or "cpu" in rc:
        return [
            "1. Identify resource hog: top -bn1 | head -20",
            "2. Restart offending process with resource limits",
            "3. Scale horizontally if sustained load",
        ]
    return [
        "1. Identify root cause service from logs",
        "2. Restart affected service",
        "3. Verify error rate returns to baseline (<5 errors/min)",
    ]


class RunbookGeneratorTool:
    """
    Purpose:
        Generate a structured incident runbook based on root cause analysis and
        persist it as a RUNBOOK-level log entry in logs.csv.
        Registers rollback metadata in AgentState immediately after writing.

    Inputs:
        root_cause   (str): primary failure cause e.g. 'DB connection pool exhausted'
        services     (str): comma-separated affected services
        incident_id  (str): identifier for this incident e.g. 'INC-20240115-1522'
        state (AgentState | None): agent state for rollback registration

    Outputs:
        ToolResult with status="success", data={
            "runbook_id": str,
            "incident_id": str,
            "root_cause": str,
            "affected_services": list[str],
            "fix_steps": list[str],
            "rollback_steps": list[str],
            "estimated_resolution_minutes": int,
            "escalation_contact": str,
        }
        OR status="error", error_message=reason

    Errors:
        - root_cause is empty
        - CSV file missing at data_dir/logs.csv
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._csv_path = data_dir / "logs.csv"
        logger.info(f"[{self.__class__.__name__}] Initialised — csv={self._csv_path}")

    def run(
        self,
        root_cause: str,
        services: str = "unknown",
        incident_id: str = "INC-001",
        state: Optional[AgentState] = None,
    ) -> ToolResult:
        """
        Generate and persist a runbook for the given root cause.

        Args:
            root_cause:  primary failure cause description
            services:    comma-separated affected service names
            incident_id: incident identifier for tracking
            state:       AgentState for rollback registration (may be None in tests)
        Returns:
            ToolResult (success|error)
        """
        logger.info(
            f"[{self.__class__.__name__}] Starting — "
            f"root_cause={root_cause!r} services={services!r}"
        )

        if not root_cause or not root_cause.strip():
            return ToolResult(status="error", data=None, error_message="root_cause must not be empty")

        try:
            if not self._csv_path.exists():
                raise FileNotFoundError(f"CSV not found: {self._csv_path}")

            df    = pd.read_csv(self._csv_path, keep_default_na=False)
            rb_id = _next_runbook_id(df)

            affected      = [s.strip() for s in services.split(",") if s.strip()]
            fix_steps     = _build_fix_steps(root_cause)
            rollback_steps = [
                "1. Revert max_connections: SET global max_connections=100;",
                "2. Remove circuit breaker config",
                "3. Restart services in reverse order",
            ]

            new_row = {
                "log_id":      rb_id,
                "timestamp":   "2024-01-15 15:25:00",
                "service":     "incident-response",
                "source":      "runbook",
                "level":       "RUNBOOK",
                "error_code":  "",
                "message":     f"Runbook generated: {root_cause[:80]}",
                "request_id":  incident_id,
                "host":        "orchestrator",
                "duration_ms": 0,
            }

            df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df_new.to_csv(self._csv_path, index=False)

            if state is not None:
                state.register_rollback(
                    action="csv_row_appended",
                    payload={"file": str(self._csv_path), "row_id": rb_id, "id_column": "log_id"},
                )

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Error — {exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        result = ToolResult(
            status="success",
            data={
                "runbook_id":                   rb_id,
                "incident_id":                  incident_id,
                "root_cause":                   root_cause.strip(),
                "affected_services":            affected,
                "fix_steps":                    fix_steps,
                "rollback_steps":               rollback_steps,
                "estimated_resolution_minutes": 5,
                "escalation_contact":           "db-team@company.com",
            },
            metadata={"csv": str(self._csv_path)},
        )
        check = self._verify_output(result)
        if not check["passed"]:
            logger.warning(f"[{self.__class__.__name__}] Layer 1 FAILED — {check['reason']}")
            return ToolResult(
                status="error", data=None,
                error_message=f"Layer 1 verification failed: {check['reason']}",
            )

        logger.info(f"[{self.__class__.__name__}] Success — runbook_id={rb_id}")
        return result

    def rollback(self, payload: dict) -> None:
        """
        Undo the last CSV row append.

        Args:
            payload: {"file": str, "row_id": str, "id_column": str}
        """
        file_path = Path(payload["file"])
        row_id    = payload["row_id"]
        id_column = payload["id_column"]

        logger.warning(f"[{self.__class__.__name__}] Rolling back row {row_id!r} from {file_path}")
        try:
            df = pd.read_csv(file_path, keep_default_na=False)
            df = df[df[id_column] != row_id]
            df.to_csv(file_path, index=False)
            logger.info(f"[{self.__class__.__name__}] Rollback complete — row {row_id!r} removed")
        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Rollback FAILED: {exc}")

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: confirm runbook fields present and row persisted in CSV."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        for key in ("runbook_id", "fix_steps", "root_cause", "affected_services"):
            if key not in result.data:
                return {"passed": False, "reason": f"missing key: {key!r}"}
        if not result.data["fix_steps"]:
            return {"passed": False, "reason": "fix_steps must not be empty"}
        try:
            df = pd.read_csv(self._csv_path, keep_default_na=False)
            if result.data["runbook_id"] not in df["log_id"].values:
                return {"passed": False, "reason": "runbook row not found in CSV after write"}
        except Exception as exc:
            return {"passed": False, "reason": f"CSV re-read failed: {exc}"}
        return {"passed": True, "reason": "ok"}
