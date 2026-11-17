"""One approved firewall window; cleanup is never blocked by authorization expiry."""
import importlib.util,json,os,subprocess,sys,time,signal
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/sigmoid/AI governance policy validator');OUT=ROOT/'docs/evidence/policy-seeding-2026-11-09';OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('cloud','/tmp/gpv_create_persistent_sql.py');cloud=importlib.util.module_from_spec(spec);spec.loader.exec_module(cloud)
RULE='gpv-policy-seed-20261109';IP='45.127.46.209';RULEURL=cloud.SERVER_URL+'/firewallRules/'+RULE+cloud.API
S={'status':'BLOCKED','firewall_creation':'NOT_ATTEMPTED','connectivity':'NOT_VERIFIED','firewall_cleanup':'NOT_NEEDED','independent_cleanup_supervisor':'NOT_VERIFIED','source_sql_mutations':0,'webapp_mutations':0,'runtime_grant_changes':0,'providers':0}
original_arm=cloud.arm;started_mono=None;started_wall=None;attempted=False;baseline=None;source=None;app=None

def save(event,**fields):
 S.update(fields);S.setdefault('events',[]).append({'utc':datetime.now(timezone.utc).isoformat(),'event':event})
 p=OUT/'result.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(S,indent=2)+'\n');t.replace(p)
 print(json.dumps({'event':event,**fields}),flush=True)

def gate():
 if started_mono is not None and (time.monotonic()-started_mono>=660 or time.time()-started_wall>=660):raise TimeoutError('NEW_OPERATION_DEADLINE')

def arm(url,method='GET',payload=None,cleanup=False):
 if not cleanup:gate()
 if method not in {'GET','PUT','DELETE'} or method!='GET' and url!=RULEURL:raise RuntimeError('WRITE_TARGET_NOT_ALLOWED')
 # Original ARM transport has its own unrelated DB-only write guard; call transport directly here for exact rule only.
 from urllib.request import Request,urlopen
 from urllib.error import HTTPError
 headers={'Authorization':'Bearer '+cloud.TOKEN}
 if payload is not None:headers['Content-Type']='application/json'
 try:
  with urlopen(Request(url,method=method,headers=headers,data=json.dumps(payload).encode() if payload is not None else None),timeout=20) as r:
   raw=r.read();return r.status,json.loads(raw) if raw else {}
 except HTTPError as error:
  code=error.code;error.close();return code,{}

def get(url,cleanup=False):
 code,data=arm(url,cleanup=cleanup)
 if code!=200:raise RuntimeError('READ_FAILED_'+str(code))
 return data

def inventory(cleanup=False):
 body=get(cloud.SERVER_URL+'/firewallRules'+cloud.API,cleanup=cleanup)
 if body.get('nextLink'):raise RuntimeError('PAGINATED_INVENTORY')
 return sorted([{'name':x['name'],'start_ip':x['properties']['startIpAddress'],'end_ip':x['properties']['endIpAddress']} for x in body['value']],key=lambda x:x['name'])

