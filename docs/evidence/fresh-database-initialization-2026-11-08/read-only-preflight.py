"""Read-only migration preflight. No ARM writes, migration execution or grants."""
import ast
import hashlib
import importlib.util
import ipaddress
import json
import re
import struct
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path('/home/sigmoid/AI governance policy validator')
OUT=ROOT/'docs/evidence/fresh-database-initialization-2026-11-08'
OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('approved_db_controller','/tmp/gpv_create_persistent_sql.py')
cloud=importlib.util.module_from_spec(spec);spec.loader.exec_module(cloud)
sys.path.insert(0,str(ROOT/'backend'))
from app.azure_sql import verify_token_identity,SQL_COPT_SS_ACCESS_TOKEN,ODBC_DRIVER
import pyodbc

report={'observed_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_PREFLIGHT','migrations_executed':False,'arm_writes':0,'sql_writes':0,'firewall_changes':0,'permission_changes':0,'provider_calls':0}
def persist():
 (OUT/'preflight.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
try:
 pins=json.loads((ROOT/'docs/evidence/master-repair-2026-11-07/qualification-pins.json').read_text())['migration_hashes']
 actual={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'backend/migrations/versions').glob('*.py'))}
 if actual!=pins:raise RuntimeError('MIGRATION_HASH_MISMATCH')
 chain=[]
 for filename in actual:
  tree=ast.parse((ROOT/filename).read_text());values={}
  for node in tree.body:
   if isinstance(node,ast.Assign):
    for target in node.targets:
     if isinstance(target,ast.Name) and target.id in ['revision','down_revision']:
      values[target.id]=ast.literal_eval(node.value)
  chain.append(values)
 if [(x.get('revision'),x.get('down_revision')) for x in chain] != [(f'{i:03}',f'{i-1:03}' if i>1 else None) for i in range(1,9)]:raise RuntimeError('MIGRATION_CHAIN_MISMATCH')
 report.update(migration_chain='PASS_001_THROUGH_008_UNCHANGED',migration_hashes=actual)
 report['subscription']=cloud.authenticate()
 server=cloud.required_get(cloud.SERVER_URL+cloud.API)
 if server['name']!=cloud.SERVER or server['properties']['fullyQualifiedDomainName']!=cloud.SERVER+'.database.windows.net':raise RuntimeError('SERVER_IDENTITY_MISMATCH')
 target=cloud.required_get(cloud.TARGET+cloud.API)
 if target['id'].casefold()!=cloud.TARGET.removeprefix('https://management.azure.com').casefold() or target['properties']['databaseId']!='80dd1ba9-74e5-4d26-8463-081572c9c22e' or target['properties']['status']!='Online':raise RuntimeError('DATABASE_IDENTITY_OR_STATUS_MISMATCH')
 report['target']={'id':target['id'],'database_id':target['properties']['databaseId'],'status':target['properties']['status'],'sku':target['sku']}
 report['hosted_before']=cloud.health()
 source=cloud.source_snapshot();app=cloud.app_snapshot()
 baseline=json.loads((ROOT/'docs/evidence/fresh-database-creation-2026-11-08/result.json').read_text())
 report['production_source_metadata_matches_creation_evidence']=source==baseline['source_after']
 report['production_app_config_matches_creation_evidence']=app==baseline['app_after']
 if not report['production_source_metadata_matches_creation_evidence'] or not report['production_app_config_matches_creation_evidence']:raise RuntimeError('PRODUCTION_BASELINE_DRIFT')
 firewall=cloud.required_get(cloud.SERVER_URL+'/firewallRules'+cloud.API)
 if firewall.get('nextLink'):raise RuntimeError('FIREWALL_INVENTORY_PAGINATED')
 report['existing_firewall_rules']=[{'name':x['name'],'start_ip':x['properties']['startIpAddress'],'end_ip':x['properties']['endIpAddress']} for x in firewall['value']]
 if ODBC_DRIVER not in pyodbc.drivers():raise RuntimeError('REQUIRED_ODBC_DRIVER_MISSING')
 token=json.loads(cloud.cli(['account','get-access-token','--subscription',cloud.SUB,'--resource','https://database.windows.net/','-o','json']))
 expiry=int(token['expires_on'])
 verify_token_identity(token['accessToken'],expiry,'4ac50105-0c66-404e-a107-7cbd8a9a6442','b5d8bfbe-f03a-4132-a13f-ab49aae834b7')
 report['sql_token_identity']='PASS_APPROVED_OPERATOR_AND_DIRECTORY'
 encoded=token['accessToken'].encode('utf-16-le')
 connection=None
 try:
  connection=pyodbc.connect(f'Driver={{{ODBC_DRIVER}}};Server=tcp:{cloud.SERVER}.database.windows.net,1433;Database={cloud.DB};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;',attrs_before={SQL_COPT_SS_ACCESS_TOKEN:struct.pack(f'<I{len(encoded)}s',len(encoded),encoded)},timeout=10,autocommit=True)
  connection.timeout=15
  cursor=connection.cursor()
  row=cursor.execute("SELECT DB_NAME(), CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)), HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL'), HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','VIEW DEFINITION'), CAST(SERVERPROPERTY('EngineEdition') AS int), CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128))").fetchone()
  if row[0]!=cloud.DB or row[1].split('.')[0].casefold()!=cloud.SERVER.casefold() or row[4]!=5:raise RuntimeError('SQL_DATABASE_OR_ENGINE_IDENTITY_MISMATCH')
  report['sql_context']={'database':row[0],'server':row[1],'database_control':row[2],'view_definition':row[3],'engine_edition':row[4],'product_version':row[5]}
  if row[2]!=1:raise RuntimeError('MIGRATION_PRIVILEGES_NOT_VERIFIED')
  tables=cursor.execute('SELECT s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name').fetchall()
  report['user_tables']=[{'schema':x[0],'table':x[1]} for x in tables]
  if tables:raise RuntimeError('TARGET_NOT_EMPTY')
  objects=cursor.execute("SELECT COUNT(*) FROM sys.objects WHERE is_ms_shipped=0 AND type IN ('V','P','FN','IF','TF','TR','SO','SN')").fetchone()[0]
  if objects:raise RuntimeError('TARGET_HAS_USER_OBJECTS')
  report.update(status='PASS_READY_FOR_APPROVED_MIGRATIONS',empty_database_verified=True)
 except pyodbc.Error as error:
  message=' '.join(str(x) for x in error.args)
  report['sql_failure']={'exception_type':type(error).__name__,'sqlstate':error.args[0] if error.args and re.fullmatch('[A-Z0-9]{5}',str(error.args[0])) else None,'native_codes':sorted(set(re.findall(r'\((40615|18456|4060|229|916|11001)\)',message)))}
  match=re.search(r"Client with IP address '([0-9.]+)'",message)
  if match and '40615' in report['sql_failure']['native_codes']:
   address=str(ipaddress.IPv4Address(match.group(1)))
   name='gpv-fresh-init-20261108'
   if any(x['name']==name for x in report['existing_firewall_rules']):raise RuntimeError('PROPOSED_FIREWALL_RULE_ALREADY_EXISTS')
   report.update(status='BLOCKED_FIREWALL_APPROVAL_REQUIRED',azure_sql_reported_blocked_client_ip=address,empty_database_verified=False,sql_permissions='NOT_VERIFIED',final_revision='NOT_READ_NO_MIGRATIONS_EXECUTED',proposed_firewall_rule={'name':name,'server':cloud.SERVER,'start_ip':address,'end_ip':address,'maximum_window_minutes':15,'requires_separate_approval':True})
  else:report['status']='BLOCKED_SQL_CONNECTION'
 finally:
  if connection is not None:connection.close()
 report['hosted_after']=cloud.health()
 report['production_source_unchanged_during_preflight']=cloud.source_snapshot()==source
 report['production_app_unchanged_during_preflight']=cloud.app_snapshot()==app
 report['firewall_inventory_unchanged']=cloud.required_get(cloud.SERVER_URL+'/firewallRules'+cloud.API)==firewall
except Exception as error:
 report['status']='BLOCKED'
 report['failure_type']=type(error).__name__
 if isinstance(error,RuntimeError) and re.fullmatch('[A-Z0-9_]+',str(error)):report['failure_code']=str(error)
persist()
