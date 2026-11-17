import json,urllib.request,urllib.error,socket,time,hashlib,zipfile,sys
from pathlib import Path
from datetime import datetime,timezone
F=Path('docs/evidence/sso-only-deployment-2026-11-05')
ORIGIN='https://app-governance-validator-atiya-1026.azurewebsites.net'
RELEASE='1.2-5aad19f7eea45a42'
record={'status':'IN_PROGRESS','phase':sys.argv[1],'started_at_utc':datetime.now(timezone.utc).isoformat(),'socket_timeout_seconds':20,'max_attempts_per_request':2,'attempts':[],'checks':[],'hosted_changes':False,'microsoft_login_started':False}
out=F/('readonly-retest-'+sys.argv[1]+'.json')
def save():out.write_text(json.dumps(record,indent=2)+'\n')
def emit(v):print(json.dumps(v),flush=True)
def is_timeout(e):return isinstance(e,(TimeoutError,socket.timeout)) or isinstance(e,urllib.error.URLError) and isinstance(e.reason,(TimeoutError,socket.timeout))
def request(method,path,headers=None,body=False):
 for attempt in range(1,3):
  entry={'method':method,'path':path,'attempt':attempt,'started_at_utc':datetime.now(timezone.utc).isoformat()};start=time.monotonic()
  try:
   req=urllib.request.Request(ORIGIN+path,method=method,headers={**(headers or {}),'Content-Type':'application/json'},data=b'{}' if method=='POST' else None)
   try:
    with urllib.request.urlopen(req,timeout=20) as response:
     status=response.status;data=response.read(2000000) if body else b''
   except urllib.error.HTTPError as e:
    status=e.code;data=b'';e.close()
   entry.update(outcome='HTTP_RESPONSE',http_status=status,elapsed_seconds=round(time.monotonic()-start,3));record['attempts'].append(entry);save();return status,data
  except Exception as e:
   entry.update(outcome='TRANSPORT_TIMEOUT' if is_timeout(e) else 'TRANSPORT_ERROR',failure_type=type(e).__name__,elapsed_seconds=round(time.monotonic()-start,3));record['attempts'].append(entry);save();emit(entry)
   if not is_timeout(e) or attempt==2:raise
   # Check health before the one permitted retry; this probe has no retries.
   with urllib.request.urlopen(ORIGIN+'/health',timeout=20) as response:
    assert response.status==200 and json.load(response)['status']=='ok','UNHEALTHY_STOP'
   record.setdefault('health_before_retry',[]).append({'path':'/health','status':'PASS'});save()
def check(method,path,expected,headers=None,label=None):
 status,_=request(method,path,headers)
 result={'case':label,'method':method,'path':path,'expected':expected,'actual':status,'pass':status==expected};record['checks'].append(result);save();emit(result)
 assert status==expected,'UNEXPECTED_SECURITY_RESULT_STOP'
def public():
 for path in ['/health','/ready','/api/sso/status']:
  status,raw=request('GET',path,body=True);assert status==200,'UNHEALTHY_OR_UNAVAILABLE_STOP'
  data=json.loads(raw)
  if path=='/health':assert data['status']=='ok'
  elif path=='/ready':assert data['status']=='ready' and data['database_revision']=='005' and data['release']['build_version']==RELEASE and data['sso_available']
  else:assert data=={'sso_enabled':True,'configured':True,'demo_login_enabled':False}
  record.setdefault('public',{})[path]={'status':status,'body':data};save();emit({'path':path,'pass':True})
try:
 if sys.argv[1]=='preflight':
  public()
  with zipfile.ZipFile('artifacts/sso-only-20261105/governance-sso-only.zip') as archive:
   assert json.loads(archive.read('release.json'))['build_version']==RELEASE
   for member in archive.namelist():
    if not member.startswith('static/'):continue
    path='/' if member=='static/index.html' else '/'+member.removeprefix('static/')
    status,data=request('GET',path,body=True)
    assert status==200 and hashlib.sha256(data).digest()==hashlib.sha256(archive.read(member)).digest(),'FRONTEND_CHECKSUM_MISMATCH_STOP'
    record.setdefault('frontend_assets',[]).append({'path':path,'checksum_match':True});save()
   js=b''.join(archive.read(n) for n in archive.namelist() if n.endswith('.js'))
   assert b'Sign in with Microsoft' in js and all(t not in js for t in [b'Use demonstration access',b'Access token',b'Connect workspace',b'/api/auth/session'])
  record['microsoft_only_served_frontend']=True;record['browser_visual_confirmation']='PENDING_USER_NO_CONNECTED_BROWSER'
 else:
  assert json.loads((F/'readonly-retest-preflight.json').read_text())['status']=='PASS'
  w=json.loads((F/'worker-readonly-retest.json').read_text());assert w['status']=='PASS' and w['source_matches_reviewed']
  assert len(w['workers'])==1
  e=w['workers'][0]['environment'];assert e['SSO_ENABLED']=='true' and e['DEMO_BROWSER_LOGIN_ENABLED']=='false' and e['ALLOW_LEGACY_API_CREDENTIALS']=='false' and e['secret_present']
  previous=json.loads((F/'denial-checks.json').read_text());done={(c['case'],c['method'],c['path']) for c in previous['checks'] if c['pass']}
  routes=[('POST','/api/auth/session'),('POST','/api/auth/logout'),('GET','/api/auth/sessions'),('POST','/api/auth/sessions/synthetic/revoke'),('GET','/api/policies?limit=1'),('GET','/api/sso/me')]
  count=0
  for label,headers in [('unauthenticated',{}),('synthetic_provisioned_credential',{'Authorization':'Bearer synthetic-demo-credential-not-valid'}),('synthetic_preissued_session',{'Authorization':'Bearer synthetic-demo-session-not-valid'})]:
   for method,path in routes:
    if (label,method,path) in done:continue
    check(method,path,403 if path.startswith('/api/auth/') else 401,headers,label);count+=1
  assert count==13
  public()
  record.update(completed_prior_checks_retained=len(done),new_denial_checks_passed=count,total_denial_checks_passed=len(done)+count)
 record['status']='PASS'
except Exception as e:
 record.update(status='STOPPED',failure_type=type(e).__name__,failure_category='TRANSPORT_TIMEOUT' if is_timeout(e) else 'ASSERTION_OR_TRANSPORT_FAILURE')
finally:
 record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save();emit({'phase':record['phase'],'status':record['status'],'failure_category':record.get('failure_category'),'timeout_attempts':sum(a['outcome']=='TRANSPORT_TIMEOUT' for a in record['attempts'])})
if record['status']!='PASS':raise SystemExit(1)
