#!/usr/bin/env python3
"""Bounded, redacted pre-publication checks. No file content is printed."""
import argparse,json,re,sys
from pathlib import Path
PATTERNS={
 'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'jwt':r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',
 'github-token':r'\b(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,})\b',
 'service-secret':r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b',
 'cloud-access-key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'literal-secret-assignment':r'''(?i)["']?(?:api[_-]?key|access[_-]?token|ugate[_-]?token|password|app[_-]?secret|client[_-]?secret|authorization)["']?\s*[:=]\s*["'](?:Bearer\s+)?[A-Za-z0-9_.+/-]{16,}["']''',
 'personal-filesystem-path':r'/Users/[A-Za-z0-9._-]+/',
}
FORBIDDEN_NAMES={'.env','.netrc','.npmrc','hosts.yml','auth-store.json'}
FORBIDDEN_DIRS={'raw','cases','investigations','.private'}
def scan(root):
 findings=[];count=0
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root)
  if '.git' in rel.parts or '__pycache__' in rel.parts:continue
  if p.is_symlink():findings.append({'file':str(rel),'rule':'symlink'});continue
  if not p.is_file():continue
  count+=1
  if p.name in FORBIDDEN_NAMES or (p.name.startswith('.env.') and p.name!='.env.example') or p.suffix.lower() in {'.pem','.key','.p12','.pfx'} or FORBIDDEN_DIRS.intersection(rel.parts):
   findings.append({'file':str(rel),'rule':'private-file-or-directory'})
  if p.stat().st_size>2_000_000:findings.append({'file':str(rel),'rule':'unexpected-large-file'});continue
  try:text=p.read_text(encoding='utf-8')
  except UnicodeDecodeError:findings.append({'file':str(rel),'rule':'unexpected-binary-file'});continue
  for name,pattern in PATTERNS.items():
   for match in re.finditer(pattern,text):
    findings.append({'file':str(rel),'line':text.count('\n',0,match.start())+1,'rule':name})
 return {'files_scanned':count,'findings':findings,'passed':not findings}
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',nargs='?',default='.');args=parser.parse_args();result=scan(Path(args.root).resolve());print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
