"""Independent exact-target ARM GET only after SQL preflight stopped before create."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from azure.identity import AzureCliCredential
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
os.environ['AZURE_CONFIG_DIR'] = str(ROOT / '.azure-sql-cli')
target = '/subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik/providers/Microsoft.Sql/servers/sql-governance-validator-dev-atiya/databases/sqldb-gpv-mig-20261106-a1'
with AzureCliCredential(process_timeout=30) as credential:
    token = credential.get_token('https://management.azure.com/.default')
    try:
        with urlopen(Request('https://management.azure.com'+target+'?api-version=2023-08-01',headers={'Authorization':'Bearer '+token.token}),timeout=45) as response:
            status, code = response.status, 'ResourceStillExists'
    except HTTPError as error:
        status, code = error.code, json.load(error).get('error',{}).get('code')
result={'utc':datetime.now(timezone.utc).isoformat(),'resource_id':target,'http_status':status,'error_code':code,'resources_created':0}
(OUT/'independent-preflight-absence.json').write_text(json.dumps(result,indent=2)+'\n')
assert status==404 and code=='ResourceNotFound'
print(json.dumps(result))
