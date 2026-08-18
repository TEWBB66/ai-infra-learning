import csv
import json
from pathlib import Path

import pytest

from scripts import serving_benchmark_matrix as sbm


def test_parse_int_list_accepts_comma_values():
    assert sbm.parse_int_list("1,2, 4") == [1, 2, 4]


@pytest.mark.parametrize("value", ["", "0", "-1", "1,nope"])
def test_parse_int_list_rejects_invalid_values(value):
    with pytest.raises(argparse_error()):
        sbm.parse_int_list(value)


def argparse_error():
    import argparse

    return argparse.ArgumentTypeError


def test_build_cases_expands_repeats_in_stable_order():
    cases = sbm.build_cases([1, 2], [32, 128], repeats=2)
    assert cases == [
        {"repeat": 1, "concurrency": 1, "max_tokens": 32},
        {"repeat": 1, "concurrency": 2, "max_tokens": 32},
        {"repeat": 1, "concurrency": 1, "max_tokens": 128},
        {"repeat": 1, "concurrency": 2, "max_tokens": 128},
        {"repeat": 2, "concurrency": 1, "max_tokens": 32},
        {"repeat": 2, "concurrency": 2, "max_tokens": 32},
        {"repeat": 2, "concurrency": 1, "max_tokens": 128},
        {"repeat": 2, "concurrency": 2, "max_tokens": 128},
    ]


def test_summarize_results_counts_status_and_latency():
    case = {"repeat": 1, "concurrency": 2, "max_tokens": 32}
    results = [
        {"http_status": 200, "logical_status": 200, "client_latency_ms": 100, "tokens_out": 10},
        {"http_status": 429, "logical_status": 429, "client_latency_ms": 20, "tokens_out": 0},
        {"http_status": 200, "logical_status": 200, "client_latency_ms": 200, "tokens_out": 12},
    ]

    summary = sbm.summarize_results(case, results, elapsed_sec=2.0)

    assert summary["total_requests"] == 3
    assert summary["http_status_counts"] == {"200": 2, "429": 1}
    assert summary["logical_status_counts"] == {"200": 2, "429": 1}
    assert summary["rejected_count_429"] == 1
    assert summary["avg_client_latency_ms"] == 106.667
    assert summary["throughput_req_per_sec"] == 1.5
    assert summary["output_tokens_per_sec"] == 11.0


def test_dry_run_writes_metadata_csv_markdown_and_cases(tmp_path):
    output_dir = tmp_path / "bench"

    rc = sbm.main(
        [
            "--dry-run",
            "--quiet",
            "--output-dir",
            str(output_dir),
            "--concurrency-matrix",
            "1,2",
            "--max-tokens-matrix",
            "32,128",
            "--repeats",
            "2",
            "--count",
            "5",
        ]
    )

    assert rc == 0
    assert (output_dir / "metadata.json").exists()
    assert (output_dir / "dry_run_cases.json").exists()
    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "raw_results.jsonl").read_text() == ""

    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert metadata["dry_run"] is True
    assert metadata["case_count"] == 8

    with (output_dir / "summary.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 8
    assert rows[0]["total_requests"] == "0"

    markdown = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "Serving Benchmark Matrix Report" in markdown
    assert "| repeat | concurrency | max_tokens |" in markdown
