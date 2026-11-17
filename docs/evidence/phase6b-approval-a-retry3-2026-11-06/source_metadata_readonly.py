"""SELECT-only source identity/schema/grant baseline; no application data selected."""
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['AZURE_CONFIG_DIR'] = str(ROOT / '.azure-sql-cli')
# Load only public directory identifiers; suppress all dotenv settings loading.
ids = {}
with (ROOT / '.env').open() as source:
    for line in source:
        key, sep, value = line.partition('=')
        if sep and key.strip() in {'AZURE_SQL_TENANT_ID', 'AZURE_SQL_USER_OBJECT_ID'}:
            ids[key.strip()] = value.strip().strip('\"\'')
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_files = lambda self: {}
from app.azure_sql import create_azure_sql_engine
from sqlalchemy.engine import URL
from sqlalchemy import text
server = 'sql-governance-validator-dev-atiya'
database = 'sqldb-governance-validator-dev'
e = create_azure_sql_engine(URL.create('mssql+pyodbc',host=server+'.database.windows.net',database=database), ids['AZURE_SQL_TENANT_ID'], ids['AZURE_SQL_USER_OBJECT_ID'])
queries = {
 'identity': "SELECT DB_NAME() db,USER_NAME() principal,SCHEMA_NAME() default_schema,CAST(DATABASEPROPERTYEX(DB_NAME(),'Collation') AS varchar(128)) collation",
 'revision': 'SELECT version_num FROM dbo.alembic_version',
 'runtime_mapping': "SELECT name,type,CONVERT(varchar(100),sid,1) sid,CONVERT(varchar(36),TRY_CONVERT(uniqueidentifier,sid)) client_id FROM sys.database_principals WHERE name='app-governance-validator-atiya-1026'",
 'new_tables': "SELECT name FROM sys.tables WHERE name IN ('workspace_policy_states','workspace_policy_assignments','workspace_policy_assignment_events','execution_policy_evidence','review_protected_content') ORDER BY name",
 'runtime_grants': "SELECT USER_NAME(p.grantee_principal_id) principal,p.state_desc,p.permission_name,OBJECT_NAME(p.major_id) object_name FROM sys.database_permissions p WHERE p.grantee_principal_id IN (SELECT principal_id FROM sys.database_principals WHERE name IN ('app-governance-validator-atiya-1026','governance_validator_web_runtime')) ORDER BY principal,object_name,permission_name",
 'runtime_roles': "SELECT USER_NAME(role_principal_id) role_name,USER_NAME(member_principal_id) member_name FROM sys.database_role_members WHERE member_principal_id=USER_ID('app-governance-validator-atiya-1026') ORDER BY role_name"
}
result = {}
with e.connect() as c:
    assert c.scalar(text('SELECT DB_NAME()')) == database
    for key,q in queries.items():
        assert q.startswith('SELECT ')
        result[key] = [dict(r) for r in c.execute(text(q)).mappings()]
e.dispose()
assert result['revision'] == [{'version_num':'005'}]
assert result['identity'][0]['collation'] == 'SQL_Latin1_General_CP1_CI_AS'
assert not result['new_tables']
assert len(result['runtime_mapping']) == 1 and result['runtime_mapping'][0]['type'] == 'E'
if '--final' in sys.argv:
    before = json.loads((OUT/'live-preflight.json').read_text())['source_sql']
    assert result == before, 'Production metadata changed'
    (OUT/'production-final-readonly.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'source_sql':result,'unchanged':True},indent=2)+'\n')
else:
    pre = json.loads((OUT/'retry-preflight.json').read_text())
    pre['source_sql'] = result
    pre['sql_metadata_utc'] = datetime.now(timezone.utc).isoformat()
    (OUT/'live-preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
print(json.dumps({'source_revision':'005','new_tables_absent':True,'runtime_mapping_verified':True,'grant_count':len(result['runtime_grants']),'production_mutations':0,'final': '--final' in sys.argv}))
