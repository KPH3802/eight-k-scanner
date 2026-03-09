#!/usr/bin/env python3
"""8-K Item 1.01 Scanner - Main. Run: python3 main.py [--dry-run|--test-email|--lookback N]"""
import sys, os, time, logging, argparse
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger(__name__)

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
    log.info(f"Fetching (lookback={a.lookback}d)...")
    try:
        filings = fetcher.fetch_recent_8k_101(a.lookback)
    except Exception as e:
        log.error(f"Fetch: {e}"); errs.append(str(e)); filings = []
    new = [f for f in filings if not db.filing_exists(f['accession_number'])]
    log.info(f"Found:{len(filings)} New:{len(new)}")
    log.info("Filtering + scoring...")
    try:
        scored = filt.filter_and_score(new)
    except Exception as e:
        log.error(f"Filter: {e}"); errs.append(str(e)); scored = new
    thr = SCORING.get('alert_threshold', 1)
    alerts = [f for f in scored if f.get('passed_filters') and f.get('signal_score',0)>=thr]
    filtered = [f for f in scored if not f.get('passed_filters')]
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

if __name__ == '__main__':
    main()
