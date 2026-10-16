import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('evaluate',ROOT/'evaluate.py')
e=importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.criteria=[dict(type='essencial',weight=3,impact='melhora_qualidade_vida'),
                       dict(type='positivo',weight=1,impact='baixo_impacto'),
                       dict(type='erro_grave',weight=-5,impact='pode_piorar')]

    def test_negative_score_and_gates(self):
        m=e.score(self.criteria,{'0':False,'1':False,'2':True})
        self.assertEqual(m['score'],-125)
        self.assertFalse(m['correct']);self.assertFalse(m['complete']);self.assertTrue(m['harm'])
        m=e.score(self.criteria,{'0':True,'1':False,'2':False})
        self.assertEqual(m['score'],75);self.assertTrue(m['correct']);self.assertFalse(m['complete'])
        self.assertTrue(e.score(self.criteria,{'0':True,'1':True,'2':False})['complete'])

    def test_strict_judgments(self):
        for hits in ({'0':True},{'0':True,'1':True,'2':'false'},{'0':True,'1':True,'2':0}):
            with self.assertRaises(ValueError): e.score(self.criteria,hits)
        for content in ('{"criterios":[{"i":0,"atingido":true},{"i":0,"atingido":false}]}',
                        '{"criterios":[{"i":true,"atingido":true}]}'):
            with self.assertRaises(ValueError):e.parse_judgment(content,1)

    def test_macro_average(self):
        summary=e.summarize([dict(guideline_id='a',metrics=e.score(self.criteria,{'0':True,'1':False,'2':False})),
                             dict(guideline_id='b',metrics=e.score(self.criteria,{'0':True,'1':True,'2':False}))])
        self.assertEqual(summary['overall']['score'],87.5)
        self.assertEqual(summary['overall']['correct'],100)
        self.assertEqual(summary['overall']['complete'],50)

    def test_resume_and_changed_answer(self):
        rubrics=e.read_rows(ROOT/'data/rubrics.jsonl');qid=next(iter(rubrics))
        criteria=rubrics[qid]['criteria']
        content=json.dumps({'criterios':[dict(i=i,atingido=c['weight']>0) for i,c in enumerate(criteria)]})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.jsonl';out=Path(tmp)/'output'
            p.write_text(json.dumps(dict(id=qid,answer='Example'))+'\n')
            args=['--predictions',str(p),'--output',str(out),'--allow-subset']
            with patch.dict(e.os.environ,{'MARITACA_API_KEY':'test-placeholder'}),patch.object(e,'call_judge',return_value=content) as api:
                e.main(args);e.main(args);self.assertEqual(api.call_count,1)
                p.write_text(json.dumps(dict(id=qid,answer='Changed'))+'\n')
                with self.assertRaises(ValueError):e.main(args)
                self.assertEqual(api.call_count,1)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['overall']['complete'],100)
            with patch.object(e,'call_judge') as api:
                e.main(['--judgments',str(out/'judgments.jsonl'),'--output',str(Path(tmp)/'offline'),'--allow-subset'])
                api.assert_not_called()

    def test_coverage_duplicates_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'p.jsonl';out=Path(tmp)/'out'
            p.write_text('{"id":"anf001","answer":""}\n')
            args=['--predictions',str(p),'--output',str(out),'--dry-run']
            with self.assertRaises(ValueError):e.main(args)
            with patch.object(e,'call_judge') as api:
                e.main(args+['--allow-subset']);api.assert_not_called()
            self.assertFalse(out.exists())
            p.write_text(p.read_text()*2)
            with self.assertRaises(ValueError):e.read_rows(p)

if __name__=='__main__':unittest.main()
