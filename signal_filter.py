"""
8-K Item 1.01 Scanner - Signal Filter
Applies L2 filters (price, VIX, sector) and scores signals.
"""
import logging
import sqlite3
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    logger.warning("yfinance not installed - filters disabled")


# ---------------------------------------------------------------------------
# Signal Intelligence — live logging
# ---------------------------------------------------------------------------
def log_signal_intelligence(scan_date, scanner, ticker, direction, fired,
                             signal_strength=None, signal_bucket=None,
                             regime_filter_passed=None, regime_value=None,
                             score=None):
    try:
        import sqlite3 as _sl
        db = os.path.expanduser('~/signal_intelligence.db')
        c = _sl.connect(db)
        c.execute('CREATE TABLE IF NOT EXISTS signal_log (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_date TEXT, scanner TEXT, ticker TEXT, direction TEXT, fired INTEGER, signal_strength REAL, signal_bucket TEXT, regime_filter_passed INTEGER, regime_value REAL, score INTEGER, autotrader_acted INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('INSERT INTO signal_log (scan_date,scanner,ticker,direction,fired,signal_strength,signal_bucket,regime_filter_passed,regime_value,score) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (scan_date,scanner,ticker,direction,fired,signal_strength,signal_bucket,regime_filter_passed,regime_value,score))
        c.commit(); c.close()
    except Exception:
        pass


class SignalFilter:
    def __init__(self, filters_cfg, scoring_cfg, form4_db=None):
        self.filters = filters_cfg
        self.scoring = scoring_cfg
        self.form4_db = form4_db
        self._vix = None

    def get_vix(self):
        if self._vix is not None:
            return self._vix
        if not HAS_YF:
            return None
        try:
            h = yf.Ticker('^VIX').history(period='1d')
            if not h.empty:
                self._vix = float(h['Close'].iloc[-1])
                logger.info(f"VIX: {self._vix:.1f}")
            return self._vix
        except Exception as e:
            logger.warning(f"VIX fetch failed: {e}")
            return None

    def get_stock(self, ticker):
        if not HAS_YF or not ticker:
            return {'price': None, 'sector': None}
        try:
            info = yf.Ticker(ticker).info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            if price is None:
                h = yf.Ticker(ticker).history(period='5d')
                if not h.empty:
                    price = float(h['Close'].iloc[-1])
            return {'price': price, 'sector': info.get('sector', 'Unknown')}
        except Exception as e:
            logger.warning(f"Stock info failed {ticker}: {e}")
            return {'price': None, 'sector': None}

    def check_insider_sells(self, ticker, filing_date):
        if not self.form4_db or not os.path.exists(self.form4_db):
            return {'count': 0, 'value': 0.0, 'available': False}
        try:
            conn = sqlite3.connect(self.form4_db)
            lb = self.filters.get('insider_lookback_days', 90)
            start = (datetime.strptime(filing_date, '%Y-%m-%d')
                     - timedelta(days=lb)).strftime('%Y-%m-%d')
            cur = conn.cursor()
            for tbl in ['transactions', 'form4_transactions', 'insider_transactions']:
                try:
                    cur.execute(f'''
                        SELECT COUNT(*), COALESCE(SUM(ABS(transaction_value)),0)
                        FROM {tbl}
                        WHERE ticker=? AND transaction_type='S'
                        AND transaction_date BETWEEN ? AND ?
                    ''', (ticker, start, filing_date))
                    r = cur.fetchone()
                    conn.close()
                    return {'count': r[0], 'value': r[1], 'available': True}
                except sqlite3.OperationalError:
                    continue
            conn.close()
        except Exception as e:
            logger.warning(f"Form4 cross-ref failed: {e}")
        return {'count': 0, 'value': 0.0, 'available': False}

    def filter_and_score(self, filings):
        vix = self.get_vix()
        results = []
        for f in filings:
            t = f.get('ticker')
            if not t:
                f.update({'notes': 'No ticker', 'passed_filters': 0, 'signal_score': 0})
                results.append(f)
                continue
            s = self.get_stock(t)
            f['price_at_scan'] = s['price']
            f['sector'] = s['sector']
            f['vix_at_scan'] = vix
            reasons, passed = [], True
            mp = self.filters.get('min_price', 50.0)
            if s['price'] is not None and s['price'] < mp:
                passed = False
                reasons.append(f"Price ${s['price']:.2f}<${mp}")
            vmin = self.filters.get('vix_min', 15.0)
            vmax = self.filters.get('vix_max', 30.0)
            if vix and (vix < vmin or vix > vmax):
                passed = False
                reasons.append(f"VIX {vix:.1f} outside {vmin}-{vmax}")
            excl = self.filters.get('excluded_sectors', [])
            if s['sector'] in excl:
                passed = False
                reasons.append(f"Excluded: {s['sector']}")
            f['passed_filters'] = 1 if passed else 0
            f['notes'] = '; '.join(reasons) if reasons else 'Passed all filters'
            score = 0
            if passed:
                score = self.scoring.get('base_score', 1)
                if s['price'] and s['price'] >= 100:
                    score += self.scoring.get('large_cap_bonus', 1)
                if vix and 15 <= vix <= 20:
                    score += self.scoring.get('optimal_vix_bonus', 1)
            ins = self.check_insider_sells(t, f.get('filing_date', ''))
            f['insider_sells_90d'] = ins['count']
            f['insider_sell_value'] = ins['value']
            if ins['count'] > 0 and passed:
                score += self.scoring.get('insider_sell_bonus', 2)
                f['notes'] += f" | INSIDER SELLS: {ins['count']} txns ${ins['value']:,.0f}"
            f['signal_score'] = score
            # Log to signal intelligence
            _scan_date = f.get('filing_date') or f.get('scan_date', '')
            log_signal_intelligence(_scan_date, '8K_1.01', t, 'SHORT',
                                    1 if passed and score >= 2 else 0,
                                    signal_strength=float(score) if score else None,
                                    signal_bucket=str(score) if score else None,
                                    score=score if passed else None)
            results.append(f)
            logger.info(f"  {t}: ${s['price']} {s['sector']} score={score} pass={passed}")
        return results
