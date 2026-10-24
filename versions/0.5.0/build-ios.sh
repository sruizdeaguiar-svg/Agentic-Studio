#!/bin/zsh
set -eu
cd "${0:A:h}"
mkdir -p analysis
IOS_TASK_BUILD=$(mktemp -d /private/tmp/agentic-ios-release.XXXXXX)
export CLANG_MODULE_CACHE_PATH=/private/tmp/agentic-studio-clang-cache
mkdir -p ios/dist
xcodebuild -project ios/AgenticMobile.xcodeproj -scheme AgenticMobile -sdk iphonesimulator -configuration Release -derivedDataPath "$IOS_TASK_BUILD" CODE_SIGNING_ALLOWED=NO build > analysis/ios-simulator-build.txt 2>&1
IOS_TASK_BUILD="$IOS_TASK_BUILD" /usr/bin/python3 - <<'PY'
import os,shutil
from pathlib import Path
source=Path(os.environ['IOS_TASK_BUILD'])/'Build/Products/Release-iphonesimulator/Agentic Studio.app';target=Path('ios/dist/Simulador/Agentic Studio.app')
if target.exists():
 def cleanup_error(fn,path,error):
  if not isinstance(error[1],FileNotFoundError):raise error[1]
 shutil.rmtree(target,onerror=cleanup_error)
target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source,target,copy_function=shutil.copyfile)
(target/'Agentic Studio').chmod(0o755)
PY
xcodebuild -project ios/AgenticMobile.xcodeproj -scheme AgenticMobile -sdk iphoneos -configuration Release -derivedDataPath "$IOS_TASK_BUILD" CODE_SIGNING_ALLOWED=NO build > analysis/ios-device-build.txt 2>&1
IOS_TASK_BUILD="$IOS_TASK_BUILD" /usr/bin/python3 - <<'PY'
import os,zipfile,plistlib,json,hashlib
from pathlib import Path
source=Path(os.environ['IOS_TASK_BUILD'])/'Build/Products/Release-iphoneos/Agentic Studio.app'
archive=Path('ios/dist/Agentic-Studio-iPhone-iPad-SIN-FIRMAR.ipa')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as out:
 for path in source.rglob('*'):
  if path.is_file() and not path.name.startswith('._'):out.write(path,'Payload/Agentic Studio.app/'+str(path.relative_to(source)))
info=plistlib.loads((source/'Info.plist').read_bytes())
report={'simulator_build':True,'device_arm64_build':True,'device_families':info['UIDeviceFamily'],'version':info['CFBundleShortVersionString'],'ipa_path':str(archive.resolve()),'ipa_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'signed_for_physical_device':False,'physical_device_installed':False,'requires':'This artifact is intentionally unsigned; sign for a target device in Xcode, or use the separately signed iPad development package','physical_device_e2e':False}
Path('analysis/ios-build-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
PY
