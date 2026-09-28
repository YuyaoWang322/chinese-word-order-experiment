> **最新筛选：仅纳入非空最终回答。** 原始空回答保留为历史证据；仅替换抽中空回答，不改变其余入选记录。详见report/empty_exclusion_note.md。

> **最新调整：每个正式模型仅分析30条，共120条。** 固定seed20260927，每模型从已完成候选池随机抽ScrRec15条、ScrQA15条。名单见data/analysis_selection.json，本次数据见results/selected_trials.csv。评分页只显示抽样内60条恢复题；完整历史记录仍保留在results/trials.csv，未入选数据不计入本次汇总。剩余采集、重试及自动跟进已停止。下文144次为原始设计，不是本次样本量。

# 词序的奥秘——大语言模型能读懂乱码吗？

这是大学人工智能课程的可复现实验项目。比较词序扰动对句子恢复（ScrRec）与阅读理解（ScrQA）的影响。仅使用 Python 3.10+ 标准库，无第三方依赖。

**当前进度以 `results/trials.csv` 和生成报告为准。** DeepSeek已完成144次；GPT网页仅部分完成。2026-09-28增加WorkBuddy界面预试验后，用户同意改用官方CLI可用的 GLM-5.1、MiniMax-M2.7、Kimi-K2.5，各144次。三个新版界面模型未测项暂停并保留待测试，不与CLI旧型号混合。ScrRec人工评分按要求跳过。程序测试的合成数据只在临时目录中。

## 1. 实验设计与材料

- 3 类中文文本，每类 2 段：常识（光合作用、水凝固）、推理（名次、钥匙位置）、对话（资料柜、见面地点）。原文、人工固定分词、问题、标准答案和恢复评分要点在 `data/materials.json`。
- 4 个文本条件：control 原文、mild 轻度、moderate 中度、heavy 重度；两项任务均包含 control。
- 每模型配置 × 6 文本 × 4 条件 × 2 任务 × 3 重复 = **144次请求**。主分析为DeepSeek加三个CLI模型（共576次计划）；另保留GPT和三个WorkBuddy界面条件的历史计划及部分结果。全部八个条件计划共1152行，暂停/待测试项不计入准确率分母。
- ScrRec：恢复文本；ScrQA：仅给当前条件文本和预先固定的问题。API 请求不发送数据表中的原文、答案或评分要点。control 条件本身是原文，这是唯一有意向模型展示原文的条件。
- 每次请求只包含当前 user prompt，无历史消息；人工测试也必须开启新对话并关闭记忆、联网等附加功能，尽量统一系统设置。三次重复不调整 prompt。
- DeepSeek API：temperature=0.7，max_tokens=512。ChatGPT Latest / 6 Pro（后端版本未确认） 网页版：参数不可控，不能宣称与 API 参数一致。网页名称由用户提供，采集时核对页面显示；无法确认后端具体版本时在元数据中说明。

### 扰动规则与复现边界

seed=20260927。为每个 text_id/level 通过 SHA-256 派生独立种子，再用 Python Random.shuffle。固定材料、分词、Python 版本与程序即可重现；`design_snapshot.json` 保存生成时配置及 Python 版本，`variants.csv` 保存实际扰动文本。

轻度：每个词首尾汉字固定，只打乱中间。中度：首字固定，打乱其余。重度：整段所有基本汉字随机置换，忽略词边界，**标点及其位置保留**。本项目汉字范围为 U+4E00–U+9FFF，覆盖全部材料；扩展材料含扩展区汉字时应调整规则。

分词由人工预定义，不调用动态分词库。短词可能完全不变，随机排列也可能恰好得到原排列；不反复抽样强求变化。`changed_fraction` 为汉字位置改变比例，实际轻、中、重变化不保证逐篇严格递增。名义扰动等级应结合此比例解释。每个条件仅一个固定扰动版本，三个重复考察模型输出波动，不考察扰动版本波动。

## 2. 目录

```text
experiment/
├── README.md
├── data/                 # 材料、模型配置、设计快照、扰动文本、固定试验计划
├── src/experiment.py     # 生成、调用、导入、评分、汇总
├── tests/test_experiment.py
├── results/
│   ├── trials.csv        # 一行一次独立实验，包含 prompt 和评分
│   ├── raw/             # API 原始 JSON 或人工回答 TXT + 元数据 JSON
│   └── summary/         # 按模型/条件/文本类别分组及稳定性
└── report/analysis.md    # 真实记录及依据数据动态生成的报告
```

## 3. 如何运行与配置 API

在终端进入本 README 所在目录：

