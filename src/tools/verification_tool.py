"""
Verification Tool — Category: Verification
Validate log analysis results against expected output schemas.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..state import ToolResult

logger = logging.getLogger(__name__)


class LogOutputVerifierTool:
    """
    Purpose:
        Validate that a given result dict matches the expected output schema
        and satisfies log-analysis-specific business rules.

    Inputs:
        result    (dict | str): output to validate (dict or JSON string)
        spec_name (str): Options: 'log_record' | 'anomaly_analysis' | 'runbook' | 'incident_report'

    Outputs:
        ToolResult with status="success", data={
            "passed": bool,
            "spec": str,
            "failures": [failure reasons],
            "warnings": [warnings],
            "checks_run": int,
        }
        OR status="error", error_message=reason

    Errors:
        - result is None
        - spec_name not recognised
        - result is not valid JSON when passed as string
    """

    SPECS: dict = {
        "log_record": {
            "required_keys":  ["log_id", "timestamp", "service", "level", "message"],
            "type_checks":    {},
            "allowed_values": {"level": ["INFO", "WARN", "ERROR", "CRITICAL", "RUNBOOK"]},
        },
        "anomaly_analysis": {
            "required_keys": [
                "anomaly_score", "risk_level", "root_cause",
                "affected_services", "spike_detected_at",
                "matched_past_incidents", "historical_match_count",
            ],
            "type_checks":    {"anomaly_score": (int, float), "historical_match_count": int},
            "allowed_values": {"risk_level": ["HIGH", "MEDIUM", "LOW"]},
        },
        "runbook": {
            "required_keys":  ["runbook_id", "root_cause", "fix_steps", "affected_services"],
            "type_checks":    {},
            "allowed_values": {},
        },
        "incident_report": {
            "required_keys":  ["summary", "layer3_verification"],
            "type_checks":    {},
            "allowed_values": {},
        },
    }

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        logger.info(f"[{self.__class__.__name__}] Initialised — specs={list(self.SPECS)}")

    def run(self, result: Any, spec_name: str) -> ToolResult:
        """
        Validate result against the named specification.

        Args:
            result:    dict or JSON string to validate
            spec_name: key in SPECS dict
        Returns:
            ToolResult (success|error)
        """
        logger.info(
            f"[{self.__class__.__name__}] Starting — spec={spec_name!r} "
            f"input_type={type(result).__name__}"
        )

        if result is None:
            return ToolResult(status="error", data=None, error_message="result must not be None")

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    status="error", data=None,
                    error_message=f"result is not valid JSON: {exc}",
                )

        if spec_name not in self.SPECS:
            return ToolResult(
                status="error", data=None,
                error_message=f"Unknown spec: {spec_name!r}. Known specs: {list(self.SPECS)}",
            )

        spec     = self.SPECS[spec_name]
        failures: list = []
        warnings: list = []
        checks   = 0

        try:
            for key in spec.get("required_keys", []):
                checks += 1
                if key not in result:
                    failures.append(f"missing required key: {key!r}")

            for key, expected_type in spec.get("type_checks", {}).items():
                checks += 1
                if key in result and not isinstance(result[key], expected_type):
                    failures.append(
                        f"field {key!r}: expected {expected_type}, "
                        f"got {type(result[key]).__name__}"
                    )

            for key, allowed in spec.get("allowed_values", {}).items():
                checks += 1
                if key in result and result[key] not in allowed:
                    failures.append(f"field {key!r}: value {result[key]!r} not in {allowed}")

            if spec_name == "anomaly_analysis" and "anomaly_score" in result:
                checks += 1
                score = result["anomaly_score"]
                if not (0 <= score <= 100):
                    failures.append(f"anomaly_score {score} out of range [0, 100]")

            if spec_name == "runbook" and "fix_steps" in result:
                checks += 1
                if not result["fix_steps"]:
                    failures.append("fix_steps list must not be empty")

        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Verification error: {exc}")
            return ToolResult(status="error", data=None, error_message=str(exc))

        passed = len(failures) == 0
        verification_result = ToolResult(
            status="success",
            data={
                "passed":     passed,
                "spec":       spec_name,
                "failures":   failures,
                "warnings":   warnings,
                "checks_run": checks,
            },
            metadata={"spec_name": spec_name},
        )

        check = self._verify_output(verification_result)
        if not check["passed"]:
            logger.warning(f"[{self.__class__.__name__}] Layer 1 FAILED — {check['reason']}")
            return ToolResult(
                status="error", data=None,
                error_message=f"Layer 1 verification failed: {check['reason']}",
            )

        status_label = "PASSED" if passed else f"FAILED ({len(failures)} issues)"
        logger.info(f"[{self.__class__.__name__}] Success — spec={spec_name!r} result={status_label}")
        return verification_result

    def _verify_output(self, result: ToolResult) -> dict:
        """Layer 1: validate this tool's own output structure."""
        if result.status != "success" or not result.data:
            return {"passed": False, "reason": "empty or failed result"}
        required = {"passed", "spec", "failures", "warnings", "checks_run"}
        missing  = required - set(result.data.keys())
        if missing:
            return {"passed": False, "reason": f"missing keys: {missing}"}
        if not isinstance(result.data["passed"], bool):
            return {"passed": False, "reason": "'passed' must be bool"}
        if not isinstance(result.data["failures"], list):
            return {"passed": False, "reason": "'failures' must be list"}
        return {"passed": True, "reason": "ok"}
