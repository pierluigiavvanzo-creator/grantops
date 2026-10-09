import hashlib
from .db import connect
from .repo import add_project,add_record,add_evidence
def seed(db):
    with connect(db) as c:
        if c.execute('SELECT COUNT(*) n FROM projects').fetchone()['n']: return False
    pid=add_project(db,'DEMO-HE-001','GrantOps Demonstration Project','Example University','Horizon Europe — synthetic demo','2026-01-01','2029-12-31','ACTIVE',notes='Synthetic demonstration dataset. Not a real grant.')
    q='The consortium shall submit the technical report by the agreed reporting deadline.'; h=hashlib.sha256(q.encode()).hexdigest(); o=add_record(db,pid,'OBLIGATION','Prepare periodic technical report','Synthetic verified record.','2026-10-20','Project Manager','IN_PROGRESS','HUMAN_VERIFIED','42','Reporting',q,h); add_evidence(db,o,'Technical narrative draft','DOCUMENT','Reporting/RP1','IN_PROGRESS'); add_evidence(db,o,'Partner inputs complete','CHECKLIST',None,'MISSING')
    q='Deliverable D1.2 is due in month 10.'; h=hashlib.sha256(q.encode()).hexdigest(); o=add_record(db,pid,'DELIVERABLE','D1.2 — Operational handbook','Synthetic deliverable.','2026-10-31','WP1 Lead','OPEN','HUMAN_VERIFIED','55','Annex 1',q,h); add_evidence(db,o,'Final PDF','DOCUMENT',None,'MISSING')
    add_record(db,pid,'MILESTONE','Consortium review meeting','Unverified synthetic record.','2026-11-15','Coordinator')
    return True