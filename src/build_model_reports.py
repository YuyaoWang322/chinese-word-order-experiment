"""One report per model, matching the teacher's clarified grouping rule."""
import experiment as e
from build_course_report import PRIMARY

def build_model_reports(rows, models):
    target=e.ROOT/'report/model_reports';target.mkdir(exist_ok=True)
    index=['# 提交说明：每个模型一组','按老师确认的分组方式，每个正式模型单独报告，最后附跨模型对比。恢复任务的人工评分完成情况按各模型单独列明，未评分不计零分。','']
    materials={x['text_id']:x for x in e.read_json(e.ROOT/'data/materials.json')}
    for name in PRIMARY:
        g=[r for r in rows if r['model']==name];done=[r for r in g if r['status']=='已完成'];qa=[r for r in done if r['task']=='ScrQA' and r['qa_correct']!=''];model=models[name]
        def rate(q):return f"{sum(r['qa_correct']=='1' for r in q)}/{len(q)}（{sum(r['qa_correct']=='1' for r in q)/len(q):.1%}）" if q else '待测试'
        levels=[{'扰动':lv,'QA正确/已评分':rate([r for r in qa if r['disturbance_level']==lv]),'Rec采集':sum(r['task']=='ScrRec' and r['disturbance_level']==lv for r in done),'Rec已评分':sum(r['task']=='ScrRec' and r['disturbance_level']==lv and bool(r['rec_score']) for r in done)} for lv in e.LEVELS]
        kinds=[{'类别':kind,'control':rate([r for r in qa if r['text_type']==kind and r['disturbance_level']=='control']),'heavy':rate([r for r in qa if r['text_type']==kind and r['disturbance_level']=='heavy'])} for kind in ['常识性陈述','推理性问题','情境对话']]
        cells=[r for r in e.read_csv(e.ROOT/'results/summary/stability.csv') if r['model']==name and r['task']=='ScrQA' and r['n_scored']=='3']
        incomplete=len(done)<len(g)
        body=[f"# {model['api_model']}：词序扰动实验报告",f"实验组：{name}；采集进度{len(done)}/{len(g)}。"+('本报告为部分数据版，未测项不计零分。' if incomplete else '预定采集已完成。')+'ScrRec人工评分按要求跳过。',
        '## 1. 实验设计',
        '常识性陈述、推理性问题、情境对话各两段。每段原文对照与轻/中/重三种扰动；每条件分别做ScrRec恢复和ScrQA问答，各独立三次，共144次。固定分词及seed20260927，每条件一个固定扰动版本。轻度保留词首尾，中度保留首字，重度全段打乱汉字并保留标点位置；短词可能完全不变。',
        f"平台：{model.get('provider','')}；模型标识：{model['api_model']}；temperature={model.get('temperature')}，max_tokens={model.get('max_tokens')}（None表示未确认或不可控，不代表0）。",
        '调用配置：'+('独立API请求，temperature=0.7、max_tokens=512。' if name=='deepseek' else '官方CLI独立进程、空目录、禁用工具/MCP、无历史消息，固定系统提示词；逐次响应核对模型。CLI的温度、输出token上限未统一控制。'),
        '## 2. 评分规则',
        'QA为预定短答案精确匹配，规范空白和常见标点，正确1、错误0；额外解释可能导致严格格式得分为0。真实空最终回答按未答0，未调用或调用失败留待测试。Rec按2/1/0人工量表，但本报告没有补造人工分数。',
        '## 3. 三个观察维度与真实现象',
        '### 观察一：不同扰动条件下的QA表现',e.md_table(levels,list(levels[0])),
        '表中结果只能描述当前材料和配置。control与heavy的变化可反映该实验设置下的下降；轻度未改变的文本不能作为抵抗扰动的证据。',
        '### 观察二：文本类型之间的差异',e.md_table(kinds,list(kinds[0])),
        '常识题可受世界知识及问题提示影响；推理与对话更需要保留角色关系和最终约定，但本实验未将这些因素独立控制，不能把类别差异直接归因于某一认知机制。',
        '### 观察三：重复稳定性与输出完整性',
        f"已完成三次QA评分的条件{len(cells)}组，其中{sum(r['all_scores_equal']=='1' for r in cells)}组三次分数一致，{sum(r['all_scores_equal']=='0' for r in cells)}组不一致。已采集回答中有{sum(not r['model_output'].strip() for r in done)}条空最终回答。稳定正确、稳定错误和稳定未答必须区分。",
        '## 4. 分析与讨论',
        'ScrRec与ScrQA是否一致：尚无Rec人工评分，不能比较成功率。QA只需一个短答案，恢复则需要保持整句关系；这种任务差异是可能的解释，不能替代评分结果。',
        '哪些任务依赖词序：可依据上表比较QA各类材料control与heavy，但每类两篇、一个扰动版本，而且全段乱序可能使原意本身不再唯一。不能据此宣称某类任务普遍更依赖词序。',
        '语言冗余与整体认知：若重度仍答对，说明任务表现可能保留，但缺少无文本QA、人类对照和冗余控制，无法区分世界知识、模式补全与文本理解，也不能确认采用了人类式整体认知。',
        'AI是否真正理解语言：行为正确不等于已经证明理解，错误或未答也可能受信息损失及输出预算影响。应把讨论限定于可观察结果。模型间差异在综合对比报告中按相同条件比较，不从本报告单独推断总体排名。',
        '## 5. 局限与复现',
        '三次是技术重复，不是三篇独立样本；标点和问题线索被保留；QA为严格格式指标；Rec未评分；各平台系统提示与预算不同。原始响应和每次prompt均保留。运行python3 src/build_course_report.py可重新生成全部报告。',
        '## 6. 完整逐次数据记录（含待测试）',
        e.md_table(g,e.FIELDS),
        '## 7. 阅读理解标准答案',e.md_table([{'text_id':x['text_id'],'问题':x['question'],'标准答案':'/'.join(x['answers'])} for x in materials.values()],['text_id','问题','标准答案']),
        '注意：标准答案仅用于评分，没有发送给被测模型。原文对照条件本身包含原文。']
        if (e.ROOT/'data/analysis_selection.json').exists():
            body.insert(2,'按用户最新要求，本组仅分析30条真实记录：恢复和问答各15条。从已完成候选池中按固定种子分层随机抽取，未参考答案内容或成绩。原始全部数据仍保留，名单冻结于data/analysis_selection.json。抽样后不保证各条件三次齐全，未齐全时不报告三次稳定性；超时未完成样本不在候选池，存在完成者偏差。')
            body=[x.replace('各独立三次，共144次。','原计划各独立三次共144次，现取30条作为正式分析样本。').replace('预定采集已完成。','30条抽样记录齐全。') for x in body]
        if (e.ROOT/'report/empty_exclusion_note.md').exists():
            body.insert(2,(e.ROOT/'report/empty_exclusion_note.md').read_text())
        body.insert(2,e.actual_disturbance_note(g))
        scored=sum(r['rec_score']!='' for r in g)
        if scored:
            body=[part.replace('ScrRec人工评分按要求跳过。',f'ScrRec已人工评分{scored}条，未评分留空。').replace('但本报告没有补造人工分数。','人工分数由评分者给出，程序不自动补评分。').replace('尚无Rec人工评分，不能比较成功率。','已有人工作出的Rec分数，仅能在完整匹配条件中比较两任务成功率，详见综合自动分析。').replace('Rec未评分','Rec未评分部分') for part in body]
        filename=f'{name}_实验报告.md';(target/filename).write_text('\n\n'.join(body)+'\n')
        index.append(f'- [{model["api_model"]} 独立报告](model_reports/{filename})：{len(done)}/{len(g)}已采集，Rec已人工评分{scored}条。')
    index.extend(['','- [跨模型综合对比分析](实验报告_真实数据版.md)','- [全部历史记录及自动统计](analysis.md)','', '主报告四份加综合对比，共五份Markdown报告。历史GPT及WorkBuddy界面预试验作为数据附件，未宣称其已完成。'])
    (e.ROOT/'report/提交说明.md').write_text('\n'.join(index)+'\n')
