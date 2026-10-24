#!/bin/zsh
set -eu
cd "${0:A:h}"
mkdir -p analysis
STUDIO_ROOT="$PWD"
STUDIO_BUILD=$(mktemp -d /private/tmp/agentic-studio-build.XXXXXX)
APP="$STUDIO_BUILD/Agentic Studio.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/prototype"
export CLANG_MODULE_CACHE_PATH="$STUDIO_BUILD/clang-cache"
export SWIFT_MODULECACHE_PATH="$STUDIO_BUILD/swift-cache"
COPYFILE_DISABLE=1 /bin/cp native/Studio.swift "$STUDIO_BUILD/main.swift"
xcrun swiftc -target arm64-apple-macos12.0 -swift-version 5 -O -framework AppKit -framework WebKit -framework Security "$STUDIO_BUILD/main.swift" native/AgentBrowser.swift -o "$APP/Contents/MacOS/Agentic Studio"
xcrun swift native/MakeIcon.swift "$STUDIO_BUILD/Studio.iconset"
/usr/bin/iconutil -c icns "$STUDIO_BUILD/Studio.iconset" -o "$APP/Contents/Resources/Studio.icns"
COPYFILE_DISABLE=1 /bin/cp prototype/server.py "$APP/Contents/Resources/prototype/server.py"
COPYFILE_DISABLE=1 /bin/cp prototype/secure_files.py prototype/bounded_http.py prototype/agent_extensions.py prototype/remote_mcp.py prototype/openai_oauth.py prototype/model_hub.py prototype/lan_server.py prototype/runtimes.py prototype/runtime_probe.py prototype/vllm_boot.py prototype/vllm_runtime.py "$APP/Contents/Resources/prototype/"
mkdir -p "$APP/Contents/Resources/prototype/web"
COPYFILE_DISABLE=1 /bin/cp prototype/web/index.html prototype/web/app.js prototype/web/style.css prototype/web/mobile.html prototype/web/mobile.js prototype/web/mobile.css "$APP/Contents/Resources/prototype/web/"
STUDIO_APP="$APP" /usr/bin/python3 - <<'PY'
import plistlib
import os
from pathlib import Path
root = Path.cwd()
info = dict(CFBundleName=os.environ.get('STUDIO_DISPLAY_NAME','Agentic Studio'), CFBundleDisplayName=os.environ.get('STUDIO_DISPLAY_NAME','Agentic Studio'), CFBundleExecutable='Agentic Studio', CFBundleIdentifier=os.environ.get('STUDIO_BUNDLE_ID','local.agenticstudio.workspace'), CFBundleVersion='9', CFBundleShortVersionString='0.5.1', CFBundlePackageType='APPL', NSHighResolutionCapable=True, NSRemovableVolumesUsageDescription='Agentic guarda tus proyectos y modelos en el volumen que elijas. El agente conserva sus permisos por proyecto.', NSLocalNetworkUsageDescription='Conectar tu iPhone o iPad al servidor del Mac en tu red local.', LSMinimumSystemVersion='12.0', StudioWorkspace=os.environ.get('STUDIO_QA_WORKSPACE','@application-support'), StudioShowSetup=os.environ.get('STUDIO_SHOW_SETUP')=='1', NSAppTransportSecurity={'NSAllowsLocalNetworking': True})
info['CFBundleIconFile']='Studio.icns'
with (Path(os.environ['STUDIO_APP'])/'Contents/Info.plist').open('wb') as f: plistlib.dump(info,f)
PY
/usr/bin/codesign --force --deep --sign - "$APP"
STUDIO_APP="$APP" STUDIO_TARGET="${STUDIO_TARGET_PATH:-$STUDIO_ROOT/Agentic Studio.app}" /usr/bin/python3 - <<'PY'
import os, shutil, uuid, subprocess
from pathlib import Path
source=Path(os.environ['STUDIO_APP']); target=Path(os.environ['STUDIO_TARGET'])
target.parent.mkdir(parents=True,exist_ok=True)
staging=target.with_name('.'+target.name+'.staging-'+uuid.uuid4().hex[:8])
shutil.copytree(source,staging,copy_function=shutil.copy2)
(staging/'Contents/MacOS/Agentic Studio').chmod(0o755)
# A fresh vnode avoids stale macOS code-signature caches from truncating a previously executed binary.
for p in staging.rglob('._*'):
    if p.is_file():p.unlink()
subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(staging)],check=True)
previous=None
if target.exists():
    previous=target.with_name(target.name+'.previous-'+uuid.uuid4().hex[:8]);target.rename(previous)
try:staging.rename(target)
except BaseException:
    if previous:previous.rename(target)
    raise

PY
echo "App creada: ${STUDIO_TARGET_PATH:-$STUDIO_ROOT/Agentic Studio.app}"
