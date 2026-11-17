"""Approved retry only; no production configuration or keys loaded into Settings."""
import os
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[3]
os.environ['PHASE6B_APPROVAL_A_WINDOW'] = 'retry-4'
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['PROVIDER_MODE'] = 'fixture'
os.environ['PII_MODE'] = 'regex'
with (ROOT/'.env').open() as source:
    for line in source:
        key, separator, value = line.partition('=')
        if separator and key.strip() in {'AZURE_SQL_TENANT_ID','AZURE_SQL_USER_OBJECT_ID'}:
            os.environ[key.strip()] = value.strip().strip('\"\'')
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files = lambda self: {}
sys.argv = [str(ROOT/'scripts/phase6b_approval_a.py'), '--execute', '--approval-token', 'PHASE6B-APPROVAL-A-RETRY4-20261106']
runpy.run_path(sys.argv[0], run_name='__main__')
