"""Validate only authentication/model availability; never log API keys."""
import json
import os
from pathlib import Path
import sys
import ssl
import socket
from tls_support import verified_context
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
def main():
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:
        print('未设置 DEEPSEEK_API_KEY。');return 1
    model=next(m for m in json.loads((ROOT/'data/design_snapshot.json').read_text())['models'] if m['name']=='deepseek')
    request=urllib.request.Request(model['base_url'].rstrip('/')+'/models',headers={'Authorization':'Bearer '+key})
    try:
        with urllib.request.urlopen(request,timeout=30,context=verified_context()) as response:
            data=json.load(response)
        available={x['id'] for x in data['data']}
        if model['api_model'] not in available:
            print('密钥认证成功，但实验配置模型不在账户返回的列表中。')
            print('可用模型：'+', '.join(sorted(available)))
            return 2
        print('DeepSeek 认证成功，实验模型可用：'+model['api_model'])
        print('仅检查模型列表，未发送实验请求、未生成实验结果。')
        return 0
    except urllib.error.HTTPError as exc:
        descriptions={401:'密钥认证失败，请检查是否完整复制、已撤销或使用了错误平台的密钥。',403:'服务器拒绝访问，请检查账户权限或网络访问限制。',429:'请求受到限流，请稍后重试。'}
        print(f'HTTP {exc.code}：'+descriptions.get(exc.code,'服务器返回错误，请稍后重试或检查账户状态。'));return 1
    except urllib.error.URLError as exc:
        if isinstance(exc.reason,ssl.SSLCertVerificationError):
            print('证书校验失败：请检查 Python CA 配置及代理证书。程序不会关闭 HTTPS 校验。')
        elif isinstance(exc.reason,socket.gaierror):
            print('DNS 解析失败：请检查网络或 DNS 设置。')
        elif isinstance(exc.reason,(TimeoutError,socket.timeout)):
            print('连接超时：请检查网络或代理后重试。')
        else:
            print('网络连接失败：'+type(exc.reason).__name__+'。请检查网络或代理。')
        return 1
    except Exception as exc:
        print('连接检查未完成：'+type(exc).__name__+'。请检查网络连接。');return 1

if __name__=='__main__': sys.exit(main())
