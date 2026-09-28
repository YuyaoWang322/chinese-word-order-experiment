#!/usr/bin/env python3
"""Standard-library-only, reproducible word-order experiment. Python >=3.10."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import urllib.request
import urllib.error
from tls_support import verified_context

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260927
LEVELS = ['control', 'mild', 'moderate', 'heavy']
FIELDS = ['trial_id','model','api_model','text_id','text_type','original_text','disturbance_level','disturbed_text','changed_fraction','task','repetition','prompt','model_output','rec_score','qa_correct','status','source','timestamp','response_file','reviewer','score_note','output_status','finish_reason']

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    temp.replace(path)

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def is_han(c):
    return '\u4e00' <= c <= '\u9fff'

def scramble(tokens, level, text_id):
    # Each text/level has its own deterministic stream, independent of iteration order.
    seed = int.from_bytes(hashlib.sha256(f'{SEED}:{text_id}:{level}'.encode()).digest()[:8], 'big')
    rng = random.Random(seed)
    original = ''.join(tokens)
    if level == 'control':
        return original
    if level == 'heavy':
        letters = [c for c in original if is_han(c)]
        rng.shuffle(letters)
        it = iter(letters)
        return ''.join(next(it) if is_han(c) else c for c in original)
    out = []
    for token in tokens:
        chars = list(token)
        positions = [i for i,c in enumerate(chars) if is_han(c)]
        positions = positions[1:-1] if level == 'mild' else positions[1:]
        values = [chars[i] for i in positions]
        rng.shuffle(values)
        for i,c in zip(positions,values):
            chars[i] = c
        out.append(''.join(chars))
    return ''.join(out)

def fraction(a,b):
    indexes = [i for i,c in enumerate(a) if is_han(c)]
    return sum(a[i] != b[i] for i in indexes)/len(indexes)

def prompt_for(text, task, question):
    if task == 'ScrRec':
        return '请将下面这段乱序文字恢复为正常、通顺的中文，并尽可能保持原句含义。\n仅输出恢复后的文字。\n文字：\n' + text
    return '请根据下面的文字回答问题，严格遵守问题中的回答格式。\n文字：\n' + text + '\n问题：\n' + question

def prepare():
    target = ROOT/'results/trials.csv'
    if target.exists():
        raise SystemExit('已有 trials.csv，拒绝覆盖。新设计请复制项目到新目录。')
    materials = read_json(ROOT/'data/materials.json')
    models = read_json(ROOT/'data/models.json')
    names = [m['name'] for m in models]
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[A-Za-z0-9_-]+',n) for n in names):
        raise SystemExit('模型 name 必须唯一且只含字母、数字、下划线、连字符')
    variants, rows = [], []
    for t in materials:
        original = ''.join(t['tokens'])
        for level in LEVELS:
            disturbed = scramble(t['tokens'],level,t['text_id'])
            changed = f'{fraction(original,disturbed):.6f}'
            variants.append(dict(text_id=t['text_id'],text_type=t['text_type'],original_text=original,disturbance_level=level,disturbed_text=disturbed,changed_fraction=changed))
            for m in models:
                for task in ['ScrRec','ScrQA']:
                    for rep in range(1,4):
                        row = dict.fromkeys(FIELDS,'')
                        row.update(trial_id=f"{m['name']}_{t['text_id']}_{level}_{task}_{rep}",model=m['name'],api_model=m['api_model'],text_id=t['text_id'],text_type=t['text_type'],original_text=original,disturbance_level=level,disturbed_text=disturbed,changed_fraction=changed,task=task,repetition=rep,prompt=prompt_for(disturbed,task,t['question']),status='待测试')
                        rows.append(row)
    write_csv(ROOT/'data/variants.csv',variants,list(variants[0]))
    write_csv(target,rows,FIELDS)
    write_csv(ROOT/'data/trial_plan.csv',[{k:r[k] for k in FIELDS[:12]} for r in rows],FIELDS[:12])
    (ROOT/'data/design_snapshot.json').write_text(json.dumps(dict(seed=SEED,materials=materials,models=models,python_version=__import__('sys').version),ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'results/raw/README.md').write_text('人工结果：每条回答保存为 UTF-8 文件 `<trial_id>.txt`，仅放真实模型回答；不要放“待测试”等占位符。必须另建同名 `.meta.json`，包含 source（manual）、actual_model、collected_at、collector。import-manual 会校验元数据及模型标识。不要创建空白回答文件。API 原始响应保存为 `<trial_id>.api.json`。\n',encoding='utf-8')
    print(f'生成 {len(variants)} 个文本条件、{len(rows)} 条待测试记录。')

def trials():
    rows = read_csv(ROOT/'results/trials.csv')
    plan = read_csv(ROOT/'data/trial_plan.csv')
    expected = {r['trial_id']:r for r in plan}
    if len(rows)!=len(plan) or {r['trial_id'] for r in rows}!=set(expected):
        raise SystemExit('记录缺失、重复或多余，请检查 trials.csv')
    for r in rows:
        if any(r[k]!=expected[r['trial_id']][k] for k in FIELDS[:12]):
            raise SystemExit('固定设计字段被修改：'+r['trial_id'])
        if r['status'] not in ['待测试','已完成']:
            raise SystemExit('非法记录状态')
        if r['rec_score'] not in ['', '0','1','2'] or r['qa_correct'] not in ['', '0','1']:
            raise SystemExit('非法评分值：'+r['trial_id'])
        if (r['task']=='ScrRec' and r['qa_correct']) or (r['task']=='ScrQA' and r['rec_score']):
            raise SystemExit('评分填入错误任务列：'+r['trial_id'])
        if r['status']=='待测试' and any(r[k] for k in ['model_output','rec_score','qa_correct']):
            raise SystemExit('待测试记录不应有回答或评分')
        if r['status']=='已完成':
            if r['source'] not in ['api','manual','cli'] or not r['timestamp']:
                raise SystemExit('已完成记录缺少回答或来源')
            path = (ROOT/r['response_file']).resolve()
            if not path.is_relative_to((ROOT/'results/raw').resolve()) or not path.is_file():
                raise SystemExit('已完成记录缺少有效原始回答文件')
            if r['source']=='cli':
                raw=read_json(path)
                if raw.get('actual_model')!=r['api_model'] or raw.get('prompt')!=r['prompt']:
                    raise SystemExit('CLI模型或提示词不匹配：'+r['trial_id'])
                original=raw['output']
                finals=[x for x in raw.get('events',[]) if x.get('type')=='result']
                actual=[x.get('providerData',{}).get('model') for x in raw.get('events',[]) if x.get('role')=='assistant']
                if len(finals)!=1 or finals[0].get('result')!=original or finals[0].get('is_error') or not actual or any(m!=r['api_model'] for m in actual):
                    raise SystemExit('CLI原始事件校验失败：'+r['trial_id'])
            else:
                original = path.read_text(encoding='utf-8').strip() if r['source']=='manual' else read_json(path)['response']['choices'][0]['message']['content']
            original = '' if original is None else original
            if not r['model_output'].strip() and (r['source'] not in ['api','cli'] or r.get('output_status')!='无最终回答'):
                raise SystemExit('空回答缺少真实 API 来源或状态标记')
            if r['model_output'] != original:
                raise SystemExit('CSV 回答与原始文件不一致：'+r['trial_id'])
    return rows

def actual_disturbance_note(rows):
    counts=[]
    for task in ['ScrRec','ScrQA']:
        for level in LEVELS:
            group=[r for r in rows if r['task']==task and r['disturbance_level']==level]
            counts.append(dict(task=task,level=level,n=len(group),unchanged=sum(r['original_text']==r['disturbed_text'] for r in group)))
    return '## 实际扰动核验\n\n'+md_table(counts,['task','level','n','unchanged'])+'\n\nunchanged表示输入与原文完全相同。对照组不变符合设计；轻/中度不变源于短词限制或随机排列未改变位置。这些记录保留原始标签及评分，但不能作为抗扰动证据；按名义等级计算的成功率会混入未扰动样本。轻/中度只扰动词内字序，并非交换整句词序。每模型30条的抽样也未平衡等级，不据此作总体鲁棒性排名。'

def analysis_rows(rows):
    path=ROOT/'data/analysis_selection.json'
    if not path.exists():return rows
    ids=read_json(path)['trial_ids'];index={r['trial_id']:r for r in rows}
    if len(ids)!=len(set(ids)) or any(i not in index or index[i]['status']!='已完成' for i in ids):
        raise SystemExit('抽样名单无效或包含未采集记录')
    return [index[i] for i in ids]

def save(rows):
    write_csv(ROOT/'results/trials.csv',rows,FIELDS)

def import_manual():
    rows = trials()
    count = 0
    for row in rows:
        path = ROOT/'results/raw'/f"{row['trial_id']}.txt"
        if row['status'] == '已完成' or not path.exists():
            continue
        output = path.read_text(encoding='utf-8').strip()
        if not output or output == '待测试':
            raise SystemExit(f'空白或占位回答：{path.name}')
        meta = read_json(path.with_suffix('.meta.json'))
        if meta.get('source') != 'manual' or any(not meta.get(k) for k in ['actual_model','collected_at','collector']):
            raise SystemExit(f'元数据不完整：{path.name}')
        if meta['actual_model'] != row['api_model']:
            raise SystemExit(f'模型标识不匹配：{path.name}；请为不同模型建立单独实验。')
        row.update(model_output=output,status='已完成',source='manual',timestamp=meta['collected_at'],response_file=str(path.relative_to(ROOT)),rec_score='',qa_correct='')
        count += 1
    save(rows)
    print(f'导入 {count} 条人工采集回答（真实性由采集者负责）。')

def run(model, limit):
    rows = trials()
    snapshot = read_json(ROOT/'data/design_snapshot.json')
    configs = {m['name']:m for m in snapshot['models']}
    if model not in configs:
        raise SystemExit('模型未包含在设计快照中')
    config = configs[model]
    if config.get('mode') == 'cli':
        raise SystemExit('该模型使用官方CLI，请运行 src/run_codebuddy.py')
    if config.get('mode') == 'manual':
        raise SystemExit('该模型使用网页版人工采集，请按 README 录入真实回答。')
    key = os.environ.get(config['api_key_env'])
    if not key:
        raise SystemExit(f"未配置 {config['api_key_env']}，记录保留待测试。")
    pending = [r for r in rows if r['model']==model and r['status']!='已完成']
    random.Random(SEED).shuffle(pending)
    selected = pending[:limit] if limit else pending
    print(f'待测试 {len(pending)} 条，本次计划执行 {len(selected)} 条。', flush=True)
    for index, row in enumerate(selected,1):
        print(f'正在请求 {index}/{len(selected)}：'+row['trial_id'], flush=True)
        result = None
        payload = dict(model=config['api_model'],messages=[dict(role='user',content=row['prompt'])],temperature=config['temperature'],max_tokens=config['max_tokens'])
        req = urllib.request.Request(config['base_url'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=120,context=verified_context()) as response:
                result = json.load(response)
            output = result['choices'][0]['message']['content']
            if output is None:
                output = ''
            if not isinstance(output,str):
                raise ValueError('Unexpected content type')
            stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            path = ROOT/'results/raw'/f"{row['trial_id']}.api.json"
            path.write_text(json.dumps(dict(request=payload,response=result,collected_at=stamp),ensure_ascii=False,indent=2),encoding='utf-8')
            row.update(model_output=output,status='已完成',source='api',timestamp=stamp,response_file=str(path.relative_to(ROOT)),rec_score='',qa_correct='')
            row.update(output_status='有最终回答' if output.strip() else '无最终回答',finish_reason=result['choices'][0].get('finish_reason') or '')
            save(rows)
            print('已完成',row['trial_id'],row['output_status'],'结束原因：'+row['finish_reason'],flush=True)
        except Exception as exc:
            # Save diagnostic response separately; never turn failed attempts into scored trials.
            diagnostic = dict(trial_id=row['trial_id'],error_type=type(exc).__name__,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
            if isinstance(exc,urllib.error.HTTPError):
                diagnostic['http_status'] = exc.code
            if isinstance(exc,urllib.error.URLError):
                diagnostic['network_reason_type'] = type(exc.reason).__name__
            if result is not None:
                diagnostic['response'] = result
                diagnostic['request'] = payload
            directory = ROOT/'results/raw/attempts'
            directory.mkdir(exist_ok=True)
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            (directory/f"{row['trial_id']}_{stamp}.json").write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2),encoding='utf-8')
            print('调用失败，停止：',row['trial_id'],type(exc).__name__,flush=True)
            if isinstance(exc,urllib.error.HTTPError):
                print('HTTP 状态码：',exc.code,flush=True)
            if isinstance(result,dict) and result.get('choices'):
                print('结束原因：',result['choices'][0].get('finish_reason'),'；是否缺少最终回答：',not bool(result['choices'][0].get('message',{}).get('content')),flush=True)
            print('诊断已保存到 results/raw/attempts/。未自动重试。',flush=True)
            return
    remaining = sum(r['model']==model and r['status']!='已完成' for r in rows)
    print(f'本次执行结束；{model} 尚余 {remaining} 条待测试。',flush=True)


def normalize(text):
    return re.sub(r'[\s。．.!！?？“”"\'，,：:；;]', '', text).casefold()

def score():
    rows = trials()
    materials = {t['text_id']:t for t in read_json(ROOT/'data/design_snapshot.json')['materials']}
    for r in rows:
        if r['status'] != '已完成':
            if r['rec_score'] or r['qa_correct']:
                raise SystemExit('待测试记录不得有分数：'+r['trial_id'])
            continue
        if r['task']=='ScrQA' and r['qa_correct']=='':
            # Strict answer-format accuracy; never substring match.
            r['qa_correct'] = str(int(normalize(r['model_output']) in {normalize(a) for a in materials[r['text_id']]['answers']}))
            r['score_note'] = '真实 API 响应无最终回答，QA 计 0' if not r['model_output'].strip() else '自动精确匹配（仅去除空白和常见标点）；语义等价的非标准答案可人工复核'
        if r['task']=='ScrRec' and r['rec_score'] not in ['', '0','1','2']:
            raise SystemExit('非法 ScrRec 分数')
        if r['task']=='ScrQA' and r['qa_correct'] not in ['0','1']:
            raise SystemExit('非法 ScrQA 分数')
    save(rows)
    print('ScrQA 评分完成；ScrRec 保留人工评分。')

def aggregate(rows, keys):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    out = []
    for key,group in sorted(groups.items()):
        task = group[0]['task']
        field = 'rec_score' if task=='ScrRec' else 'qa_correct'
        scores = [int(r[field]) for r in group if r['status']=='已完成' and r[field]!='']
        maximum = 2 if task=='ScrRec' else 1
        record = dict(zip(keys,key))
        record.update(n_planned=len(group),n_completed=sum(r['status']=='已完成' for r in group),n_scored=len(scores),mean_score=round(statistics.mean(scores),6) if scores else '',success_rate=round(sum(x==maximum for x in scores)/len(scores),6) if scores else '',partial_rate=round(sum(x==1 for x in scores)/len(scores),6) if scores and task=='ScrRec' else '',status='已评分' if scores else '待测试/待评分')
        out.append(record)
    return out

def md_table(rows, fields):
    def esc(value):
        return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','&#124;').replace('\n','<br>') or '—'
    return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+['| '+' | '.join(esc(r.get(k,'')) for k in fields)+' |' for r in rows])

def analyze():
    score()
    rows = analysis_rows(trials())
    write_csv(ROOT/'results/selected_trials.csv',rows,FIELDS)
    summaries = {}
    for name,keys in [('by_model',['model','task']),('by_level',['model','task','disturbance_level']),('by_type',['model','task','text_type']),('by_type_level',['model','task','text_type','disturbance_level'])]:
        result = aggregate(rows,keys)
        write_csv(ROOT/'results/summary'/f'{name}.csv',result,list(result[0]))
        summaries[name] = result
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['model'],r['text_id'],r['disturbance_level'],r['task'])].append(r)
    stability=[]
    for key,group in sorted(groups.items()):
        field = 'rec_score' if key[3]=='ScrRec' else 'qa_correct'
        values = [int(r[field]) for r in group if r['status']=='已完成' and r[field]!='']
        outputs=[r['model_output'] for r in group if r['status']=='已完成']
        complete = len(values)==3
        stability.append(dict(zip(['model','text_id','disturbance_level','task'],key)) | dict(n_scored=len(values),score_mean=statistics.mean(values) if values else '',sample_sd=statistics.stdev(values) if complete else '',score_range=max(values)-min(values) if complete else '',all_scores_equal=int(len(set(values))==1) if complete else '',output_exact_agreement=int(len(set(outputs))==1) if len(outputs)==3 else '',status='完整三次评分' if complete else '待测试/待评分'))
    write_csv(ROOT/'results/summary/stability.csv',stability,list(stability[0]))
    completed=sum(r['status']=='已完成' for r in rows)
    scored=sum(bool(r['rec_score'] or r['qa_correct']) for r in rows)
    report=['# 词序的奥秘——实验分析','',f'已完成采集：{completed}/{len(rows)}；已评分记录：{scored}。待测试不计零分；真实 API 返回空最终回答单独标记，QA 按未答计 0，ScrRec 等待人工评分。','',
    '## 1. 实验设计','6 段中文（3 类×2 段），4 个条件（含原文对照），2 项任务，每组合独立重复 3 次。扰动固定 seed=20260927，固定分词；各重复共用同一扰动文本和 prompt。DeepSeek API 采用独立请求，无历史对话；调用顺序固定随机化。GPT 网页版通过独立临时对话采集，网页采样参数不可控，采集方式的差异须纳入解释。新增CodeBuddy CLI模型采用独立进程、禁用工具、空目录和固定系统提示词，逐次核对响应模型；WorkBuddy界面预试验已暂停并保留。重复是同一文本的技术重复，不是独立文本样本。','',
    '## 2. 汇总',md_table(summaries['by_model'],list(summaries['by_model'][0])),'',
    '## 3. 值得注意的实验现象']
    for title,subset in [('恢复表现',[r for r in summaries['by_model'] if r['task']=='ScrRec']),('理解表现',[r for r in summaries['by_model'] if r['task']=='ScrQA']),('扰动影响',summaries['by_level'])]:
        observed=[r for r in subset if r['n_scored']]
        report.append('\n### '+title+'\n'+ (md_table(observed,list(observed[0]))+'\n以上为已评分样本的描述，样本未齐时不可作完整比较。' if observed else '待测试：没有足够的真实评分数据，不报告实验现象。'))
    # Only matched, fully scored cells support directional comparisons.
    cells={(r['model'],r['text_id'],r['disturbance_level'],r['task']):r for r in stability if r['n_scored']==3}
    report += ['','## 4. ScrRec 与 ScrQA 是否一致','ScrRec 成功按 2 分计，ScrQA 成功按 1 分计；以下仅比较双方均完成评分的匹配条件。']
    paired=[]
    for k,cell in cells.items():
        if k[3]!='ScrRec': continue
        other=cells.get(k[:3]+('ScrQA',))
        if other:
            matched=[r for r in rows if (r['model'],r['text_id'],r['disturbance_level'])==k[:3]]
            rec=sum(r['rec_score']=='2' for r in matched if r['task']=='ScrRec')/3
            qa=sum(r['qa_correct']=='1' for r in matched if r['task']=='ScrQA')/3
            paired.append(dict(model=k[0],text_id=k[1],level=k[2],rec_success=rec,qa_accuracy=qa,equal=int(rec==qa)))
    report.append(md_table(paired,list(paired[0])) if paired else '待测试：尚无两项任务均完成三次评分的匹配条件。')
    report += ['','## 5. 哪些任务更加依赖词序','使用同模型、同文本、同任务的对照成功率减去扰动成功率；差值越大表示本材料上性能下降越多。']
    drops=[]
    for k,cell in cells.items():
        if k[2]=='control' or k[:2]+('control',k[3]) not in cells: continue
        def rate(level):
            group=[r for r in rows if (r['model'],r['text_id'],r['disturbance_level'],r['task'])==(k[0],k[1],level,k[3])]
            return sum((r['rec_score']=='2' if k[3]=='ScrRec' else r['qa_correct']=='1') for r in group)/3
        drops.append(dict(model=k[0],text_id=k[1],task=k[3],level=k[2],control_success=rate('control'),disturbed_success=rate(k[2]),drop=rate('control')-rate(k[2])))
    report.append(md_table(drops,list(drops[0])) if drops else '待测试：尚无完整配对的对照与扰动评分。')
    report += ['','## 6. 不同模型的鲁棒性','待测试：完整匹配条件不足，不能比较模型。' if not all(r['rec_score'] or r['qa_correct'] for r in rows) else '当前入选样本均已评分，但抽样后的条件不平衡且未必配对；仅作描述性比较，不代表总体能力排名。',
    '', '## 7. 冗余信息能否弥补词序缺失','待测试：当前没有可支持结论的匹配评分。' if not drops else '上表中扰动后仍成功的条件可作为恢复或理解保留的观察证据，但本实验没有独立操纵冗余程度，也没有无文本问答基线，无法把保留表现因果归因于语言冗余。常识题可能仅靠世界知识作答。',
    '', '## 8. AI 是否真正理解语言','待测试：尚无真实回答，不能据此讨论本次模型表现。' if not completed else '实际任务回答与评分见表。有限文本上的正确回答只能支持相应任务表现；无法单独区分理解、模式匹配、记忆或猜测，更不能据此证明或否定“真正理解”。',
    '', '## 9. 稳定性与局限','详见 results/summary/stability.csv：三次评分齐全才计算样本标准差、极差和全一致率。三次输出完全相同不等于语义表现稳定。每类只有两篇，禁止把重复调用当成独立文本扩大样本量。重度保留标点位置、打乱汉字；QA 问题本身提供语义线索；单一固定扰动版本不能代表所有乱码。自动 QA 为严格格式准确率，人工复核需留名和说明。',
    '', '## 10. 完整逐次数据记录',md_table(rows,FIELDS)]
    audit = []
    for model in sorted({r['model'] for r in rows}):
        completed_rows = [r for r in rows if r['model']==model and r['status']=='已完成']
        if not completed_rows: continue
        reasons = collections.Counter()
        for r in completed_rows:
            if r['source']=='api':
                reasons[read_json(ROOT/r['response_file'])['response']['choices'][0].get('finish_reason','未知')] += 1
        audit.append(f"{model}：已采集 {len(completed_rows)} 次；无最终回答 {sum(not r['model_output'].strip() for r in completed_rows)} 次；API 结束原因 {dict(reasons)}。")
        for level in LEVELS:
            qa = [r for r in completed_rows if r['task']=='ScrQA' and r['disturbance_level']==level and r['qa_correct']!='']
            if qa:
                audit.append(f"- {level} QA：{sum(r['qa_correct']=='1' for r in qa)}/{len(qa)} 正确；无最终回答 {sum(not r['model_output'].strip() for r in qa)} 次。")
    report += ['','## 12. 实际响应完整性与解释边界',*audit,'length 表示长度上限导致结束；空最终回答与错误答案须分开解释。固定预算下未能答出，不等价于充分预算下无法理解。ScrRec 在人工评分完成之前不作任务间优劣判断。']
    deviations = ROOT/'report/protocol_notes.md'
    if deviations.exists():
        report += ['','## 11. 采集偏差与故障记录',deviations.read_text(encoding='utf-8')]
    if (ROOT/'data/analysis_selection.json').exists():
        report.insert(2,'当前采用用户要求的30条/模型抽样版：每模型ScrRec/ScrQA各15条，固定seed20260927，从已完成记录中抽取，名单已冻结。下文原设计的三次重复在子样本中不一定齐全；只有完整三次才计算稳定性。未入选及中止记录均保留在原始CSV。')
    report.insert(2,actual_disturbance_note(rows))
    if (ROOT/'report/empty_exclusion_note.md').exists():
        report.insert(2,(ROOT/'report/empty_exclusion_note.md').read_text())
    (ROOT/'report/analysis.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print('生成 5 张汇总表和 report/analysis.md。')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for cmd in ['prepare','import-manual','score','analyze']:
        sub.add_parser(cmd)
    runner=sub.add_parser('run')
    runner.add_argument('--model',required=True)
    runner.add_argument('--limit',type=int,default=0,help='0 表示全部待测试记录')
    args=parser.parse_args()
    if args.command=='run':
        if args.limit<0: parser.error('--limit 不能为负数')
        run(args.model,args.limit)
    else:
        {'prepare':prepare,'import-manual':import_manual,'score':score,'analyze':analyze}[args.command]()

if __name__=='__main__':
    main()
