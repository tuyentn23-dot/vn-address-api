from fastapi import FastAPI, Query
import json, os, re, urllib.request
ROOT = 'D:/TNT_AI/bug_hunter/projects/rapidapi_vn'
PROVINCES = json.load(open(os.path.join(ROOT, 'vn_provinces.json'), encoding='utf-8'))
app = FastAPI(title='VN Address Normalizer')
LOOKUP = {p.get('codename','').lower(): p for p in PROVINCES}
@app.get('/health')
def health():
	return {'ok': True, 'provinces': len(PROVINCES)}
@app.get('/provinces')
def list_provinces():
	return {'count': len(PROVINCES), 'items': [{'code': p.get('code'), 'name': p.get('name'), 'codename': p.get('codename')} for p in PROVINCES]}
@app.get('/normalize')
def normalize(q: str = Query(...)):
	norm = q.lower().replace(chr(32), chr(95))
	matches = [p for k, p in LOOKUP.items() if k and (k in norm or norm in k)]
	if not matches:
		return {'ok': False, 'input': q, 'province': None}
	best = matches[0]
	return {'ok': True, 'input': q, 'province': {'code': best.get('code'), 'name': best.get('name'), 'codename': best.get('codename')}}
@app.get('/validate-phone')
def validate_phone(p: str = Query(...)):
	digits = re.sub(r'[^0-9]', '', p)
	if digits.startswith('84'):
		digits = chr(48) + digits[2:]
	valid = len(digits) == 10 and digits[:2] in ('03','05','07','08','09')
	return {'ok': valid, 'input': p, 'normalized': digits, 'prefix': digits[:2] if valid else None}
@app.get('/validate-bank')
def validate_bank(bin: str = Query(...)):
	try:
		req = urllib.request.Request('https://api.vietqr.io/v2/banks', headers={'User-Agent': 'TNT/1.0'})
		resp = urllib.request.urlopen(req, timeout=5)
		data = json.loads(resp.read())
		banks = data.get('data', [])
		match = [b for b in banks if str(b.get('bin')) == str(bin)]
		if match:
			b = match[0]
			return {'ok': True, 'bin': bin, 'shortName': b.get('shortName'), 'name': b.get('name')}
		return {'ok': False, 'bin': bin, 'error': 'Bank not found'}
	except Exception as e:
		return {'ok': False, 'error': str(e)[:100]}
@app.get('/stats')
def stats():
	return {'name': 'VN Address Normalizer', 'version': '1.0.0', 'provinces': len(PROVINCES), 'endpoints': ['health','provinces','normalize','validate-phone','validate-bank']}
@app.get('/validate-cccd')
def validate_cccd(id: str = Query(...)):
	d = re.sub(r'[^0-9]', '', id)
	ok = len(d) == 12
	g = 'male' if ok and int(d[3])%2==0 else ('female' if ok else None)
	return {'ok':ok,'prov':d[:3] if ok else None,'gender':g}

@app.get('/validate-email')
def validate_email(e: str = Query(...)):
	p = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}$'
	ok = bool(re.match(p, e))
	d = e.split(chr(64))[-1].lower() if chr(64) in e else None
	return {'ok':ok,'domain':d}

@app.get('/validate-taxcode')
def validate_taxcode(code: str = Query(...)):
	d = re.sub(r'[^0-9]', '', code)
	n = len(d)
	typ = 'company' if n==10 else ('branch' if n==13 else 'invalid')
	return {'ok':n in (10,13),'normalized':d,'type':typ}

