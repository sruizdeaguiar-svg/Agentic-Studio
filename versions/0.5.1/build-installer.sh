#!/bin/zsh
set -eu
cd "${0:A:h}"
mkdir -p analysis
BUILD_ROOT=$(mktemp -d /private/tmp/agentic-clean-installer.XXXXXX)
DEPENDENCIES="${AGENTIC_INSTALLER_DEPENDENCIES:-/private/tmp/agentic-installer-dependencies}"
if [[ ! -f "$DEPENDENCIES/manifest.json" ]]; then /usr/bin/python3 scripts/fetch-runtimes.py "$DEPENDENCIES"; fi
STUDIO_TARGET_PATH="$BUILD_ROOT/Agentic Studio.app" STUDIO_QA_WORKSPACE='@application-support' STUDIO_SHOW_SETUP=1 ./build-app.sh
AGENTIC_INSTALL_BUILD="$BUILD_ROOT" AGENTIC_DEPENDENCIES="$DEPENDENCIES" /usr/bin/python3 scripts/package-installer.py
