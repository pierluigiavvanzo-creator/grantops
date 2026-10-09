from pathlib import Path
from datetime import date
import hashlib
from .db import connect,now,audit
TYPES={'OBLIGATION','DELIVERABLE','MILESTONE','REPORTING_PERIOD','EVIDENCE_REQUIREMENT'}
STATES={'OPEN','IN_PROGRESS','DONE','BLOCKED'}
def add_project(db,code,title,coordinator,programme='Horizon Europe',start_date=None,end_date=None,status='ACTIVE',source_url=None,notes=None):
    with connect(db) as c:
        cur=c.execute('INSERT INTO projects(code,title,coordinator,programme,start_date,end_date,status,source_url,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(code.strip(),title.strip(),coordinator.strip(),programme,start_date,end_date,status,source_url,notes,now())); pid=cur.lastrowid; audit(c,pid,'PROJECT_CREATED',code,'PROJECT',pid); return pid
def projects(db):
    with connect(db) as c:return [dict(r) for r in c.execute('SELECT * FROM projects ORDER BY id')]
def project(db,pid):
    with connect(db) as c:
        r=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone(); return dict(r) if r else None
def add_record(db,pid,record_type,title,description=None,due_date=None,owner=None,status='OPEN',verification_status='UNVERIFIED',source_page=None,source_section=None,source_quote=None,source_text_sha256=None):
    if record_type not in TYPES: raise ValueError('Unsupported record type')
    if status not in STATES: raise ValueError('Unsupported status')
    if verification_status not in {'UNVERIFIED','HUMAN_VERIFIED'}: raise ValueError('Unsupported verification status')
    if verification_status=='HUMAN_VERIFIED' and not(source_quote and source_text_sha256): raise ValueError('Verified records require source quote and source hash')
    with connect(db) as c:
        cur=c.execute('INSERT INTO obligations(project_id,record_type,title,description,due_date,owner,status,verification_status,source_page,source_section,source_quote,source_text_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,record_type,title.strip(),description,due_date,owner,status,verification_status,source_page,source_section,source_quote,source_text_sha256,now())); oid=cur.lastrowid; audit(c,pid,'RECORD_CREATED',title,'OBLIGATION',oid); return oid
def records(db,pid):
    with connect(db) as c:return [dict(r) for r in c.execute('SELECT * FROM obligations WHERE project_id=? ORDER BY due_date IS NULL,due_date,id',(pid,))]
def update_record_status(db,oid,status):
    if status not in STATES: raise ValueError('Unsupported status')
    with connect(db) as c:
        r=c.execute('SELECT project_id FROM obligations WHERE id=?',(oid,)).fetchone()
        if not r: raise ValueError('Record not found')
        c.execute('UPDATE obligations SET status=? WHERE id=?',(status,oid)); audit(c,r['project_id'],'RECORD_STATUS_CHANGED',status,'OBLIGATION',oid)
def add_evidence(db,oid,label,evidence_type='DOCUMENT',location=None,status='MISSING',notes=None):
    with connect(db) as c:
        r=c.execute('SELECT project_id FROM obligations WHERE id=?',(oid,)).fetchone()
        if not r: raise ValueError('Record not found')
        cur=c.execute('INSERT INTO evidence(obligation_id,label,evidence_type,location,status,notes,created_at) VALUES(?,?,?,?,?,?,?)',(oid,label.strip(),evidence_type,location,status,notes,now())); eid=cur.lastrowid; audit(c,r['project_id'],'EVIDENCE_CREATED',label,'EVIDENCE',eid); return eid
def evidence(db,pid):
    with connect(db) as c:return [dict(r) for r in c.execute('SELECT e.*,o.title obligation_title FROM evidence e JOIN obligations o ON o.id=e.obligation_id WHERE o.project_id=? ORDER BY e.id',(pid,))]
def stage_pdf(db,pid,src,uploads):
    src=Path(src); data=src.read_bytes()
    if src.suffix.lower()!='.pdf': raise ValueError('Only PDF supported')
    if len(data)>25*1024*1024: raise ValueError('PDF exceeds 25 MiB')
    sha=hashlib.sha256(data).hexdigest(); dest=Path(uploads)/str(pid); dest.mkdir(parents=True,exist_ok=True); out=dest/f'{sha[:12]}_{src.name}'; out.write_bytes(data)
    with connect(db) as c:
        cur=c.execute('INSERT INTO grant_documents(project_id,filename,stored_path,sha256,byte_count,status,created_at) VALUES(?,?,?,?,?,?,?)',(pid,src.name,str(out),sha,len(data),'STAGED_NOT_PARSED',now())); did=cur.lastrowid; audit(c,pid,'GRANT_DOCUMENT_STAGED',f'{src.name} sha256={sha}','GRANT_DOCUMENT',did)
    return {'id':did,'sha256':sha,'bytes':len(data),'path':str(out)}
def documents(db,pid):
    with connect(db) as c:return [dict(r) for r in c.execute('SELECT * FROM grant_documents WHERE project_id=? ORDER BY id DESC',(pid,))]
def metrics(db,pid):
    rs=records(db,pid); t=date.today(); due=over=0
    for r in rs:
        if not r['due_date'] or r['status']=='DONE': continue
        try:d=date.fromisoformat(r['due_date'])
        except:continue
        delta=(d-t).days
        if delta<0: over+=1
        elif delta<=30: due+=1
    return {'records':len(rs),'verified':sum(r['verification_status']=='HUMAN_VERIFIED' for r in rs),'due30':due,'overdue':over,'done':sum(r['status']=='DONE' for r in rs)}
def audit_events(db,pid,limit=200):
    with connect(db) as c:return [dict(r) for r in c.execute('SELECT * FROM audit_log WHERE project_id=? ORDER BY id DESC LIMIT ?',(pid,limit))]