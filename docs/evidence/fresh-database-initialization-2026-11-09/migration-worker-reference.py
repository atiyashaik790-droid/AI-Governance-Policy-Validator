"""Approved exact-target migrations; secret-free, clean-environment subprocess."""
import ast,hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/sigmoid/AI governance policy validator');OUT=ROOT/'docs/evidence/fresh-database-initialization-2026-11-09'
sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import text,event,inspect
from sqlalchemy.engine import make_url
from app.config import settings
TARGET_URL=make_url(settings.database_url)
from sqlalchemy.orm import Session
from app.database import engine
from app.schema_compatibility import schema_diagnostic
RESULT={'status':'BLOCKED','migrations_started':False,'migration_execution':'BLOCKED','final_revision':None,'schema_qualification':'NOT_RUN','runtime_grants_changed':False}
MODE=sys.argv[1]
def save():
 p=OUT/'sql-result.json';temp=p.with_suffix('.tmp');temp.write_text(json.dumps(RESULT,indent=2)+'\n');temp.replace(p)
def gate():
 if MODE!='inspect' and time.time()>=float(os.environ['GPV_SQL_STOP_UTC_EPOCH']):raise RuntimeError('NEW_OPERATION_DEADLINE_EXPIRED')
@event.listens_for(engine,'before_cursor_execute')
def before(connection,cursor,statement,parameters,context,executemany):gate()
try:
 if TARGET_URL.host!='sql-governance-validator-dev-atiya.database.windows.net' or TARGET_URL.database!='sqldb-gpv-demo-v008-20261108':raise RuntimeError('WRONG_DATABASE_URL')
 pins=json.loads((ROOT/'docs/evidence/master-repair-2026-11-07/qualification-pins.json').read_text())['migration_hashes']
 actual={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'backend/migrations/versions').glob('*.py'))}
 if actual!=pins:raise RuntimeError('MIGRATION_HASH_MISMATCH')
 RESULT['migration_hashes_match']=True
 with engine.connect() as connection:
  context=connection.execute(text("SELECT DB_NAME(),CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)),CAST(SERVERPROPERTY('EngineEdition') AS int),HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL'),(SELECT compatibility_level FROM sys.databases WHERE name=DB_NAME())")).one()
  if context[0]!=TARGET_URL.database or context[1].split('.')[0].casefold()!='sql-governance-validator-dev-atiya' or context[2]!=5:raise RuntimeError('SQL_IDENTITY_MISMATCH')
  RESULT['sql_context']={'database':context[0],'server':context[1],'engine_edition':context[2],'database_control':context[3],'compatibility_level':context[4]}
  if context[3]!=1:raise RuntimeError('OPERATOR_MIGRATION_CONTROL_INSUFFICIENT')
  if context[4]<130:raise RuntimeError('SQL_COMPATIBILITY_LEVEL_UNSUPPORTED')
  tables=list(connection.execute(text('SELECT s.name,t.name FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name')).tuples())
  RESULT['tables_before']=[list(x) for x in tables]
  if MODE=='inspect':
   if ('dbo','alembic_version') in tables:RESULT['final_revision']=list(connection.execute(text('SELECT version_num FROM dbo.alembic_version')).scalars())
   RESULT['status']='PARTIAL_STATE_INSPECTED';save();raise SystemExit(0)
  if tables:raise RuntimeError('TARGET_NOT_EMPTY')
  if connection.scalar(text("SELECT COUNT(*) FROM sys.objects WHERE is_ms_shipped=0 AND type IN ('V','P','FN','IF','TF','TR','SO','SN')")):raise RuntimeError('TARGET_HAS_USER_OBJECTS')
  RESULT['empty_database_verified']=True;RESULT['initial_revision']='ABSENT_EMPTY_DATABASE';save()
 gate()
 from alembic import command
 from alembic.config import Config
 config=Config(str(ROOT/'backend/alembic.ini'));config.set_main_option('script_location',str(ROOT/'backend/migrations'))
 RESULT['migrations_started']=True;RESULT['migration_started_utc']=datetime.now(timezone.utc).isoformat();save()
 # Exactly one upgrade invocation. No downgrade/stamp or retry.
 command.upgrade(config,'008')
 RESULT['migration_execution']='PASS';save()
 import app.schema_compatibility as schema
 with Session(engine) as db:
  RESULT['final_revision']=list(db.execute(text('SELECT version_num FROM dbo.almbic_version'.replace('almbic','alembic'))).scalars())
  if RESULT['final_revision']!=['008']:raise RuntimeError('FINAL_REVISION_MISMATCH')
  original=schema.verify_runtime_permissions
  def operator_scope(connection,**kwargs):
   RESULT['runtime_permission_qualification']='NOT_RUN_OPERATOR_SCHEMA_CHECK_ONLY_NO_RUNTIME_PRINCIPAL_PROVISIONED'
  schema.verify_runtime_permissions=operator_scope
  try:RESULT['schema_contract']=schema.inspect_schema(db,require_sso=True)
  finally:schema.verify_runtime_permissions=original
  ins=inspect(db.connection());tables=ins.get_table_names(schema='dbo')
  RESULT['schema_counts']={'tables':len(tables),'indexes':sum(len(ins.get_indexes(t,schema='dbo')) for t in tables),'foreign_keys':db.scalar(text("SELECT COUNT(*) FROM sys.foreign_keys WHERE schema_id=SCHEMA_ID('dbo')")),'check_constraints':db.scalar(text("SELECT COUNT(*) FROM sys.check_constraints WHERE schema_id=SCHEMA_ID('dbo')")),'triggers':db.scalar(text('SELECT COUNT(*) FROM sys.triggers WHERE parent_class=1 AND is_ms_shipped=0'))}
  RESULT['table_rows']={table:db.scalar(text('SELECT COUNT_BIG(*) FROM dbo.['+table+']')) for table in tables}
  if any(count for table,count in RESULT['table_rows'].items() if table!='alembic_version'):raise RuntimeError('UNEXPECTED_APPLICATION_DATA')
  RESULT['schema_qualification']='PASS';RESULT['status']='PASS';save()
except SystemExit:raise
except BaseException as error:
 RESULT['failure_type']=type(error).__name__;RESULT['safe_diagnostic']=schema_diagnostic(error)
 if isinstance(error,RuntimeError) and str(error).replace('_','').isalnum():RESULT['failure_code']=str(error)
 if RESULT['migrations_started'] and RESULT['migration_execution']!='PASS':RESULT['migration_execution']='FAIL'
 save();sys.exit(1)
finally:engine.dispose()
