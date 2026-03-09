"""
8-K Item 1.01 Scanner - Email Alerts

Actionable format:
  TRADE (Score 2+) — ticker, company, price, sector, action line
  WATCH (Score 1)  — compact one-liner
  Filtered         — single count line
"""
import re
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────

def _clean_name(name, ticker=None):
    """Strip CIK numbers, ticker duplicates, and state suffixes."""
    if not name:
        return 'Unknown'
    name = re.sub(r'\s*\(?\s*CIK[:\s#]*\d+\s*\)?\s*', '', name)
    if ticker:
        name = re.sub(rf'\s*\({re.escape(ticker)}\)\s*', '', name,
                       flags=re.IGNORECASE)
    name = re.sub(r'\s*/[A-Z]{2}/\s*$', '', name)
    return name.strip().rstrip('.') or 'Unknown'


def _next_trading_day(date_str):
    """Next Mon-Fri after date_str (YYYY-MM-DD)."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
    dt += timedelta(days=1)
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt


def _add_trading_days(date_str, n):
    """Add n trading days to date_str (YYYY-MM-DD)."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
    added = 0
    while added < n:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            added += 1
    return dt


def _action_line_html(f):
    """Build SHORT action line: entry day, stop, exit date."""
    price = f.get('price_at_scan')
    filing_date = f.get('filing_date', '')
    entry_dt = _next_trading_day(filing_date)
    exit_dt = _add_trading_days(filing_date, 5)

    entry_str = entry_dt.strftime('%a %b %-d') if entry_dt else 'Next open'
    exit_str = exit_dt.strftime('%a %b %-d') if exit_dt else '+5 trading days'
    stop_str = f"${price * 1.03:.2f}" if price else 'Entry +3%'

    return (f'<div style="background:#fff0f0;border-left:4px solid #dc3545;'
            f'padding:8px 12px;margin-top:10px;font-size:13px;'
            f'font-weight:600;color:#333">'
            f'SHORT at {entry_str} open &nbsp;|&nbsp; '
            f'Stop {stop_str} &nbsp;|&nbsp; '
            f'Exit {exit_str}'
            f'</div>')


# ── HTML Builder ─────────────────────────────────────────────────

