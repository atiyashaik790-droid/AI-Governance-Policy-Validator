"""One bounded, read-only diagnostic against the approved SQL endpoint only."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SERVER = 'sql-governance-validator-dev-atiya.database.windows.net'
DATABASE = 'sqldb-governance-validator-dev'
SUB = '25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'
OUT = ROOT / 'docs/evidence/phase6b-sql-connectivity-2026-11-06'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ['AZURE_CONFIG_DIR'] = str(ROOT / '.azure-sql-cli')
    result = {'endpoint': SERVER, 'port': 1433, 'database': DATABASE, 'mutations': 0, 'checks': {}}
    stage, engine, credential = 'account', None, None
    started = time.monotonic()
    from sql_diagnostics import classify

    def deadline(*args):
        raise TimeoutError('Bounded diagnostic stage exceeded')

    signal.signal(signal.SIGALRM, deadline)
    try:
        account = subprocess.run(['az', 'account', 'show', '--query', 'id', '-o', 'json'], capture_output=True, text=True, timeout=15)
        assert account.returncode == 0 and json.loads(account.stdout) == SUB
        result['checks']['subscription'] = 'PASS'
        stage = 'dns'
        signal.alarm(8)
        addresses = socket.getaddrinfo(SERVER, 1433, type=socket.SOCK_STREAM)
        signal.alarm(0)
        assert addresses
        result['checks']['dns'] = 'PASS'
        stage = 'tcp'
        with socket.create_connection((SERVER, 1433), timeout=5):
            pass
        result['checks']['tcp1433'] = 'PASS'
        stage = 'driver'
        import pyodbc
        assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers()
        result['checks']['odbc18'] = 'PASS'
        sys.path.insert(0, str(ROOT / 'backend'))
        from pydantic_settings.sources import DotEnvSettingsSource
        DotEnvSettingsSource._read_env_files = lambda self: {}
        from azure.identity import AzureCliCredential
        from app.azure_sql import create_azure_sql_engine
        from sqlalchemy.engine import URL
        from sqlalchemy import text
        ids = {}
        with (ROOT / '.env').open() as source:
            for line in source:
                key, sep, value = line.partition('=')
                if sep and key.strip() in {'AZURE_SQL_TENANT_ID', 'AZURE_SQL_USER_OBJECT_ID'}:
                    ids[key.strip()] = value.strip().strip('\"\'')
        stage = 'configuration'
        credential = AzureCliCredential(tenant_id=ids['AZURE_SQL_TENANT_ID'], process_timeout=15)

        class ObservedCredential:
            def get_token(self, *args, **kwargs):
                token = credential.get_token(*args, **kwargs)
                result['checks']['token_acquisition'] = 'PASS'
                return token

        engine = create_azure_sql_engine(URL.create('mssql+pyodbc', host=SERVER, database=DATABASE),
                                         ids['AZURE_SQL_TENANT_ID'], ids['AZURE_SQL_USER_OBJECT_ID'], credential=ObservedCredential())
        result['checks']['secure_odbc_configuration'] = 'PASS'
        result['tls'] = {'encrypt': True, 'trust_server_certificate': False}
        stage = 'sql_connect'
        with engine.connect() as connection:
            result['checks']['sql_connect_tls_identity_pin'] = 'PASS'
            stage = 'readonly_identity'
            assert connection.scalar(text('SELECT DB_NAME()')) == DATABASE
            assert connection.scalar(text('SELECT version_num FROM dbo.alembic_version')) == '005'
        result['checks']['readonly_database_revision005'] = 'PASS'
        result['status'] = 'PASS'
    except Exception as error:
        result['status'] = 'BLOCKED'
        if stage in {'account', 'dns', 'tcp', 'driver'}:
            result['diagnostic'] = {'category': {'account':'SUBSCRIPTION_CONTEXT_UNAVAILABLE','dns':'DNS_RESOLUTION_UNAVAILABLE','tcp':'SQL_TCP_UNAVAILABLE','driver':'ODBC_DRIVER_UNAVAILABLE'}[stage], 'stage': stage}
        else:
            result['diagnostic'] = classify(error, stage)
    finally:
        signal.alarm(0)
        if engine is not None:
            engine.dispose()
        if credential is not None:
            credential.close()
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    (OUT / 'diagnostic.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
