"""Synthetic fixtures ONLY; no fixture is a real model experiment result."""
import collections
import importlib.util
import json
import io
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

spec = importlib.util.spec_from_file_location('experiment', Path(__file__).resolve().parents[1]/'src/experiment.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous = e.ROOT
        (self.root/'data').mkdir()
        (self.root/'results/raw').mkdir(parents=True)
        (self.root/'report').mkdir()
        for name in ['materials.json','models.json']:
            (self.root/'data'/name).write_bytes((self.previous/'data'/name).read_bytes())
        e.ROOT = self.root
        e.prepare()

    def tearDown(self):
        e.ROOT = self.previous
        self.tmp.cleanup()

    def test_disturbance_invariants(self):
        for t in e.read_json(self.root/'data/materials.json'):
            original = ''.join(t['tokens'])
            for level in e.LEVELS:
                output=e.scramble(t['tokens'],level,t['text_id'])
                self.assertEqual(output,e.scramble(t['tokens'],level,t['text_id']))
                self.assertEqual(collections.Counter(original),collections.Counter(output))
                for i,c in enumerate(original):
                    if not e.is_han(c): self.assertEqual(output[i],c)
                if level=='control': self.assertEqual(original,output)
                if level in ['mild','moderate']:
                    offset=0
                    for token in t['tokens']:
                        part=output[offset:offset+len(token)]
                        self.assertEqual(collections.Counter(token),collections.Counter(part))
                        self.assertEqual(part[0],token[0])
                        if level=='mild': self.assertEqual(part[-1],token[-1])
                        offset += len(token)

    def test_design_and_no_hidden_context(self):
        rows=e.trials()
        self.assertEqual(len(rows),144 * len(e.read_json(self.root/'data/models.json')))
        self.assertEqual(len({r['trial_id'] for r in rows}),len(rows))
        grouped=collections.defaultdict(list)
        for r in rows:
            grouped[(r['model'],r['text_id'],r['disturbance_level'],r['task'])].append(r)
            t=next(t for t in e.read_json(self.root/'data/materials.json') if t['text_id']==r['text_id'])
            self.assertEqual(r['prompt'],e.prompt_for(r['disturbed_text'],r['task'],t['question']))
            self.assertEqual(r['status'],'待测试')
        for group in grouped.values():
            self.assertEqual({r['repetition'] for r in group},{'1','2','3'})
            self.assertEqual(len({r['prompt'] for r in group}),1)
        with self.assertRaises(SystemExit): e.prepare()

    def test_missing_data_not_zero(self):
        e.analyze()
        for r in e.read_csv(self.root/'results/summary/by_model.csv'):
            self.assertEqual(r['n_scored'],'0')
            self.assertEqual(r['success_rate'],'')
        self.assertIn('待测试',(self.root/'report/analysis.md').read_text())
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(SystemExit): e.run('deepseek',1)
        self.assertTrue(all(r['model_output']=='' for r in e.trials()))

    def test_manual_import_scoring_and_stability(self):
        chosen=[r for r in e.trials() if r['model']=='deepseek' and r['text_id']=='L1' and r['task']=='ScrQA' and r['disturbance_level']=='control']
        # Explicitly synthetic software test fixtures in TemporaryDirectory.
        for r,output in zip(chosen,['丙。','不是丙，是甲','丙']):
            path=self.root/'results/raw'/f"{r['trial_id']}.txt"
            path.write_text(output,encoding='utf-8')
            path.with_suffix('.meta.json').write_text(json.dumps(dict(source='manual',actual_model=r['api_model'],collected_at='synthetic-test-only',collector='unit-test')),encoding='utf-8')
        e.import_manual()
        e.analyze()
        result=[r for r in e.trials() if r['trial_id'] in {x['trial_id'] for x in chosen}]
        self.assertEqual([r['qa_correct'] for r in result],['1','0','1'])
        cell=next(r for r in e.read_csv(self.root/'results/summary/stability.csv') if r['model']=='deepseek' and r['text_id']=='L1' and r['task']=='ScrQA' and r['disturbance_level']=='control')
        self.assertAlmostEqual(float(cell['sample_sd']),3**-.5)
        self.assertEqual(cell['score_range'],'1')
        self.assertTrue(all(r['rec_score']=='' for r in e.trials()))
        rows=e.trials()
        manual=next(r for r in rows if r['trial_id']==chosen[1]['trial_id'])
        manual.update(qa_correct='1',reviewer='test',score_note='synthetic override test')
        e.save(rows)
        e.score()
        self.assertEqual(next(r for r in e.trials() if r['trial_id']==chosen[1]['trial_id'])['qa_correct'],'1')

    def test_api_request_contract_and_resume(self):
        captured=[]
        def fake_urlopen(request, timeout, context):
            self.assertTrue(context.check_hostname)
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'model':'synthetic-model-test', 'choices':[{'message':{'content':'synthetic fixture only'},'finish_reason':'stop'}]}).encode())
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'synthetic-test-key'}), patch.object(e.urllib.request,'urlopen',fake_urlopen):
            e.run('deepseek',1)
            e.run('deepseek',1)
        self.assertEqual(len(captured),2)
        rows=e.trials()
        completed=[r for r in rows if r['status']=='已完成']
        self.assertEqual(len(completed),2)
        for payload in captured:
            self.assertEqual(len(payload['messages']),1)
            self.assertEqual(payload['messages'][0]['role'],'user')
            self.assertIn(payload['messages'][0]['content'],{r['prompt'] for r in completed})
        for path in (self.root/'results/raw').glob('*.api.json'):
            self.assertNotIn('synthetic-test-key',path.read_text())

    def test_reject_design_edits_and_invalid_score(self):
        rows=e.trials()
        rows[0]['prompt']='changed'
        e.save(rows)
        with self.assertRaises(SystemExit): e.trials()
        rows[0]['prompt']=e.read_csv(self.root/'data/trial_plan.csv')[0]['prompt']
        rows[0]['rec_score']='0'
        e.save(rows)
        with self.assertRaises(SystemExit): e.trials()

    def test_empty_final_response_is_preserved_without_retry(self):
        response={'choices':[{'message':{'content':'','reasoning_content':'synthetic test reasoning'},'finish_reason':'length'}]}
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'synthetic-test-key'}), patch.object(e.urllib.request,'urlopen',side_effect=lambda *a,**kw:io.BytesIO(json.dumps(response).encode())) as mock:
            e.run('deepseek',2)
        self.assertEqual(mock.call_count,2)
        completed=[r for r in e.trials() if r['status']=='已完成']
        self.assertEqual(len(completed),2)
        self.assertTrue(all(r['output_status']=='无最终回答' and r['finish_reason']=='length' for r in completed))
        e.analyze()
        for r in e.trials():
            if r['status']=='已完成':
                self.assertEqual(r['model_output'],'')
                self.assertEqual(r['rec_score'],'')
                if r['task']=='ScrQA': self.assertEqual(r['qa_correct'],'0')

if __name__=='__main__':
    unittest.main()