def build_html(alerts, filtered, stats):
    now = datetime.now().strftime('%B %d, %Y %I:%M %p')
    vix = stats.get('vix')
    vix_str = f"{vix:.1f}" if isinstance(vix, (int, float)) else 'N/A'

    # Split: TRADE (score 2+) vs WATCH (score 1)
    trades = sorted(
        [a for a in alerts if a.get('signal_score', 0) >= 2],
        key=lambda x: x.get('signal_score', 0), reverse=True)
    watches = [a for a in alerts if a.get('signal_score', 0) == 1]
    n_filtered = len(filtered) if filtered else 0

    # Header banner
    if trades:
        hbg, htxt = '#dc3545', (f'{len(trades)} SHORT SIGNAL'
                                f'{"S" if len(trades) != 1 else ""}')
    elif watches:
        hbg, htxt = '#fd7e14', (f'{len(watches)} WATCH SIGNAL'
                                f'{"S" if len(watches) != 1 else ""}'
                                ' (no trades)')
    else:
        hbg, htxt = '#6c757d', 'NO SIGNALS TODAY'

    h = (f'<html><body style="font-family:Arial,sans-serif;'
         f'max-width:700px;margin:auto;padding:0">'
         # Header
         f'<div style="background:{hbg};color:white;padding:20px;'
         f'text-align:center">'
         f'<h1 style="margin:0;font-size:22px">8-K Item 1.01</h1>'
         f'<p style="margin:5px 0 0;font-size:20px;font-weight:bold">'
         f'{htxt}</p>'
         f'<p style="margin:5px 0 0;font-size:12px;opacity:0.85">'
         f'{now} | VIX: {vix_str}</p>'
         f'</div>')

    # ── VIX Warning Banner ──
    if isinstance(vix, (int, float)) and vix >= 25:
        h += (f'<div style="background:#fff3cd;border-left:5px solid #ff9800;'
              f'padding:12px 15px;font-size:14px;font-weight:bold;'
              f'color:#856404">'
              f'VIX {vix:.1f} — Elevated volatility. '
              f'Consider half-sizing positions and wider stops.</div>')

    # ── TRADE Section (Score 2+) ──
    if trades:
        h += ('<div style="padding:15px">'
              '<h2 style="margin:0 0 12px;font-size:16px;color:#dc3545;'
              'border-bottom:2px solid #dc3545;padding-bottom:6px">'
              'TRADE — SHORT SIGNALS</h2>')

        for f in trades:
            sc = f.get('signal_score', 0)
            ticker = f.get('ticker', 'N/A')
            company = _clean_name(f.get('company_name', ''), ticker)
            price = f.get('price_at_scan')
            price_str = f"${price:.2f}" if price else 'N/A'
            sector = f.get('sector', 'N/A')
            url = f.get('filing_url', '#')

            badge_bg = ('#dc3545' if sc >= 4 else
                        '#e65100' if sc >= 3 else '#fd7e14')

            # Insider sells overlay
            ins = ''
            if f.get('insider_sells_90d', 0) > 0:
                ins = (f'<div style="color:#dc3545;font-size:12px;'
                       f'font-weight:bold;margin-top:4px">'
                       f'INSIDER SELLS: {f["insider_sells_90d"]} txns '
                       f'${f.get("insider_sell_value", 0):,.0f} (90d)</div>')

            h += (f'<div style="background:white;border:1px solid #e0e0e0;'
                  f'border-radius:8px;padding:15px;margin-bottom:12px">'
                  # Row 1: ticker + score
                  f'<div style="display:flex;justify-content:space-between;'
                  f'align-items:center">'
                  f'<div>'
                  f'<span style="font-size:22px;font-weight:bold">'
                  f'{ticker}</span>'
                  f'<span style="color:#666;font-size:13px;margin-left:8px">'
                  f'{company}</span>'
                  f'</div>'
                  f'<span style="background:{badge_bg};color:white;'
                  f'padding:4px 10px;border-radius:4px;font-weight:bold;'
                  f'font-size:14px">Score {sc}</span>'
                  f'</div>'
                  # Row 2: price / sector / link
                  f'<div style="color:#555;font-size:13px;margin-top:4px">'
                  f'{price_str} | {sector} | '
                  f'<a href="{url}" style="color:#2196F3">EDGAR</a></div>'
                  # Insider sells
                  f'{ins}'
                  # Action line
                  f'{_action_line_html(f)}'
                  f'</div>')

        h += '</div>'

    # ── WATCH Section (Score 1) ──
    if watches:
        h += ('<div style="padding:0 15px 15px">'
              '<h2 style="margin:0 0 8px;font-size:14px;color:#6c757d;'
              'border-bottom:1px solid #dee2e6;padding-bottom:4px">'
              'WATCH — Low Conviction (Score 1)</h2>')

        for f in watches:
            ticker = f.get('ticker', 'N/A')
            company = _clean_name(f.get('company_name', ''), ticker)
            price = f.get('price_at_scan')
            price_str = f"${price:.2f}" if price else 'N/A'
            sector = f.get('sector', '')
            url = f.get('filing_url', '#')

            h += (f'<div style="font-size:13px;padding:4px 0;color:#555">'
                  f'<b>{ticker}</b> {company} — {price_str} — {sector} '
                  f'<a href="{url}" style="color:#2196F3;font-size:12px">'
                  f'EDGAR</a></div>')

        h += '</div>'

    # ── Filtered Count ──
    if n_filtered:
        h += (f'<div style="padding:4px 15px 12px;font-size:12px;'
              f'color:#999">'
              f'{n_filtered} filings filtered (price/sector/VIX)</div>')

    # ── Footer ──
    h += ('<div style="padding:10px 15px;font-size:11px;color:#aaa;'
          'border-top:1px solid #eee">'
          'Backtest: -2.89% avg 5d (t=-9.98) | '
          'Filters: $50+, VIX 15-30, excl Basic Materials/Utilities | '
          'Not financial advice.</div></body></html>')
    return h


# ── Send ─────────────────────────────────────────────────────────

def send_alert(email_cfg, alerts, filtered, stats, dry_run=False):
    html = build_html(alerts, filtered, stats)

    # Subject with actual tickers
    trades = [a for a in alerts if a.get('signal_score', 0) >= 2]
    watches = [a for a in alerts if a.get('signal_score', 0) == 1]

    if trades:
        names = [a.get('ticker', '?') for a in sorted(
            trades, key=lambda x: x.get('signal_score', 0), reverse=True)]
        subj = f"8-K SHORT: {', '.join(names[:6])}"
        if len(names) > 6:
            subj += f" +{len(names) - 6}"
    elif watches:
        names = [a.get('ticker', '?') for a in watches]
        subj = f"8-K WATCH: {', '.join(names[:6])}"
        if len(names) > 6:
            subj += f" +{len(names) - 6}"
    else:
        subj = "8-K: No signals today"

    if dry_run:
        logger.info(f"[DRY RUN] {subj}")
        with open('last_email_preview.html', 'w') as f:
            f.write(html)
        logger.info("[DRY RUN] Saved to last_email_preview.html")
        return True

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subj
    msg['From'] = email_cfg['sender_email']
    msg['To'] = email_cfg['recipient_email']
    msg.attach(MIMEText(html, 'html'))
    try:
        srv = smtplib.SMTP(email_cfg['smtp_server'], email_cfg['smtp_port'])
        srv.starttls()
        srv.login(email_cfg['sender_email'], email_cfg['sender_password'])
        srv.send_message(msg)
        srv.quit()
        logger.info(f"Email sent: {subj}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False
