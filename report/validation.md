# 最终程序与数据核验（2026-09-28）

- Python 3.14.7，7项自动化测试通过。
- 正式计划288条：DeepSeek144条已完成；GPT网页12条已完成、132条待测试。
- 每条已完成记录均通过固定计划校验与原始回答内容一致性校验。
- DeepSeek QA 58/72正确，14条未答；所有ScrRec人工分数保持空白。
- 原始文件SHA-256清单逐个核验通过，见 raw_file_manifest.json。
- 测试合成数据只存在于临时目录，没有混入正式原始记录。
- 网页验证失败与API网络失败单独留档，不作为模型回答计分。
- 报告明确披露length截断、网页未完成、后端版本未确认及跳过人工评分等限制。

复验：`python3 -m unittest discover -s tests -v`；重建报告：`python3 src/build_course_report.py`。
