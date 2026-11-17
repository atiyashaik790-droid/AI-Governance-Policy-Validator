import ipaddress,json,os,subprocess,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/sigmoid/AI governance policy validator')
OUT=ROOT/'docs/evidence/phase6b-firewall-create-2026-11-07'
OUT.mkdir(parents=True,exist_ok=True)
os.environ['AZURE_CONFIG_DIR']=str(ROOT/'.azure-sql-cli')
SUB='25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'; GROUP='rg_techdemo_Atiya_Tabsum_Shaik'; SERVER='sql-governance-validator-dev-atiya'; NAME='gpv-verifier-single-ip-20261107'; IP='101.0.62.127'
def az(*args):
 p=subprocess.run(['az',*args,'-o','json'],capture_output=True,text=True,timeout=45)
 if p.returncode: raise RuntimeError('Azure operation failed; raw output suppressed')
 return json.loads(p.stdout)
assert az('account','show','--query','id')==SUB
base=['--subscription',SUB,'-g',GROUP,'-s',SERVER]
server=az('sql','server','show','--subscription',SUB,'-g',GROUP,'-n',SERVER,'--query','{id:id,fullyQualifiedDomainName:fullyQualifiedDomainName}')
assert server['id'].lower()==f'/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/{SERVER}'.lower()
assert server['fullyQualifiedDomainName']==SERVER+'.database.windows.net'
before=az('sql','server','firewall-rule','list',*base)
for r in before:
 assert r['name'].lower()!=NAME.lower(), 'Approved name already exists; stop'
 assert not int(ipaddress.IPv4Address(r['startIpAddress']))<=int(ipaddress.IPv4Address(IP))<=int(ipaddress.IPv4Address(r['endIpAddress'])), 'Equivalent allowance exists; stop'
# Last guard immediately before the sole authorized mutation; no proxy and TLS verification retained.
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('https://api.ipify.org?format=json',timeout=15) as response: observed=json.load(response)['ip']
assert observed==IP, 'Outbound IP changed; stop'
checked=datetime.now(timezone.utc).isoformat()
created=az('sql','server','firewall-rule','create',*base,'-n',NAME,'--start-ip-address',IP,'--end-ip-address',IP)
(OUT/'creation-response.json').write_text(json.dumps(created,indent=2)+'\n')
after=az('sql','server','firewall-rule','list',*base)
def normalized(rows): return {r['name']:(r['startIpAddress'],r['endIpAddress']) for r in rows}
a=normalized(after); b=normalized(before)
assert a==dict(b,**{NAME:(IP,IP)}), 'Unexpected firewall difference; stop'
result={'status':'PASS','subscription':SUB,'server':SERVER,'outbound_ip':observed,'ip_checked_utc':checked,'rule_name':NAME,'start_ip':IP,'end_ip':IP,'existing_rules_unchanged':True,'only_change':NAME,'before_count':len(before),'after_count':len(after),'broad_azure_services_rule_added':False,'approval_a_run':False}
(OUT/'firewall-verification.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'creation-source.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(result))
