"""Synthetic grading fixtures are isolated in temporary directories."""
import tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import scoring_store as s
class GradingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'results').mkdir()
        self.row=dict(trial_id='synthetic-only',prompt='synthetic prompt',model_output='synthetic output',task='ScrRec',status='已完成',rec_score='',reviewer='',score_note='')
    def tearDown(self):self.tmp.cleanup()
    def test_save_undo_and_history(self):
        s.put(self.root,self.row,'2','tester','fixture',0)
        self.assertEqual(s.overlay(self.root,[self.row])[0]['rec_score'],'2')
        s.put(self.root,self.row,'','tester','',1)
        self.assertEqual(s.overlay(self.root,[self.row])[0]['rec_score'],'')
        with s.connect(self.root) as db:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],2)
        self.assertEqual(self.row['rec_score'],'')
        self.assertFalse((self.root/'results/trials.csv').exists())
    def test_stale_tab_cannot_overwrite(self):
        s.put(self.root,self.row,'1','tester','',0)
        with self.assertRaises(s.Conflict):s.put(self.root,self.row,'0','tester','',0)
    def test_changed_response_rejected(self):
        s.put(self.root,self.row,'1','tester','',0)
        altered={**self.row,'model_output':'different synthetic output'}
        with self.assertRaises(s.Conflict):s.overlay(self.root,[altered])
    def test_no_score_for_untested_or_qa(self):
        for row in [{**self.row,'status':'待测试'},{**self.row,'task':'ScrQA'}]:
            with self.assertRaises(ValueError):s.put(self.root,row,'2','tester','',0)
        with self.assertRaises(ValueError):s.put(self.root,self.row,'2','','',0)
if __name__=='__main__':unittest.main()
