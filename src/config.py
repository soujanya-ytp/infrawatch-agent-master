"""
Configuration — load .env, expose typed constants.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL:   str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR:   Path = Path(__file__).parent.parent
DATA_DIR:   Path = BASE_DIR / "data"
OUTPUT_DIR: Path = BASE_DIR / "output"

# ── Agent identity ────────────────────────────────────────────────────────────
DOMAIN:     str = "log-analysis"
AGENT_NAME: str = "Log Analysis & Incident Response Agent"

# ── Retry / timeouts ─────────────────────────────────────────────────────────
MAX_RETRIES:         int = int(os.getenv("MAX_RETRIES", "3"))
MAX_ITERATIONS:      int = int(os.getenv("MAX_ITERATIONS", "10"))
MAX_EXECUTION_TIME:  int = int(os.getenv("MAX_EXECUTION_TIME", "120"))

# ── Domain-specific thresholds ────────────────────────────────────────────────
ANOMALY_HIGH_THRESHOLD:   float = float(os.getenv("ANOMALY_HIGH_THRESHOLD", "80.0"))
ANOMALY_MEDIUM_THRESHOLD: float = float(os.getenv("ANOMALY_MEDIUM_THRESHOLD", "50.0"))
ERROR_RATE_SPIKE_FACTOR:  float = float(os.getenv("ERROR_RATE_SPIKE_FACTOR", "5.0"))
PATTERN_REPEAT_MIN:       int   = int(os.getenv("PATTERN_REPEAT_MIN", "3"))
RECURRENCE_WINDOW_MIN:    int   = int(os.getenv("RECURRENCE_WINDOW_MIN", "5"))
