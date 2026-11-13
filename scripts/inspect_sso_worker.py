"""Read-only main-container inspection. Run with /opt/az/bin/python3 from repo root.

Uses the existing CLI identity and exec WebSocket; never writes hosted files or
queries SQL. Only selected non-secret flags and sanitized lifecycle labels return.
"""

import os
import sys
import json
import subprocess
import base64
import time
import re
import ssl
from pathlib import Path
from datetime import datetime, timezone
import websocket

R = Path.cwd()
os.environ["AZURE_CONFIG_DIR"] = str(R / ".azure-sql-cli")
sys.path.insert(0, str(R / "scripts"))
import hashlib
import verify_hosted_runtime as p

expected = {
    n: hashlib.sha256((R / "backend/app" / n).read_bytes()).hexdigest()
    for n in ("config.py", "sso.py", "hosting.py")
}


def payload(marker):
    return (
        """import os,json,sys,hashlib,time,datetime
from pathlib import Path
r={'status':'PASS','sql_accessed':False,'hosted_files_written':False}
try:
 from app.config import settings,Settings
 import app.config as config
 base=Path(config.__file__).parent
 r['loaded_config_path']=str(config.__file__)
 r['reconstructed_settings']={'sso_enabled':settings.sso_enabled,'demo_enabled':settings.demo_browser_login_enabled,'secret_present':bool(settings.entra_client_secret)}
 keys=('SSO_ENABLED','APPSETTING_SSO_ENABLED','DEMO_BROWSER_LOGIN_ENABLED','WEBSITE_SLOT_NAME','WEBSITE_HOSTNAME')
 r['shell_environment']={k:os.environ.get(k) for k in keys}
 r['shell_environment']['secret_present']=bool(os.environ.get('ENTRA_CLIENT_SECRET'))
 r['source_hashes']={n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in ('config.py','sso.py','hosting.py')}
 r['source_matches_reviewed']=r['source_hashes']=="""
        + repr(expected)
        + """
 r['env_file_path']=str(Settings.model_config.get('env_file'));r['env_file_exists']=Path(Settings.model_config['env_file']).exists()
 r['workers']=[]
 boot=time.time()-float(Path('/proc/uptime').read_text().split()[0]);hz=os.sysconf('SC_CLK_TCK')
 for path in Path('/proc').iterdir():
  if not path.name.isdigit() or int(path.name)==os.getpid():continue
  try:
   a=(path/'cmdline').read_bytes().split(b'\\0')
   if not any(b'uvicorn' in v or b'gunicorn' in v for v in a):continue
   raw=(path/'environ').read_bytes().split(b'\\0');env={'secret_present':False}
   for part in raw:
    if b'=' in part:
     k,v=part.split(b'=',1)
     if k.decode(errors='ignore') in keys:env[k.decode()]=v.decode(errors='replace')
     if k==b'ENTRA_CLIENT_SECRET':env['secret_present']=bool(v)
   st=(path/'stat').read_text().rsplit(')',1)[1].split();start=boot+int(st[19])/hz
   r['workers'].append({'pid':int(path.name),'environment':env,'started_at_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'entrypoint_hosting':any(b'app.hosting:app' in v for v in a),'executable':str((path/'exe').resolve()),'safe_argv':[v.decode() if v in {b'-m',b'uvicorn',b'app.hosting:app',b'--host',b'0.0.0.0',b'--port',b'8000',b'--workers',b'1',b'--no-access-log'} else 'EXECUTABLE_OR_OTHER_REDACTED' for v in a if v]})
  except (OSError,ValueError):continue
 r['lifecycle_events']=[]
 import re
 files=sorted(Path('/home/LogFiles').glob('*docker*.log'),key=lambda f:f.stat().st_mtime,reverse=True)[:6]
 for f in files:
  with f.open('rb') as log:
   log.seek(max(0,f.stat().st_size-2000000));lines=log.read().decode(errors='replace').splitlines()
  for line in lines:
   if not ('2026-11-04T18:' in line or '2026-11-04 18:' in line):continue
   tags={'starting_container':'starting container','container_started':'container started','container_ready':'container is ready','initiating_warmup':'initiating warmup','warmup_complete':'initialized successfully','stopping_container':'stopping container','started_server_process':'started server process','startup_complete':'application startup complete','startup_failed':'startup failed','recycling':'recycl','site_startup_probe_succeeded':'site startup probe succeeded','site_startup_probe_failed':'site startup probe failed','site_running':'site is running','site_stopped':'site stopped','container_start_finished':'container start method finished','termination_started':'container is terminating'}
   categories=[k for k,v in tags.items() if v in line.lower()]
   if not categories:continue
   stamp=re.search(r'2026-11-04[T ]18:[0-9:.]+Z?',line)
   pid_text=line.lower().split('started server process [',1)[1].split(']',1)[0] if 'started server process [' in line.lower() else ''
   r['lifecycle_events'].append({'log_file':f.name,'timestamp':stamp.group(0) if stamp else None,'categories':categories,'worker_pid':int(pid_text) if pid_text.isdigit() else None})
 r['application_diagnostics']=[]
 appfiles=list(Path('/home/LogFiles').glob('*default*.log'))+list(Path('/home/LogFiles/Application').glob('*.log'))
 r['application_log_files']=[{'name':f.name,'bytes':f.stat().st_size} for f in appfiles[:12]]
 for f in appfiles[:12]:
  with f.open('rb') as log:
   log.seek(max(0,f.stat().st_size-2000000));lines=log.read().decode(errors='replace').splitlines()
  r.setdefault('application_log_summary',[]).append({'name':f.name,'mtime_epoch':f.stat().st_mtime,'keyword_counts':{k:sum(k in line for line in lines) for k in ('Traceback','RuntimeError','Started server process','Application startup','ERROR')},'timestamp_samples':re.findall(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+',chr(10).join(lines))[-3:]})
  for line in lines:
   stamp=re.search(r'2026-11-04[T ]18:[0-9:.]+Z?',line)
   if not stamp:continue
   tags={'hosting_configuration_rejected':'App Service requires reviewed live SQL managed identity','runtime_error':'RuntimeError:','validation_error':'ValidationError:','import_error':'ImportError:','module_missing':'ModuleNotFoundError:','traceback':'Traceback (most recent call last)','started_server_process':'Started server process','startup_complete':'Application startup complete','shutting_down':'Shutting down','startup_failed':'Application startup failed'}
   categories=[k for k,v in tags.items() if v in line]
   if categories:r['application_diagnostics'].append({'log_file':f.name,'timestamp':stamp.group(0),'categories':categories})
 r['startup_files']=[]
 for name in ('/opt/startup/startup.sh','/home/site/wwwroot/startup.sh',str(base.parent/'startup.sh')):
  f=Path(name)
  if not f.is_file():continue
  s=f.read_text();r['startup_files'].append({'path':name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'mentions_sso_enabled':'SSO_ENABLED' in s,'uses_uvicorn':'uvicorn' in s,'uses_hosting_entrypoint':'app.hosting:app' in s,'mtime_utc':datetime.datetime.fromtimestamp(f.stat().st_mtime,datetime.timezone.utc).isoformat()})
except Exception as e:r['status']='UNKNOWN';r['error_kind']=type(e).__name__
print("""
        + repr(marker)
        + """+json.dumps(r),file=sys.__stdout__,flush=True)
"""
    )


