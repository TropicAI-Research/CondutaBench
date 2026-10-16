import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import providers
import evaluate
import run

class ProviderTests(unittest.TestCase):
    def test_http_protocols_and_extraction(self):
        results={
            'openai':{'status':'completed','output':[{'type':'reasoning','summary':[]},{'type':'message','content':[{'type':'output_text','text':'answer'}]}]},
            'anthropic':{'stop_reason':'end_turn','content':[{'type':'thinking','thinking':'private'},{'type':'text','text':'answer'}]},
            'maritaca':{'choices':[{'finish_reason':'stop','message':{'content':'answer'}}]},
            'openrouter':{'choices':[{'finish_reason':'stop','message':{'content':'answer','reasoning':'private'}}]},
        }
        for provider,result in results.items():
            with self.subTest(provider=provider):
                spec=providers.prepare(provider,'model-id',[dict(role='user',content='question')])
                with patch.object(providers.urllib.request,'build_opener') as opener:
                    opener.return_value.open.return_value=io.BytesIO(json.dumps(result).encode())
                    self.assertEqual(providers.send(spec,'test-placeholder')['text'],'answer')
                    req=opener.return_value.open.call_args.args[0]
                    self.assertEqual(req.full_url,providers.PROVIDERS[provider][0])
                    body=json.loads(req.data)
                    if provider=='anthropic':
                        self.assertEqual(req.get_header('X-api-key'),'test-placeholder')
                        self.assertIsNone(req.get_header('Authorization'))
                        self.assertEqual(req.get_header('Anthropic-version'),'2023-06-01')
                    else:self.assertEqual(req.get_header('Authorization'),'Bearer test-placeholder')
                    if provider=='openai':
                        self.assertEqual(body['max_output_tokens'],8000)
                        self.assertFalse(body['store']);self.assertNotIn('messages',body)
                    else:self.assertEqual(body['max_tokens'],8000)
                    self.assertNotIn('temperature',body)
                    self.assertNotIn('test-placeholder',json.dumps(spec))

    def test_incomplete_responses_never_pass(self):
        for provider,result in [('openai',{'status':'incomplete'}),('anthropic',{'stop_reason':'max_tokens'}),
                                ('openrouter',{'choices':[{'finish_reason':'length'}]})]:
            with self.assertRaises(providers.APIError):providers.extract(provider,result)
        with self.assertRaises(providers.APIError):
            providers.extract('openai',{'status':'completed','output':[{'type':'message','content':[{'type':'refusal'}]}]})
        self.assertIsNone(providers.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))

    def test_provider_and_settings_change_fingerprint(self):
        signatures=[]
        for provider in providers.PROVIDERS:
            signatures.append(evaluate.fingerprint(providers.prepare(provider,'same-name',[],8000)))
        self.assertEqual(len(set(signatures)),4)
        self.assertNotEqual(evaluate.fingerprint(providers.prepare('openai','same-name',[],8000)),
                            evaluate.fingerprint(providers.prepare('openai','same-name',[],16000)))

    def test_generate_and_evaluate_resume(self):
        first=next(iter(evaluate.read_rows(ROOT/'data/questions.jsonl').values()))
        rubric=evaluate.read_rows(ROOT/'data/rubrics.jsonl')[first['id']]
        votes=json.dumps({'criterios':[dict(i=i,atingido=c['weight']>0) for i,c in enumerate(rubric['criteria'])]})
        captured=[]
        def fake_send(spec,key):
            captured.append(spec)
            return dict(text='Generated answer' if spec['provider']=='openai' else votes,usage={},model='returned-id')
        with tempfile.TemporaryDirectory() as tmp,patch.object(providers,'api_key',return_value='test-placeholder'),patch.object(providers,'send',side_effect=fake_send):
            args=['--provider','openai','--model','candidate','--limit','1','--output',tmp,
                  '--evaluate','--judge-provider','anthropic','--judge-model','judge']
            run.main(args);run.main(args)
            self.assertEqual(len(captured),2)
            self.assertEqual(captured[0]['body']['input'],[dict(role='user',content=first['scenario']+'\n\n'+first['question'])])
            summary=json.loads((Path(tmp)/'evaluation/summary.json').read_text())
            self.assertEqual(summary['overall']['complete'],100)
            self.assertEqual(summary['judge_provider'],'anthropic')
            with self.assertRaises(evaluate.EvaluationError):
                run.main(args+['--temperature','0.5'])
            self.assertEqual(len(captured),2)

    def test_dry_run_needs_no_key_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(providers,'send') as send,patch.object(providers,'api_key') as key:
            out=Path(tmp)/'out'
            run.main(['--provider','openrouter','--model','vendor/model','--output',str(out),'--limit','2','--dry-run'])
            send.assert_not_called();key.assert_not_called();self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
