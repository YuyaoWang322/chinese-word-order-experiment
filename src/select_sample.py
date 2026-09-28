"""Freeze a reproducible 30-row sample per model without inspecting answers/scores."""
import datetime,hashlib,json,random
import experiment as e
MODELS=['deepseek','codebuddy_cli_glm51','codebuddy_cli_minimax27','codebuddy_cli_kimi25']

def choose(rows,seed=e.SEED):
    pools={};selected=[]
    for model in MODELS:
        pools[model]={}
        for task in ['ScrRec','ScrQA']:
            ids=sorted(r['trial_id'] for r in rows if r['model']==model and r['task']==task and r['status']=='已完成')
            if len(ids)<15:raise ValueError(f'{model} {task}不足15条真实记录')
            pools[model][task]=ids
            derived=int.from_bytes(hashlib.sha256(f'{seed}:{model}:{task}:sample30'.encode()).digest()[:8],'big')
            selected+=random.Random(derived).sample(ids,15)
    return pools,selected

def main():
    path=e.ROOT/'data/analysis_selection.json'
    if path.exists():raise SystemExit('抽样名单已冻结，拒绝反复抽样')
    pools,ids=choose(e.trials())
    path.write_text(json.dumps(dict(seed=e.SEED,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),method='每模型按任务分层：ScrRec/ScrQA各随机不放回抽15条；不读取回答内容、得分或人工评分选择样本',eligible_pools=pools,trial_ids=ids,reason='用户将每模型正式分析缩减为30条；原始完整记录保留'),ensure_ascii=False,indent=2))
    print({m:sum(i.startswith(m+'_') for i in ids) for m in MODELS})
if __name__=='__main__':main()

def replace_empty(rows, previous, seed=e.SEED):
    """Keep nonempty selected rows; replace only empty finals, never filter by score."""
    index={r['trial_id']:r for r in rows}
    excluded=[i for i in previous if not index[i]['model_output'].strip()]
    keep=[i for i in previous if i not in excluded];added=[];pools={}
    for model in MODELS:
        pools[model]={}
        for task in ['ScrRec','ScrQA']:
            count=sum(index[i]['model']==model and index[i]['task']==task for i in keep)
            eligible=sorted(r['trial_id'] for r in rows if r['model']==model and r['task']==task and r['status']=='已完成' and r['model_output'].strip() and r['trial_id'] not in previous)
            pools[model][task]=eligible
            needed=15-count
            if len(eligible)<needed:raise ValueError(f'{model}/{task}非空回答不足，不能补足15条')
            derived=int.from_bytes(hashlib.sha256(f'{seed}:{model}:{task}:replace-empty-v1'.encode()).digest()[:8],'big')
            added+=random.Random(derived).sample(eligible,needed)
    return keep+added,excluded,added,pools
