#!/usr/bin/env python3
"""Check the public distribution without printing possible sensitive matches."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
ALLOWED={'LICENSE','LICENSE-DATA','providers.py','run.py','tests/test_providers.py','README.md','.gitignore','evaluate.py','audit_release.py','tests/test_evaluate.py','SHA256SUMS',
         'data/questions.jsonl','data/rubrics.jsonl','data/support.jsonl'}
PATTERNS={
    'credential':r'(?<![A-Za-z0-9])(?:sk-(?:proj-|ant-|or-v1-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{25,}|AIza[A-Za-z0-9_-]{30,})',
    'hf_credential':r'(?<![A-Za-z0-9])hf_[A-Za-z0-9]{24,}',
    'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'local_path':r'/(?:home|Users|run/user)/[A-Za-z0-9]',
    'private_host':r'https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+)(?:[:/]|$)',
}


def load_rows(name):
    return [json.loads(line) for line in (ROOT/name).read_text().splitlines() if line.strip()]


def check(condition,message):
    if not condition:raise ValueError(message)


def main():
    paths=[p for p in ROOT.rglob('*') if '.git' not in p.relative_to(ROOT).parts]
    check(not any(p.is_symlink() for p in paths),'Symbolic links are forbidden.')
    actual={p.relative_to(ROOT).as_posix() for p in paths if p.is_file()}
    check(actual==ALLOWED,'Unexpected or missing file in release; use a clean distribution directory.')
    for name in sorted(actual):
        text=(ROOT/name).read_text(encoding='utf-8')
        for label,pattern in PATTERNS.items():
            check(not re.search(pattern,text),f'Potential {label} detected in {name}; inspect privately.')
    hashes={}
    for line in (ROOT/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        check(name not in hashes,'Duplicate checksum entry.')
        hashes[name]=digest
    check(set(hashes)==ALLOWED-{'SHA256SUMS'},'Checksum coverage is incomplete.')
    for name,digest in hashes.items():
        check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,f'Checksum mismatch: {name}')
    questions=load_rows('data/questions.jsonl');rubrics=load_rows('data/rubrics.jsonl');support=load_rows('data/support.jsonl')
    check(len(questions)==715 and len({q['id'] for q in questions})==715,'Invalid question coverage.')
    ids={q['id'] for q in questions}
    check(len(rubrics)==len(support)==715 and {r['id'] for r in rubrics}=={r['id'] for r in support}==ids,'Invalid label/support coverage.')
    check(sum(len(r['criteria']) for r in rubrics)==4722,'Invalid criterion count.')
    for q in questions:
        check(set(q)=={'id','guideline_id','topic','scenario','question'},'Unapproved question field.')
    impacts={'reduz_mortalidade':5,'melhora_qualidade_vida':3,'baixo_impacto':1,'desvio_sem_dano':-2,'pode_piorar':-5}
    for r in rubrics:
        check(set(r)=={'id','reference_answer','criteria'},'Unapproved rubric field.')
        for i,c in enumerate(r['criteria']):
            check(set(c)=={'index','text','type','impact','weight','original_reference'},'Unapproved criterion field.')
            check(set(c['original_reference'])=={'page','text'},'Unapproved reference field.')
            check(c['index']==i and impacts[c['impact']]==c['weight'],'Invalid criterion index/weight.')
            check(c['type'] in {'essencial','positivo','erro_grave','acao_proibida'},'Invalid criterion type.')
    check(len({q['guideline_id'] for q in questions})==14,'Invalid guideline coverage.')
    for r in support:
        check(set(r)=={'id','guideline_id','passages','limitations'},'Unapproved support field.')
        passages=list(r['passages'])
        for note in r['limitations']:
            check(set(note)<={'criterion_index','support_status','limitation','selected_passages'},'Unapproved support note.')
            passages+=note.get('selected_passages',[])
        for p in passages:
            check(set(p)=={'page','text'},'Unapproved passage field.')
            check(isinstance(p['page'],int) and p['page']>0 and isinstance(p['text'],str) and bool(p['text'].strip()),'Invalid passage.')
    print(json.dumps(dict(status='passed',files=len(actual),questions=715,criteria=4722,guidelines=14)))


if __name__=='__main__':
    main()
