import json,os,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
os.environ['AZURE_CONFIG_DIR']=str(ROOT/'.azure-sql-cli')
with urllib.request.urlopen('https://api.ipify.org?format=json',timeout=30) as response:
    ip=json.load(response)['ip']
p=subprocess.run(['az','sql','server','firewall-rule','show','--subscription','25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6','-g','rg_techdemo_Atiya_Tabsum_Shaik','-s','sql-governance-validator-dev-atiya','-n','gpv-verifier-single-ip-20261107','-o','json'],capture_output=True,text=True,timeout=60)
assert p.returncode==0,'Firewall read failed'
rule=json.loads(p.stdout)
assert rule['startIpAddress']==rule['endIpAddress']==ip,'Firewall IP drift; stop without mutation'
result={'status':'PASS','current_public_ip':ip,'rule':rule['name'],'start_ip':rule['startIpAddress'],'end_ip':rule['endIpAddress'],'mutations':0}
(Path(__file__).resolve().parent/'firewall-recheck.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
