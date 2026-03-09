"""
8-K Item 1.01 Scanner - Database Module
Tracks processed filings to avoid duplicate alerts.
"""
import sqlite3
from datetime import datetime


class EightKDatabase:
    def __init__(self, db_path='eight_k_filings.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS filings (
                accession_number TEXT PRIMARY KEY,
                cik TEXT NOT NULL,
                ticker TEXT,
                company_name TEXT,
                filing_date TEXT NOT NULL,
                acceptance_datetime TEXT,
                items TEXT,
                filing_url TEXT,
                price_at_scan REAL,
                sector TEXT,
                vix_at_scan REAL,
                insider_sells_90d INTEGER DEFAULT 0,
                insider_sell_value REAL DEFAULT 0.0,
                signal_score INTEGER DEFAULT 0,
                passed_filters INTEGER DEFAULT 0,
                alerted INTEGER DEFAULT 0,
                alert_date TEXT,
                scan_date TEXT NOT NULL,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                total_8k_found INTEGER DEFAULT 0,
                item_101_found INTEGER DEFAULT 0,
                passed_filters INTEGER DEFAULT 0,
                alerts_sent INTEGER DEFAULT 0,
                vix_level REAL,
                errors TEXT,
                duration_seconds REAL
            )
        ''')
        self.conn.commit()

    def filing_exists(self, accession_number):
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM filings WHERE accession_number = ?', (accession_number,))
        return cursor.fetchone() is not None

    def save_filing(self, filing_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO filings (
                accession_number, cik, ticker, company_name,
                filing_date, acceptance_datetime, items, filing_url,
                price_at_scan, sector, vix_at_scan,
                insider_sells_90d, insider_sell_value,
                signal_score, passed_filters,
                alerted, alert_date, scan_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filing_data.get('accession_number'), filing_data.get('cik'),
            filing_data.get('ticker'), filing_data.get('company_name'),
            filing_data.get('filing_date'), filing_data.get('acceptance_datetime'),
            filing_data.get('items'), filing_data.get('filing_url'),
            filing_data.get('price_at_scan'), filing_data.get('sector'),
            filing_data.get('vix_at_scan'), filing_data.get('insider_sells_90d', 0),
            filing_data.get('insider_sell_value', 0.0), filing_data.get('signal_score', 0),
            filing_data.get('passed_filters', 0), filing_data.get('alerted', 0),
            filing_data.get('alert_date'),
            filing_data.get('scan_date', datetime.now().strftime('%Y-%m-%d')),
            filing_data.get('notes'),
        ))
        self.conn.commit()

    def log_scan(self, scan_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO scan_log (
                scan_date, total_8k_found, item_101_found,
                passed_filters, alerts_sent, vix_level, errors, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_data.get('scan_date', datetime.now().strftime('%Y-%m-%d %H:%M')),
            scan_data.get('total_8k_found', 0), scan_data.get('item_101_found', 0),
            scan_data.get('passed_filters', 0), scan_data.get('alerts_sent', 0),
            scan_data.get('vix_level'), scan_data.get('errors'),
            scan_data.get('duration_seconds'),
        ))
        self.conn.commit()

    def get_recent_filings(self, days=7):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM filings WHERE scan_date >= date('now', ?)
            ORDER BY filing_date DESC
        ''', (f'-{days} days',))
        return cursor.fetchall()

    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM filings')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM filings WHERE passed_filters = 1')
        passed = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM filings WHERE alerted = 1')
        alerted = cursor.fetchone()[0]
        return {'total_filings': total, 'passed_filters': passed, 'alerts_sent': alerted}

    def close(self):
        self.conn.close()
