"""Create a release source tree from an explicit allowlist, never the working data tree."""
import hashlib,json,re,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
destination=Path(sys.argv[1]).resolve()
if destination.exists():raise SystemExit('Choose a fresh export destination.')
paths=[root/name for name in ('README.md','README.en.md','LICENSE','SECURITY.md','SECURITY.en.md','CHANGELOG.md','CHANGELOG.en.md','THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.en.md','.gitignore','build-app.sh','build-ios.sh','build-installer.sh','install-app.sh','Iniciar Studio.command')]
for pattern in ('native/*.swift','native/tests/*.swift','prototype/*.py','prototype/web/*.html','prototype/web/*.js','prototype/web/*.css','prototype/tests/test_*.py','scripts/*.py','ios/AgenticMobile/**/*.swift','ios/AgenticMobile/**/*.plist','ios/AgenticMobile/**/*.json','ios/AgenticMobile/**/*.png','ios/AgenticMobile.xcodeproj/project.pbxproj','ios/AgenticMobile.xcodeproj/xcshareddata/xcschemes/*.xcscheme','ios/README-es.md','ios/README-en.md','docs/**/*.md','docs/images/*.png'):
 paths.extend(root.glob(pattern))
paths=sorted(set(p for p in paths if p.is_file() and not p.name.startswith('._')))
manifest=[]
for p in paths:
 relative=p.relative_to(root)
 if p.is_symlink():raise SystemExit('Symlink rejected: '+str(relative))
 raw=p.read_bytes()
 if p.suffix!='.png':
  text=raw.decode('utf-8')
  forbidden=[r'/Users/[A-Za-z0-9_.-]+/',r'/Volumes/'+r'Seguridad',r'75E8'+r'44Z232',r'0000'+r'8142-',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}',r'\bgh[pousr]_[A-Za-z0-9]{30,}',r'\bhf_[A-Za-z0-9]{30,}']
  if any(re.search(pattern,text) for pattern in forbidden):raise SystemExit('Potential private content: '+str(relative))
  if p.name=='project.pbxproj' and any(value.strip()!='""' for value in re.findall(r'DEVELOPMENT_TEAM\s*=([^;]*);',text)):raise SystemExit('Personal signing team rejected.')
 target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 if p.suffix in ('.sh','.command'):target.chmod(0o755)
 manifest.append({'path':str(relative),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
report={'passed':True,'files':manifest,'excluded':['data','analysis','.qa','app bundles','signed IPA','credentials','personal signing profiles','xcuserdata'],'source_root':str(destination)}
(root/'analysis/public-export-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({'passed':True,'files':len(paths),'destination':str(destination)}))