```bash
python3 --version
python3 -m unittest discover -s tests -v
# 已附生成数据，不必再次 prepare；该命令拒绝覆盖已有 trials.csv。
python3 src/experiment.py analyze
```

### DeepSeek 密钥配置

1. 在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 登录并创建 API key。接口依据 [DeepSeek 官方文档](https://api-docs.deepseek.com/)，当前项目使用 `deepseek-flash`、基址 `https://api.deepseek.com`。
2. 双击项目中的 `启动DeepSeek.command`，或在终端执行 `zsh ./启动DeepSeek.command`。
3. 在本地终端提示处粘贴密钥并回车。输入不回显，密钥不写磁盘、不进入聊天，也不出现在 shell 命令历史中。脚本将其导出为 `DEEPSEEK_API_KEY`，程序仅从环境变量读取。
4. 脚本访问 `/models` 验证认证与模型可用性，不调用生成接口、不产生实验结果。成功后在同一终端执行下列命令。

```bash
python3 src/experiment.py run --model deepseek --limit 1
python3 src/experiment.py run --model deepseek
python3 src/experiment.py analyze
```

生成请求可能计费。密钥只在该终端会话中有效；关闭窗口后需重新输入。不要把密钥写进代码、CSV、Git 或截图。代码不读取 `.env`。Codex 的其他终端不会自动继承这个窗口的环境变量。

### ChatGPT Latest / 6 Pro（后端版本未确认） 网页采集

不需要 OpenAI API key。模型配置名为 `chatgpt_web`，模式为 `manual`，模型名称为用户指定的 `ChatGPT Latest / 6 Pro（后端版本未确认）`。`run --model chatgpt_web` 会明确拒绝 API 调用。

使用 `data/web_prompts.csv` 中的 144 条提示词，表中只包含试验编号、重复编号及 prompt，不含标准答案或隐藏原文。每次使用独立新对话，原样提交 prompt。真实回答按下节保存，元数据 `actual_model` 填 `ChatGPT Latest / 6 Pro（后端版本未确认）`；若网页显示另一个名称，先核对配置，不要强行把不同模型标成该名称。可在元数据额外记录 `displayed_model`、`settings` 及版本无法确认的情况。

缺 key 会停止，保留待测试；接口错误或超时会停止，不填写输出、不给零分、不自动重试。真实 API 空最终回答会保存、标为“无最终回答”并继续；QA 未答计 0，ScrRec 保留人工评分。再次运行会重试尚未完成的记录；请求超时不代表服务端未计费。拒绝回答或有内容但被截断的真实输出仍保留供评分，原始响应包含 finish_reason 等信息。检查原始响应识别截断和供应商返回的实际模型版本。

**模型配置冻结：** prepare 时保存快照，后续 run 使用快照。不要在采集中途修改模型、材料或参数。如需新增“其他模型”、改版本或改设计，复制项目至新目录，保留当前结果；在新副本中移除 `results/trials.csv` 与旧 raw/summary/report 数据，修改 models.json/materials.json 后重新 `prepare`。新模型 name 必须唯一、仅字母数字下划线连字符；API 模型填写 api_model、base_url、api_key_env、temperature、max_tokens，网页模型填写 mode=manual 与实际显示的 api_model 名称。没有 API 的模型也可先列入配置再人工录入。网页模型和 API 模型应视为不同模型配置，勿混用标识。

## 4. 如何人工采集并录入

1. 在 `results/trials.csv` 找到一条待测试记录，原样复制 `prompt` 到目标模型的新对话。**不要复制整行，不展示 original_text、其他条件、答案或先前输出。** 每个 repetition 都重新采集，不能把一次输出复制三份。
2. 把真实模型回答保存为 UTF-8 文件：`results/raw/<trial_id>.txt`。文件只包含回答，不要加评分或解释，不要用占位文本创建文件。
3. 同目录创建 `<trial_id>.meta.json`，记录来源。下例是填写格式，不是实验结果；尖括号内容必须替换为真实信息：

```json
{
  "source": "manual",
  "actual_model": "<与该记录 api_model 完全一致的实际模型标识>",
  "collected_at": "<实际采集时间，建议 ISO 8601 含时区>",
  "collector": "<采集者姓名或编号>"
}
```

4. 执行：

```bash
python3 src/experiment.py import-manual
python3 src/experiment.py analyze
```

程序拒绝空白、占位回答和缺少必要元数据的文件，并且不覆盖已完成回答。人工来源由采集者保证真实，程序无法证明外部网站确实生成了回答。更正已完成记录应保留旧文件备份与修改说明，不应偷偷替换回答。API 原始文件不含密钥。

## 5. 评分

直接用电子表格软件编辑 `results/trials.csv` 的评分列，保存为 UTF-8 CSV。**不要修改试验计划字段、模型输出或状态来制造已完成记录。** CSV 带 BOM，中文与多行 prompt 由标准 CSV 引号保护。

ScrRec 必须人工评分（程序从不自动填写）：

| rec_score | 标准 |
|---|---|
| 2 | 基本恢复原句及原意，关键实体、关系和限制条件全部正确；允许不改变含义的同义改写 |
| 1 | 主要意思正确，但有明显词序、遗漏或内容偏差 |
| 0 | 关键关系颠倒、主要含义错误或无法恢复 |

参照 `materials.json` 的 rec_rubric；对含糊情况先统一评分口径，再盲评。建议两名评分者独立评定后协商，最终分数填 rec_score，reviewer 填评分者，score_note 记录理由及争议。未评分留空，不能填 0 代替未评分。

ScrQA：1 正确、0 错误。所有问题要求短答案。自动仅去除空白和常见标点，做完整答案精确匹配，**不会用包含标准答案的子串判正确**，所以“不是丙，是甲”不会误判。

超出格式但语义正确的回答可能被自动判 0：这是严格格式准确率，需要人工复核。可修改 qa_correct 并填写 reviewer、score_note；后续命令保留非空分数，避免覆盖人工复核。若要重新自动评某行，先清空 qa_correct 并记录原因。改变标准答案须另建实验设计，不能为了结论调整规则。ScrRec 的 qa_correct 和 ScrQA 的 rec_score 始终留空。

```bash
python3 src/experiment.py score
python3 src/experiment.py analyze
```

## 6. 统计与报告

每次 analyze 先为新回答填充 QA 分数，再重新生成汇总和 report/analysis.md。报告是生成文件，个人讨论可另存 `report/discussion.md`，避免被覆盖。

- `by_model.csv`：模型 × 任务。
- `by_level.csv`：模型 × 任务 × 等级。
- `by_type.csv`：模型 × 任务 × 类别。
- `by_type_level.csv`：模型 × 任务 × 类别 × 等级。
- `stability.csv`：每模型 × 文本 × 等级 × 任务的三次重复。

每张分组表列出计划数、实际完成数、已评分数。均分分母仅为已评分记录；ScrRec success_rate=2 分比例、partial_rate=1 分比例，QA success_rate=准确率。没有评分时数值为空，不填零。**跨任务均分尺度不同，不可直接比较**，报告用成功率进行匹配比较。

稳定性仅在同一组合三次均已评分时计算样本标准差（分母 n−1）、极差、评分是否全一致；输出完全一致率另列，二者含义不同。报告列出完整逐次记录、三个待观察维度、匹配的恢复/理解成功率与相对 control 的性能下降。未获得数据的章节明确写待测试。

## 7. 解释边界

不要预设“乱码也能读懂”。重度仍保留标点、字频与问题线索；常识题可能无需阅读即可回答。单一扰动版本与每类两篇材料不足以作总体排名或显著性推断；三次技术重复不是三个独立文本样本。本设计没有单独操纵冗余、没有无文本 QA 基线，因此不能从成功作答因果推断冗余弥补词序。可在后续另建实验加入这两个因素。

即使恢复与理解有差异，也应依据具体输出及评分说明；行为表现不能单独证明或否定“AI 真正理解语言”。API 采样和远端模型更新使输出不能保证逐字复现，可复现的是固定材料、请求与分析流程，原始响应留档用于审计。

## 连接故障修复（2026-09-28）

已实测本机 Python 默认 CA 路径缺失，使用默认配置会报 CERTIFICATE_VERIFY_FAILED；使用 `/etc/ssl/cert.pem` 后无密钥请求能收到 API 的 HTTP 401 响应，说明该路径的 HTTPS 连通正常，但不代表任何密钥已验证。程序已加入 macOS 系统 CA 回退，保持证书和主机名校验；显式设置的 SSL_CERT_FILE/SSL_CERT_DIR 仍优先。

如果原终端仍保留密钥，直接执行 `python3 src/check_deepseek.py`；无需再次粘贴。窗口已关闭则重新运行启动脚本。请只反馈错误提示，不发送密钥。

空回答修复（2026-09-28）：新增 output_status 与 finish_reason，空最终回答不再触发 ValueError。该次请求已有真实响应，因此计为已完成采集，而非待测试。原始 content 保持为空，不填虚构文字。旧版未保存响应的失败尝试见 `report/protocol_notes.md`，不能追溯补造评分。7 项自动化测试通过，包括空回答保留及继续执行。

## 当前报告与采集说明

优先阅读 `report/实验报告_真实数据版.md`。使用 `python3 src/build_course_report.py` 重建报告、汇总和原始文件SHA-256清单；`report/analysis.md` 包含完整288行记录表。

GPT网页当前实际标签为 Latest / 6 Pro，后端版本未核实，不能声称为已验证的GPT6 astra。已有12条结果使用非个性化临时对话，经浏览器界面采集；source=manual表示通过外部界面采集而非API，collector元数据明确记录Codex browser UI。原始文件包含回答、采集时间和可获得的对话URL。Classic提示词清单是备用手动材料，实际未从Classic采集数据。

DeepSeek中47次响应因length结束、45次无最终回答。这一预算限制必须保留在报告解释中。GPT6/6条已测QA均正确，但只覆盖简单常识的对照及轻度条件，不能与DeepSeek全样本准确率作直接排名。


## 7. 官方 CodeBuddy CLI 批量实验

使用WorkBuddy安装包自带或官方安装的`codebuddy`，无需把客户端额度转为非官方API。参考[官方Headless文档](https://www.codebuddy.ai/docs/cli/headless)及[CLI参数文档](https://www.codebuddy.ai/docs/cli/cli-reference)。首先正常登录官方客户端/CLI；程序复用其认证，项目不复制或保存凭证。本机登录已验证成功，但其他电脑须自行登录。

```bash
# node 必须可在 PATH 中找到；如安装路径不同可设置 CODEBUDDY_BIN。
python3 src/run_codebuddy.py --limit 3
python3 src/run_codebuddy.py
# 可选择一个模型或指定 Node 所在目录
python3 src/run_codebuddy.py --model codebuddy_cli_glm51 --node-dir /path/to/node/bin
# 等待采集进程结束后再评分和生成报告，避免同时写CSV
python3 src/build_course_report.py
```

每次调用启动独立进程和新的空临时目录，不使用resume/continue；关闭所有内置工具，使用空MCP配置，不加载用户/项目设置，不持久化会话。三个模型统一系统提示词为“你是一个中文语言实验的答题助手。请严格按照用户要求作答。”，原固定user prompt不变。CLI可能附加运行环境提醒；其平台系统环境与DeepSeek API仍不同。温度及输出token上限未通过CLI统一控制，不能宣称纯模型对照。

程序最多并发3次；保存完整CLI JSON事件、最终回答、时间、实际模型和调用参数到`.cli.json`。逐次核对`providerData.model`，模型不一致或调用失败不纳入正式回答、不评分，诊断保存到`raw/attempts/`。结果来源为`cli`。有效但错误的回答不会重试；重新运行仅处理待测试项。不要在采集运行期间导入人工答案或编辑CSV。

界面预试验的人工采集方式、CLI正式实验和原API实验分别记录，不能混合不同版本。追加模型只扩展固定计划，原行和原始响应不覆盖；设计扩展说明见`report/protocol_notes.md`。


## 8. 按老师确认的分组方式提交

老师确认每个模型作为一组，可分别写报告，最后进行对比。`src/build_course_report.py`生成`report/model_reports/`下四份正式模型独立报告（各含完整144行表）、一份综合对比及`report/提交说明.md`。历史网页/界面部分数据保留为附件，不冒充完成的独立实验。


## 9. 点击式人工评分页面

双击项目根目录的`打开人工评分.command`，或者运行：

```bash
python3 src/scoring_server.py --open-browser
```

访问`http://127.0.0.1:8765/`，填写评分者姓名或编号。页面并排展示原文、扰动文本、评分要点和真实回答；点击“完全正确（2分）”“部分正确（1分）”“错误（0分）”自动保存，并可自动进入下一条。支持按模型、类型、等级、未评分筛选，填写备注、跳过、撤销上次评分、清除评分及隐藏当前模型名称。隐藏名称不等同于严格双盲实验。

评分独立存放在`results/human_scores.sqlite3`，含修改历史与回答指纹；不会覆盖正在采集的CSV。可随时下载含人工评分的CSV。采集及收尾状态为finished或finished_with_pending后，“合并评分并更新报告 / 压缩包”按钮启用，点击即可将人工分数写入正式CSV并重建报告和压缩包。尚未调用的记录不显示为可评分项；真实空最终回答显式展示，由评分者判断，不预填0。备注随评分按钮或“保存备注”保存。

关闭页面不影响已保存评分；下次重新启动即可继续。页面仅绑定127.0.0.1，无外部资源和上传功能。不要在采集运行时手工改写trials.csv。
