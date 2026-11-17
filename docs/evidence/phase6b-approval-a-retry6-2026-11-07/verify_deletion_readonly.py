"""Independent read-only exact-target deletion and source preservation checks."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUB = '25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'
GROUP = 'rg_techdemo_Atiya_Tabsum_Shaik'
SERVER = 'sql-governance-validator-dev-atiya'
DB = 'sqldb-gpv-mig-20261106-a1'
TARGET = f'/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/{SERVER}/databases/{DB}'
os.environ['AZURE_CONFIG_DIR'] = str(ROOT/'.azure-sql-cli')
from azure.identity import AzureCliCredential
from urllib.request import Request, urlopen
from urllib.error import HTTPError
credential = AzureCliCredential(process_timeout=30)
token = credential.get_token('https://management.azure.com/.default')
try:
    with urlopen(Request('https://management.azure.com'+TARGET+'?api-version=2023-08-01',headers={'Authorization':'Bearer '+token.token}),timeout=45) as response:
        status=response.status
        code='ResourceStillExists'
except HTTPError as error:
    status=error.code
    code=json.load(error).get('error',{}).get('code')
credential.close()
result={'utc':datetime.now(timezone.utc).isoformat(),'resource_id':TARGET,'target_arm_get':{'http_status':status,'error_code':code}}
(OUT/'independent-deletion.json').write_text(json.dumps(result,indent=2)+'\n')
assert status == 404 and code == 'ResourceNotFound', 'CLEANUP NOT CONFIRMED'
p=subprocess.run(['az','sql','db','list','--subscription',SUB,'-g',GROUP,'-s',SERVER,'--query','[].{name:name,id:id,status:status}','-o','json'],capture_output=True,text=True,timeout=60)
assert p.returncode == 0, 'Independent inventory read failed'
result['inventory']=json.loads(p.stdout)
assert not any(d['name'] == DB for d in result['inventory'])
result['unexpected_test_names']=[d['name'] for d in result['inventory'] if d['name'] not in {'master','sqldb-governance-validator-dev'}]
assert not result['unexpected_test_names']
state=json.loads((OUT/'execution.json').read_text())
result['incarnations']=state['incarnations']
result['harness_status']=state.get('status')
result['elapsed_seconds']=state.get('elapsed_seconds')
result['sqlite_sha256']=hashlib.sha256((ROOT/'backend/governance.db').read_bytes()).hexdigest()
dry=json.loads((OUT/'harness-dry-run.json').read_text())
assert result['sqlite_sha256']==dry['sqlite_sha256']
result['source_hashes_unchanged']=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in dry['source_hashes'].items())
assert result['source_hashes_unchanged']
result['conservative_compute_estimate_usd']=json.loads((OUT/'retry-preflight.json').read_text())['daily_usd'] * (math.ceil(state['elapsed_seconds']/3600)+state['incarnations'])/24
assert result['conservative_compute_estimate_usd']<1
(OUT/'independent-deletion.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
