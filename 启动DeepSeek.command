#!/bin/zsh
cd -- "${0:A:h}" || exit 1
print '密钥仅用于当前终端环境，不写入文件。粘贴时不会显示字符。'
read -rs 'DEEPSEEK_API_KEY?请粘贴 DeepSeek API key，然后回车：'
print
if [[ -z "$DEEPSEEK_API_KEY" ]]; then
  print '未输入密钥，已退出。'
  exit 1
fi
export DEEPSEEK_API_KEY
python3 src/check_deepseek.py
print
print '如认证成功，可在本窗口运行一次实验：'
print 'python3 src/experiment.py run --model deepseek --limit 1'
print '继续全部待测试记录：python3 src/experiment.py run --model deepseek'
print '生成报告：python3 src/experiment.py analyze'
print '密钥只在本窗口环境中有效，关闭窗口后需要重新输入。'
exec /bin/zsh -i
