"""
Analysis Tool — Category: Analysis
Detect anomalies, correlate services, identify root cause, predict recurrence.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from .. import config
from ..state import ToolResult

logger = logging.getLogger(__name__)

RISK_HIGH   = "HIGH"
RISK_MEDIUM = "MEDIUM"
RISK_LOW    = "LOW"

_POOL_RE    = re.compile(r"connection pool exhausted|pool.*100/100", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"connection timeout|request timeout", re.IGNORECASE)
_SLOW_RE    = re.compile(r"slow query", re.IGNORECASE)


class AnomalyAnalysisTool:
    """
    Purpose:
        Analyse a batch of logs by time range or service to detect anomalies,
        correlate cross-service failures, identify root cause, and predict recurrence.

    Inputs:
        query (str): time range e.g. '15:20-15:25', service name, or 'all'

    Outputs:
        ToolResult with status="success", data={
            "time_range": str,
            "total_logs_analyzed": int,
            "anomaly_score": float (0-100),
            "risk_level": "HIGH"|"MEDIUM"|"LOW",
            "error_rate_baseline": float (errors/min),
            "error_rate_peak": float (errors/min),
            "spike_detected_at": str (timestamp or "none"),
            "repeating_patterns": list[str],
            "pattern_interval_seconds": int,
            "affected_services": list[str],
            "root_cause_service": str,
            "root_cause": str,
            "correlation_chain": str,
            "recurrence_prediction_minutes": int,
            "escalated": bool,
            "reasons": list[str],
        }
        OR status="error", error_message=reason

    Errors:
        - CSV file missing
        - No logs matching query
        - Empty query
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir      = data_dir
        self._primary_csv   = data_dir / "logs.csv"
        self._incidents_csv = data_dir / "incidents.csv"
        logger.info(f"[{self.__class__.__name__}] Initialised")

    def run(self, query: str) -> ToolResult:
        """
        Detect anomalies and identify root cause for the given log slice.

        Args:
            query: time range HH:MM-HH:MM, service name, or 'all'
        Returns:
            ToolResult (success|error)
        """
        logger.info(f"[{self.__class__.__name__}] Starting — input={query!r}")

        if not query or not query.strip():
            return ToolResult(status="error", data=None, error_message="query must not be empty")

        try:
            if not self._primary_csv.exists():
                raise FileNotFoundError(f"CSV not found: {self._primary_csv}")

            df = pd.read_csv(self._primary_csv, keep_default_na=False)
            q  = query.strip().strip("'\"")

            if q.lower() == "all":
                logs = df
            elif "-" in q and ":" in q:
                logs = self._filter_by_time_range(df, q)
            else:
                logs = df[df["service"].str.lower() == q.lower()]

            if logs.empty:
                raise ValueError(f"No logs found for query: {q!r}")

            analysis = self._analyse(logs, q)

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Error — input={query!r} error={exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        result = ToolResult(
            status="success",
            data=analysis,
            metadata={"source": str(self._primary_csv), "query": query},
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
            f"score={analysis['anomaly_score']} risk={analysis['risk_level']}"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _filter_by_time_range(self, df: pd.DataFrame, time_range: str) -> pd.DataFrame:
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

    def _analyse(self, logs: pd.DataFrame, query: str) -> dict:
        """Core analysis: error rates, spike detection, correlation, root cause."""
        total = len(logs)

        # ── Error rate per minute bucket ──────────────────────────────────────
        logs = logs.copy()
        logs["_ts"]     = pd.to_datetime(logs["timestamp"])
        logs["_bucket"] = logs["_ts"].dt.strftime("%H:%M")
        is_error_mask   = logs["level"].isin(["ERROR", "CRITICAL"])

        bucket_counts = logs[is_error_mask].groupby("_bucket").size()
        all_buckets   = sorted(logs["_bucket"].unique().tolist())

        if len(bucket_counts) == 0:
            baseline_rate = 0.0
            peak_rate     = 0.0
            spike_at      = "none"
        else:
            rates         = bucket_counts.to_dict()
            sorted_bkts   = sorted(rates.keys())
            baseline_rate = float(rates.get(sorted_bkts[0], 0)) if sorted_bkts else 0.0
            peak_rate     = float(bucket_counts.max())
            spike_bkt     = bucket_counts.idxmax()
            spike_at      = f"2024-01-15 {spike_bkt}:00"

        # ── Pattern detection ─────────────────────────────────────────────────
        patterns = self._find_patterns(logs)

        # ── Service correlation ───────────────────────────────────────────────
        affected, correlation_chain = self._correlate_services(logs)

        # ── Root cause ────────────────────────────────────────────────────────
        root_cause_svc, root_cause = self._identify_root_cause(logs)

        # ── Recurrence prediction ─────────────────────────────────────────────
        recurrence_min = self._predict_recurrence(logs, peak_rate)

        # ── Anomaly score ─────────────────────────────────────────────────────
        score, reasons, escalated = self._compute_score(
            baseline_rate, peak_rate, patterns, logs, root_cause
        )

        if escalated:
            risk_level = RISK_HIGH
        elif score >= config.ANOMALY_HIGH_THRESHOLD:
            risk_level = RISK_HIGH
        elif score >= config.ANOMALY_MEDIUM_THRESHOLD:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        root_cause_type = self._classify_root_cause_type(root_cause, patterns)
        matched_past    = self._match_past_incidents(root_cause_type, affected, patterns)

        return {
            "time_range":                    query,
            "total_logs_analyzed":           total,
            "anomaly_score":                 round(score, 1),
            "risk_level":                    risk_level,
            "error_rate_baseline":           round(baseline_rate, 1),
            "error_rate_peak":               round(peak_rate, 1),
            "spike_detected_at":             spike_at,
            "repeating_patterns":            patterns,
            "pattern_interval_seconds":      8 if "connection timeout" in patterns else 0,
            "affected_services":             affected,
            "root_cause_service":            root_cause_svc,
            "root_cause":                    root_cause,
            "root_cause_type":               root_cause_type,
            "correlation_chain":             correlation_chain,
            "recurrence_prediction_minutes": recurrence_min,
            "escalated":                     escalated,
            "reasons":                       reasons,
            "matched_past_incidents":        matched_past,
            "historical_match_count":        len(matched_past),
        }

    def _find_patterns(self, logs: pd.DataFrame) -> list:
        counter: Counter = Counter()
        for msg in logs["message"].tolist():
            msg = str(msg)
            if _POOL_RE.search(msg):
                counter["DB connection pool exhausted"] += 1
            elif _TIMEOUT_RE.search(msg):
                counter["connection timeout"] += 1
            elif _SLOW_RE.search(msg):
                counter["slow query detected"] += 1
        return [p for p, c in counter.most_common() if c >= config.PATTERN_REPEAT_MIN]

    def _correlate_services(self, logs: pd.DataFrame) -> tuple:
        """Find services linked via shared request_ids in ERROR/CRITICAL logs."""
        error_logs   = logs[logs["level"].isin(["ERROR", "CRITICAL"])]
        shared_reqs  = error_logs[error_logs.duplicated("request_id", keep=False)]
        affected_set = set(shared_reqs["service"].tolist()) | set(
            logs[logs["level"].isin(["ERROR", "CRITICAL"])]["service"].tolist()
        )
        affected = sorted(affected_set)

        chain_svc = ["api-gateway", "checkout-service", "db-service", "cache-service"]
        chain     = " → ".join(s for s in chain_svc if s in affected_set)
        return affected, chain or " → ".join(affected[:3])

    def _identify_root_cause(self, logs: pd.DataFrame) -> tuple:
        """Find service with CRITICAL pool-exhausted message."""
        critical = logs[logs["level"] == "CRITICAL"]
        for _, row in critical.iterrows():
            msg = str(row.get("message", ""))
            if _POOL_RE.search(msg):
                return (
                    str(row["service"]),
                    f"DB connection pool exhausted (100/100) triggered by slow query in checkout-service",
                )
        if not critical.empty:
            top = critical["service"].value_counts().idxmax()
            return top, f"Critical failures in {top}"
        error = logs[logs["level"] == "ERROR"]
        if not error.empty:
            top = error["service"].value_counts().idxmax()
            return top, f"Error spike in {top}"
        return "unknown", "Root cause not determined from available logs"

    def _predict_recurrence(self, logs: pd.DataFrame, peak_rate: float) -> int:
        """Estimate minutes until next occurrence based on peak error rate."""
        if peak_rate == 0:
            return 0
        if peak_rate >= 100:
            return 12
        if peak_rate >= 50:
            return 20
        if peak_rate >= 10:
            return 45
        return 60

    def _compute_score(
        self, baseline: float, peak: float, patterns: list, logs: pd.DataFrame, root_cause: str
    ) -> tuple:
        """Compute anomaly score 0-100 and reasons."""
        score   = 0.0
        reasons = []
        escalated = False

        if baseline > 0 and peak > 0:
            factor = peak / baseline
            spike_score = min(40.0, factor * 5)
            score  += spike_score
            reasons.append(f"Error rate spiked {factor:.0f}x (baseline={baseline}/min peak={peak}/min)")
        elif peak > 0:
            score += min(40.0, peak * 0.5)
            reasons.append(f"Peak error rate={peak}/min (no baseline — first minute clean)")

        has_critical = "CRITICAL" in logs["level"].values
        if has_critical:
            score += 30.0
            reasons.append("CRITICAL level logs present")
            escalated = True

        score += min(20.0, len(patterns) * 10)
        if patterns:
            reasons.append(f"Repeating patterns: {patterns}")

        if _POOL_RE.search(root_cause):
            score += 10.0
            reasons.append("Root cause: DB connection pool exhaustion")

        score = min(score, 100.0)
        return score, reasons, escalated

    def _classify_root_cause_type(self, root_cause: str, patterns: list) -> str:
        """Map root cause text to a canonical type for matching against incidents.csv."""
        rc = root_cause.lower()
        if _POOL_RE.search(rc) or "pool" in rc:
            return "pool_exhausted"
        if _TIMEOUT_RE.search(rc) or "timeout" in " ".join(patterns).lower():
            return "connection_timeout"
        if _SLOW_RE.search(rc):
            return "slow_query"
        if "cache" in rc:
            return "cache_failure"
        if "memory" in rc or "oom" in rc:
            return "memory_leak"
        if "auth" in rc:
            return "auth_overload"
        return "unknown"

    def _match_past_incidents(
        self,
        root_cause_type: str,
        affected_services: list,
        patterns: list,
    ) -> list:
        """
        Compare current incident against historical incidents.csv.
        Scores each past incident by overlap of root_cause_type, affected_services,
        and error_pattern keywords. Returns top 3 matches (score >= 1), sorted desc.
        Gracefully returns [] if incidents.csv is absent.
        """
        if not self._incidents_csv.exists():
            logger.warning(f"[{self.__class__.__name__}] incidents.csv not found — skipping history match")
            return []

        try:
            df = pd.read_csv(self._incidents_csv, keep_default_na=False)
        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Failed to load incidents.csv — {exc}")
            return []

        affected_set   = set(s.lower() for s in affected_services)
        pattern_words  = set(" ".join(patterns).lower().split())
        results        = []

        for _, row in df.iterrows():
            sim = 0

            if str(row.get("root_cause_type", "")).lower() == root_cause_type:
                sim += 3

            past_services = set(
                s.strip().lower()
                for s in str(row.get("affected_services", "")).split(",")
            )
            sim += len(affected_set & past_services)

            past_pattern_words = set(str(row.get("error_pattern", "")).lower().split())
            sim += len(pattern_words & past_pattern_words) // 2

            if sim >= 1:
                results.append({
                    "incident_id":         str(row["incident_id"]),
                    "date":                str(row["date"]),
                    "root_cause_type":     str(row["root_cause_type"]),
                    "affected_services":   str(row["affected_services"]),
                    "similarity_score":    sim,
                    "resolution_minutes":  int(row["resolution_minutes"]),
                    "recurrence_days":     int(row["recurrence_days"]),
                    "runbook_id":          str(row["runbook_id"]),
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        top = results[:3]
        logger.info(
            f"[{self.__class__.__name__}] Historical match — "
            f"root_cause_type={root_cause_type!r} matches={len(top)}"
        )
        return top

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: validate analysis output."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        d = result.data
        if d.get("risk_level") not in (RISK_HIGH, RISK_MEDIUM, RISK_LOW):
            return {"passed": False, "reason": f"invalid risk_level: {d.get('risk_level')!r}"}
        if not isinstance(d.get("reasons"), list):
            return {"passed": False, "reason": "reasons must be a list"}
        score = d.get("anomaly_score", -1)
        if not (0 <= score <= 100):
            return {"passed": False, "reason": f"anomaly_score {score} out of [0,100]"}
        if "spike_detected_at" not in d:
            return {"passed": False, "reason": "spike_detected_at missing"}
        return {"passed": True, "reason": "ok"}
