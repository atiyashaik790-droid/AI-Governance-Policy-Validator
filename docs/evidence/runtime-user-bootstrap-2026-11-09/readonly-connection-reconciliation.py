import json,sys,struct,importlib.util
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();out=root/'docs/evidence/runtime-user-bootstrap-2026-11-09'
spec=importlib.util.spec_from_file_location('c','/tmp/gpv_create_persistent_sql.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
sys.path.insert(0,str(root/'backend'))
import pyodbc
from app.azure_sql import verify_token_identity,SQL_COPT_SS_ACCESS_TOKEN
r={'observed_utc':datetime.now(timezone.utc).isoformat(),'mode':'SELECT_ONLY_CONNECTION_RECONCILIATION','azure_or_sql_mutations':0}
try:
 c.authenticate();t=json.loads(c.cli(['account','get-access-token','--subscription',c.SUB,'--resource','https://database.windows.net/','-o','json']));verify_token_identity(t['accessToken'],int(t['expires_on']),'4ac50105-0c66-404e-a107-7cbd8a9a6442','b5d8bfbe-f03a-4132-a13f-ab49aae834b7');e=t['accessToken'].encode('utf-16-le')
 with pyodbc.connect('Driver={ODBC Driver 18 for SQL Server};Server=tcp:sql-governance-validator-dev-atiya.database.windows.net,1433;Database=sqldb-gpv-demo-v008-20261108;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;',attrs_before={SQL_COPT_SS_ACCESS_TOKEN:struct.pack(f'<I{len(e)}s',len(e),e)},timeout=10,autocommit=True) as connection:
  connection.timeout=15;cursor=connection.cursor();row=cursor.execute("SELECT DB_NAME(),CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)),CONVERT(nvarchar(64),CONNECTIONPROPERTY('client_net_address')),HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL')").fetchone()
  r['connection']={'database':row[0],'server':row[1],'client_net_address':row[2],'operator_database_control':row[3]}
  if row[0]!='sqldb-gpv-demo-v008-20261108':raise RuntimeError('WRONG_DATABASE')
  r['revision']=[x[0] for x in cursor.execute('SELECT version_num FROM dbo.alembic_version').fetchall()]
  r['application_membership_count']=cursor.execute('SELECT COUNT(*) FROM dbo.sso_memberships').fetchone()[0]
  r['runtime_principals_present']=[x[0] for x in cursor.execute("SELECT name FROM sys.database_principals WHERE name IN ('app-governance-validator-atiya-1026','governance_validator_web_runtime')").fetchall()]
  r['status']='READ_ONLY_RECONCILIATION_PASS'
except Exception as error:
 r['status']='BLOCKED';r['failure_type']=type(error).__name__
 if isinstance(error,pyodbc.Error):
  import re
  msg=' '.join(map(str,error.args));r['native_codes']=sorted(set(re.findall(r'\((40615|18456|4060|229|916)\)',msg)));m=re.search(r"Client with IP address '([0-9.]+)'",msg)
  if m:r['azure_reported_blocked_ip']=m.group(1)
(out/'connection-reconciliation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
