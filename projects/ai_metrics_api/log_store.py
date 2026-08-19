"""Log storage backends for inference observability."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from projects.ai_metrics_api.prometheus_histogram import (
    build_latency_histogram_prometheus,
    build_latency_histogram_prometheus_from_records,
)
from projects.log_analyzer.analyze_logs import (
    analyze_records,
    is_valid_record,
    parse_log_line,
)


class InferenceLogStore:
    def __init__(
        self,
        backend: str = "file",
        log_path: str | Path = "data/day02/inference.log",
        sqlite_path: str | Path = "data/day02/inference.sqlite3",
    ):
        self.backend = backend.lower()
        self.log_path = Path(log_path)
        self.sqlite_path = Path(sqlite_path)

        if self.backend not in {"file", "sqlite"}:
            raise ValueError(f"unsupported log backend: {backend}")

    def append(self, log_line: str) -> None:
        if self.backend == "sqlite":
            self._append_sqlite(log_line)
            return

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

    def load_records(self) -> list[dict]:
        if self.backend == "sqlite":
            return self._load_sqlite_records()

        if not self.log_path.exists():
            return []

        records = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            record = parse_log_line(line)
            if is_valid_record(record):
                records.append(record)
        return records

    def analyze(self) -> dict:
        return analyze_records(self.load_records())

    def build_latency_histogram_prometheus(self) -> list[str]:
        if self.backend == "sqlite":
            return build_latency_histogram_prometheus_from_records(self.load_records())
        return build_latency_histogram_prometheus(self.log_path)

    def _connect(self):
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.sqlite_path)

    def _ensure_schema(self, conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inference_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                request_id TEXT NOT NULL,
                trace_id TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL
            )
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(inference_logs)").fetchall()
        }
        if "trace_id" not in columns:
            conn.execute(
                "ALTER TABLE inference_logs ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''"
            )

    def _append_sqlite(self, log_line: str) -> None:
        record = parse_log_line(log_line)
        if not is_valid_record(record):
            return

        timestamp = log_line.strip().split()[0]
        if "=" in timestamp:
            timestamp = ""

        with self._connect() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO inference_logs (
                    created_at,
                    request_id,
                    trace_id,
                    model,
                    endpoint,
                    status,
                    latency_ms,
                    tokens_in,
                    tokens_out
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    record["request_id"],
                    record.get("trace_id", ""),
                    record["model"],
                    record.get("endpoint", ""),
                    int(record["status"]),
                    int(record["latency_ms"]),
                    int(record["tokens_in"]),
                    int(record["tokens_out"]),
                ),
            )

    def _load_sqlite_records(self) -> list[dict]:
        if not self.sqlite_path.exists():
            return []

        with self._connect() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT
                    request_id,
                    trace_id,
                    model,
                    endpoint,
                    status,
                    latency_ms,
                    tokens_in,
                    tokens_out
                FROM inference_logs
                ORDER BY id
                """
            ).fetchall()

        records = []
        for row in rows:
            request_id, trace_id, model, endpoint, status, latency_ms, tokens_in, tokens_out = row
            records.append(
                {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "model": model,
                    "endpoint": endpoint,
                    "status": str(status),
                    "latency_ms": str(latency_ms),
                    "tokens_in": str(tokens_in),
                    "tokens_out": str(tokens_out),
                }
            )
        return records
