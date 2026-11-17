"""One atomic approved new-DB permission + two-membership bootstrap; no migration/provider."""
import json,hashlib,os,sys,time
from pathlib import Path
ROOT=Path('/home/sigmoid/AI governance policy validator');OUT=ROOT/'docs/evidence/runtime-user-bootstrap-2026-11-09'
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
S={'status':'BLOCKED','sql_mutation_attempted':False,'transaction_committed':False,'runtime_grants':'NOT_APPLIED','admin_membership':'NOT_APPLIED','user_membership':'NOT_APPLIED','tenant_isolation':'NOT_VERIFIED','real_hosted_mi_login':'NOT_VERIFIED','real_user_sso':'NOT_VERIFIED'}
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
try:
 pre=json.loads((OUT/'preflight.json').read_text());plan=json.loads((ROOT/'deployment/fresh-runtime-and-memberships.REVIEW_ONLY.json').read_text());permit=json.loads((ROOT/'deployment/fresh-database-permissions.REVIEW_ONLY.json').read_text())
 for name,h in pre['proposal_hashes'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise RuntimeError('PROPOSAL_CHANGED')
 mappings=[validate_mapping(plan['admin_membership_proposed']),validate_mapping(plan['user_membership']['selected_mapping'])]
 if mappings!=[pre['approved_admin_mapping'],pre['approved_user_mapping']]:raise RuntimeError('MEMBERSHIP_PLAN_MISMATCH')
 S['source_before']=source_snapshot()
 baseline=json.loads((ROOT/'docs/evidence/firewall-verification-2026-11-08/sql-select-results.json').read_text())['runtime_grants']
 canon=lambda rows:sorted(json.dumps(x,sort_keys=True,default=str) for x in rows)
 if S['source_before']['revision']!=['005'] or canon(S['source_before']['runtime_grants'])!=canon(baseline):raise RuntimeError('SOURCE_BASELINE_DRIFT')
 with engine.connect() as conn:
  ctx=conn.execute(text("SELECT DB_NAME(),CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)),HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL')")).one()
  if ctx[0]!='sqldb-gpv-demo-v008-20261108' or ctx[1].split('.')[0]!='sql-governance-validator-dev-atiya' or ctx[2]!=1:raise RuntimeError('TARGET_OR_OPERATOR_PERMISSION_MISMATCH')
  if list(conn.scalars(text('SELECT version_num FROM dbo.alembic_version')))!=['008']:raise RuntimeError('REVISION_MISMATCH')
  if conn.scalar(text("SELECT COUNT(*) FROM sys.database_principals WHERE name IN ('app-governance-validator-atiya-1026','governance_validator_web_runtime')")):raise RuntimeError('UNEXPECTED_EXISTING_RUNTIME_PRINCIPAL')
  from app.schema_manifests import metadata_for_revision
  counts={t:conn.scalar(text('SELECT COUNT_BIG(*) FROM dbo.['+t+']')) for t in metadata_for_revision('008').tables}
  if any(counts.values()):raise RuntimeError('UNEXPECTED_APPLICATION_RECORDS')
  S['revision']='008';S['empty_application_state_confirmed']=True;S['tables_before_counts']=counts;conn.rollback()
  approved=(ROOT/'deployment/fresh-runtime-provision.REVIEW_ONLY.sql').read_text().replace('DECLARE @explicit_approval bit = 0;','DECLARE @explicit_approval bit = 1;')
  start=approved.index('BEGIN TRY\n BEGIN TRANSACTION;');end=approved.index(' COMMIT;',start)
  # Preserve exact reviewed guards, declarations and operation order; SQLAlchemy owns one outer transaction including memberships.
  batch=approved[:start]+approved[start+len('BEGIN TRY\n BEGIN TRANSACTION;'):end]
  S['sql_mutation_attempted']=True;save();gate()
  with conn.begin():
   conn.exec_driver_sql(batch)
   with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
    for mapping in mappings:apply_mapping(db,mapping,'atiya-tabsum-shaik','bootstrap-20261109')
    db.flush()
    audit_before=db.scalar(text('SELECT COUNT(*) FROM dbo.audit_events'))
    for mapping in mappings:apply_mapping(db,mapping,'atiya-tabsum-shaik','bootstrap-20261109')
    db.flush()
    if audit_before!=2 or db.scalar(text('SELECT COUNT(*) FROM dbo.audit_events'))!=2:raise RuntimeError('MEMBERSHIP_IDEMPOTENCE_OR_AUDIT_MISMATCH')
    actual=[dict(x) for x in conn.execute(text(MEMBERS)).mappings()]
    if canon(actual)!=canon([{**m,'enabled':1} for m in mappings]):raise RuntimeError('MEMBERSHIP_READBACK_MISMATCH')
    for mapping in mappings:
     found=db.scalar(select(SsoMembership).where(SsoMembership.directory_tenant==DIR,SsoMembership.object_id==mapping['object_id'],SsoMembership.enabled==1))
     if not found or found.role!=mapping['role'] or found.tenant!=mapping['tenant'] or found.actor!=mapping['actor']:raise RuntimeError('SUBJECT_TENANT_BINDING_MISMATCH')
     wrong=db.scalar(select(SsoMembership).where(SsoMembership.object_id==mapping['object_id'],SsoMembership.tenant=='foreign-unapproved-tenant'))
     if wrong is not None:raise RuntimeError('CROSS_TENANT_MEMBERSHIP_VISIBLE')
    user=Identity('gpv-demo-user',mappings[1]['tenant'],'User',directory_tenant=DIR,object_id=mappings[1]['object_id'])
    for method,path in [('GET','/api/policies'),('GET','/api/audit'),('GET','/api/reviews')]:
     try:authorize(Request({'type':'http','method':method,'path':path,'headers':[]}),user)
     except HTTPException as denied:
      if denied.status_code!=403:raise RuntimeError('USER_DENIAL_STATUS_MISMATCH')
     else:raise RuntimeError('USER_ADMIN_API_NOT_DENIED')
    authorize(Request({'type':'http','method':'POST','path':'/api/v2/governance/generate','headers':[]}),user)
    S['membership_readback']=actual;S['membership_idempotence']='PASS_NO_DUPLICATE_AUDIT';S['tenant_isolation']='PASS_SUBJECT_BINDINGS_NEGATIVE_TENANT_LOOKUP_AND_BACKEND_ROLE_GUARD';S['hosted_tenant_sign_in']='NOT_VERIFIED'
   grants=[dict(x) for x in conn.execute(text(GRANTS)).mappings()]
   expected=[{'principal':RUNTIME,'state_desc':'GRANT','permission_name':'CONNECT','object_name':None}]
   for table,rights in permit['permissions'].items():
    expected += [{'principal':ROLE,'state_desc':'GRANT','permission_name':right,'object_name':table} for right in [*rights,'VIEW DEFINITION']]
   expected += [{'principal':ROLE,'state_desc':'DENY','permission_name':right,'object_name':'validation_executions'} for right in ['UPDATE','DELETE']]
   if canon(grants)!=canon(expected):raise RuntimeError('EXACT_GRANT_OR_DENY_SET_MISMATCH')
   sid=conn.scalar(text("SELECT CONVERT(varchar(36),CONVERT(uniqueidentifier,sid)) FROM sys.database_principals WHERE name='app-governance-validator-atiya-1026' AND type='E'"))
   if sid.lower()!='f7bacace-698a-4968-8add-cba221319a17':raise RuntimeError('CONTAINED_SID_MISMATCH')
   roles=[tuple(x) for x in conn.execute(text("SELECT r.name,m.name FROM sys.database_role_members rm JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id JOIN sys.database_principals m ON m.principal_id=rm.member_principal_id WHERE m.name IN ('app-governance-validator-atiya-1026','governance_validator_web_runtime')"))]
   if roles!=[(ROLE,RUNTIME)]:raise RuntimeError('UNEXPECTED_ROLE_INHERITANCE')
   conn.exec_driver_sql("EXECUTE AS USER = 'app-governance-validator-atiya-1026'")
   try:
    with Session(bind=conn,join_transaction_mode='rollback_only') as runtime:
     S['runtime_schema_contract']=inspect_schema(runtime,require_sso=True)
     broad={right:conn.scalar(text("SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE',:right)"),{'right':right}) for right in ['CONTROL','ALTER','ALTER ANY USER','ALTER ANY ROLE','CREATE TABLE']}
     if any(value!=0 for value in broad.values()):raise RuntimeError('EXCESSIVE_RUNTIME_DATABASE_RIGHTS')
     S['broad_database_permissions']=broad
   finally:conn.exec_driver_sql('REVERT')
   S['explicit_permission_rows']=grants;S['explicit_permission_row_count']=len(grants);S['contained_sid']=sid;S['role_memberships']=[list(x) for x in roles]
   gate()
  S['transaction_committed']=True;S['runtime_grants']='PASS';S['admin_membership']='PASS';S['user_membership']='PASS';save()
 # Independently read committed state on a new connection, no extra application writes.
 with engine.connect() as c:
  if list(c.scalars(text('SELECT version_num FROM dbo.alembic_version')))!=['008']:raise RuntimeError('POSTCOMMIT_REVISION_MISMATCH')
  if canon([dict(x) for x in c.execute(text(MEMBERS)).mappings()])!=canon(S['membership_readback']):raise RuntimeError('COMMITTED_MEMBERSHIP_READBACK_MISMATCH')
  if canon([dict(x) for x in c.execute(text(GRANTS)).mappings()])!=canon(S['explicit_permission_rows']):raise RuntimeError('COMMITTED_PERMISSION_READBACK_MISMATCH')
  S['committed_membership_count']=c.scalar(text('SELECT COUNT(*) FROM dbo.sso_memberships'));S['committed_audit_count']=c.scalar(text('SELECT COUNT(*) FROM dbo.audit_events'))
  S['policy_count']=c.scalar(text('SELECT COUNT(*) FROM dbo.policies'))
 S['source_after']=source_snapshot();S['source_sql_baseline_unchanged']=S['source_before']==S['source_after']
 if not S['source_sql_baseline_unchanged']:raise RuntimeError('SOURCE_SQL_BASELINE_DRIFT')
 S['status']='PASS';save()
except BaseException as error:
 S['failure_type']=type(error).__name__;S['safe_diagnostic']=schema_diagnostic(error)
 if isinstance(error,(RuntimeError,TimeoutError)) and str(error).replace('_','').isalnum():S['failure_code']=str(error)
 S['transaction_rolled_back']=S['sql_mutation_attempted'] and not S['transaction_committed'];save();sys.exit(1)
finally:engine.dispose()
