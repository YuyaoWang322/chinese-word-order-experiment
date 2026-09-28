"""Human-only grading, stored separately from ongoing model collection."""
import datetime, hashlib, json, sqlite3
from pathlib import Path

class Conflict(ValueError): pass

def digest(row):
    return hashlib.sha256(json.dumps([row['trial_id'],row['prompt'],row['model_output']],ensure_ascii=False).encode()).hexdigest()

def connect(root):
    p=Path(root)/'results/human_scores.sqlite3'
    db=sqlite3.connect(p,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS scores (trial_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, score TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, trial_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)')
    db.commit();return db

def overlay(root, rows):
    with connect(root) as db: saved={r['trial_id']:dict(r) for r in db.execute('SELECT * FROM scores')}
    result=[]
    for original in rows:
        r=dict(original);r['score_revision']=0;r['score_saved_at']=''
        s=saved.get(r['trial_id'])
        if s:
            if r['status']!='已完成' or r['task']!='ScrRec' or s['fingerprint']!=digest(r):raise Conflict('回答发生变化，请检查原始数据：'+r['trial_id'])
            r.update(rec_score=s['score'],reviewer=s['reviewer'],score_note=s['note'],score_revision=s['revision'],score_saved_at=s['updated_at'])
        result.append(r)
    return result

def put(root,row,score,reviewer,note,expected_revision):
    if row['task']!='ScrRec' or row['status']!='已完成':raise ValueError('只允许给已采集的恢复任务评分')
    if score not in ['','0','1','2']:raise ValueError('非法评分')
    if not reviewer.strip():raise ValueError('请先填写评分者姓名或编号')
    if len(reviewer)>100 or len(note)>3000:raise ValueError('姓名或备注过长')
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    db=connect(root)
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM scores WHERE trial_id=?',(row['trial_id'],)).fetchone()
        revision=previous['revision'] if previous else 0
        if revision!=expected_revision:raise Conflict('这条记录已在其他页面更新，请刷新后再评分')
        if previous and previous['fingerprint']!=digest(row):raise Conflict('回答发生变化，拒绝覆盖评分')
        value=dict(trial_id=row['trial_id'],fingerprint=digest(row),score=score,reviewer=reviewer.strip(),note=note,revision=revision+1,updated_at=now)
        db.execute('INSERT OR REPLACE INTO scores VALUES (:trial_id,:fingerprint,:score,:reviewer,:note,:revision,:updated_at)',value)
        db.execute('INSERT INTO events(trial_id,payload,created_at) VALUES(?,?,?)',(row['trial_id'],json.dumps({'before':dict(previous) if previous else None,'after':value},ensure_ascii=False),now))
        db.commit();return value
    finally:db.close()
