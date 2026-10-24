# Changes

[Español](CHANGELOG.md) · English

## 0.5.1 — macOS installer portability

- Preserves execute permissions for the app, Python and Codex while packaging.
- Explicitly targets macOS 12 for native app/installer instead of inheriting macOS 27 from the build machine.
- Uses the user's Application Support directory independently of the checkout.
- Prefers bundled Codex and handles absent/nonstandard optional engines.
- Adds a reproducible native test with an empty user environment and blocked access to real data, host engines, ChatGPT, Xcode and system Python.
- 73 regression tests passed. See [portability](docs/en/portability.md) for reproduction and limits. Earlier security fixes remain in place.

The iOS client remains at 0.5.0. Earlier versions are kept in `historial-versiones` and their tags. The package is not notarized; execution on a freshly installed OS or macOS 12 is not claimed.
