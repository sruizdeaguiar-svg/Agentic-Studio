"""Build an allowlisted, self-contained, credential-free macOS installer payload."""
import hashlib,json,os,plistlib,shutil,subprocess,tarfile,zipfile as zip_module
from pathlib import Path
from portable_checks import verify_payload
root=Path.cwd();stage=Path(os.environ['AGENTIC_INSTALL_BUILD']);deps=Path(os.environ['AGENTIC_DEPENDENCIES']);manifest=json.loads((deps/'manifest.json').read_text());app=stage/'Agentic Studio.app';resources=app/'Contents/Resources'
# The manifest is a cache, not an independent trust anchor. Keep these pins in
# sync with fetch-runtimes.py when intentionally updating dependencies.
trusted_sha256={
 'python':'7b8d00b751db21cea87dc551a8f8165147c5fbc5251d5537d7e5497dde00a219',
 'codex':'aa8299c169d80111aac05543ad2621c9bdbedb9bc252c905fe3f5a5baf9a4142',
}
for name in ('python','codex'):
 archive=Path(manifest[name]['archive'])
 digest=hashlib.sha256(archive.read_bytes()).hexdigest()
 if manifest[name]['sha256'] != trusted_sha256[name] or digest != trusted_sha256[name]:
  raise ValueError('Untrusted or corrupt runtime archive: '+name)
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
payload_checks=verify_payload(app)
subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(app)],check=True)
subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
installer=stage/'Instalar Agentic Studio.app';(installer/'Contents/MacOS').mkdir(parents=True);(installer/'Contents/Resources/Payload').mkdir(parents=True)
shutil.copytree(app,installer/'Contents/Resources/Payload/Agentic Studio.app',copy_function=shutil.copy2,symlinks=True)
subprocess.run(['/usr/bin/xcrun','swiftc','-target','arm64-apple-macos12.0','-swift-version','5','-O','-framework','AppKit',str(root/'native/Installer.swift'),'-o',str(installer/'Contents/MacOS/Instalar Agentic Studio')],check=True)
info={'CFBundleName':'Instalar Agentic Studio','CFBundleDisplayName':'Instalar Agentic Studio','CFBundleIdentifier':'local.agenticstudio.installer','CFBundleExecutable':'Instalar Agentic Studio','CFBundlePackageType':'APPL','CFBundleShortVersionString':'0.5.2','CFBundleVersion':'1','LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True,'NSRemovableVolumesUsageDescription':'Instalar Agentic Studio en la carpeta que selecciones.'}
(installer/'Contents/Info.plist').write_bytes(plistlib.dumps(info));shutil.copyfile(resources/'Studio.icns',installer/'Contents/Resources/Studio.icns');info['CFBundleIconFile']='Studio.icns';(installer/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(installer)],check=True);subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(installer)],check=True)
verify_payload(installer/'Contents/Resources/Payload/Agentic Studio.app')
out=root/'dist';out.mkdir(exist_ok=True);destination=out/'Instalar Agentic Studio.app'
if destination.exists():destination.rename(out/('Instalar Agentic Studio.previous-'+os.urandom(4).hex()+'.app'))
shutil.copytree(installer,destination,copy_function=shutil.copy2,symlinks=True)
zipfile=out/'Agentic-Studio-0.5.2-macOS-AppleSilicon.zip'
subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(installer),str(zipfile)],check=True)
with zip_module.ZipFile(zipfile,'a',compression=zip_module.ZIP_DEFLATED) as archive:
 archive.writestr('INSTALL-LEEME.md',(root/'docs/installer-guide.md').read_text())
report={'version':'0.5.2','architecture':'arm64','installer':str(destination),'archive':str(zipfile),'sha256':hashlib.sha256(zipfile.read_bytes()).hexdigest(),'portable_runtime':clean,'contains_data':False,'contains_credentials':False,'payload_checks':payload_checks,'notarized':False,'codesign':'ad-hoc','native_install_test_pending':True};(root/'analysis/installer-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
