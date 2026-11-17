"""Run only after user confirms private Portal secret save. No secret output."""
import os,json,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
R=Path.cwd();os.environ['AZURE_CONFIG_DIR']=str(R/'.azure-sql-cli');P=R/'docs/evidence/stage-f-execution-2026-11-04/activation.json'
sub='25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6';group='rg_techdemo_Atiya_Tabsum_Shaik';app='app-governance-validator-atiya-1026';tenant='4ac50105-0c66-404e-a107-7cbd8a9a6442';client='a1a7da0b-ad29-49ec-a9ea-c59219e60df5';origin='https://'+app+'.azurewebsites.net'
args=['--subscription',sub,'-g',group,'-n',app]
r={'stage':'F','started_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PRECHECK','activation_submitted':False,'stage_g_executed':False,'database_writes':False,'secret_value_logged':False}
def save():P.write_text(json.dumps(r,indent=2)+'\n')
def az(command):
 p=subprocess.run(['az']+command+['-o','json','--only-show-errors'],capture_output=True,text=True,timeout=60)
 if p.returncode:raise RuntimeError('Azure operation failed; raw output withheld')
 return json.loads(p.stdout) if p.stdout.strip() else None
def settings():return {x['name']:x.get('value','') for x in az(['webapp','config','appsettings','list']+args)}
def set_values(values):az(['webapp','config','appsettings','set']+args+['--settings']+[k+'='+v for k,v in values.items()])
def http(route):
 with urllib.request.urlopen(origin+route,timeout=45) as response:return {'http_status':response.status,'body':json.load(response)}
values={'ENTRA_TENANT_ID':tenant,'ENTRA_CLIENT_ID':client,'SSO_PUBLIC_ORIGIN':origin,'SSO_SESSION_MINUTES':'60','DEMO_BROWSER_LOGIN_ENABLED':'true','SSO_ENABLED':'true'}
try:
 confirm=R/'docs/evidence/stage-f-execution-2026-11-04/user-secret-save-confirmation.json'
 assert confirm.exists() and json.loads(confirm.read_text()).get('user_confirmed_saved') is True,'Wait for actual user confirmation'
 prereq=json.loads((P.parent/'prerequisites.json').read_text());assert prereq['status']=='PREREQUISITES_VERIFIED_AWAITING_USER_SECRET_ENTRY'
 a=az(['account','show','--query','{subscription:id,tenant:tenantId}']);assert a=={'subscription':sub,'tenant':tenant}
 reg=az(['ad','app','show','--id',client,'--query','{clientId:appId,redirectUris:web.redirectUris}']);assert reg['clientId']==client and set(reg['redirectUris'])=={origin+'/',origin+'/api/sso/callback'}
 logs=az(['webapp','log','show']+args+['--query','{http:httpLogs.fileSystem.enabled,application:applicationLogs.fileSystem.level}']);assert logs=={'http':False,'application':'Information'}
 before=settings();assert before.get('ENTRA_CLIENT_SECRET','').strip() and before.get('SSO_ENABLED','false').lower()=='false' and before.get('DEMO_BROWSER_LOGIN_ENABLED','true').lower()=='true'
 assert before.get('CORS_ORIGIN')==origin
 r['secret_presence_verified']=True;r['redirect_and_logging_prerequisites_verified']=True;r['status']='SUBMITTING_APPROVED_SETTINGS';r['activation_submitted']=True;save()
 set_values(values)
 after=settings();assert all(after.get(k)==v for k,v in values.items())
 assert {k:v for k,v in before.items() if k not in values}=={k:v for k,v in after.items() if k not in values}
 r['unrelated_settings_and_secret_preserved']=True;r['configured_setting_names']=list(values);save()
 for attempt in range(36):
  try:
   checks={route:http(route) for route in ('/health','/ready','/api/sso/status')}
   ready=checks['/ready']['body'];flags=checks['/api/sso/status']['body']
   assert ready['status']=='ready' and ready['database_revision']=='005' and ready['release']['build_version']=='1.2-6749226f1af65b63' and ready['sso_available'] is True
   assert flags=={'sso_enabled':True,'configured':True,'demo_login_enabled':True}
   r['checks']=checks;r['status']='CONFIGURATION_HTTP_PASS_LOGIN_CHOICES_PENDING';break
  except Exception:
   if attempt==35:raise RuntimeError('Bounded readiness checks failed')
   time.sleep(5)
except Exception as e:
 r['status']='BLOCKED';r['error_kind']=type(e).__name__
 if r['activation_submitted']:
  try:
   set_values({'SSO_ENABLED':'false','DEMO_BROWSER_LOGIN_ENABLED':'true'})
   az(['webapp','config','appsettings','delete']+args+['--setting-names','ENTRA_CLIENT_SECRET'])
   s=settings();assert s.get('SSO_ENABLED')=='false' and s.get('DEMO_BROWSER_LOGIN_ENABLED')=='true' and 'ENTRA_CLIENT_SECRET' not in s
   r['rollback_settings_verified']=True
  except Exception as rollback_error:r['rollback_error_kind']=type(rollback_error).__name__
r['updated_at_utc']=datetime.now(timezone.utc).isoformat();save();print(json.dumps(r))
