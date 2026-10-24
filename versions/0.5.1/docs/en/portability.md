# Download, build and portability

[Español](../portability.md) · English

## Separate requirements

**Using the installer:** Apple Silicon Mac. Version 0.5.1 native binaries explicitly target macOS 12 as their minimum. The package includes Python and the official Codex client. Homebrew, ChatGPT, system Python and Xcode are not required to run the packaged app. Local engines and models are optional, installed separately and have their own macOS requirements.

**Building source:** macOS with a selected full Xcode installation and command-line tools. Packaging needs GitHub access to fetch official SHA-256-pinned dependencies. iOS builds require the iOS SDK; physical installation needs your own signing. No credentials or personal signing team are included.

The package is still ad hoc signed and not notarized by Apple. Gatekeeper may block a quarantined download. Automated tests do not remove quarantine or disable that protection. An intervention-free double-click installation is not promised.

## Build from scratch

```sh
git clone https://github.com/sruizdeaguiar-svg/Agentic-Studio.git
cd Agentic-Studio
./build-app.sh
./build-installer.sh
./build-ios.sh
```

Compiled apps use the current user's Application Support folder by default and can move independently of the checkout. `build-app.sh` creates a development build that needs the developer tools' Python unless a runtime is packaged. Use the `build-installer.sh` output to distribute to a Mac without developer tools.

To verify downloads with an empty cache:

```sh
AGENTIC_INSTALLER_DEPENDENCIES="$(mktemp -d)/dependencies" ./build-installer.sh
```

`STUDIO_QA_WORKSPACE` is an optional explicit development data location. It is not needed for installation. `AGENTIC_VLLM_PYTHON` and `AGENTIC_OMLX_ROOT` support nonstandard engine locations. Missing engines do not prevent startup or OAuth setup.

## Reproducible installer test

On a Mac with a graphical session, run from the source tree:

```sh
python3 scripts/validate-portable-install.py \
  --installer '/path/Instalar Agentic Studio.app' \
  --report '/tmp/agentic-portability-report.json'
```

The test uses a temporary folder and empty HOME/Foundation user environment. It denies access to real user data, external volumes, Homebrew, host engines and ChatGPT, Xcode and system Python. It installs into a path with spaces, checks execute permissions, starts the native app/backend, checks empty state and onboarding, initializes bundled Codex without an account, performs fictitious file IO and verifies an update preserving the database. It does not use real conversations or credentials.

This tests independence from host paths and configuration. **It is not a freshly installed Mac or clean VM, and does not prove execution on macOS 12.** Minimum OS metadata is checked in compiler arguments and Mach-O headers; older systems and Gatekeeper need separate testing.

## Fixes in 0.5.1

- Explicit minimum compilation target: 0.5.0 declared macOS 12 in Info.plist while its own binaries required macOS 27.
- Execute permissions preserved during package copies; the public 0.5.0 installer lost these permissions in its payload.
- Data location independent of the build checkout.
- Bundled Codex preferred over the host ChatGPT installation.
- vLLM discovery no longer exclusively pins a Python minor version; absent or inaccessible engines are handled gracefully.

Release notes record concrete results. An isolated result does not verify every engine/model or replace an independent security audit.

The native app is tested inside the host-denial sandbox. Codex is tested separately in the product's own mandatory sandbox, because macOS rejects applying a second Seatbelt policy. Xcode SwiftUI plugins likewise use their own sandbox, so iOS compilation uses an empty user environment without the external wrapper. No product sandbox or compiler protection is disabled.

## Verified results

The GitHub candidate was cloned into a new path with spaces. The complete installer was rebuilt with an empty dependency cache, empty user home and blocked host-user/volume/Homebrew access. Official Python and Codex archives were downloaded again and SHA-256 verified. Native install, Desktop link, backend startup, empty onboarding state, no-engine handling, bundled Codex in its own sandbox, fictitious file IO, owned-backend shutdown and database-preserving update passed. Thirteen Mach-O files were inspected; the highest declared minimum macOS was 12.0.0. The source also built unsigned iOS simulator and ARM64 device packages with empty user settings. No clean OS VM, older macOS runtime or Gatekeeper/quarantine success is claimed.

The full local regression suite passed 78 tests, including the configured official stdio MCP fixture. The fresh GitHub source suite reported 71 cases with one optional stdio-fixture skip, using bundled Codex and no host MCP installation. The installation fixture never invokes the global LM Studio stop control; shutdown checks target only its own native app and backend.
