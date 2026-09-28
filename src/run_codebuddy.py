"""Run independent trials using the official CodeBuddy CLI (no private API)."""
import argparse, concurrent.futures, datetime, json, os, random, re, shutil, subprocess, tempfile
from pathlib import Path
import experiment as e

SYSTEM_PROMPT='你是一个中文语言实验的答题助手。请严格按照用户要求作答。'
DEFAULT_BIN='/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy'

def invoke(row, executable, node_dir):
    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    env=os.environ.copy()
    if node_dir: env['PATH']=str(node_dir)+os.pathsep+env.get('PATH','')
    args=[executable,'-p',row['prompt'],'--model',row['api_model'],'--tools','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','','--no-session-persistence','--max-turns','1','--system-prompt',SYSTEM_PROMPT,'--output-format','json']
    record=dict(trial_id=row['trial_id'],requested_model=row['api_model'],prompt=row['prompt'],timestamp=timestamp,system_prompt=SYSTEM_PROMPT,options=args[4:],collector='official CodeBuddy CLI',workspace='fresh empty temporary directory')
    try:
        with tempfile.TemporaryDirectory(prefix='wordorder_cli_') as tmp:
            p=subprocess.run(args,cwd=tmp,env=env,capture_output=True,text=True,timeout=240)
        record['returncode']=p.returncode
        if p.returncode or not p.stdout.strip(): raise ValueError('CLI returned no successful JSON result')
        events=json.loads(p.stdout)
        if not isinstance(events,list): raise ValueError('Unexpected CLI JSON structure')
        record['events']=events
        final=[x for x in events if x.get('type')=='result']
        if len(final)!=1 or final[0].get('is_error') or final[0].get('subtype')!='success': raise ValueError('CLI result not success')
        assistants=[x for x in events if x.get('role')=='assistant']
        actual=[x.get('providerData',{}).get('model') for x in assistants]
        if not actual or any(m!=row['api_model'] for m in actual): raise ValueError('Response model mismatch')
        if any(x.get('type') in ['function_call','tool_use'] for x in events): raise ValueError('Unexpected tool call')
        output=final[0].get('result')
        if not isinstance(output,str): raise ValueError('Result is not a string')
        record.update(output=output,actual_model=actual[-1],collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        return record,None
    except Exception as exc:
        # Never print raw stderr/headers/credential-bearing diagnostics.
        record['error_type']=type(exc).__name__; record['error']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        return record,record['error']

def main():
    if (e.ROOT/'data/analysis_selection.json').exists():
        raise SystemExit('已切换为每模型30条抽样分析；剩余采集已按用户要求停止。')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--limit',type=int,default=0);p.add_argument('--workers',type=int,default=3);p.add_argument('--model');p.add_argument('--cli',default=os.environ.get('CODEBUDDY_BIN') or shutil.which('codebuddy') or DEFAULT_BIN);p.add_argument('--node-dir',default=os.environ.get('CODEBUDDY_NODE_DIR',''))
    a=p.parse_args()
    if not 1<=a.workers<=3 or a.limit<0:p.error('workers must be 1..3; limit nonnegative')
    rows=e.trials(); pending=[r for r in rows if r['model'].startswith('codebuddy_cli_') and r['status']=='待测试' and (not a.model or r['model']==a.model)]
    random.Random(e.SEED).shuffle(pending)
    if a.limit:pending=pending[:a.limit]
    print(f'计划独立请求 {len(pending)} 次；并发 {a.workers}；不自动重试有效回答。',flush=True)
    done=0;errors=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(invoke,r,a.cli,a.node_dir):r for r in pending}
        for f in concurrent.futures.as_completed(futures):
            row=futures[f];record,error=f.result()
            if error:
                errors+=1
                path=e.ROOT/'results/raw/attempts'/f"{row['trial_id']}_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}.cli-error.json"
                path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
                print('失败，保留待测试',row['trial_id'],error,flush=True)
                continue
            path=e.ROOT/'results/raw'/f"{row['trial_id']}.cli.json"
            if path.exists():raise RuntimeError('拒绝覆盖已有原始响应 '+path.name)
            path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
            row.update(model_output=record['output'],status='已完成',source='cli',timestamp=record['collected_at'],response_file=str(path.relative_to(e.ROOT)),output_status='有最终回答' if record['output'].strip() else '无最终回答',finish_reason='cli_success')
            e.save(rows);done+=1
            print(f'完成 {done}/{len(pending)} {row["trial_id"]}',flush=True)
    e.analyze()
    print(f'本次完成 {done}，失败 {errors}。',flush=True)

if __name__=='__main__':main()
