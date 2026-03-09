"""
8-K Item 1.01 Scanner - Configuration
Copy this to config.py and fill in your credentials.
NEVER commit config.py to GitHub.
"""

# =============================================================================
# EMAIL SETTINGS
# =============================================================================
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your_email@gmail.com',
    'sender_password': 'xxxx xxxx xxxx xxxx',  # Gmail App Password
    'recipient_email': 'your_email@gmail.com',
}

# =============================================================================
# SEC EDGAR SETTINGS
# =============================================================================
EDGAR_CONFIG = {
    # SEC requires User-Agent with name and email
    'user_agent': 'YourName your_email@gmail.com',
    # Conservative rate limit (SEC allows 10/sec)
    'request_delay': 0.15,
    # EFTS full-text search endpoint
    'efts_base_url': 'https://efts.sec.gov/LATEST/search-index',
    # Company tickers mapping (CIK to ticker)
    'tickers_url': 'https://www.sec.gov/files/company_tickers.json',
}

# =============================================================================
# L2 SIGNAL FILTERS (from backtest validation)
# =============================================================================
FILTERS = {
    # Price filter: stocks >= $50 showed strongest signal
    'min_price': 50.0,
    # VIX regime: signal works best 15-30, dies above 30
    'vix_min': 15.0,
    'vix_max': 30.0,
    # Sectors where signal is weak or reversed
    'excluded_sectors': [
        'Basic Materials',
        'Utilities',
    ],
    # Insider sell lookback window (days before 8-K filing)
    'insider_lookback_days': 90,
}

# =============================================================================
# SCORING WEIGHTS
# =============================================================================
SCORING = {
    'base_score': 1,           # Any 1.01 filing passing filters
    'insider_sell_bonus': 2,   # Insider selling confirmed in lookback
    'large_cap_bonus': 1,      # Price >= $100
    'optimal_vix_bonus': 1,    # VIX in sweet spot 15-20
    'alert_threshold': 1,      # Minimum score for email inclusion
}

# =============================================================================
# DATABASE
# =============================================================================
DB_PATH = 'eight_k_filings.db'

# =============================================================================
# FORM 4 CROSS-REFERENCE (optional)
# =============================================================================
# Path to Form 4 DB for insider sell confirmation. None = skip cross-ref.
FORM4_DB_PATH = '../form4_scanner/insider_transactions.db'
