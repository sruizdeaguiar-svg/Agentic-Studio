#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ ! -x "Agentic Studio.app/Contents/MacOS/Agentic Studio" ]]; then
  /bin/zsh ./build-app.sh
fi
open "$PWD/Agentic Studio.app"
