"""Sampling fixtures exist only in memory; never model results."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from select_sample import choose,replace_empty,MODELS
class SamplingTests(unittest.TestCase):
    def test_fixed_balanced_and_score_independent(self):
        rows=[dict(trial_id=f'{m}_{t}_{i}',model=m,task=t,status='已完成',model_output='synthetic',rec_score='') for m in MODELS for t in ['ScrRec','ScrQA'] for i in range(20)]
        pools,ids=choose(rows)
        self.assertEqual(len(ids),120);self.assertEqual(len(set(ids)),120)
        for m in MODELS:
            for t in ['ScrRec','ScrQA']:self.assertEqual(sum(i.startswith(f'{m}_{t}_') for i in ids),15)
        changed=[{**r,'model_output':'different synthetic answer','rec_score':'0'} for r in reversed(rows)]
        self.assertEqual(choose(changed)[1],ids)
    def test_replace_only_empty_and_ignore_scores(self):
        rows=[dict(trial_id=f'{m}_{t}_{i}',model=m,task=t,status='已完成',model_output='synthetic',rec_score='0') for m in MODELS for t in ['ScrRec','ScrQA'] for i in range(20)]
        _,previous=choose(rows)
        empty=previous[0]
        for r in rows:
            if r['trial_id']==empty:r['model_output']='  '
        selected,excluded,added,_=replace_empty(rows,previous)
        self.assertEqual(excluded,[empty]);self.assertEqual(len(added),1)
        self.assertEqual(set(previous)-{empty},set(selected)-set(added))
        self.assertEqual(len(set(selected)),120)
        changed=[{**r,'rec_score':'2'} for r in reversed(rows)]
        self.assertEqual(replace_empty(changed,previous)[0],selected)
if __name__=='__main__':unittest.main()
