"""Approved bootstrap preflight: read-only; no firewall/grant/membership writes."""
import json,hashlib,importlib.util,re,sys,struct,fnmatch
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=ROOT/'docs/evidence/runtime-user-bootstrap-2026-11-09';OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('cloud','/tmp/gpv_create_persistent_sql.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
S={'status':'BLOCKED','azure_writes':0,'sql_writes':0,'directory_writes':0,'started_utc':datetime.now(timezone.utc).isoformat()}
ADMIN='b5d8bfbe-f03a-4132-a13f-ab49aae834b7';USER='f4799f3f-703a-42b7-acf7-4cbbf55e7320';DIR='4ac50105-0c66-404e-a107-7cbd8a9a6442';IP='45.127.46.209';RULE='gpv-runtime-init-20261109'
try:
 plan=json.loads((ROOT/'deployment/fresh-runtime-and-memberships.REVIEW_ONLY.json').read_text());permit=json.loads((ROOT/'deployment/fresh-database-permissions.REVIEW_ONLY.json').read_text());sql=(ROOT/'deployment/fresh-runtime-provision.REVIEW_ONLY.sql').read_text()
 expected={'deployment/fresh-runtime-provision.REVIEW_ONLY.sql':'99f61353fc47791d419fd2e0dd808efa224cc7dcc7815e3fa1fd3ef8709cfb59','deployment/fresh-database-permissions.REVIEW_ONLY.json':'08c82dd56efd125626a787155206c7bb7815ad8bd799ed14f46fd2aec2f8c24c','deployment/fresh-runtime-and-memberships.REVIEW_ONLY.json':'0badd456cc1125d21a6eb5be20560f3f4018c090ebbaef30ceb7a2f28abff3ce'}
 for name,h in expected.items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise RuntimeError('REVIEWED_PROPOSAL_HASH_MISMATCH')
 admin={'directory_tenant':DIR,'object_id':ADMIN,'tenant':'demo-appservice-4e2dcce8d618','actor':'atiya-tabsum-shaik','role':'Admin','enabled':True}
 user={'directory_tenant':DIR,'object_id':USER,'tenant':admin['tenant'],'actor':'gpv-demo-user','role':'User','enabled':True}
 if plan['admin_membership_proposed']!=admin or plan['user_membership']['selected_mapping']!=user:raise RuntimeError('UNEXPECTED_IDENTITY_MAPPING')
 if permit['database']!=c.DB or permit['revision']!='008' or len(permit['permissions'])!=23 or sum(map(len,permit['permissions'].values()))!=59:raise RuntimeError('UNEXPECTED_GRANT_COUNTS')
 for table,rights in permit['permissions'].items():
  if f' GRANT {", ".join(rights)} ON OBJECT::dbo.[{table}] TO [governance_validator_web_runtime];' not in sql:raise RuntimeError('UNEXPECTED_GRANT_CONTENT')
 if len(re.findall(r'^ GRANT .* ON OBJECT::dbo',sql,re.M))!=46 or 'DENY UPDATE, DELETE ON OBJECT::dbo.validation_executions' not in sql:raise RuntimeError('UNEXPECTED_PERMISSION_SQL')
 S['proposal_hashes']=expected;S['approved_admin_mapping']=admin;S['approved_user_mapping']=user
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
  connection.close();raise RuntimeError('ACCESS_ALREADY_PRESENT_REQUIRES_IP_RECONCILIATION')
 except pyodbc.Error as error:
  message=' '.join(str(x) for x in error.args);m=re.search(r"Client with IP address '([0-9.]+)'",message)
  if '(40615)' not in message or not m or m.group(1)!=IP:raise RuntimeError('FIREWALL_IP_NOT_CONFIRMED') from None
 S.update(status='PASS',verified_blocked_client_ip=IP,firewall_rule=RULE,safe_cleanup_procedure='TESTED_EXACT_RULE_DELETE_WITH_UNCONDITIONAL_DEADLINE_EXEMPT_RESTORATION_AND_INVENTORY_READBACK',independent_supervisor='NOT_VERIFIED',preflight_finished_utc=datetime.now(timezone.utc).isoformat())
except Exception as error:
 S['failure_type']=type(error).__name__
 if isinstance(error,RuntimeError) and str(error).replace('_','').isalnum():S['failure_code']=str(error)
(OUT/'preflight.json').write_text(json.dumps(S,indent=2)+'\n');print(json.dumps(S,indent=2))
