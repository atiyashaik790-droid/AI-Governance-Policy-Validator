"""Explicitly approved read-only firewall/current-egress inspection."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from datetime import datetime, timezone

ROOT = Path('/home/sigmoid/AI governance policy validator')
OUT = ROOT / 'docs/evidence/phase6b-firewall-readonly-2026-11-07'
SUB = '25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'
GROUP = 'rg_techdemo_Atiya_Tabsum_Shaik'
SERVER = 'sql-governance-validator-dev-atiya'
SERVER_ID = f'/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/{SERVER}'
os.environ['AZURE_CONFIG_DIR'] = str(ROOT / '.azure-sql-cli')

def read(*args):
    p = subprocess.run(['az', *args, '-o', 'json'], capture_output=True, text=True, timeout=40)
    if p.returncode:
        raise RuntimeError('Read-only Azure inspection failed: ' + ' '.join(args[:3]))
    return json.loads(p.stdout)

assert read('account', 'show', '--query', 'id') == SUB
server = read('sql','server','show','--subscription',SUB,'-g',GROUP,'-n',SERVER,'--query','{id:id,location:location,publicNetworkAccess:publicNetworkAccess,fullyQualifiedDomainName:fullyQualifiedDomainName}')
assert server['id'].lower() == SERVER_ID.lower()
assert server['fullyQualifiedDomainName'] == SERVER + '.database.windows.net'
# Only the observed IP is sent back by this HTTPS echo service; no Azure credentials.
with urllib.request.urlopen('https://api.ipify.org?format=json', timeout=15) as response:
    public_ip = ipaddress.IPv4Address(json.load(response)['ip'])
rules = read('sql','server','firewall-rule','list','--subscription',SUB,'-g',GROUP,'-s',SERVER,
             '--query','[].{name:name,id:id,startIpAddress:startIpAddress,endIpAddress:endIpAddress}')
matching, broad = [], []
for rule in rules:
    start, end = ipaddress.IPv4Address(rule['startIpAddress']), ipaddress.IPv4Address(rule['endIpAddress'])
    if int(start) == 0 and int(end) == 0:
        broad.append(rule['name'])
    elif int(start) <= int(public_ip) <= int(end):
        matching.append(rule)
name = 'gpv-verifier-single-ip-20261107'
collision = next((r for r in rules if r['name'] == name), None)
proposal = None if matching else {'name': name, 'startIpAddress': str(public_ip), 'endIpAddress': str(public_ip),
                                'cidrEquivalent': str(public_ip)+'/32', 'scope':SERVER_ID+'/firewallRules/'+name,
                                'nameAvailable':collision is None}
result = {'utc':datetime.now(timezone.utc).isoformat(),'subscription':SUB,'server':server,'public_outbound_ipv4':str(public_ip),
          'ip_observation_source':'https://api.ipify.org?format=json','firewall_rules':rules,'matching_explicit_rules':matching,
          'azure_services_zero_rule_names':broad,'public_ip_explicitly_permitted':bool(matching),'proposal':proposal,
          'mutations':0,'sql_connections':0,'approval_a_run':False,
          'egress_caveat':'HTTPS egress observation; NAT/proxy routing to SQL may differ. No SQL connection was attempted under this inspection-only approval.'}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'inspection.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'inspection-source.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(result))
