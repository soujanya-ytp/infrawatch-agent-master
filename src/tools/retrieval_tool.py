"""
Retrieval Tool — Category: Retrieval
Ingest logs from logs.csv by time range, service name, or log_id.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..state import ToolResult

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"log_id", "timestamp", "service", "level", "message", "error_code"}


class LogRetrieverTool:
    """
    Purpose:
        Fetch log records from logs.csv filtered by time range, service name, or log_id.

    Inputs:
        query (str): one of:
            - log_id e.g. 'LOG013'
            - service name e.g. 'db-service'
            - time range e.g. '15:20-15:25'
            - 'all' to return every record

    Outputs:
        ToolResult with status="success", data={"logs": [...], "count": int}
        OR status="error", error_message=reason

    Errors:
        - CSV file missing
        - No logs found for query
        - Empty query string
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._csv_path = data_dir / "logs.csv"
        logger.info(f"[{self.__class__.__name__}] Initialised — csv={self._csv_path}")

    def run(self, query: str) -> ToolResult:
        """
        Fetch log records matching query.

        Args:
            query: log_id, service name, time range HH:MM-HH:MM, or 'all'
        Returns:
            ToolResult (success|error)
        """
        logger.info(f"[{self.__class__.__name__}] Starting — input={query!r}")

        if not query or not query.strip():
            return ToolResult(status="error", data=None, error_message="query must not be empty")

        try:
            if not self._csv_path.exists():
                raise FileNotFoundError(f"CSV not found: {self._csv_path}")

            df = pd.read_csv(self._csv_path, keep_default_na=False)
            q  = query.strip().strip("'\"")

            if q.lower() == "all":
                filtered = df
            elif q.upper().startswith("LOG") and len(q) <= 8:
                filtered = df[df["log_id"] == q.upper()]
            elif "-" in q and ":" in q and not q.upper().startswith("LOG"):
                filtered = self._filter_by_time_range(df, q)
            else:
                filtered = df[df["service"].str.lower() == q.lower()]

            if filtered.empty:
                raise ValueError(f"No logs found for query: {q!r}")

            records = filtered.to_dict(orient="records")

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Error — input={query!r} error={exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        result = ToolResult(
            status="success",
            data={"logs": records, "count": len(records)},
            metadata={"source": str(self._csv_path), "query": query},
        )
        check = self._verify_output(result)
        if not check["passed"]:
            logger.warning(f"[{self.__class__.__name__}] Layer 1 FAILED — {check['reason']}")
            return ToolResult(
                status="error", data=None,
                error_message=f"Layer 1 verification failed: {check['reason']}",
            )

        logger.info(f"[{self.__class__.__name__}] Success — count={result.data['count']}")
        return result

    def _filter_by_time_range(self, df: pd.DataFrame, time_range: str) -> pd.DataFrame:
        """Parse 'HH:MM-HH:MM' and filter rows by timestamp."""
        parts = time_range.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid time range: {time_range!r}. Use HH:MM-HH:MM")
        start_str, end_str = parts[0].strip(), parts[1].strip()
        df = df.copy()
        df["_ts"]  = pd.to_datetime(df["timestamp"])
        start_time = pd.to_datetime(f"2024-01-15 {start_str}:00")
        end_time   = pd.to_datetime(f"2024-01-15 {end_str}:59")
        mask = (df["_ts"] >= start_time) & (df["_ts"] <= end_time)
        return df[mask].drop(columns=["_ts"])

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: validate output before returning."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        if not isinstance(result.data.get("logs"), list):
            return {"passed": False, "reason": "data.logs must be a list"}
        if result.data["count"] == 0:
            return {"passed": False, "reason": "no records returned"}
        for rec in result.data["logs"][:3]:
            missing = REQUIRED_KEYS - set(rec.keys())
            if missing:
                return {"passed": False, "reason": f"record missing keys: {missing}"}
        return {"passed": True, "reason": "ok"}
