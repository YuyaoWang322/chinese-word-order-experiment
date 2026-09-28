"""Local click-to-grade interface. Only humans select reconstruction scores."""
import argparse,csv,io,json,secrets,subprocess,sys,threading,webbrowser,zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import experiment as e
import scoring_store as store

TOKEN=secrets.token_urlsafe(32)
LOCK=threading.Lock()
DONE_PHASES={'finished','finished_with_pending'}

def collection_state():
    p=e.ROOT/'results/collection_status.json'
    state=e.read_json(p) if p.exists() else {'phase':'unknown'}
    state['can_publish']=state.get('phase') in DONE_PHASES
    return state

def data():
    rows=e.analysis_rows(store.overlay(e.ROOT,e.trials()));materials={m['text_id']:m for m in e.read_json(e.ROOT/'data/materials.json')}
    eligible=[]
    for r in rows:
        if r['task']=='ScrRec' and r['status']=='已完成':
            r['rubric']=materials[r['text_id']]['rec_rubric'];eligible.append(r)
    return dict(rows=eligible,pending=sum(r['task']=='ScrRec' and r['status']=='待测试' for r in rows),collection=collection_state())

def publish():
    if not collection_state()['can_publish']:raise store.Conflict('采集或收尾仍在运行。评分已安全保存，结束后再合并报告。')
    rows=store.overlay(e.ROOT,e.trials())
    clean=[{k:r[k] for k in e.FIELDS} for r in rows]
    e.save(clean)
    p=subprocess.run([sys.executable,str(e.ROOT/'src/build_course_report.py')],capture_output=True,text=True)
    if p.returncode:raise RuntimeError('评分已合并，但报告生成失败；请检查报告程序')
    archive=e.ROOT.parent/'词序实验项目_真实数据版.zip';temp=archive.with_suffix('.tmp.zip')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for f in e.ROOT.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts and '.git' not in f.parts and f.name!='.DS_Store' and not f.name.endswith('.tmp'):
                z.write(f,Path('experiment')/f.relative_to(e.ROOT))
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('压缩包校验失败')
    temp.replace(archive)
    return dict(message='评分已合并，报告与压缩包已更新。',scored=sum(r['rec_score']!='' for r in clean))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,kind='application/json; charset=utf-8'):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def local(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def do_GET(self):
        if not self.local():return self.send(403,{'error':'仅允许本机访问'})
        try:
            if self.path=='/':
                html=(e.ROOT/'src/scoring_ui/index.html').read_text().replace('__TOKEN_JSON__',json.dumps(TOKEN))
                return self.send(200,html.encode(),'text/html; charset=utf-8')
            if self.path=='/api/data':return self.send(200,data())
            if self.path=='/api/export':
                with LOCK:rows=e.analysis_rows(store.overlay(e.ROOT,e.trials()))
                buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=e.FIELDS);w.writeheader();w.writerows({k:r[k] for k in e.FIELDS} for r in rows)
                return self.send(200,('\ufeff'+buf.getvalue()).encode(),'text/csv; charset=utf-8')
            self.send(404,{'error':'页面不存在'})
        except (Exception,SystemExit) as exc:self.send(400,{'error':str(exc)})
    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.local() or self.headers.get('X-Score-Token')!=TOKEN or (origin and origin!=f'http://127.0.0.1:{self.server.server_port}'):
            return self.send(403,{'error':'请求来源校验失败'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=20000:raise ValueError('请求长度无效')
            body=json.loads(self.rfile.read(length))
            with LOCK:
                if self.path=='/api/score':
                    row=next((r for r in e.trials() if r['trial_id']==body.get('trial_id')),None)
                    if row is None:raise ValueError('记录不存在')
                    if row['trial_id'] not in {r['trial_id'] for r in e.analysis_rows(e.trials())}:raise ValueError('该记录未入选本次30条样本')
                    value=store.put(e.ROOT,row,body.get('score'),str(body.get('reviewer','')),str(body.get('note','')),body.get('revision'))
                    return self.send(200,value)
                if self.path=='/api/publish':return self.send(200,publish())
                self.send(404,{'error':'接口不存在'})
        except store.Conflict as exc:self.send(409,{'error':str(exc)})
        except (Exception,SystemExit) as exc:self.send(400,{'error':str(exc)})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--open-browser',action='store_true');a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);url=f'http://127.0.0.1:{server.server_port}/'
    print('评分页面：'+url,flush=True);print('评分自动保存到 results/human_scores.sqlite3；不会写入运行中的采集CSV。',flush=True)
    if a.open_browser:webbrowser.open(url)
    server.serve_forever()

if __name__=='__main__':main()
