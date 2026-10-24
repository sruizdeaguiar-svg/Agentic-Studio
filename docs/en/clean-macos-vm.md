# Clean virtualized macOS verification · 0.5.2

[Español](../clean-macos-vm.md) · English

## Actual environment

Two independent macOS **26.6.2 (25G83)** guests, hardware `VirtualMac2,1`, ran through Tart 2.41.1 and Apple Virtualization.framework. Each used 2 CPUs and 4096 MiB RAM. No host folders, clipboard, audio or USB accessories were shared. Only fictitious QA projects and files were used.

Image: `ghcr.io/cirruslabs/macos-tahoe-vanilla@sha256:eeec54bfe1f076e27786c5d92b89187a05b1d109b5071eb2dcdf02d596e34640`.

Cirrus Labs' vanilla image has no extra software, but configures automatic login and remote access for automation. It is not an untouched factory configuration. Xcode, Command Line Tools, Homebrew and ChatGPT were confirmed absent; `xcode-select -p` failed as expected. None was installed to run the tests.

## Functional results

The public 0.5.1 installer was downloaded directly from GitHub inside the guest and matched its published SHA-256. Version 0.5.2 was tested in a separate clean guest. Final package SHA-256:

`b971d62e316b766534de05b77374fd93d8de107ea6a84628830e3209e7db131c`

| Version 0.5.2 check | Result |
| --- | --- |
| Conflicting application rejected without hanging | Passed, exit 2 |
| Native install to a path with spaces and Desktop shortcut | Passed |
| App, Python and Codex execute permissions | Passed |
| Native backend starts and binds only to loopback | Passed |
| Empty initial projects, conversations and settings | Passed |
| Data inside the guest user directory, outside any checkout | Passed |
| Missing optional engines do not prevent startup | Passed |
| Bundled OpenAI helper available | Passed |
| Bundled Codex starts in the product sandbox without an account | Passed |
| Fictitious project file write/read | Passed |
| Setup saved without models | Passed |
| App exit stops its own backend | Passed |
| Update preserves the database hash | Passed |

The installed UI and icon were observed in the VM. One idle 0.5.1 UI observation showed approximately 49 MiB for the backend; this is not total application or inference memory.

A 0.5.1 defect was reproduced: command-line installation did not exit when another app occupied the destination, hitting the 15-second test timeout. Version 0.5.2 exits promptly with code 2, preserves the other application and improves signature-verification error reporting. Its ZIP includes a bilingual installation guide.

The first QA invocation ran bundled Python without `-B`, writing caches into the signed payload and invalidating sealed resources. This was a test error, retained as evidence and rerun from a fresh extraction with caches disabled. The product backend already disables them. This is not attributed to normal installation.

## Gatekeeper remains unresolved

The upstream recipe disables Gatekeeper. Assessments were re-enabled before functional tests; this left the image in **App Store only** mode. A fresh copy with test quarantine was rejected by `spctl` (exit 3), and normal launch showed the block. Quarantine was not removed and Gatekeeper was not disabled to pass this test. Acceptance under “App Store and identified developers” is not established here.

Separately, `syspolicy_check distribution` on 0.5.2 reported **Adhoc Signed App** and **Notary Ticket Missing** (fatal). Ad-hoc signing remains unsuitable for general distribution. The build Mac has only an Apple Development identity; Developer ID Application signing and Apple notarization are missing. **Normal downloaded-app acceptance remains unresolved**, even though command-line package operation was verified.

## Reproduce functional testing

Use a new disposable guest without these dependencies, with an active graphical login and Gatekeeper assessments enabled. Download and extract the ZIP. Copy `scripts/validate-macos-vm.py` from source and run:

```sh
PYTHONDONTWRITEBYTECODE=1 \
  './Instalar Agentic Studio.app/Contents/Resources/Payload/Agentic Studio.app/Contents/Resources/python/bin/python3' \
  -B validate-macos-vm.py \
  --installer './Instalar Agentic Studio.app' \
  --report ./vm-report.json
```

The script refuses physical Macs or guests with detected dependencies. It requires a user with no existing Agentic Studio data. It does not erase existing data or invoke global engine shutdown. This CLI test is separate from distribution/quarantine evaluation and does not replace it.

Real-account OAuth consent, local model inference, macOS 12 runtime and all iOS devices were not tested in the VM. The iOS client remains at 0.5.0 without changes in this release.
