import sys,asyncio,tempfile,json
from pathlib import Path
ROOT=Path.cwd();sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'backend/tests')]
from test_multi_policy_phase_b import migrate,fixture_engine
from approved_policy_seed_core import documents,seed,readback,evaluate
from sqlalchemy.orm import Session
from sqlalchemy import text
path=Path(tempfile.mkdtemp(prefix='gpv-policy-'))/'test.db';migrate(path,'008');engine=fixture_engine(path);reviewed=documents(ROOT/'deployment/demo-policy-seed.REVIEW_ONLY.json')
# A domain-owned commit must remain inside the outer transaction, including failure.
with engine.connect() as conn:
 try:
  with conn.begin():
   with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
    assert seed(db,reviewed)==8
    raise RuntimeError('SIMULATED_INTERRUPT')
 except RuntimeError as e:
  assert str(e)=='SIMULATED_INTERRUPT'
 assert conn.scalar(text('SELECT COUNT(*) FROM policies'))==0
 conn.rollback()
 with conn.begin():
  with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
   assert seed(db,reviewed)==8
   pins,rev=readback(db,reviewed)
   results=asyncio.run(evaluate(pins))
 with Session(bind=conn,expire_on_commit=False,join_transaction_mode='rollback_only') as db:
  before=db.scalar(text('SELECT COUNT(*) FROM audit_events'))
  assert seed(db,reviewed)==0
  assert db.scalar(text('SELECT COUNT(*) FROM audit_events'))==before
  assert before==41
print(json.dumps({'status':'PASS','atomic_interruption_rollback':'PASS','committed_readback':'PASS','idempotence_no_extra_audits':'PASS','audit_events':before,'cases':results},indent=2))