def parse(raw, marker):
    for line in p.terminal_text(raw).splitlines(keepends=True):
        if line.startswith(marker + "{") and line.endswith("\n"):
            return json.loads(line[len(marker) :])
    return None


original_payload = payload


def corrected_payload(marker):
    return original_payload(marker).replace("b'\\\\0'", "b'\\0'")


p.payload = corrected_payload
P = R / "docs/evidence/stage-f-live-worker-2026-11-05/runtime-final.json"
r = {
    "status": "BLOCKED",
    "method": "EXISTING_MAIN_CONTAINER_EXEC_WEBSOCKET",
    "hosted_changes": False,
    "sql_accessed": False,
}
ws = None
try:
    a = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            "https://management.azure.com/",
            "--tenant",
            "4ac50105-0c66-404e-a107-7cbd8a9a6442",
            "-o",
            "json",
            "--only-show-errors",
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert a.returncode == 0
    token = json.loads(a.stdout)["accessToken"]
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
    assert (
        claims["tid"] == "4ac50105-0c66-404e-a107-7cbd8a9a6442"
        and claims["oid"] == "b5d8bfbe-f03a-4132-a13f-ab49aae834b7"
    )
    r["pinned_operator_identity_verified"] = True
    url = "wss://app-governance-validator-atiya-1026.scm.azurewebsites.net/exec/shell?shell=%2Fbin%2Fsh"
    ws = websocket.create_connection(
        url,
        header={"Authorization": "Bearer " + token},
        sslopt={"cert_reqs": ssl.CERT_REQUIRED},
        timeout=20,
        enable_multithread=True,
    )
    r["handshake"] = "PASS"
    ws.settimeout(5)
    ws.send(json.dumps({"width": 160, "height": 40}))
    marker = "SSO_PROBE_" + os.urandom(12).hex() + ":"
    buf = b""
    sent = False
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        try:
            chunk = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        if not chunk:
            break
        buf += chunk.encode() if isinstance(chunk, str) else chunk
        buf = buf[-524288:]
        if not sent and re.search(
            r"(?:^|[\r\n])[^\r\n]{0,180}[#$] *$", p.terminal_text(buf)
        ):
            ws.send_binary(p.remote_input(marker))
            sent = True
            r["payload_sent"] = True
        out = parse(buf, marker)
        if out is not None:
            r.update(out)
            break
    if r.get("status") != "PASS":
        r["category"] = "NO_PARSED_RUNTIME_RESULT"
        r["payload_sent"] = sent
except Exception as e:
    r["error_kind"] = type(e).__name__
    r["http_status"] = getattr(e, "status_code", None)
finally:
    if ws is not None:
        ws.close()
r["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
P.write_text(json.dumps(r, indent=2) + "\n")
print(json.dumps(r))