def worker(mode,timeout):
 gate()
 env={'PATH':str(ROOT/'.venv/bin')+':/usr/bin:/bin','HOME':os.environ.get('HOME','/home/sigmoid'),'AZURE_CONFIG_DIR':str(ROOT/'.azure-sql-cli'),'PYTHONPATH':str(ROOT/'docs/evidence/master-repair-2026-11-07/continued-guard')+':'+str(ROOT/'backend'),'PYTHONDONTWRITEBYTECODE':'1','DATABASE_URL':'mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-gpv-demo-v008-20261108','AZURE_SQL_AUTH_MODE':'cli','AZURE_SQL_TENANT_ID':'4ac50105-0c66-404e-a107-7cbd8a9a6442','AZURE_SQL_USER_OBJECT_ID':'b5d8bfbe-f03a-4132-a13f-ab49aae834b7','PROVIDER_MODE':'fixture','PII_MODE':'regex','GPV_SQL_STOP_UTC_EPOCH':str(started_wall+660)}
 with (OUT/('worker-'+mode+'.log')).open('w') as log:
  return subprocess.run([str(ROOT/'.venv/bin/python'),'-B','/tmp/gpv_policy_seed_worker.py',mode],cwd=ROOT/'backend',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode

try:
 account=cloud.authenticate();S['subscription']=account
 target=get(cloud.TARGET+cloud.API)
 if target['properties']['databaseId']!='80dd1ba9-74e5-4d26-8463-081572c9c22e' or target['id'].casefold()!=cloud.TARGET.removeprefix('https://management.azure.com').casefold() or target['properties']['status']!='Online':raise RuntimeError('TARGET_MISMATCH')
 server=get(cloud.SERVER_URL+cloud.API)
 if server['properties']['fullyQualifiedDomainName']!='sql-governance-validator-dev-atiya.database.windows.net':raise RuntimeError('SERVER_MISMATCH')
 # Read-only conditional preflight is durable; never replay a migration.
 pre=json.loads((OUT/'preflight.json').read_text())
 if pre['status']!='PASS' or pre.get('verified_blocked_client_ip')!=IP or pre.get('firewall_rule')!=RULE:raise RuntimeError('BOOTSTRAP_PRECHECK_MISMATCH')
 if datetime.now(timezone.utc).timestamp()-datetime.fromisoformat(pre['preflight_finished_utc']).timestamp()>300:raise RuntimeError('BOOTSTRAP_PREFLIGHT_STALE')
 import hashlib
 for name,expected_hash in pre['proposal_hashes'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected_hash:raise RuntimeError('REVIEWED_PROPOSAL_CHANGED')
 baseline=inventory()
 if any(x['name']==RULE for x in baseline):raise RuntimeError('RULE_ALREADY_EXISTS')
 source=cloud.source_snapshot();app=cloud.app_snapshot();S['hosted_before']=cloud.health()
 (OUT/'original-firewall-rules.json').write_text(json.dumps(baseline,indent=2)+'\n')
 S.update(target_database=cloud.DB,server=cloud.SERVER,source_before=source,app_before=app)
 started_mono=time.monotonic();started_wall=time.time();attempted=True
 save('RULE_CREATION_INTENT_DURABLE',firewall_creation='ATTEMPTED',rule=RULE,ip=IP,window_started_epoch=started_wall,window_deadline_epoch=started_wall+900,sql_operation_deadline_epoch=started_wall+660)
 code,_=arm(RULEURL,'PUT',{'properties':{'startIpAddress':IP,'endIpAddress':IP}})
 if code not in {200,201,202}:raise RuntimeError('RULE_PUT_FAILED_'+str(code))
 expected=sorted(baseline+[{'name':RULE,'start_ip':IP,'end_ip':IP}],key=lambda x:x['name'])
 if inventory()!=expected:raise RuntimeError('RULE_INVENTORY_MISMATCH')
 save('FIREWALL_CREATION_PASS',firewall_creation='PASS')
 # Read-only connectivity attempts only; no migration is retried.
 sys.path.insert(0,str(ROOT/'backend'))
 import pyodbc,struct
 from app.azure_sql import verify_token_identity,SQL_COPT_SS_ACCESS_TOKEN
 token=json.loads(cloud.cli(['account','get-access-token','--subscription',cloud.SUB,'--resource','https://database.windows.net/','-o','json']))
 verify_token_identity(token['accessToken'],int(token['expires_on']),'4ac50105-0c66-404e-a107-7cbd8a9a6442','b5d8bfbe-f03a-4132-a13f-ab49aae834b7')
 encoded=token['accessToken'].encode('utf-16-le');connected=False
 for n in range(6):
  gate()
  try:
   connection=pyodbc.connect('Driver={ODBC Driver 18 for SQL Server};Server=tcp:sql-governance-validator-dev-atiya.database.windows.net,1433;Database=sqldb-gpv-demo-v008-20261108;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;',attrs_before={SQL_COPT_SS_ACCESS_TOKEN:struct.pack(f'<I{len(encoded)}s',len(encoded),encoded)},timeout=10)
   connection.timeout=10
   if connection.cursor().execute("SELECT DB_NAME(),CAST(SERVERPROPERTY('ServerName') AS nvarchar(128))").fetchone()[0]!=cloud.DB:raise RuntimeError('SQL_TARGET_MISMATCH')
   connection.close();connected=True;break
  except pyodbc.Error as error:
   if '(40615)' not in str(error):raise RuntimeError('SQL_CONNECTION_FAILED') from None
   if n<5:time.sleep(10)
 if not connected:raise RuntimeError('FIREWALL_PROPAGATION_TIMEOUT')
 save('CONNECTIVITY_PASS',connectivity='PASS')
 remaining=min(500,660-(time.time()-started_wall),660-(time.monotonic()-started_mono))
 if remaining<120:raise TimeoutError('INSUFFICIENT_SQL_WINDOW')
 code=worker('seed',remaining)
 sql=json.loads((OUT/'sql-result.json').read_text());save('SQL_WORK_FINISHED',sql_result=sql,runtime_grant_changes=0)
 if code!=0:raise RuntimeError('BOOTSTRAP_OR_QUALIFICATION_FAILED_NO_RETRY')

except BaseException as error:
 save('OPERATION_STOPPED',failure_type=type(error).__name__,failure_code=str(error) if isinstance(error,(RuntimeError,TimeoutError)) and str(error).replace('_','').isalnum() else None)
finally:
 if attempted:
  save('CLEANUP_STARTED',firewall_cleanup='IN_PROGRESS')
  for attempt in range(3):
   try:
    # Cleanup deliberately has no authorization/deadline guard.
    code,_=arm(RULEURL,'DELETE',cleanup=True)
    if code==401:
     cloud.authenticate();code,_=arm(RULEURL,'DELETE',cleanup=True)
    if code not in {200,202,204,404}:raise RuntimeError('RULE_DELETE_FAILED_'+str(code))
    for n in range(6):
     current=inventory(cleanup=True)
     if not any(x['name']==RULE for x in current):break
     time.sleep(3)
    absent=not any(x['name']==RULE for x in current)
    unchanged=current==baseline
    save('CLEANUP_VERIFIED',temporary_rule_absent=absent,original_rules_unchanged=unchanged,firewall_cleanup='PASS' if absent and unchanged else 'FAIL',firewall_elapsed_seconds=round(max(time.time()-started_wall,time.monotonic()-started_mono),3),restoration_overdue=time.time()-started_wall>900)
    (OUT/'final-firewall-rules.json').write_text(json.dumps(current,indent=2)+'\n')
    if absent:break
   except BaseException as error:save('CLEANUP_FAILURE',cleanup_error_type=type(error).__name__,firewall_cleanup='FAIL')
   time.sleep(3)
 try:
  hosted=cloud.health();same_source=cloud.source_snapshot()==source if source is not None else None;same_app=cloud.app_snapshot()==app if app is not None else None
  save('PRODUCTION_POSTCHECK',hosted_after=hosted,production_source_unchanged=same_source,production_app_unchanged=same_app)
 except BaseException as error:save('POSTCHECK_FAILURE',postcheck_failure_type=type(error).__name__)
 passed=S.get('sql_result',{}).get('status')=='PASS' and S.get('firewall_cleanup')=='PASS' and S.get('production_source_unchanged') and S.get('production_app_unchanged') and not S.get('restoration_overdue')
 save('FINISHED',status='PASS' if passed else 'BLOCKED',finished_utc=datetime.now(timezone.utc).isoformat())
