from pathlib import Path
import tempfile,os
from grantops.db import init_db
from grantops.seed import seed
from grantops.repo import *
def run():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td); db=td/'x.db'; init_db(db); assert seed(db); assert not seed(db); ps=projects(db); assert len(ps)==1; pid=ps[0]['id']; assert len(records(db,pid))==3; assert metrics(db,pid)['verified']==2; oid=add_record(db,pid,'OBLIGATION','Test',due_date='2026-12-01'); add_evidence(db,oid,'Proof'); assert evidence(db,pid); update_record_status(db,oid,'DONE');
    try:add_record(db,pid,'OBLIGATION','Bad',verification_status='HUMAN_VERIFIED'); raise AssertionError('must block')
    except ValueError:pass
    pdf=td/'ga.pdf'; pdf.write_bytes(b'%PDF-1.4\n%test'); r=stage_pdf(db,pid,pdf,td/'up'); assert len(r['sha256'])==64; assert documents(db,pid)[0]['status']=='STAGED_NOT_PARSED'
  print('PASS_MVP_CORE_TESTS')
if __name__=='__main__':run()