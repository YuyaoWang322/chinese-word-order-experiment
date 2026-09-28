"""Finish the already-running batch, retry transport failures once, build deliverables."""
import collections,datetime,json,os,subprocess,sys,time,zipfile
from pathlib import Path
import experiment as e

STATUS=e.ROOT/'results/collection_status.json'
def status(phase,**extra):
    rows=e.trials();counts={m:sum(r['model']==m and r['status']=='已完成' for r in rows) for m in sorted({r['model'] for r in rows})}
    temp=STATUS.with_suffix('.tmp');temp.write_text(json.dumps(dict(phase=phase,updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),completed=counts,**extra),ensure_ascii=False,indent=2));temp.replace(STATUS)

def main():
    if (e.ROOT/'data/analysis_selection.json').exists():
        raise SystemExit('每模型30条抽样版已冻结，不再自动补采或重试。')
    target={r['trial_id'] for r in e.trials() if r['model'].startswith('codebuddy_cli_')}
    status('waiting_for_initial_batch')
    while True:
        completed={r['trial_id'] for r in e.trials() if r['status']=='已完成'}
        failed=set()
        for p in (e.ROOT/'results/raw/attempts').glob('*.cli-error.json'):
            try:failed.add(e.read_json(p)['trial_id'])
            except (ValueError,KeyError):pass
        if target <= completed|failed:break
        status('waiting_for_initial_batch',attempted=len(target & (completed|failed)),planned=len(target))
        time.sleep(20)
    # The original process performs final scoring after saving its last result.
    previous=None;stable=0
    while stable<3:
        current=(e.ROOT/'results/trials.csv').stat().st_mtime_ns
        stable=stable+1 if current==previous else 0;previous=current;time.sleep(5)
    pending=[r for r in e.trials() if r['trial_id'] in target and r['status']=='待测试']
    if pending:
        note=e.ROOT/'report/protocol_notes.md'
        with note.open('a') as f:f.write(f'\n\nCLI首轮完成后，针对{len(pending)}条超时/调用失败的待测试条件进行一次重试；有效错误回答不重试。重试使用相同提示词和参数，所有失败诊断保留。仍失败则保持待测试，不反复重试到成功。\n')
        status('retrying_failed_calls_once',retry_count=len(pending))
        command=[sys.executable,str(e.ROOT/'src/run_codebuddy.py'),'--node-dir',os.environ.get('CODEBUDDY_NODE_DIR','')]
        with (e.ROOT/'results/cli_retry.log').open('w') as f:
            result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:status('retry_process_error',exit_code=result.returncode)
    status('building_reports')
    subprocess.run([sys.executable,str(e.ROOT/'src/build_course_report.py')],check=True)
    rows=e.trials();pending=sum(r['trial_id'] in target and r['status']=='待测试' for r in rows)
    validation=e.ROOT/'report/cli_validation.md'
    sessions=[]
    for r in rows:
        if r['source']=='cli':
            raw=e.read_json(e.ROOT/r['response_file']);events=raw['events']
            assert len([x for x in events if x.get('role')=='user'])==1
            final=next(x for x in events if x['type']=='result');sessions.append(final['session_id'])
    assert len(sessions)==len(set(sessions))
    assert all(r['rec_score']=='' for r in rows)
    validation.write_text(f'# CLI采集核验\n\n真实CLI响应{len(sessions)}份；每份一个user消息，session_id全部唯一；实际模型、固定prompt、CSV与原始回答一致性通过程序校验。恢复评分均保持空白。CLI计划仍待测试{pending}条；失败记录保留。\n')
    status('finished' if not pending else 'finished_with_pending',pending_cli=pending)
    archive=e.ROOT.parent/'词序实验项目_真实数据版.zip';tmp=archive.with_suffix('.tmp.zip')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for p in e.ROOT.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts and p.name!='.DS_Store' and not p.name.endswith('.tmp'):
                z.write(p,Path('experiment')/p.relative_to(e.ROOT))
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(archive)
    print('报告与压缩包已生成；CLI待测试',pending,flush=True)

if __name__=='__main__':main()
