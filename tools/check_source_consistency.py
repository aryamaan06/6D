"""Check canonical LF runtime sources; optionally compare exact committed bytes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def check(root=ROOT, git_ref=None):
    root = Path(root).resolve()
    attributes = root / '.gitattributes'
    policy = attributes.is_file() and '* text=auto eol=lf' in attributes.read_text(encoding='utf-8').splitlines()
    records = []
    for path in sorted((root/'src'/'sixd').rglob('*.py')):
        raw = path.read_bytes(); name = path.relative_to(root).as_posix()
        row = {'path':name,'sha256':sha256(raw).hexdigest(),'lf_only':b'\r' not in raw}
        if git_ref is not None:
            try:
                published = subprocess.check_output(['git','show',git_ref+':'+name],cwd=root,stderr=subprocess.DEVNULL)
                row['matches_git_ref'] = raw == published
            except (OSError,subprocess.CalledProcessError):
                row['matches_git_ref'] = False
        records.append(row)
    passed = policy and bool(records) and all(r['lf_only'] and r.get('matches_git_ref',True) for r in records)
    return {'schema':'sixd.source-consistency.v1','passed':passed,'lf_policy_present':policy,
            'git_ref':git_ref,'files_checked':len(records),'files':records,
            'meaning':'Exact checkout/committed-byte consistency. No source hashes or historical receipts are rewritten.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--git-ref',help='Optional immutable commit/ref for exact byte comparison.')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=check(args.root,args.git_ref)
    if args.output:args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'passed':report['passed'],'files_checked':report['files_checked'],
        'git_ref':report['git_ref'],'failed_paths':[r['path'] for r in report['files'] if not r['lf_only'] or not r.get('matches_git_ref',True)]}))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
