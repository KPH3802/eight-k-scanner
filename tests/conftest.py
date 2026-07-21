"""Offline scaffolding for the 8-K scanner.

main() imports config + four app modules (database, edgar_fetcher, signal_filter,
emailer) lazily. Inject light fakes via sys.modules so main() can be driven
offline without EDGAR / SMTP / yfinance. No real credentials are introduced.
"""
import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- fake config ---
if "config" not in sys.modules:
    _cfg = types.ModuleType("config")
    _cfg.EMAIL_CONFIG = {}
    _cfg.EDGAR_CONFIG = {}
    _cfg.FILTERS = {}
    _cfg.SCORING = {"alert_threshold": 1}
    _cfg.DB_PATH = ":memory:"
    _cfg.FORM4_DB_PATH = None
    sys.modules["config"] = _cfg

# --- fake database module ---
if "database" not in sys.modules:
    _db = types.ModuleType("database")

    class EightKDatabase:
        def __init__(self, *a, **k):
            pass

        def filing_exists(self, acc):
            return False

        def save_filing(self, f):
            pass

        def log_scan(self, d):
            pass

        def get_stats(self):
            return {"total_filings": 0, "alerts_sent": 0}

        def close(self):
            pass

    _db.EightKDatabase = EightKDatabase
    sys.modules["database"] = _db

# --- fake edgar_fetcher (fetch raises -> FETCH_FAIL path) ---
if "edgar_fetcher" not in sys.modules:
    _ef = types.ModuleType("edgar_fetcher")

    class EdgarFetcher:
        def __init__(self, *a, **k):
            pass

        def fetch_recent_8k_101(self, lookback):
            raise RuntimeError("simulated EDGAR outage")

    _ef.EdgarFetcher = EdgarFetcher
    sys.modules["edgar_fetcher"] = _ef

# --- fake signal_filter ---
if "signal_filter" not in sys.modules:
    _sf = types.ModuleType("signal_filter")

    class SignalFilter:
        def __init__(self, *a, **k):
            pass

        def filter_and_score(self, new):
            return []

        def get_vix(self):
            return 18.0

    _sf.SignalFilter = SignalFilter
    sys.modules["signal_filter"] = _sf

# --- fake emailer ---
if "emailer" not in sys.modules:
    _em = types.ModuleType("emailer")
    _em.send_alert = lambda *a, **k: True
    sys.modules["emailer"] = _em
