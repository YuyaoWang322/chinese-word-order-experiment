"""Generate report strictly from preserved responses; never infer Rec scores."""
import collections,hashlib,itertools,json
import experiment as e

PRIMARY=['deepseek','codebuddy_cli_glm51','codebuddy_cli_minimax27','codebuddy_cli_kimi25']

def build():
    e.analyze();rows=e.analysis_rows(e.trials());snap=e.read_json(e.ROOT/'data/design_snapshot.json');models={m['name']:m for m in snap['models'] if m['name'] in {r['model'] for r in rows}}
    done=[r for r in rows if r['status']=='已完成'];qa=[r for r in done if r['task']=='ScrQA' and r['qa_correct']!='']
    rate=lambda g: f"{sum(r['qa_correct']=='1' for r in g)}/{len(g)}（{sum(r['qa_correct']=='1' for r in g)/len(g):.1%}）" if g else '待测试'
    def table(data):return e.md_table(data,list(data[0])) if data else '待测试：暂无相应已评分记录。'
    progress=[]
    for name,m in models.items():
        g=[r for r in rows if r['model']==name];d=[r for r in g if r['status']=='已完成'];q=[r for r in qa if r['model']==name]
        progress.append({'配置':name,'实际模型/标签':m['api_model'],'采集/计划':f'{len(d)}/{len(g)}','QA正确/已评分':rate(q),'Rec已评分':sum(r['rec_score']!='' for r in d),'用途':'主比较' if name in PRIMARY else '历史部分结果/暂停预试验'})
    bylevel=[];bytype=[]
    for name in PRIMARY:
        bylevel.append({'模型':name,**{lv:rate([r for r in qa if r['model']==name and r['disturbance_level']==lv]) for lv in e.LEVELS}})
        for kind in ['常识性陈述','推理性问题','情境对话']:
            bytype.append({'模型':name,'类别':kind,'control':rate([r for r in qa if r['model']==name and r['text_type']==kind and r['disturbance_level']=='control']),'heavy':rate([r for r in qa if r['model']==name and r['text_type']==kind and r['disturbance_level']=='heavy'])})
    stability=e.read_csv(e.ROOT/'results/summary/stability.csv');stable=[]
    for name in PRIMARY:
        cells=[r for r in stability if r['model']==name and r['task']=='ScrQA' and r['n_scored']=='3']
        stable.append({'模型':name,'完整三次QA条件数':len(cells),'三次分数相同':sum(r['all_scores_equal']=='1' for r in cells),'存在分数变化':sum(r['all_scores_equal']=='0' for r in cells)})
    pairs=[]
    for a,b in itertools.combinations(PRIMARY,2):
        idx={tuple(r[k] for k in ['text_id','disturbance_level','repetition']):r for r in qa if r['model']==a}
        matched=[(idx[tuple(r[k] for k in ['text_id','disturbance_level','repetition'])],r) for r in qa if r['model']==b and tuple(r[k] for k in ['text_id','disturbance_level','repetition']) in idx]
        if matched:pairs.append({'模型A':a,'模型B':b,'同条件QA调用对':len(matched),'A正确':sum(x['qa_correct']=='1' for x,y in matched),'B正确':sum(y['qa_correct']=='1' for x,y in matched),'A对B错':sum(x['qa_correct']=='1' and y['qa_correct']=='0' for x,y in matched),'A错B对':sum(x['qa_correct']=='0' and y['qa_correct']=='1' for x,y in matched)})
    integrity=[]
    for name in PRIMARY:
        g=[r for r in done if r['model']==name];q=[r for r in g if r['task']=='ScrQA'];rec=[r for r in g if r['task']=='ScrRec']
        integrity.append({'模型':name,'已采集':len(g),'QA空最终回答':sum(not r['model_output'].strip() for r in q),'Rec空最终回答':sum(not r['model_output'].strip() for r in rec),'API长度截断':sum(r['finish_reason']=='length' for r in g) if name=='deepseek' else 'CLI未提供统一finish_reason'})
    variants=e.read_csv(e.ROOT/'data/variants.csv');strength=[]
    for lv in e.LEVELS:
        g=[r for r in variants if r['disturbance_level']==lv];v=[float(r['changed_fraction']) for r in g]
        strength.append({'等级':lv,'字位置变化比例':f'{min(v):.1%}–{max(v):.1%}','文本完全未改变数':sum(x==0 for x in v)})
    materials={m['text_id']:m for m in snap['materials']}
    wrong=[{'trial_id':r['trial_id'],'实际回答':r['model_output'] or '（真实响应无最终回答）','预定答案':'/'.join(materials[r['text_id']]['answers']),'QA得分':r['qa_correct']} for r in qa if r['model'] in PRIMARY and r['qa_correct']=='0']
    heavy=[{'模型':name,**{tid:rate([r for r in qa if r['model']==name and r['text_id']==tid and r['disturbance_level']=='heavy']) for tid in materials}} for name in PRIMARY]
    rec_examples=[]
    for name in PRIMARY:
        selected=next((r for r in done if r['model']==name and r['text_id']=='K1' and r['disturbance_level']=='heavy' and r['task']=='ScrRec' and r['repetition']=='2'),None)
        if selected:rec_examples.append({'trial_id':selected['trial_id'],'原样输出':selected['model_output'] or '（真实响应无最终回答）','rec_score':selected['rec_score'] or '未人工评分'})
    primary_done=sum(r['model'] in PRIMARY for r in done);primary_plan=sum(r['model'] in PRIMARY for r in rows)
    report=[
    '# 词序的奥秘——大语言模型能读懂乱码吗？',
    f'大学人工智能课程实验报告 · 真实数据版\n\n主比较采集进度：{primary_done}/{primary_plan}；全部历史计划采集：{len(done)}/{len(rows)}。ScrRec人工评分按要求跳过，不能声称两任务都已完成评分。',
    '## 一、实验设计与问题理解',
    '实验考察汉字位置扰动对句子恢复ScrRec与阅读理解ScrQA的影响。三类文本各两段：常识性陈述、逻辑推理、情境对话。每段含control、mild、moderate、heavy四条件，两任务各独立重复三次，即每模型144次。固定分词和随机种子20260927，每条件只生成一个扰动版本。三次调用是同一材料的技术重复，不能当成三篇独立文本。',
    '轻度保持词首尾汉字，随机排列中间字；中度保持首字、排列其余字；重度忽略词边界排列整段汉字，但保留标点及位置。这更准确地说是“词内/全段字序扰动”，不是单纯交换完整词的顺序；恢复难度也可能来自词形被破坏。',
    table(strength),
    '部分短词无法产生变化，轻度和对照可能完全相同；不能据此声称模型抵抗了实际不存在的扰动。等级也不是等距量尺。',
    '## 二、模型、平台和数据来源',table(progress),
    '主比较为DeepSeek API与官方CodeBuddy CLI的GLM-5.1、MiniMax-M2.7、Kimi-K2.5。后者使用WorkBuddy自带CLI，每次独立进程、全新空目录，不续接会话；固定系统提示词、禁用内置工具及MCP、不加载用户/项目设置。逐次核对响应providerData.model并保存完整JSON。调用次序以固定种子随机化，先验证3条正式请求，再执行剩余条件；最多同时3条。',
    'DeepSeek为deepseek-flash，temperature=0.7、max_tokens=512。CLI温度、输出上限没有统一控制，且可能附加平台环境提醒，故比较的是模型与运行配置的联合表现。WorkBuddy界面的Hy4 preview、GLM-5.3-Flash、MiniMax-M3与CLI旧型号不同，已有界面记录保留为预试验，未测项按用户改用CLI的决定暂停。GPT页面仅能确认Latest / 6 Pro，后端版本未核验，不声称为GPT6 astra。',
    '## 三、评分与完整性',
    'ScrQA按预定短答案精确匹配，规范空白及常见标点，正确1、错误0。这里的指标是严格格式准确率：含解释、保留意见或多个候选的回答可能因格式被判0，即使含有正确词。规则事先固定，不因结果修改；错误回答全集列在附录，便于复核。真实空最终回答计未答0；调用失败或未采集记录为待测试，不计零分。',
    'ScrRec采用2/1/0人工量表，本次按用户要求留空。通顺与否不等于是否恢复原意，不能让程序凭相似度或由本助手直接补填恢复成绩。',table(integrity),
    'DeepSeek存在length截断及空最终回答；CLI成功状态不等价于无限输出预算。预算不同是跨模型解释的主要限制。',
    '## 四、三个值得注意的现象',
    '### 现象1：按扰动条件考察QA成功情况',table(bylevel),
    '表中分母仅含已评分的真实调用。比较同模型control与heavy才可讨论本批材料上的下降；部分样本结果不能与其他模型的完整样本总率直接比较。轻/中度实际变动较少，接近对照的成绩不能独自证明模型已理解严重乱码。',
    '### 现象2：常识、推理与对话的重度表现可分开观察',table(bytype),table(heavy),
    '常识题的问题本身提供了强线索，例如不读文本也可能知道光合作用吸收二氧化碳。因此重度常识答对，既可能来自文本恢复，也可能来自先验知识。推理中的“谁比谁靠前”和对话中最后约定的地点，依赖关系和语境；全段重排后往往不存在可唯一恢复的关系。这使错误既可能反映模型不足，也可能反映输入信息已经丢失。',
    '### 现象3：重复一致性和正确性必须区分',table(stable),
    '三次分数相同可能是稳定正确，也可能是稳定错误或稳定未答。一致性只描述该固定扰动版本的调用波动，不能证明答案正确，更不能替代文本样本量。具体极差、样本标准差和原文完全一致指标见stability.csv。',
    '## 五、ScrRec和ScrQA表现是否一致',
    '尚不能作定量判断：ScrRec未人工评分。以下是相同重度常识条件的真实恢复输出，仅供观察，不计恢复成功率。',table(rec_examples),
    'QA只要求一个短答案，可能利用问题线索或世界知识；ScrRec要求重建整句及关系，两个任务的成功标准不同。这个解释是实验设计上的可能机制，当前无Rec评分不能把它写成已证实的任务难度排名。',
    '## 六、哪些任务更依赖词序',
    'ScrRec与ScrQA的依赖程度暂不可比较。QA内部可依据上表比较同一类别control与heavy的变化，但每类只有两篇文本，且重度处理破坏了词形和关系方向，同时保留标点、问题提示。应将结论限定为“这些材料、这个扰动版本和这些配置下的成功率变化”，而不是语言任务普遍规律。',
    '## 七、不同模型的鲁棒性',table(pairs),
    '上表只按相同文本、扰动等级和重复编号匹配QA调用。完整模型对最多72对，仍只有6篇独立材料。分数差异可作描述，不能直接称“显著差异”。DeepSeek短预算导致未答，CLI与API系统提示及采样设置又未统一；不能据此把差异归因于模型规模、训练语料或架构。训练差异等只能作为未验证假说。',
    '## 八、冗余、整体识别与“真正理解”',
    '扰动后仍答对的真实条件说明部分任务表现可以在字序受损时保留，但本实验未独立操纵冗余，也没有无文本QA基线，不能确认是冗余造成了补偿。保留的汉字、标点和问题都可能提供线索。',
    '模型可能利用熟悉搭配、语义约束和世界知识来补全句子；从行为上看这与人类利用上下文有相似之处，但实验没有人类对照，更无法据此认定模型采用了人类式整体认知。恢复成一段通顺的文字，仍可能改变原来的角色关系。',
    '有限任务的正确回答不足以证明或否定AI真正理解语言。更有区分力的新实验可采用虚构事实、主客体可逆句、问题单独呈现的基线、多种扰动种子，以及各平台统一充分的输出预算。它们应作为后续新设计，而非为了改善本次结论修改已采集数据。',
    '## 九、复现、局限与附件',
    '运行python3 src/build_course_report.py重建报告；原始JSON/TXT与逐次CSV是数据依据。API密钥仅从环境变量读取，CLI使用官方本机登录，项目不保存密钥。主报告以描述性分析为主，无显著性检验。ScrRec尚未人工评分、历史暂停计划、预算/平台差异、严格格式评分和小样本均须保留披露。',
    '- [全部逐次完整数据记录表](analysis.md#10-完整逐次数据记录)\n- [完整CSV（含prompt、原文、扰动文和原样回答）](../results/trials.csv)\n- [逐类型/等级汇总](../results/summary/by_type_level.csv)\n- [重复稳定性](../results/summary/stability.csv)\n- [采集偏差说明](protocol_notes.md)\n- [原始文件校验清单](raw_file_manifest.json)',
    '## 附录A：主比较QA所有零分记录',table(wrong),
    '## 附录B：历史网页与界面预试验记录',
    table([{k:r[k] for k in ['trial_id','api_model','model_output','qa_correct','rec_score']} for r in done if r['model'] not in PRIMARY]),
    '空白评分为待评分，不等于0分。暂停计划仍显示待测试，不能补造回答。'
    ]
    if (e.ROOT/'data/analysis_selection.json').exists():
        report.insert(2,'本次改为每模型30条，共120条：从停止采集时已完成的记录中按任务分层随机抽取ScrRec15条、ScrQA15条。固定seed20260927，名单与候选池保存在data/analysis_selection.json；没有依据答案或得分筛选。各模型独立抽样，文本/等级分布未必相同，跨模型总体率不能解释为严格配对效果。原计划每条件三次重复在样本中不一定保留，稳定性仅报告齐全条件。超时记录未进入已完成候选池，可能存在完成者偏差，不能将结果外推到全部原计划。')
        report=[x.replace('全部历史计划采集：','本次分析样本采集：').replace('即每模型144次。','原计划每模型144次，现仅分析固定抽取的30次。').replace('完整模型对最多72对','本次抽样的匹配对数量见上表').replace('完整CSV（含prompt、原文、扰动文和原样回答）](../results/trials.csv)','本次120条样本CSV](../results/selected_trials.csv)；[完整历史CSV](../results/trials.csv)') for x in report]
    if (e.ROOT/'report/empty_exclusion_note.md').exists():
        report.insert(2,(e.ROOT/'report/empty_exclusion_note.md').read_text())
    report.insert(2,e.actual_disturbance_note(rows))
    rec_scored=sum(r['rec_score']!='' for r in rows)
    if rec_scored:
        rec_total=sum(r['task']=='ScrRec' and r['status']=='已完成' for r in rows)
        replacements={
            'ScrRec人工评分按要求跳过，不能声称两任务都已完成评分。':f'ScrRec人工评分已完成{rec_scored}/{rec_total}条已采集记录；未评分仍留空。',
            'ScrRec采用2/1/0人工量表，本次按用户要求留空。通顺与否不等于是否恢复原意，不能让程序凭相似度或由本助手直接补填恢复成绩。':'ScrRec采用2/1/0人工量表，由评分者通过本地页面或CSV填写，程序不自动判断。通顺与否不等于是否恢复原意，人工分数与修改历史保留。',
            '尚不能作定量判断：ScrRec未人工评分。':'已有人工作出的恢复评分。任务间比较仅使用双方均完成三次评分的匹配条件，详见自动分析报告第4节；不以未评分记录充当0分。',
            '仅供观察，不计恢复成功率。':'同时保留人工评分状态，未评分样本不计成功率。',
            '当前无Rec评分不能把它写成已证实的任务难度排名。':'不能只凭未匹配的总体均值将它写成已证实的任务难度排名。',
            'ScrRec与ScrQA的依赖程度暂不可比较。':'ScrRec与ScrQA应按完整匹配条件比较，详见自动分析报告第4—5节。',
            'ScrRec尚未人工评分':'ScrRec未评分部分',
            'rec_score':'rec_score'
        }
        for old,new in replacements.items():report=[part.replace(old,new) for part in report]
        summary=[r for r in e.read_csv(e.ROOT/'results/summary/by_model.csv') if r['task']=='ScrRec']
        report+=['## 人工恢复评分汇总',table(summary),'人工分数仅来自评分者选择。待评分不计零分；各条件完整性见自动分析报告。']
    (e.ROOT/'report/实验报告_真实数据版.md').write_text('\n\n'.join(report)+'\n')
    manifest=[dict(path=str(p.relative_to(e.ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((e.ROOT/'results/raw').rglob('*')) if p.is_file()]
    (e.ROOT/'report/raw_file_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    from build_model_reports import build_model_reports
    build_model_reports(rows,models)
    print('已生成各模型独立报告、综合对比及原始文件校验清单。')

if __name__=='__main__':build()
