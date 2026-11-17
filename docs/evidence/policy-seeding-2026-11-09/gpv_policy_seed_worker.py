"""One atomic approved new-DB permission + two-membership bootstrap; no migration/provider."""
import json,hashlib,os,sys,time
from pathlib import Path
ROOT=Path('/home/sigmoid/AI governance policy validator');OUT=ROOT/'docs/evidence/policy-seeding-2026-11-09'
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'scripts')]
from sqlalchemy import text,select,event
from sqlalchemy.orm import Session
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool
from app.database import engine
from app.azure_sql import create_azure_sql_engine
from app.models import SsoMembership,Audit
from app.schema_compatibility import inspect_schema,schema_diagnostic
from app.security import Identity
from app.user_access import authorize
from fastapi import HTTPException
from starlette.requests import Request
from manage_sso_membership import apply_mapping,validate_mapping
S={'status':'BLOCKED','sql_mutation_attempted':False,'transaction_committed':False,'provider_calls':0,'runtime_grant_changes':0,'membership_changes':0}
RUNTIME='app-governance-validator-atiya-1026';ROLE='governance_validator_web_runtime';DIR='4ac50105-0c66-404e-a107-7cbd8a9a6442';ADMIN='b5d8bfbe-f03a-4132-a13f-ab49aae834b7'
def gate():
 if time.time()>=float(os.environ['GPV_SQL_STOP_UTC_EPOCH']):raise TimeoutError('NEW_SQL_DEADLINE_EXPIRED')
@event.listens_for(engine,'before_cursor_execute')
def protect(conn,cursor,statement,parameters,context,executemany):
 if statement.strip().upper()!='REVERT':gate()
def save():
 p=OUT/'sql-result.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(S,indent=2,default=str)+'\n');t.replace(p)
GRANTS="SELECT r.name AS principal,p.state_desc,p.permission_name,OBJECT_NAME(p.major_id) AS object_name FROM sys.database_permissions p JOIN sys.database_principals r ON r.principal_id=p.grantee_principal_id WHERE r.name IN ('app-governance-validator-atiya-1026','governance_validator_web_runtime') ORDER BY principal,state_desc,permission_name,object_name"
MEMBERS="SELECT directory_tenant,object_id,tenant,actor,role,enabled FROM dbo.sso_memberships WHERE object_id IN ('b5d8bfbe-f03a-4132-a13f-ab49aae834b7','f4799f3f-703a-42b7-acf7-4cbbf55e7320') ORDER BY object_id"
def source_snapshot():
 e=create_azure_sql_engine(URL.create('mssql+pyodbc',host='sql-governance-validator-dev-atiya.database.windows.net',database='sqldb-governance-validator-dev'),DIR,ADMIN,query_timeout=15)
 @event.listens_for(e,'before_cursor_execute')
 def source_readonly(conn,cursor,statement,parameters,context,executemany):
  gate()
  if not statement.lstrip().upper().startswith('SELECT'):raise RuntimeError('SOURCE_NON_SELECT_REJECTED')
 try:
  with e.connect() as c:
   if c.scalar(text('SELECT DB_NAME()'))!='sqldb-governance-validator-dev':raise RuntimeError('SOURCE_DATABASE_MISMATCH')
   return {'revision':list(c.scalars(text('SELECT version_num FROM dbo.alembic_version'))),'runtime_grants':[dict(x) for x in c.execute(text(GRANTS)).mappings()],'memberships':[dict(x) for x in c.execute(text(MEMBERS)).mappings()]}
 finally:e.dispose()
