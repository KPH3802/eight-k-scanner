"""Run-level logging: one row per scanner run in the shared signal-intelligence DB."""
import sqlite3

import main as eightk


def test_log_scan_run_writes_one_row(tmp_path):
    db = tmp_path / "intel.db"
    eightk.log_scan_run("EIGHTK_101", "OK", 7, n_fired=1, note="unit", db_path=str(db))
    rows = sqlite3.connect(str(db)).execute(
        "SELECT scanner, source_status, n_evaluated, n_fired, note FROM scan_runs"
    ).fetchall()
    assert rows == [("EIGHTK_101", "OK", 7, 1, "unit")]


def test_log_scan_run_never_raises_on_bad_path():
    eightk.log_scan_run("EIGHTK_101", "OK", 1, db_path="/does/not/exist/x.db")


def test_main_logs_run_row_on_fetch_fail(tmp_path, monkeypatch):
    intel = tmp_path / "intel.db"
    monkeypatch.setattr(eightk, "SIGNAL_INTEL_DB", str(intel))
    # conftest's fake EdgarFetcher.fetch_recent_8k_101 raises -> FETCH_FAIL path.
    monkeypatch.setattr(eightk.sys, "argv", ["main.py", "--dry-run"])

    eightk.main()

    rows = sqlite3.connect(str(intel)).execute(
        "SELECT scanner, source_status, n_evaluated, n_fired FROM scan_runs"
    ).fetchall()
    assert rows == [("EIGHTK_101", "FETCH_FAIL", 0, 0)]
