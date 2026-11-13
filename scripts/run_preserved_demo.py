"""Run the local demo against the preserved SQLite database without deleting it."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'private' / 'demo-preserved'
DB = DATA / 'offline.db'
TOKENS = DATA / '.demo-tokens.json'


def main():
    if not DB.is_file() or not TOKENS.is_file():
        raise SystemExit('Preserved database or demo credentials are missing')
    saved = json.loads(TOKENS.read_text())
    accounts = [
        {'user': 'offline-' + role.lower().replace(' ', '-'),
         'tenant': 'clean-demo-local', 'role': role,
         'token_hash': hashlib.sha256(saved[role].encode()).hexdigest()}
        for role in ('Admin', 'User', 'Policy Owner', 'Developer', 'Reviewer', 'Auditor')
    ]
    os.environ.update({
        'DATABASE_URL': 'sqlite:///' + str(DB),
        'PROVIDER_MODE': 'fixture', 'PII_MODE': 'presidio',
        'CORS_ORIGIN': 'http://localhost:5175',
        'DEMO_ACCOUNTS_JSON': json.dumps(accounts),
        'SSO_ENABLED': 'false', 'DEMO_BROWSER_LOGIN_ENABLED': 'true',
        'AZURE_SQL_TENANT_ID': '', 'AZURE_SQL_USER_OBJECT_ID': '',
        'AZURE_OPENAI_ENDPOINT': '', 'AZURE_OPENAI_DEPLOYMENT': '',
        'AZURE_OPENAI_API_KEY': '', 'AZURE_OPENAI_API_VERSION': 'v1',
        'OPENAI_API_KEY': '', 'ADLS_ACCOUNT_URL': '', 'ADLS_FILE_SYSTEM': '',
    })
    sys.path.insert(0, str(ROOT / 'backend'))
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8011, workers=1,
                log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
