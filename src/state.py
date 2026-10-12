"""
Central state management — domain-agnostic. Copy as-is; do not edit.

Every agent loop passes a single AgentState through all 6 steps.
Tools never modify state directly — only agent.py does.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Enumerations ──────────────────────────────────────────────────────────────

class AgentStep(str, Enum):
    IDLE     = "idle"
    OBSERVE  = "observe"
    REASON   = "reason"
    PLAN     = "plan"
    ACT      = "act"
    VERIFY   = "verify"
    ITERATE  = "iterate"
    COMPLETE = "complete"
    FAILED   = "failed"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PASSED  = "passed"
    FAILED  = "failed"
    PARTIAL = "partial"


# ── ToolResult ────────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    """
    Standardised return structure required by the hackathon brief.
    Every tool MUST return a ToolResult — never raise, never return raw dicts.

    Fields:
        status        : "success" | "error"
        data          : domain payload (dict, list, str, …)
        metadata      : timing, row counts, source file, etc.
        error_message : human-readable reason on error; None on success
    """
    status: str
    data: Any
    metadata: dict = field(default_factory=dict)
    error_message: Optional[str] = None


# ── AgentState ────────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    """
    Single source of truth threaded through the Observe→Reason→Plan→Act→Verify→Iterate loop.

    Responsibilities:
      - Record each loop step as it executes
      - Track which tools have run (for Layer 3 verification)
      - Accumulate errors without crashing
      - Journal rollback entries so execution tools can be undone
      - Produce the standardised output JSON required by the brief
    """
    domain: str = "{{DOMAIN}}"  # TODO: set in config.py

    steps_executed:      list[str]            = field(default_factory=list)
    tools_used:          list[str]            = field(default_factory=list)
    errors:              list[str]            = field(default_factory=list)
    retries:             int                  = 0
    verification_status: VerificationStatus   = VerificationStatus.PENDING

    # Internal — not serialised
    _start:        float       = field(default_factory=time.time,  repr=False)
    _rollback_log: list[dict]  = field(default_factory=list,       repr=False)

    # ── Mutation helpers ──────────────────────────────────────────────────────

    def record_step(self, step: AgentStep) -> None:
        """Append step to steps_executed (no duplicates)."""
        if step.value not in self.steps_executed:
            self.steps_executed.append(step.value)
            logger.debug(f"[STATE] step={step.value}")

    def record_tool(self, tool_name: str) -> None:
        """Append tool class name to tools_used (no duplicates)."""
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)
            logger.debug(f"[STATE] tool={tool_name}")

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error(f"[STATE] error recorded: {message}")

    # ── Rollback journal ──────────────────────────────────────────────────────

    def register_rollback(self, action: str, payload: dict) -> None:
        """
        Execution tools call this immediately after a side-effecting operation.
        If a downstream step fails, agent.py iterates _rollback_log in reverse
        and calls each tool's rollback() method.

        Args:
            action  : human-readable label, e.g. "csv_row_appended"
            payload : enough data to undo the action, e.g. {"file": "...", "row_id": "..."}
        """
        entry = {"action": action, "payload": payload}
        self._rollback_log.append(entry)
        logger.debug(f"[STATE] rollback registered: {action} payload={payload}")

    def get_rollback_log(self) -> list[dict]:
        return list(self._rollback_log)

    # ── Timing ────────────────────────────────────────────────────────────────

    def elapsed_seconds(self) -> float:
        return round(time.time() - self._start, 2)

    # ── Output ────────────────────────────────────────────────────────────────

    def to_output_dict(self, success: bool, result: str) -> dict:
        """
        Produce the standardised output schema required by the hackathon brief.

        Returns:
            {
              "success": bool,
              "result": str,
              "verification_status": "passed|failed|partial|pending",
              "steps_executed": [...],
              "tools_used": [...],
              "execution_time_seconds": float,
              "errors": [...],
              "metadata": {"retries": int, "domain": str}
            }
        """
        return {
            "success": success,
            "result": result,
            "verification_status": self.verification_status.value,
            "steps_executed": self.steps_executed,
            "tools_used": self.tools_used,
            "execution_time_seconds": self.elapsed_seconds(),
            "errors": self.errors,
            "metadata": {
                "retries": self.retries,
                "domain": self.domain,
            },
        }

    def save_output(self, output_dir: Path, success: bool, result: str) -> Path:
        """
        Persist output JSON to output/report.json.
        Required by brief: demo should show this file with correct schema.

        Returns:
            Path to the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "report.json"
        payload = self.to_output_dict(success, result)
        path.write_text(json.dumps(payload, indent=2, default=str))
        logger.info(f"[STATE] output saved → {path}")
        return path