from approved_policy_seed_core import documents,seed,readback,evaluate
import asyncio
from dataclasses import asdict
from app.schema_manifests import metadata_for_revision
canon=lambda rows:sorted(json.dumps(x,sort_keys=True,default=str) for x in rows)
try:
 reviewed=documents(ROOT/'deployment/demo-policy-seed.REVIEW_ONLY.json')
 baseline=json.loads((ROOT/'docs/evidence/runtime-user-bootstrap-2026-11-09/sql-result.json').read_text())
 S['source_before']=source_snapshot()
 if S['source_before']!=baseline['source_after']:raise RuntimeError('SOURCE_BASELINE_DRIFT')
 allowed={'policies','policy_versions','workspace_policy_states','workspace_policy_assignments','workspace_policy_assignment_events','audit_events','rate_buckets'}
 def counts(c):return {t:c.scalar(text('SELECT COUNT_BIG(*) FROM dbo.['+t+']')) for t in metadata_for_revision('008').tables}
 def preserved(c):
  if canon([dict(x) for x in c.execute(text(GRANTS)).mappings()])!=canon(baseline['explicit_permission_rows']):raise RuntimeError('RUNTIME_GRANT_DRIFT')
  if canon([dict(x) for x in c.execute(text(MEMBERS)).mappings()])!=canon(baseline['membership_readback']):raise RuntimeError('MEMBERSHIP_DRIFT')
 with engine.connect() as conn:
  ctx=conn.execute(text("SELECT DB_NAME(),CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)),HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL')")).one()
  if ctx[0]!='sqldb-gpv-demo-v008-20261108' or ctx[1].split('.')[0]!='sql-governance-validator-dev-atiya' or ctx[2]!=1:raise RuntimeError('TARGET_OR_PERMISSION_MISMATCH')
  if list(conn.scalars(text('SELECT version_num FROM dbo.alembic_version')))!=['008']:raise RuntimeError('REVISION_MISMATCH')
  preserved(conn);S['tables_before_counts']=counts(conn);conn.rollback()
  # Serialize full-database policy seeding against other operator instances.
  with conn.begin():
   lock=conn.scalar(text("DECLARE @r int; EXEC @r=sys.sp_getapplock @Resource='gpv-reviewed-eight-policy-seed',@LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=0; SELECT @r;"))
   if lock is None or lock<0:raise RuntimeError('CONCURRENT_SEED_OPERATOR')
   with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
    S['sql_mutation_attempted']=True;save()
    S['policies_created']=seed(db,reviewed)
    pins,revision=readback(db,reviewed)
    S['synthetic_checks']=asyncio.run(evaluate(pins))
    S['policy_inventory']=[{'policy_id':p.policy_id,'version_id':p.version_id,'version_number':p.number,'document_sha256':p.document_sha256,'name':json.loads(p.document_json)['name'],'status':'PUBLISHED','enabled':True,'active':True} for p in pins]
    S['workspace_mode']='MULTI';S['set_revision']=revision
   preserved(conn);now=counts(conn)
   if any(now[t]!=n for t,n in S['tables_before_counts'].items() if t not in allowed):raise RuntimeError('UNAPPROVED_RECORD_COUNT_CHANGE')
   if S['policies_created']==8 and now['audit_events']-S['tables_before_counts']['audit_events']!=41:raise RuntimeError('LIFECYCLE_AUDIT_COUNT_MISMATCH')
   S['precommit_checks']='PASS';save();gate()
  S['transaction_committed']=True;save()
 with engine.connect() as conn:
  with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
   pins,revision=readback(db,reviewed)
  preserved(conn);S['tables_after_counts']=counts(conn)
  if any(S['tables_after_counts'][t]!=n for t,n in S['tables_before_counts'].items() if t not in allowed):raise RuntimeError('COMMITTED_UNAPPROVED_RECORD_CHANGE')
  if list(conn.scalars(text('SELECT version_num FROM dbo.alembic_version')))!=['008']:raise RuntimeError('POSTCOMMIT_REVISION_DRIFT')
 S['source_after']=source_snapshot()
 if S['source_before']!=S['source_after']:raise RuntimeError('SOURCE_CHANGED')
 S.update(status='PASS',revision='008',policy_count=8,active_policy_count=8,precedence_and_attribution='PASS_SYNTHETIC_MODERATION_NO_PROVIDER_CALLS',tenant_isolation='PASS_FOREIGN_TENANT_POLICY_LOOKUP_404',source_sql_baseline_unchanged=True,grants_and_memberships_unchanged=True);save()
except BaseException as error:
 S['failure_type']=type(error).__name__;S['safe_diagnostic']=schema_diagnostic(error)
 if isinstance(error,(RuntimeError,TimeoutError)) and str(error).replace('_','').isalnum():S['failure_code']=str(error)
 S['transaction_rolled_back']=S['sql_mutation_attempted'] and not S['transaction_committed'];save();sys.exit(1)
finally:engine.dispose()
