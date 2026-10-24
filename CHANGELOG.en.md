# Changes

[Español](CHANGELOG.md) · English

## 0.5.2 — Clean macOS VM verification

- Thirteen checks passed on macOS 26.6.2 without Xcode, Command Line Tools, Homebrew or ChatGPT.
- Fixes CLI installation hanging when another app occupies the destination; it now exits with code 2 without replacing it.
- Improves signature diagnostics and bundles a bilingual installation guide in the ZIP.
- Adds a reproducible script and [VM results](docs/en/clean-macos-vm.md).
- Gatekeeper remains unresolved: macOS confirmed ad-hoc signing and a missing notarization ticket. Normal downloaded-app acceptance is not claimed.
- iOS client stays at 0.5.0 without changes.

## 0.5.1 — macOS installer portability

- Preserves execute permissions for the app, Python and Codex while packaging.
- Explicitly targets macOS 12 for native app/installer instead of inheriting macOS 27 from the build machine.
- Uses the user's Application Support directory independently of the checkout.
- Prefers bundled Codex and handles absent/nonstandard optional engines.
- Adds a reproducible native test with an empty user environment and blocked access to real data, host engines, ChatGPT, Xcode and system Python.
- 78 regression tests passed. See [portability](docs/en/portability.md) for reproduction and limits. Earlier security fixes remain in place.

The iOS client remains at 0.5.0. Earlier versions are kept in `historial-versiones` and their tags. The package is not notarized; execution on a freshly installed OS or macOS 12 is not claimed.

- Optional per-model memory admission override, off by default, with context/KV/concurrency and permission limits retained.
