#!/usr/bin/env python3
"""8-K Item 1.01 Scanner - Main. Run: python3 main.py [--dry-run|--test-email|--lookback N]"""
import sys, os, time, logging, argparse
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger(__name__)

# Run-level logging — one row per scanner run (ran-at, source status, N evaluated).
SIGNAL_INTEL_DB = os.path.expanduser('~/signal_intelligence.db')

def log_scan_run(scanner, source_status, n_evaluated, n_fired=0, note='', db_path=None):
    """Append exactly one row per scanner run to the shared signal-intelligence DB.

    A run that evaluated nothing (empty or unreachable EDGAR feed) is otherwise
    indistinguishable from a scanner that never ran, so without this row the
    scanner looks dead in the cross-scanner monitor. Never raises.
    """
    try:
        import sqlite3 as _sl
        db = db_path or SIGNAL_INTEL_DB
        c = _sl.connect(db)
        c.execute('CREATE TABLE IF NOT EXISTS scan_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TEXT DEFAULT CURRENT_TIMESTAMP, scanner TEXT, source_status TEXT, n_evaluated INTEGER, n_fired INTEGER, note TEXT)')
        c.execute('INSERT INTO scan_runs (scanner, source_status, n_evaluated, n_fired, note) VALUES (?,?,?,?,?)',
                  (scanner, source_status, n_evaluated, n_fired, note))
        c.commit(); c.close()
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--test-email', action='store_true')
    ap.add_argument('--lookback', type=int, default=2)
    a = ap.parse_args()
    t0 = time.time()
    log.info(f"=== 8-K 1.01 SCANNER | {datetime.now():%Y-%m-%d %H:%M} | {'DRY' if a.dry_run else 'LIVE'} ===")
    try:
        from config import EMAIL_CONFIG, EDGAR_CONFIG, FILTERS, SCORING, DB_PATH, FORM4_DB_PATH
    except ImportError:
        log.error("No config.py! Copy config_example.py -> config.py"); sys.exit(1)
    from database import EightKDatabase
    from edgar_fetcher import EdgarFetcher
    from signal_filter import SignalFilter
    from emailer import send_alert
    if a.test_email:
        ta = [{'ticker':'TEST','company_name':'Test Corp','signal_score':3,'price_at_scan':150.0,
               'sector':'Technology','filing_date':datetime.now().strftime('%Y-%m-%d'),
               'filing_url':'https://sec.gov','insider_sells_90d':2,'insider_sell_value':500000}]
        ok = send_alert(EMAIL_CONFIG, ta, [], {'vix':18.5,'total_101':25,'insider_xref':True})
        sys.exit(0 if ok else 1)
    db = EightKDatabase(DB_PATH)
    fetcher = EdgarFetcher(EDGAR_CONFIG)
    filt = SignalFilter(FILTERS, SCORING, FORM4_DB_PATH)
    errs = []
    # Run-level accounting — one row logged per run in the finally block below,
    # so an unreachable EDGAR feed ('FETCH_FAIL') or an empty feed ('EMPTY') is
    # visible in the shared DB, not silent.
    run = {'source_status': 'FETCH_FAIL', 'n_evaluated': 0, 'n_fired': 0}
    try:
        log.info(f"Fetching (lookback={a.lookback}d)...")
        try:
            filings = fetcher.fetch_recent_8k_101(a.lookback)
        except Exception as e:
            log.error(f"Fetch: {e}"); errs.append(str(e)); filings = []
        else:
            run['source_status'] = 'OK' if filings else 'EMPTY'
        new = [f for f in filings if not db.filing_exists(f['accession_number'])]
        run['n_evaluated'] = len(new)
        log.info(f"Found:{len(filings)} New:{len(new)}")
        log.info("Filtering + scoring...")
        try:
            scored = filt.filter_and_score(new)
        except Exception as e:
            log.error(f"Filter: {e}"); errs.append(str(e)); scored = new
        thr = SCORING.get('alert_threshold', 1)
        alerts = [f for f in scored if f.get('passed_filters') and f.get('signal_score',0)>=thr]
        filtered = [f for f in scored if not f.get('passed_filters')]
        run['n_fired'] = len(alerts)
        log.info(f"Alerts:{len(alerts)} Filtered:{len(filtered)}")
        for f in scored:
            f['scan_date'] = datetime.now().strftime('%Y-%m-%d')
            if f in alerts:
                f['alerted'], f['alert_date'] = 1, datetime.now().strftime('%Y-%m-%d')
            db.save_filing(f)
        ss = {'vix':filt.get_vix(),'total_101':len(filings),
              'insider_xref':bool(FORM4_DB_PATH and os.path.exists(str(FORM4_DB_PATH or '')))}
        ok = send_alert(EMAIL_CONFIG, alerts, filtered, ss, dry_run=a.dry_run)
        el = time.time()-t0
        db.log_scan({'scan_date':datetime.now().strftime('%Y-%m-%d %H:%M'),
                     'total_8k_found':len(filings),'item_101_found':len(new),
                     'passed_filters':len(alerts),'alerts_sent':len(alerts) if ok else 0,
                     'vix_level':filt.get_vix(),'errors':';'.join(errs) or None,
                     'duration_seconds':el})
        st = db.get_stats()
        log.info(f"DONE {el:.1f}s | Alerts:{len(alerts)} Email:{'OK' if ok else 'FAIL'} | "
                 f"DB: {st['total_filings']} total {st['alerts_sent']} alerted")
        db.close()
    finally:
        log_scan_run('EIGHTK_101', run['source_status'], run['n_evaluated'], run['n_fired'])

if __name__ == '__main__':
    main()
