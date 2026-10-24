"""Fetch official, pinned dependencies; verify before any binary is executed."""
import hashlib,json,sys,urllib.request,urllib.parse,urllib.error
from pathlib import Path
out=Path(sys.argv[1] if len(sys.argv)>1 else '/private/tmp/agentic-installer-dependencies');out.mkdir(parents=True,exist_ok=True)
records={
 'python':('astral-sh/python-build-standalone','20261021','cpython-3.12.15+20261021-aarch64-apple-darwin-install_only_stripped.tar.gz','7b8d00b751db21cea87dc551a8f8165147c5fbc5251d5537d7e5497dde00a219'),
 'codex':('openai/codex','rust-v0.164.0','codex-aarch64-apple-darwin.tar.gz','aa8299c169d80111aac05543ad2621c9bdbedb9bc252c905fe3f5a5baf9a4142')}
def fetch(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Agentic-Studio-Build'}),timeout=90)
manifest={}
for kind,(repo,release,name,digest) in records.items():
 url='https://github.com/'+repo+'/releases/download/'+release+'/'+urllib.parse.quote(name);target=out/name
 if not target.exists():
  with fetch(url) as r,target.open('wb') as f:
   while True:
    chunk=r.read(131072)
    if not chunk:break
    f.write(chunk)
 h=hashlib.sha256()
 with target.open('rb') as f:
  for chunk in iter(lambda:f.read(131072),b''):h.update(chunk)
 if h.hexdigest()!=digest:raise ValueError('SHA-256 incorrecto: '+name)
 manifest[kind]={'archive':str(target.resolve()),'sha256':digest,'url':url,'release':release}
for name in ('LICENSE','NOTICE'):
 try:
  with fetch('https://raw.githubusercontent.com/openai/codex/rust-v0.164.0/'+name) as r:(out/('CODEX-'+name)).write_bytes(r.read())
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('Dependencias oficiales verificadas.')
