"""
Shared pytest fixtures for log analysis agent tests.
All unit tests use these fixtures — never read real CSVs directly.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Generator

import pytest


SAMPLE_INCIDENTS_RECORDS = [
    {
        "incident_id":        "INC001",
        "date":               "2023-11-02",
        "time_range":         "14:10-14:35",
        "root_cause_type":    "pool_exhausted",
        "root_cause_service": "db-service",
        "affected_services":  "api-gateway,checkout-service,db-service",
        "error_pattern":      "DB connection pool exhausted slow query blocking",
        "resolution_minutes": "25",
        "recurrence_days":    "14",
        "runbook_id":         "RB-HIST-001",
    },
    {
        "incident_id":        "INC003",
        "date":               "2023-12-05",
        "time_range":         "22:45-23:10",
        "root_cause_type":    "pool_exhausted",
        "root_cause_service": "db-service",
        "affected_services":  "api-gateway,checkout-service,db-service,cache-service",
        "error_pattern":      "DB connection pool exhausted active=100 max=100 waiting cascade",
        "resolution_minutes": "30",
        "recurrence_days":    "10",
        "runbook_id":         "RB-HIST-003",
    },
    {
        "incident_id":        "INC005",
        "date":               "2024-01-03",
        "time_range":         "16:00-16:22",
        "root_cause_type":    "cache_failure",
        "root_cause_service": "cache-service",
        "affected_services":  "api-gateway,cache-service",
        "error_pattern":      "cache write failed backend unreachable eviction failed",
        "resolution_minutes": "22",
        "recurrence_days":    "7",
        "runbook_id":         "RB-HIST-005",
    },
]


SAMPLE_PRIMARY_RECORDS = [
    {
        "log_id":     "LOG001",
        "timestamp":  "2024-01-15 15:20:00",
        "service":    "api-gateway",
        "source":     "nginx",
        "level":      "INFO",
        "error_code": "200",
        "message":    "GET /api/checkout 200 OK",
        "request_id": "REQ001",
        "host":       "app-node-01",
        "duration_ms": "45",
    },
    {
        "log_id":     "LOG013",
        "timestamp":  "2024-01-15 15:22:08",
        "service":    "db-service",
        "source":     "application",
        "level":      "CRITICAL",
        "error_code": "500",
        "message":    "DB connection pool exhausted: active=100 max=100 waiting=47 slow_query_id=4821",
        "request_id": "REQ005",
        "host":       "db-node-01",
        "duration_ms": "0",
    },
    {
        "log_id":     "LOG010",
        "timestamp":  "2024-01-15 15:22:00",
        "service":    "checkout-service",
        "source":     "application",
        "level":      "ERROR",
        "error_code": "500",
        "message":    "connection timeout after 5000ms: upstream db-service unresponsive",
        "request_id": "REQ004",
        "host":       "app-node-02",
        "duration_ms": "5000",
    },
]


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Isolated temp directory with pre-populated logs.csv and incidents.csv for each test.
    """
    primary_path   = tmp_path / "logs.csv"
    incidents_path = tmp_path / "incidents.csv"
    if SAMPLE_PRIMARY_RECORDS:
        _write_csv(primary_path, SAMPLE_PRIMARY_RECORDS)
    if SAMPLE_INCIDENTS_RECORDS:
        _write_csv(incidents_path, SAMPLE_INCIDENTS_RECORDS)
    yield tmp_path


@pytest.fixture
def sample_incidents_record() -> dict:
    """Return the first sample past incident (pool_exhausted matching record)."""
    return dict(SAMPLE_INCIDENTS_RECORDS[0])


@pytest.fixture
def sample_primary_record() -> dict:
    """Return the first sample record (happy-path INFO log)."""
    return dict(SAMPLE_PRIMARY_RECORDS[0])


@pytest.fixture
def sample_high_risk_record() -> dict:
    """Return the CRITICAL db-service record (high-risk case)."""
    return dict(SAMPLE_PRIMARY_RECORDS[1])


@pytest.fixture
def sample_logs_payload() -> dict:
    """Return a logs payload dict as returned by LogRetrieverTool."""
    return {
        "logs":  [dict(r) for r in SAMPLE_PRIMARY_RECORDS],
        "count": len(SAMPLE_PRIMARY_RECORDS),
    }


def _write_csv(path: Path, records: list) -> None:
    """Write list of dicts to CSV."""
    if not records:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
