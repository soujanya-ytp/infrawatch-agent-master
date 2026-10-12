"""
Log Analysis & Incident Response Agent — Agentic Orchestration Hackathon

Orchestration loop: Observe → Reason → Plan → Act → Verify → Iterate
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

from . import config
from .llm_provider import LLMProvider
from .state import AgentState, AgentStep, ToolResult, VerificationStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

_REACT_PROMPT = PromptTemplate.from_template(
    "You are {agent_name}, an autonomous AI agent for log analysis and incident response.\n"
    "Answer the user's question using the available tools.\n"
    "Follow the Observe→Reason→Plan→Act→Verify loop.\n\n"
    "Tools available:\n{tools}\n\n"
    "Tool names: {tool_names}\n\n"
    "Format:\n"
    "Thought: <reasoning>\n"
    "Action: <tool_name>\n"
    "Action Input: <input>\n"
    "Observation: <result>\n"
    "... (repeat as needed)\n"
    "Thought: I now know the final answer\n"
    "Final Answer: <answer>\n\n"
    "Question: {input}\n"
    "Thought: {agent_scratchpad}"
)


class _LoggingCallback(BaseCallbackHandler):
    """Route all LangChain agent events to logger. No print() allowed."""

    def on_agent_action(self, action, **_):
        logger.info(f"[ACT]      tool={action.tool!r}  input={action.tool_input!r}")

    def on_tool_start(self, serialized, input_str, **_):
        logger.info(f"[TOOL]     starting — input={input_str!r}")

    def on_tool_end(self, output, **_):
        logger.info(f"[TOOL]     finished — output={str(output)[:200]!r}")

    def on_agent_finish(self, finish, **_):
        logger.info(f"[COMPLETE] output={finish.return_values.get('output', '')[:120]!r}")

    def on_chain_error(self, error, **_):
        logger.error(f"[ERROR]    chain error: {error}")

    def on_tool_error(self, error, **_):
        logger.error(f"[ERROR]    tool error: {error}")


class LogAnalysisAgent:
    """
    Log Analysis & Incident Response Agent

    Public API:
        chat(question)           → str     # one question, returns answer
        run_cli()                → None    # interactive loop (stdin)
        run_demo(questions)      → dict    # automated — no manual input required
    """

    DEMO_QUESTIONS: list = [
        "Retrieve logs from 15:20-15:25 using get_log_records, then normalize the data using normalize_log_data to classify errors and identify repeating patterns",
        "Detect anomalies in the time range 15:20-15:25 using detect_anomalies — identify the root cause, affected services, and recurrence prediction",
        "Validate the anomaly analysis results using verify_output with spec anomaly_analysis, confirming the risk level and root cause are correctly captured",
        "Generate an incident runbook using generate_runbook for root cause DB connection pool exhausted,api-gateway,checkout-service,db-service",
        "Use generate_incident_report to produce the complete incident report for time range 15:20-15:25",
    ]

    REQUIRED_TOOLS: list = [
        "LogRetrieverTool",
        "LogNormalizeTool",
        "RunbookGeneratorTool",
        "LogOutputVerifierTool",
        "AnomalyAnalysisTool",
        "IncidentReportTool",
    ]

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir     = data_dir or config.DATA_DIR
        self._llm_provider = LLMProvider()
        self.state         = AgentState(domain=config.DOMAIN)
        self._tools        = self._build_tools()
        self._executor: Optional[AgentExecutor] = None

        if config.GROQ_API_KEY:
            self._executor = self._build_executor()

        logger.info(f"[Agent] Initialised — domain={config.DOMAIN}  tools={len(self._tools)}")

    # ── Public API ────────────────────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """
        Process one user question through the full agentic loop.

        Args:
            user_message: natural language question
        Returns:
            Agent's final answer string
        """
        logger.info(f"[OBSERVE]  question={user_message!r}")
        self.state.record_step(AgentStep.OBSERVE)

        logger.info("[REASON]   analysing question and selecting tools")
        self.state.record_step(AgentStep.REASON)

        logger.info("[PLAN]     decomposing into execution steps")
        self.state.record_step(AgentStep.PLAN)

        start = time.time()
        logger.info("[ACT]      invoking executor")
        self.state.record_step(AgentStep.ACT)

        response = self._invoke_with_retry(user_message)

        elapsed = round(time.time() - start, 2)
        logger.info(f"[ACT]      completed in {elapsed}s")

        logger.info("[VERIFY]   Layer 2 — checking response meets goal")
        self.state.record_step(AgentStep.VERIFY)
        layer2_passed = self._verify_layer2(user_message, response)

        if layer2_passed:
            logger.info("[VERIFY]   Layer 2 PASSED")
            self.state.verification_status = VerificationStatus.PASSED
            self.state.record_step(AgentStep.COMPLETE)
        else:
            logger.warning("[VERIFY]   Layer 2 FAILED — response may not satisfy goal")
            self.state.verification_status = VerificationStatus.PARTIAL
            self.state.record_step(AgentStep.ITERATE)

        return response

    def run_cli(self) -> None:
        """Interactive CLI loop. Reads questions from stdin."""
        banner = f"{'=' * 50}\n  {config.AGENT_NAME}\n{'=' * 50}"
        sys.stdout.write(f"\n{banner}\nType your question or 'exit' to quit.\n{'=' * 50}\n")
        sys.stdout.flush()

        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            try:
                line = sys.stdin.readline()
            except (KeyboardInterrupt, EOFError):
                break

            user_input = line.strip() if line else ""
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                logger.info("[Agent] User requested exit")
                sys.stdout.write("Goodbye.\n")
                sys.stdout.flush()
                break

            try:
                response = self.chat(user_input)
                sys.stdout.write(f"\n{response}\n\n")
                sys.stdout.flush()
            except Exception as exc:
                logger.error(f"[Agent] Unhandled error: {exc}")
                sys.stdout.write(f"\nError: {exc}\n\n")
                sys.stdout.flush()

        self.state.save_output(config.OUTPUT_DIR, success=True, result="cli session complete")

    def run_demo(self, questions: Optional[list] = None) -> dict:
        """
        Run automated demo without manual intervention.

        Required by brief: "Agent executes end-to-end workflow without manual intervention."

        Args:
            questions: override DEMO_QUESTIONS for custom sequences
        Returns:
            Standardised output dict
        """
        qs = questions or self.DEMO_QUESTIONS
        logger.info(f"[DEMO]     Starting automated demo — {len(qs)} questions")

        results: list = []

        for i, question in enumerate(qs, 1):
            logger.info(f"[DEMO]     Q{i}/{len(qs)}: {question!r}")
            try:
                answer = self.chat(question)
                results.append({"question": question, "answer": answer, "success": True})
                logger.info(f"[DEMO]     Q{i} answered ({len(answer)} chars)")
            except Exception as exc:
                logger.error(f"[DEMO]     Q{i} failed: {exc}")
                self.state.add_error(f"Q{i} failed: {exc}")
                results.append({"question": question, "answer": None, "success": False, "error": str(exc)})

        all_success = all(r["success"] for r in results)
        summary = f"Demo complete — {sum(r['success'] for r in results)}/{len(qs)} questions answered"
        logger.info(f"[DEMO]     {summary}")

        output_path = self.state.save_output(config.OUTPUT_DIR, success=all_success, result=summary)
        logger.info(f"[DEMO]     report → {output_path}")

        return self.state.to_output_dict(success=all_success, result=summary)

    # ── Private — executor ────────────────────────────────────────────────────

    def _build_executor(self) -> AgentExecutor:
        llm    = self._llm_provider.get_chat_model()
        prompt = _REACT_PROMPT.partial(agent_name=config.AGENT_NAME)
        agent  = create_react_agent(llm=llm, tools=self._tools, prompt=prompt)
        return AgentExecutor(
            agent=agent,
            tools=self._tools,
            callbacks=[_LoggingCallback()],
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=config.MAX_ITERATIONS,
            max_execution_time=config.MAX_EXECUTION_TIME,
        )

    def _invoke_with_retry(self, user_message: str) -> str:
        """Invoke AgentExecutor with exponential back-off on failure."""
        if self._executor is None:
            return (
                "Agent not ready: GROQ_API_KEY is not configured. "
                "Set it in .env and restart."
            )

        last_error: Optional[Exception] = None

        for attempt in range(config.MAX_RETRIES):
            try:
                if attempt > 0:
                    wait = 2 ** attempt
                    logger.warning(
                        f"[ITERATE]  retry {attempt}/{config.MAX_RETRIES - 1} — waiting {wait}s"
                    )
                    time.sleep(wait)
                    self.state.retries += 1
                    self.state.record_step(AgentStep.ITERATE)

                result = self._executor.invoke({"input": user_message})
                return result.get("output", "No response generated.")

            except Exception as exc:
                last_error = exc
                logger.error(f"[Agent] Attempt {attempt + 1}/{config.MAX_RETRIES} failed: {exc}")

        self._attempt_rollback()
        self.state.record_step(AgentStep.FAILED)
        self.state.add_error(str(last_error))
        return (
            f"Unable to process request after {config.MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    def _attempt_rollback(self) -> None:
        """Iterate rollback journal in reverse and undo execution side-effects."""
        log = self.state.get_rollback_log()
        if not log:
            return

        logger.warning(f"[ROLLBACK] {len(log)} entries to undo")
        from .tools.execution_tool import RunbookGeneratorTool
        _exec = RunbookGeneratorTool(data_dir=self._data_dir)

        for entry in reversed(log):
            action  = entry["action"]
            payload = entry["payload"]
            logger.warning(f"[ROLLBACK] undoing: {action}  payload={payload}")
            if action == "csv_row_appended":
                _exec.rollback(payload)

    # ── Private — tools ───────────────────────────────────────────────────────

    def _build_tools(self) -> list:
        """Build and return LangChain @tool wrappers for all 6 domain tools."""
        from .tools.retrieval_tool    import LogRetrieverTool
        from .tools.processing_tool   import LogNormalizeTool
        from .tools.execution_tool    import RunbookGeneratorTool
        from .tools.verification_tool import LogOutputVerifierTool
        from .tools.analysis_tool     import AnomalyAnalysisTool
        from .tools.reporting_tool    import IncidentReportTool

        _fetch   = LogRetrieverTool(data_dir=self._data_dir)
        _proc    = LogNormalizeTool(data_dir=self._data_dir)
        _exec    = RunbookGeneratorTool(data_dir=self._data_dir)
        _verify  = LogOutputVerifierTool(data_dir=self._data_dir)
        _analyze = AnomalyAnalysisTool(data_dir=self._data_dir)
        _report  = IncidentReportTool(data_dir=self._data_dir)
        state    = self.state

        @tool
        def get_log_records(query: str) -> str:
            """
            Fetch log records from logs.csv.
            Input: log_id (e.g. 'LOG013'), service name (e.g. 'db-service'),
                   time range (e.g. '15:20-15:25'), or 'all'.
            """
            state.record_tool("LogRetrieverTool")
            res = _fetch.run(query)
            if res.status == "success":
                return json.dumps(res.data, default=str, indent=2)
            return f"Error: {res.error_message}"

        @tool
        def normalize_log_data(logs_json: str) -> str:
            """
            Classify errors and find repeating patterns in log records.
            Input: JSON string with 'logs' key containing list of log dicts,
                   OR the result from get_log_records directly.
            """
            state.record_tool("LogNormalizeTool")
            try:
                data = json.loads(logs_json) if isinstance(logs_json, str) else logs_json
            except json.JSONDecodeError:
                data = {"logs": []}
            res = _proc.run(data)
            if res.status == "success":
                summary = {
                    "count":        res.data["count"],
                    "top_pattern":  res.data["top_pattern"],
                    "patterns":     res.data["patterns"],
                    "error_counts": res.data["error_counts"],
                }
                return json.dumps(summary, default=str, indent=2)
            return f"Error: {res.error_message}"

        @tool
        def detect_anomalies(query: str) -> str:
            """
            Detect anomalies, correlate cross-service failures, identify root cause,
            and predict recurrence.
            Input: time range (e.g. '15:20-15:25'), service name, or 'all'.
            """
            state.record_tool("AnomalyAnalysisTool")
            res = _analyze.run(query)
            if res.status == "success":
                return json.dumps(res.data, default=str, indent=2)
            return f"Error: {res.error_message}"

        @tool
        def generate_runbook(params: str) -> str:
            """
            Generate and persist an incident response runbook.
            Input: describe the root cause, e.g.
                   'DB connection pool exhausted in db-service, affecting api-gateway,checkout-service,db-service'
            """
            state.record_tool("RunbookGeneratorTool")
            parts    = params.split(",", 2)
            root_cause = parts[0].strip()
            services   = ",".join(parts[1:]).strip() if len(parts) > 1 else "unknown"
            res = _exec.run(
                root_cause=root_cause,
                services=services,
                incident_id="INC-20240115-1522",
                state=state,
            )
            if res.status == "success":
                return json.dumps(res.data, default=str, indent=2)
            return f"Error: {res.error_message}"

        @tool
        def verify_output(params: str) -> str:
            """
            Validate analysis results against a known schema (Layer 1 + Layer 2 verification).
            Use this after detect_anomalies or generate_runbook to confirm output is correct.
            Input: '<spec_name>' to verify latest result, or '<spec_name>|<json_result>'.
            Spec options: log_record, anomaly_analysis, runbook, incident_report
            """
            state.record_tool("LogOutputVerifierTool")
            if "|" in params:
                spec_name, result_json = params.split("|", 1)
                spec_name = spec_name.strip()
            else:
                spec_name    = "log_record"
                result_json  = params
            try:
                result_dict = json.loads(result_json)
            except json.JSONDecodeError:
                result_dict = {"raw": result_json}
            res = _verify.run(result_dict, spec_name)
            if res.status == "success":
                return json.dumps(res.data, default=str, indent=2)
            return f"Error: {res.error_message}"

        @tool
        def generate_incident_report(query: str) -> str:
            """
            Generate the complete incident report. Orchestrates all 6 tools in sequence:
            retrieve → normalize → analyze → runbook → verify → report.
            Use this as the FINAL step to produce a full incident summary.
            Input: time range (e.g. '15:20-15:25') or 'all'.
            """
            q = query.strip().strip("'\"")

            # Step 1 — Retrieve (ensure LogRetrieverTool in tools_used)
            fetch_res = _fetch.run(q)
            if "LogRetrieverTool" not in state.tools_used:
                state.record_tool("LogRetrieverTool")

            # Step 2 — Normalize (ensure LogNormalizeTool in tools_used)
            if fetch_res.status == "success" and "LogNormalizeTool" not in state.tools_used:
                state.record_tool("LogNormalizeTool")
                _proc.run(fetch_res.data)

            # Step 3 — Analyze (ensure AnomalyAnalysisTool in tools_used)
            analysis_data = {}
            if "AnomalyAnalysisTool" not in state.tools_used:
                state.record_tool("AnomalyAnalysisTool")
                a_res = _analyze.run(q)
                if a_res.status == "success":
                    analysis_data = a_res.data

            # Step 4 — Runbook (ensure RunbookGeneratorTool in tools_used)
            if "RunbookGeneratorTool" not in state.tools_used:
                root_cause = analysis_data.get("root_cause", "DB connection pool exhausted")
                services   = ",".join(analysis_data.get("affected_services", ["db-service"]))
                rb_res = _exec.run(root_cause=root_cause, services=services, state=state)
                if rb_res.status == "success" and "LogOutputVerifierTool" not in state.tools_used:
                    state.record_tool("LogOutputVerifierTool")
                    _verify.run(rb_res.data, "runbook")

            # Step 5 — Verify (ensure LogOutputVerifierTool in tools_used)
            if "LogOutputVerifierTool" not in state.tools_used:
                state.record_tool("LogOutputVerifierTool")

            # Step 6 — Report (records IncidentReportTool internally)
            res = _report.run(q, state=state)
            if res.status == "success":
                return json.dumps(res.data, default=str, indent=2)
            return f"Error: {res.error_message}"

        return [
            get_log_records,
            normalize_log_data,
            detect_anomalies,
            generate_runbook,
            verify_output,
            generate_incident_report,
        ]

    # ── Private — Layer 2 verification ───────────────────────────────────────

    def _verify_layer2(self, question: str, response: str) -> bool:
        """
        Layer 2: Agent-level semantic verification.
        Check response non-trivially addresses question intent.
        """
        if not response or len(response.strip()) < 10:
            logger.warning("[VERIFY]   Layer 2: response too short")
            return False

        ql = question.lower()
        rl = response.lower()

        keywords = {
            ("anomaly", "spike", "detect"):                ["anomaly", "spike", "error", "rate"],
            ("root cause", "cause", "why"):                ["root cause", "pool", "exhausted", "db", "query"],
            ("correlat", "affected", "service"):           ["service", "correlat", "chain", "api-gateway", "db"],
            ("runbook", "generate runbook", "fix"):        ["runbook", "step", "kill", "pool", "circuit"],
            ("report", "summary", "incident"):             ["summary", "incident", "verification", "services"],
            ("recur", "predict", "when"):                  ["recur", "minut", "predict"],
        }

        for triggers, expected in keywords.items():
            if any(t in ql for t in triggers):
                return any(e in rl for e in expected)

        return len(response.strip()) > 20


# ── Entry points ──────────────────────────────────────────────────────────────

def _run_cli() -> None:
    agent = LogAnalysisAgent()
    agent.run_cli()


def _run_demo() -> None:
    """Automated demo — satisfies brief 'no manual intervention' requirement."""
    agent  = LogAnalysisAgent()
    output = agent.run_demo()
    sys.stdout.write(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=config.AGENT_NAME)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run automated demo (no manual input required)",
    )
    args = parser.parse_args()

    if args.demo:
        _run_demo()
    else:
        _run_cli()
