"""Bounded, offline Vietnam province normalization and syntax checks.

No identity, ownership, deliverability or government registry verification.
Business routes fail closed unless the configured RapidAPI proxy secret matches.
"""
import hmac
import hashlib
import threading
from datetime import datetime, timezone
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
CURRENT = json.loads((ROOT / 'data/provinces_2025.json').read_text(encoding='utf-8'))
LEGACY = json.loads((ROOT / 'vn_provinces.json').read_text(encoding='utf-8'))
Version = Literal['2025', 'legacy']
COUNTERS = {'total_requests':0,'total_errors':0}
OBSERVED_USERS = set()
COUNTER_LOCK = threading.Lock()
METRICS_STARTED = datetime.now(timezone.utc).isoformat()


def plain(value):
    value = unicodedata.normalize('NFKD', value.lower().replace('đ', 'd'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def alias(value):
    return re.sub(r'^(tinh|thanh pho|tp)\s+', '', plain(value))


def dataset(version):
    rows = CURRENT['items'] if version == '2025' else LEGACY
    return [{'code': str(p['code']).zfill(2), 'name': p['name']} for p in rows]


def normalize_value(value, version='2025'):
    text = plain(value)
    matches = []
    for row in dataset(version):
        name = alias(row['name'])
        names = {name}
        if row['code'] == '79':
            names.update(('hcm', 'tphcm', 'sai gon', 'saigon'))
        segments = [plain(s) for s in re.split(r'[,;]', value)]
        def found(n):
            if len(n.split()) == 1 and n not in ('hcm', 'tphcm', 'saigon'):
                return n in segments or bool(re.search(r'\b(?:tinh|thanh pho|tp) ' + re.escape(n) + r'\b', text))
            return bool(re.search(r'(?<![a-z0-9])' + re.escape(n) + r'(?![a-z0-9])', text))
        if any(found(n) for n in names):
            matches.append(row)
    status = 'matched' if len(matches) == 1 else ('ambiguous' if matches else 'not_found')
    return {'ok': status == 'matched', 'status': status, 'province': matches[0] if status == 'matched' else None,
            'candidates': matches, 'datasetVersion': version, 'scope': 'province_only',
            'effectiveFrom': CURRENT['effectiveFrom'] if version == '2025' else 'historical_before_2025_07',
            'note': 'Snapshot lookup; not a geocode, full-address validation, or a legacy-to-current conversion.'}


class Batch(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=50)
    version: Version = '2025'


app = FastAPI(title='Vietnam Checkout Data Toolkit', version='2.0.0',
              description='Province snapshot lookup with explicit ambiguity and bounded batch processing. '
                          'Phone/email/tax/ID endpoints check syntax only. No identity or legal validation.',
              docs_url=None, redoc_url=None, openapi_url=None)


class Guard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] == '/health':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        if scope['path'] == '/metrics':
            admin=os.environ.get('ADMIN_TOKEN','')
            if not admin:return await JSONResponse({'detail':'Metrics not configured'},status_code=503)(scope,receive,send)
            if not hmac.compare_digest(headers.get(b'authorization',b''),('Bearer '+admin).encode()):
                return await JSONResponse({'detail':'Unauthorized'},status_code=401)(scope,receive,send)
            return await self.app(scope,receive,send)
        secret = os.environ.get('RAPIDAPI_PROXY_SECRET', '')
        if not secret:
            return await JSONResponse({'detail': 'Service not configured'}, status_code=503)(scope, receive, send)
        supplied = headers.get(b'x-rapidapi-proxy-secret', b'')
        if not hmac.compare_digest(supplied, secret.encode('utf-8')):
            return await JSONResponse({'detail': 'Unauthorized'}, status_code=401)(scope, receive, send)
        if len(scope.get('query_string', b'')) > 4096:
            return await JSONResponse({'detail': 'Query too large'}, status_code=413)(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > 65536:
                return await JSONResponse({'detail': 'Body too large'}, status_code=413)(scope, receive, send)
            if not message.get('more_body', False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        async def counted_send(message):
            if message['type']=='http.response.start':
                with COUNTER_LOCK:
                    COUNTERS['total_requests']+=1
                    COUNTERS['total_errors']+=int(message['status']>=400)
                    salt=os.environ.get('ADMIN_TOKEN','')
                    user=headers.get(b'x-rapidapi-user',b'')
                    if salt and user:OBSERVED_USERS.add(hmac.new(salt.encode(),user,hashlib.sha256).hexdigest())
            await send(message)
        await self.app(scope, replay, counted_send)


app.add_middleware(Guard)

@app.get('/metrics',include_in_schema=False)
def metrics():
    with COUNTER_LOCK:
        return {**COUNTERS,'unique_subscribers':len(OBSERVED_USERS) if os.environ.get('ADMIN_TOKEN') else None,
                'process_started_at':METRICS_STARTED,'counter_scope':'process_memory_since_start; includes owner; not paid subscribers','storage_persistence':'ephemeral'}


@app.get('/health', include_in_schema=False)
def health():
    return {'ok': True, 'version': app.version, 'currentProvinceCount': len(CURRENT['items'])}


@app.get('/provinces', tags=['Province lookup'])
def provinces(version: Version = '2025'):
    """Return the 2025 snapshot or an explicitly historical 63-province list."""
    rows = dataset(version)
    return {'datasetVersion': version, 'count': len(rows), 'items': rows,
            'sourceUrl': CURRENT['sourceUrl'] if version == '2025' else 'https://provinces.open-api.vn/api/v1/',
            'snapshotVerifiedUtc': CURRENT['snapshotVerifiedUtc'] if version == '2025' else 'unknown'}


@app.get('/normalize', tags=['Province lookup'])
def normalize(q: str = Query(min_length=1, max_length=500), version: Version = '2025'):
    """Find province-name mentions. Multiple province mentions remain ambiguous."""
    return normalize_value(q, version)


@app.post('/normalize/batch', tags=['Province lookup'])
def normalize_batch(batch: Batch):
    """Normalize up to 50 values, maintaining their order. Long values are rejected."""
    if any(not q.strip() or len(q) > 500 for q in batch.queries):
        return JSONResponse({'detail': 'Each query must contain 1 to 500 characters'}, status_code=422)
    rows = [normalize_value(q, batch.version) for q in batch.queries]
    return {'count': len(rows), 'results': rows,
            'summary': {s: sum(r['status'] == s for r in rows) for s in ('matched', 'ambiguous', 'not_found')}}


@app.get('/validate-phone', tags=['Syntax checks'])
def phone(p: str = Query(min_length=1, max_length=40)):
    """Check Vietnamese mobile number shape only; no live-number verification."""
    allowed = bool(re.fullmatch(r'\+?[0-9\s().-]+', p))
    digits = re.sub(r'[^0-9]', '', p) if allowed else ''
    if digits.startswith('84'):
        digits = '0' + digits[2:]
    ok = allowed and bool(re.fullmatch(r'0[35789][0-9]{8}', digits))
    return {'ok': ok, 'normalized': digits if ok else None, 'scope': 'syntax_only', 'verifiedActive': False}


@app.get('/validate-email', tags=['Syntax checks'])
def email(e: str = Query(min_length=1, max_length=254)):
    """Conservative ASCII email syntax check; no DNS or mailbox verification."""
    parts = e.split('@')
    ok = False
    if len(parts) == 2:
        local, domain = parts
        labels = domain.split('.')
        ok = (0 < len(local) <= 64 and not local.startswith('.') and not local.endswith('.') and '..' not in local
              and bool(re.fullmatch(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+", local))
              and len(labels) >= 2 and all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', s) for s in labels)
              and bool(re.fullmatch(r'[a-zA-Z]{2,63}', labels[-1])))
    return {'ok': bool(ok), 'scope': 'ascii_syntax_only', 'verifiedDeliverable': False}


@app.get('/validate-taxcode', tags=['Syntax checks'])
def taxcode(code: str = Query(min_length=1, max_length=20)):
    """Check 10-digit tax code or 10+3-digit branch shape; no registry query."""
    ok = bool(re.fullmatch(r'[0-9]{10}(?:-?[0-9]{3})?', code))
    return {'ok': ok, 'scope': 'syntax_only', 'registryVerified': False,
            'normalized': code.replace('-', '') if ok else None}


@app.get('/validate-cccd', tags=['Syntax checks'], deprecated=True)
def id_shape(id: str = Query(min_length=1, max_length=20)):
    """Deprecated: 12 ASCII digits only. No identity or encoded-demographic inference."""
    return {'ok': bool(re.fullmatch(r'[0-9]{12}', id)), 'scope': 'length_and_digits_only', 'identityVerified': False}


@app.get('/stats', tags=['Metadata'])
def stats():
    return {'name': app.title, 'version': app.version, 'datasets': {'2025': 34, 'legacy': 63},
            'dataSource': CURRENT['sourceUrl'], 'effectiveFrom': CURRENT['effectiveFrom'],
            'limitations': ['province lookup only', 'snapshot not live registry', 'syntax checks not identity verification']}
