"""Export an import candidate and review package; never contacts RapidAPI."""
import copy
import hashlib
import json
from pathlib import Path
from src.main import app

ROOT = Path(__file__).resolve().parent


def oas30(value):
    if isinstance(value, list):
        return [oas30(v) for v in value]
    if not isinstance(value, dict):
        return value
    value = {k: oas30(v) for k, v in value.items()}
    branches = value.get('anyOf')
    if branches and any(v.get('type') == 'null' for v in branches):
        others = [v for v in branches if v.get('type') != 'null']
        if len(others) == 1:
            value.pop('anyOf')
            value.update(others[0])
        else:
            value['anyOf'] = others
        value['nullable'] = True
    for key in ('exclusiveMinimum', 'exclusiveMaximum'):
        if isinstance(value.get(key), (int, float)) and not isinstance(value[key], bool):
            value[key.replace('exclusive', '').lower()] = value[key]
            value[key] = True
    return value


def main():
    target = ROOT / 'listing'
    target.mkdir(exist_ok=True)
    spec = oas30(copy.deepcopy(app.openapi()))
    spec['openapi'] = '3.0.3'
    spec['servers'] = [{'url': 'https://REPLACE_WITH_VERIFIED_BACKEND.example'}]
    # Identity checks are not part of this product's sales promise.
    spec['paths'].pop('/validate-cccd', None)
    (target / 'openapi.import.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {
        'productId': 'vietnam-checkout-data-toolkit', 'version': app.version,
        'name': app.title, 'backendUrl': 'unknown', 'category': 'Data',
        'stage': 'prepared_unpublished', 'listingUrl': 'unknown', 'apiId': 'unknown',
        'paidCustomers': 0, 'revenueConfirmed': False, 'proxySecretConfigured': 'unknown',
        'importVerifiedInSellerAccount': False, 'publishApproved': False,
        'pricingProposed': [
            {'name': 'BASIC', 'monthlyUsd': '0', 'requestsMonthly': 100, 'hardLimit': True, 'requestsPerMinute': 10},
            {'name': 'PRO', 'monthlyUsd': '9.99', 'requestsMonthly': 10000, 'hardLimit': True, 'requestsPerMinute': 60},
            {'name': 'ULTRA', 'monthlyUsd': '29.99', 'requestsMonthly': 50000, 'hardLimit': True, 'requestsPerMinute': 120}],
        'costNote': 'Offline snapshot processing, no upstream paid calls. Hosting costs unknown; 25% platform fee plus payout fees.',
        'nextAction': 'Verify backend and seller import/pricing/security; obtain publication approval before public listing',
        'openapiSha256': hashlib.sha256((target / 'openapi.import.json').read_bytes()).hexdigest(),
    }
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'stage': manifest['stage'], 'version': app.version, 'paths': len(spec['paths']), 'published': False}))


if __name__ == '__main__':
    main()
