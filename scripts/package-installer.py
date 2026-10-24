"""Build an allowlisted, self-contained, credential-free macOS installer payload."""
import hashlib,json,os,plistlib,shutil,subprocess,tarfile
from pathlib import Path
root=Path.cwd();stage=Path(os.environ['AGENTIC_INSTALL_BUILD']);deps=Path(os.environ['AGENTIC_DEPENDENCIES']);manifest=json.loads((deps/'manifest.json').read_text());app=stage/'Agentic Studio.app';resources=app/'Contents/Resources'
for name in ('python','codex'):
 archive=Path(manifest[name]['archive']);digest=hashlib.sha256(archive.read_bytes()).hexdigest();assert digest==manifest[name]['sha256']
 target=resources if name=='python' else resources/'codex';target.mkdir(exist_ok=True)
 with tarfile.open(archive) as tar:
  # Official, checksum-pinned archives only. Also reject absolute and escaping paths.
  for m in tar.getmembers():
   if m.name.startswith('/') or '..' in Path(m.name).parts:raise ValueError('Unsafe archive member')
  tar.extractall(target)
if not (resources/'python/bin/python3').exists():raise RuntimeError('Missing portable Python')
candidates=[p for p in (resources/'codex').iterdir() if p.is_file() and p.name.startswith('codex-')];assert candidates
candidates[0].rename(resources/'codex/codex');(resources/'codex/codex').chmod(0o755)
for name in ('CODEX-LICENSE','CODEX-NOTICE'):
 if (deps/name).exists():shutil.copyfile(deps/name,resources/'codex'/name)
# Absolute build paths are not part of the public provenance file.
clean={k:{x:y for x,y in v.items() if x!='archive'} for k,v in manifest.items()};(resources/'runtime-sources.json').write_text(json.dumps(clean,indent=2))
subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(app)],check=True)
subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
installer=stage/'Instalar Agentic Studio.app';(installer/'Contents/MacOS').mkdir(parents=True);(installer/'Contents/Resources/Payload').mkdir(parents=True)
shutil.copytree(app,installer/'Contents/Resources/Payload/Agentic Studio.app',copy_function=shutil.copy2,symlinks=True)
subprocess.run(['/usr/bin/xcrun','swiftc','-target','arm64-apple-macos12.0','-swift-version','5','-O','-framework','AppKit',str(root/'native/Installer.swift'),'-o',str(installer/'Contents/MacOS/Instalar Agentic Studio')],check=True)
info={'CFBundleName':'Instalar Agentic Studio','CFBundleDisplayName':'Instalar Agentic Studio','CFBundleIdentifier':'local.agenticstudio.installer','CFBundleExecutable':'Instalar Agentic Studio','CFBundlePackageType':'APPL','CFBundleShortVersionString':'0.5.1','CFBundleVersion':'1','LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True,'NSRemovableVolumesUsageDescription':'Instalar Agentic Studio en la carpeta que selecciones.'}
(installer/'Contents/Info.plist').write_bytes(plistlib.dumps(info));shutil.copyfile(resources/'Studio.icns',installer/'Contents/Resources/Studio.icns');info['CFBundleIconFile']='Studio.icns';(installer/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(installer)],check=True);subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(installer)],check=True)
out=root/'dist';out.mkdir(exist_ok=True);destination=out/'Instalar Agentic Studio.app'
if destination.exists():destination.rename(out/('Instalar Agentic Studio.previous-'+os.urandom(4).hex()+'.app'))
shutil.copytree(installer,destination,copy_function=shutil.copy2,symlinks=True)
zipfile=out/'Agentic-Studio-0.5.1-macOS-AppleSilicon.zip'
subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(installer),str(zipfile)],check=True)
report={'version':'0.5.1','architecture':'arm64','installer':str(destination),'archive':str(zipfile),'sha256':hashlib.sha256(zipfile.read_bytes()).hexdigest(),'portable_runtime':clean,'contains_data':False,'contains_credentials':False,'notarized':False,'codesign':'ad-hoc','native_install_test_pending':True};(root/'analysis/installer-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
