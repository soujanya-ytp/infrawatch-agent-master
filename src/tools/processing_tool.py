"""
Processing Tool — Category: Processing
Classify errors and find repeating patterns in log records.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..state import ToolResult

logger = logging.getLogger(__name__)

_TIMEOUT_RE = re.compile(r"connection timeout|request timeout|timed out", re.IGNORECASE)
_POOL_RE    = re.compile(r"connection pool exhausted|pool.*100/100", re.IGNORECASE)
_SLOW_RE    = re.compile(r"slow query|duration=\d{4,}ms", re.IGNORECASE)
_HEALTH_RE  = re.compile(r"health check failed", re.IGNORECASE)
_CIRCUIT_RE = re.compile(r"circuit breaker", re.IGNORECASE)


def _classify_error(record: dict) -> str:
    code = str(record.get("error_code", ""))
    msg  = str(record.get("message", ""))
    if _POOL_RE.search(msg):
        return "pool_exhausted"
    if _TIMEOUT_RE.search(msg):
        return "timeout"
    if _SLOW_RE.search(msg):
        return "slow_query"
    if _HEALTH_RE.search(msg):
        return "health_check_failure"
    if _CIRCUIT_RE.search(msg):
        return "circuit_breaker"
    if code.startswith("5"):
        return "5xx"
    if code.startswith("4"):
        return "4xx"
    if code == "200":
        return "none"
    return "other"


def _time_bucket(timestamp: str) -> str:
    try:
        return str(timestamp)[11:16]
    except Exception:
        return "unknown"


def _extract_pattern_key(message: str) -> str:
    if _POOL_RE.search(message):
        return "DB connection pool exhausted"
    if _TIMEOUT_RE.search(message):
        return "connection timeout"
    if _SLOW_RE.search(message):
        return "slow query detected"
    if _HEALTH_RE.search(message):
        return "health check failed"
    if _CIRCUIT_RE.search(message):
        return "circuit breaker open"
    if "500 Internal Server Error" in message:
        return "500 Internal Server Error"
    if "Cache write failed" in message or "Cache eviction failed" in message:
        return "cache failure"
    return ""


class LogNormalizeTool:
    """
    Purpose:
        Receive a dict with a 'logs' list from LogRetrieverTool and return
        enriched records with computed fields plus pattern analysis.

    Inputs:
        record (dict): must contain key "logs" with list of log dicts.

    Outputs:
        ToolResult with status="success", data={
            "logs": enriched list with error_category/time_bucket/is_error added,
            "patterns": {pattern_key: count} for repeating messages,
            "error_counts": {HH:MM: count} per minute bucket,
            "top_pattern": str,
            "count": int,
        }
        OR status="error", error_message=reason

    Errors:
        - record is not a dict or missing 'logs' key
        - logs list is empty
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        logger.info(f"[{self.__class__.__name__}] Initialised")

    def run(self, record: dict) -> ToolResult:
        """
        Normalise and enrich log records, extract repeating patterns.

        Args:
            record: dict with key "logs" containing list of log dicts
        Returns:
            ToolResult (success|error)
        """
        logger.info(f"[{self.__class__.__name__}] Starting — input type={type(record).__name__}")

        if not record or not isinstance(record, dict):
            return ToolResult(status="error", data=None, error_message="record must be a non-empty dict")
        if "logs" not in record or not isinstance(record["logs"], list):
            return ToolResult(status="error", data=None, error_message="record must contain 'logs' list")
        if not record["logs"]:
            return ToolResult(status="error", data=None, error_message="logs list is empty")

        try:
            enriched_logs: list[dict[str, Any]] = []
            pattern_counter: Counter = Counter()
            bucket_errors: Counter   = Counter()

            for raw in record["logs"]:
                log = dict(raw)
                log["error_category"] = _classify_error(raw)
                log["time_bucket"]    = _time_bucket(str(raw.get("timestamp", "")))
                log["is_error"]       = log["error_category"] not in ("none", "other")
                log["duration_ms"]    = int(raw.get("duration_ms", 0))

                if log["is_error"]:
                    bucket_errors[log["time_bucket"]] += 1

                keyword = _extract_pattern_key(str(raw.get("message", "")))
                if keyword:
                    pattern_counter[keyword] += 1

                enriched_logs.append(log)

            repeating   = {k: v for k, v in pattern_counter.items() if v >= 2}
            top_pattern = pattern_counter.most_common(1)[0][0] if pattern_counter else ""

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Error — {exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        result = ToolResult(
            status="success",
            data={
                "logs":         enriched_logs,
                "patterns":     repeating,
                "error_counts": dict(bucket_errors),
                "top_pattern":  top_pattern,
                "count":        len(enriched_logs),
            },
            metadata={"fields_added": ["error_category", "time_bucket", "is_error", "duration_ms"]},
        )
        check = self._verify_output(result)
        if not check["passed"]:
            logger.warning(f"[{self.__class__.__name__}] Layer 1 FAILED — {check['reason']}")
            return ToolResult(
                status="error", data=None,
                error_message=f"Layer 1 verification failed: {check['reason']}",
            )

        logger.info(
            f"[{self.__class__.__name__}] Success — "
            f"count={result.data['count']} patterns={list(repeating.keys())[:3]}"
        )
        return result

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: validate enriched records."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        if not isinstance(result.data.get("logs"), list):
            return {"passed": False, "reason": "data.logs must be a list"}
        if not result.data["logs"]:
            return {"passed": False, "reason": "no enriched logs"}
        sample = result.data["logs"][0]
        for field in ("error_category", "time_bucket", "is_error"):
            if field not in sample:
                return {"passed": False, "reason": f"enriched record missing field: {field}"}
        if not isinstance(result.data.get("patterns"), dict):
            return {"passed": False, "reason": "patterns must be a dict"}
        return {"passed": True, "reason": "ok"}
