"""Synthetic CLI contract fixtures; never produce formal experiment results."""
import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import run_codebuddy as c

class CliContractTests(unittest.TestCase):
    def response(self,model):
        return SimpleNamespace(returncode=0,stderr='',stdout=json.dumps([
            {'type':'message','role':'assistant','providerData':{'model':model}},
            {'type':'result','subtype':'success','is_error':False,'result':'synthetic fixture only'}]))
    def test_independent_cli_tools_disabled(self):
        row={'trial_id':'synthetic-only','api_model':'glm-5.1','prompt':'synthetic prompt only'}
        calls=[]
        def fake(args,**kw):
            calls.append((args,kw));self.assertEqual(list(Path(kw['cwd']).iterdir()),[])
            return self.response('glm-5.1')
        with patch.object(c.subprocess,'run',side_effect=fake):
            for _ in range(2):
                result,error=c.invoke(row,'synthetic-bin','');self.assertIsNone(error);self.assertEqual(result['output'],'synthetic fixture only')
        self.assertNotEqual(calls[0][1]['cwd'],calls[1][1]['cwd'])
        args=calls[0][0]
        self.assertEqual(args[args.index('--tools')+1],'')
        self.assertIn('--strict-mcp-config',args);self.assertIn('--no-session-persistence',args)
        self.assertNotIn('--continue',args);self.assertNotIn('--resume',args)
        self.assertEqual(args[2],row['prompt'])
    def test_mismatched_model_rejected(self):
        with patch.object(c.subprocess,'run',return_value=self.response('wrong-synthetic-model')):
            result,error=c.invoke({'trial_id':'synthetic-only','api_model':'glm-5.1','prompt':'synthetic prompt'},'synthetic-bin','')
        self.assertEqual(error,'Response model mismatch');self.assertNotIn('output',result)

if __name__=='__main__':unittest.main()
