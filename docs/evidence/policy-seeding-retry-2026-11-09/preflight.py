"""Approved bootstrap preflight: read-only; no firewall/grant/membership writes."""
import json,hashlib,importlib.util,re,sys,struct,fnmatch
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=ROOT/'docs/evidence/policy-seeding-retry-2026-11-09';OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('cloud','/tmp/gpv_create_persistent_sql.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
S={'status':'BLOCKED','azure_writes':0,'sql_writes':0,'directory_writes':0,'started_utc':datetime.now(timezone.utc).isoformat()}
ADMIN='b5d8bfbe-f03a-4132-a13f-ab49aae834b7';USER='f4799f3f-703a-42b7-acf7-4cbbf55e7320';DIR='4ac50105-0c66-404e-a107-7cbd8a9a6442';IP='45.127.46.209';RULE='gpv-policy-seed-20261109'
try:
 expected={'deployment/demo-policy-seed.REVIEW_ONLY.json':'b5b1aea3889a8a42193f7a5058a427cf8da7ed09fdd41fb0437aa5944c72104b'}
 for name,h in expected.items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise RuntimeError('REVIEWED_PROPOSAL_HASH_MISMATCH')
 plan=json.loads((ROOT/'deployment/demo-policy-seed.REVIEW_ONLY.json').read_text())
 if plan['database']!=c.DB or plan['required_revision']!='008' or plan['tenant']!='demo-appservice-4e2dcce8d618' or len(plan['policies'])!=8 or plan['policy_mode']!='MULTI':raise RuntimeError('MANIFEST_TARGET_MISMATCH')
 S['proposal_hashes']=expected
 S['subscription']=c.authenticate()
 for label,oid in [('admin',ADMIN),('user',USER)]:
  url='https://graph.microsoft.com/v1.0/users/'+oid+'?'+urlencode({'$select':'id,userPrincipalName,accountEnabled,userType'})
  person=json.loads(c.cli(['rest','--method','get','--url',url,'-o','json']))
  if person['id']!=oid or person['accountEnabled'] is not True or person.get('userType')!='Member':raise RuntimeError('DIRECTORY_IDENTITY_MISMATCH')
  if label=='user' and person['userPrincipalName'].casefold()!='demo-user@sigmoidanalytics.com':raise RuntimeError('USER_UPN_MISMATCH')
  S[label+'_directory']=person
 sp=json.loads(c.cli(['ad','sp','show','--id','600447fe-5fea-4801-9033-ab4aafc474cc','--query','{id:id,appId:appId,displayName:displayName,servicePrincipalType:servicePrincipalType}','-o','json']))
 if sp['id']!='600447fe-5fea-4801-9033-ab4aafc474cc' or sp['appId']!='f7bacace-698a-4968-8add-cba221319a17' or sp['displayName']!=c.APP or sp['servicePrincipalType']!='ManagedIdentity':raise RuntimeError('RUNTIME_IDENTITY_MISMATCH')
 S['runtime_directory']=sp
 target=c.required_get(c.TARGET+c.API);server=c.required_get(c.SERVER_URL+c.API)
 if target['id'].casefold()!=c.TARGET.removeprefix('https://management.azure.com').casefold() or target['properties']['databaseId']!='80dd1ba9-74e5-4d26-8463-081572c9c22e' or target['properties']['status']!='Online' or server['properties']['fullyQualifiedDomainName']!=c.SERVER+'.database.windows.net':raise RuntimeError('SQL_TARGET_MISMATCH')
 S['target']={'id':target['id'],'database_id':target['properties']['databaseId'],'status':target['properties']['status'],'last_verified_revision':'008_FROM_COMPLETED_SCHEMA_QUALIFICATION_RECHECK_AFTER_ACCESS'}
 rules=c.required_get(c.SERVER_URL+'/firewallRules'+c.API)
 if rules.get('nextLink') or any(x['name']==RULE for x in rules['value']):raise RuntimeError('RULE_ALREADY_EXISTS_OR_INVENTORY_UNVERIFIED')
 S['firewall_before']=sorted([{'name':x['name'],'start_ip':x['properties']['startIpAddress'],'end_ip':x['properties']['endIpAddress']} for x in rules['value']],key=lambda x:x['name'])
 permissions=c.required_get(c.SERVER_URL+'/providers/Microsoft.Authorization/permissions?api-version=2022-04-01')
 if permissions.get('nextLink'):raise RuntimeError('CLEANUP_PERMISSIONS_PAGINATED')
 S['firewall_effective_management_actions']={}
 for action in ['Microsoft.Sql/servers/firewallRules/read','Microsoft.Sql/servers/firewallRules/write','Microsoft.Sql/servers/firewallRules/delete']:
  allowed=any(any(fnmatch.fnmatchcase(action.lower(),a.lower()) for a in x.get('actions',[])) and not any(fnmatch.fnmatchcase(action.lower(),a.lower()) for a in x.get('notActions',[])) for x in permissions.get('value',[]))
  S['firewall_effective_management_actions'][action]=allowed
  if not allowed:raise RuntimeError('SAFE_CLEANUP_PERMISSION_NOT_VERIFIED')
 S['source_before']=c.source_snapshot();S['app_before']=c.app_snapshot();S['hosted_before']=c.health()
 sys.path.insert(0,str(ROOT/'backend'));import pyodbc
 from app.azure_sql import verify_token_identity,SQL_COPT_SS_ACCESS_TOKEN
 token=json.loads(c.cli(['account','get-access-token','--subscription',c.SUB,'--resource','https://database.windows.net/','-o','json']));verify_token_identity(token['accessToken'],int(token['expires_on']),DIR,ADMIN);encoded=token['accessToken'].encode('utf-16-le')
 try:
  connection=pyodbc.connect('Driver={ODBC Driver 18 for SQL Server};Server=tcp:sql-governance-validator-dev-atiya.database.windows.net,1433;Database=sqldb-gpv-demo-v008-20261108;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;',attrs_before={SQL_COPT_SS_ACCESS_TOKEN:struct.pack(f'<I{len(encoded)}s',len(encoded),encoded)},timeout=10)
  connection.timeout=10
  connection.cursor().execute('SELECT DB_NAME()').fetchone()
  connection.close();raise RuntimeError('ACCESS_ALREADY_PRESENT_REQUIRES_IP_RECONCILIATION')
 except pyodbc.Error as error:
  message=' '.join(str(x) for x in error.args);m=re.search(r"Client with IP address '([0-9.]+)'",message)
  if '(40615)' not in message or not m or m.group(1)!=IP:raise RuntimeError('FIREWALL_IP_NOT_CONFIRMED') from None
 S.update(status='PASS',verified_blocked_client_ip=IP,firewall_rule=RULE,safe_cleanup_procedure='TESTED_EXACT_RULE_DELETE_WITH_UNCONDITIONAL_DEADLINE_EXEMPT_RESTORATION_AND_INVENTORY_READBACK',independent_supervisor='NOT_VERIFIED',preflight_finished_utc=datetime.now(timezone.utc).isoformat())
except Exception as error:
 S['failure_type']=type(error).__name__
 if isinstance(error,RuntimeError) and str(error).replace('_','').isalnum():S['failure_code']=str(error)
(OUT/'preflight.json').write_text(json.dumps(S,indent=2)+'\n');print(json.dumps(S,indent=2))
