"""
8-K Item 1.01 Scanner - EDGAR Fetcher
Fetches recent 8-K filings containing Item 1.01 from SEC EDGAR.
Uses EFTS full-text search and company_tickers.json for CIK-to-ticker mapping.
"""
import requests
import json
import time
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EdgarFetcher:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config['user_agent'],
            'Accept': 'application/json',
        })
        self.delay = config.get('request_delay', 0.15)
        self._ticker_map = None

    def _wait(self):
        time.sleep(self.delay)

    def get_ticker_map(self):
        if self._ticker_map is not None:
            return self._ticker_map
        cache = 'company_tickers_cache.json'
        if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) < 86400:
            try:
                with open(cache, 'r') as f:
                    self._ticker_map = json.load(f)
                logger.info(f"Ticker cache loaded: {len(self._ticker_map)} entries")
                return self._ticker_map
            except Exception:
                pass
        url = self.config.get('tickers_url', 'https://www.sec.gov/files/company_tickers.json')
        logger.info(f"Downloading ticker map from SEC...")
        self._wait()
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            tmap = {}
            for entry in raw.values():
                cik = str(entry['cik_str']).zfill(10)
                tmap[cik] = {'ticker': entry['ticker'], 'title': entry.get('title', '')}
            with open(cache, 'w') as f:
                json.dump(tmap, f)
            self._ticker_map = tmap
            logger.info(f"Ticker map: {len(tmap)} companies")
            return self._ticker_map
        except Exception as e:
            logger.error(f"Ticker map download failed: {e}")
            if os.path.exists(cache):
                with open(cache, 'r') as f:
                    self._ticker_map = json.load(f)
                return self._ticker_map
            return {}

    def cik_to_ticker(self, cik):
        tmap = self.get_ticker_map()
        entry = tmap.get(str(cik).zfill(10))
        return entry['ticker'] if entry else None

    def fetch_recent_8k_101(self, lookback_days=2):
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        logger.info(f"Searching EDGAR: 8-K Item 1.01 from {start_date} to {end_date}")
        filings = []
        seen_accessions = set()  # Fix: deduplicate by accession number
        from_idx = 0
        page_size = 50
        for page in range(20):
            self._wait()
            params = {
                'q': '"Item 1.01"',
                'dateRange': 'custom', 'startdt': start_date, 'enddt': end_date,
                'forms': '8-K', 'from': from_idx, 'size': page_size,
            }
            try:
                resp = self.session.get(
                    'https://efts.sec.gov/LATEST/search-index',
                    params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"EDGAR request failed: {e}")
                break
            hits = data.get('hits', {}).get('hits', [])
            total = data.get('hits', {}).get('total', {})
            total_count = total.get('value', 0) if isinstance(total, dict) else total
            if not hits:
                break
            for hit in hits:
                f = self._parse_hit(hit)
                if f:
                    acc = f['accession_number']
                    if acc not in seen_accessions:
                        seen_accessions.add(acc)
                        filings.append(f)
            from_idx += page_size
            if from_idx >= total_count:
                break
            logger.info(f"  Page {page+1}: {len(hits)} hits (total: {total_count})")
        for f in filings:
            if not f.get('ticker'):
                f['ticker'] = self.cik_to_ticker(f['cik'])
        logger.info(f"Found {len(filings)} Item 1.01 filings (deduped from {total_count} hits)")
        return filings

    def _parse_hit(self, hit):
        try:
            src = hit.get('_source', {})
            raw_id = hit.get('_id', '')
            # Fix: EFTS _id can be 'accession:filename.htm' — strip the filename
            accession = raw_id.split(':')[0] if ':' in raw_id else raw_id
            cik = str(src.get('entity_id', '')).lstrip('0') or ''
            if isinstance(src.get('ciks'), list) and src['ciks']:
                cik = str(src['ciks'][0])
            names = src.get('display_names', [])
            name = names[0] if names else src.get('entity_name', 'Unknown')
            items = src.get('items', '')
            if isinstance(items, list):
                items = ','.join(items)
            # Fix: Build proper EDGAR index URL from clean accession number
            acc_no_dashes = accession.replace('-', '')
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{accession}-index.htm"
            return {
                'accession_number': accession,
                'cik': str(cik).zfill(10),
                'company_name': name,
                'filing_date': src.get('file_date', ''),
                'acceptance_datetime': src.get('acceptance_datetime', ''),
                'items': items,
                'filing_url': url,
                'ticker': None,
            }
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return None
