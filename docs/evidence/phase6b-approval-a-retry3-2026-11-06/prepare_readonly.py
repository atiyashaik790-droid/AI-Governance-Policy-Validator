"""Approval gate preparation only: ARM GET/list and public price read; no SQL writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUB = '25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'
GROUP = 'rg_techdemo_Atiya_Tabsum_Shaik'
SERVER = 'sql-governance-validator-dev-atiya'
DB = 'sqldb-gpv-mig-20261106-a1'
SERVER_ID = f'/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/{SERVER}'
env = {**os.environ, 'AZURE_CONFIG_DIR': str(ROOT / '.azure-sql-cli')}

def read(*args):
    p = subprocess.run(['az', *args, '-o', 'json'], env=env, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise RuntimeError('Read-only Azure metadata query failed: ' + ' '.join(args[:3]))
    return json.loads(p.stdout)

result = {'utc': datetime.now(timezone.utc).isoformat(), 'mutations': 0}
result['account'] = read('account', 'show', '--query', '{id:id,tenantId:tenantId}')
assert result['account']['id'] == SUB
result['server'] = read('sql', 'server', 'show', '--subscription', SUB, '-g', GROUP, '-n', SERVER,
                        '--query', '{id:id,fqdn:fullyQualifiedDomainName,location:location}')
assert result['server'] == {'id': SERVER_ID, 'fqdn': SERVER + '.database.windows.net', 'location': 'westus2'}
result['databases'] = read('sql', 'db', 'list', '--subscription', SUB, '-g', GROUP, '-s', SERVER,
                          '--query', '[].{name:name,id:id,status:status,sku:sku}')
assert not any(d['name'] == DB for d in result['databases'])
result['s0_capability'] = read('sql', 'db', 'list-editions', '--subscription', SUB, '--location', 'westus2',
                             '--service-objective', 'S0')
assert result['s0_capability']
for scope, label in [(f'/subscriptions/{SUB}', 'subscription'), (f'/subscriptions/{SUB}/resourceGroups/{GROUP}', 'group'), (SERVER_ID, 'server')]:
    for suffix, key in [('/providers/Microsoft.Authorization/locks?api-version=2016-09-01', 'locks'),
                        ('/providers/Microsoft.Authorization/denyAssignments?api-version=2022-04-01', 'deny')]:
        result[label + '_' + key] = read('rest', '--method', 'get', '--url', 'https://management.azure.com' + scope + suffix)
        assert not result[label + '_' + key]['value']
url = 'https://prices.azure.com/api/retail/prices?' + urllib.parse.urlencode({'$filter': "serviceName eq 'SQL Database' and armRegionName eq 'westus2' and skuName eq 'S0' and priceType eq 'Consumption'"})
with urllib.request.urlopen(url, timeout=30) as response:
    prices = json.load(response)
(OUT / 'retail-live.json').write_text(json.dumps(prices, indent=2) + '\n')
meters = [p for p in prices['Items'] if p['skuName'] == 'S0' and p['meterName'] == 'S0 DTUs' and p['currencyCode'] == 'USD' and p['unitOfMeasure'] == '1/Day']
assert len(meters) == 1
result['daily_usd'] = meters[0]['retailPrice']
result['conservative_10_billed_hours_usd'] = result['daily_usd'] * 10 / 24
assert result['conservative_10_billed_hours_usd'] < 0.5
result['sqlite_sha256'] = hashlib.sha256((ROOT / 'backend/governance.db').read_bytes()).hexdigest()
assert result['sqlite_sha256'] == '0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766'
(OUT / 'retry-preflight.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'account': result['account']['id'], 'server': result['server'], 'temporary_name_absent': DB,
                  'daily_usd': result['daily_usd'], 'conservative_10_billed_hours_usd': result['conservative_10_billed_hours_usd'], 'mutations': 0}))
