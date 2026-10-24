#!/bin/zsh
set -eu
cd "${0:A:h}"
STUDIO_TARGET_PATH="$HOME/Applications/Agentic Studio.app" ./build-app.sh
/usr/bin/python3 - <<'PY'
import os,shutil,uuid,subprocess
from pathlib import Path
source=Path.home()/'Applications/Agentic Studio.app'
link=Path.home()/'Desktop/Agentic Studio.app'
if link.exists() and not link.is_symlink():raise RuntimeError('El acceso del escritorio no es un enlace; revísalo antes de reemplazarlo.')
staging=link.with_name('.Agentic-Studio-link-'+uuid.uuid4().hex[:8]);staging.symlink_to(source);os.replace(staging,link)
# Keep the workspace artifact reviewable, with the identical signed contents.
target=Path.cwd()/'Agentic Studio.app';stage=target.with_name('.Agentic-Studio-copy-'+uuid.uuid4().hex[:8]);shutil.copytree(source,stage,copy_function=shutil.copy2);(stage/'Contents/MacOS/Agentic Studio').chmod(0o755)
subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(stage)],check=True)
if target.exists():target.rename(target.with_name(target.name+'.previous-'+uuid.uuid4().hex[:8]))
stage.rename(target)
print('Instalada en '+str(source)+'; acceso del escritorio actualizado.')
PY
