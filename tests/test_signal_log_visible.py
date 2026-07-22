"""A signal-log write failure must be VISIBLE, not silently swallowed.

The per-signal ``log_signal_intelligence`` writer must not swallow a failed
write with a bare ``except: pass`` -- a silent failure is indistinguishable
from a scanner that logged nothing. On write failure it must print a
one-line ``[SIGNAL_LOG_FAIL]`` diagnostic and keep going (never re-raise).

conftest injects a *fake* ``signal_filter`` into sys.modules so main() runs
offline; load the REAL module by file path here (without disturbing the fake)
to exercise the actual writer.
"""
import importlib.util
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "_real_signal_filter", os.path.join(_REPO, "signal_filter.py"))
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


def test_signal_log_failure_is_printed(capsys, monkeypatch):
    # Force the DB write to fail by pointing the hardcoded path at an unwritable dir.
    monkeypatch.setattr(sf.os.path, "expanduser",
                        lambda p: "/does/not/exist/nope/signal_intelligence.db")
    # Must not raise.
    sf.log_signal_intelligence("2026-07-22", "8K", "ABC", "LONG", 1)
    out = capsys.readouterr().out
    assert "[SIGNAL_LOG_FAIL]" in out
    assert "8K" in out and "ABC" in out
