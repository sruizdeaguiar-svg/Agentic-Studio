# Changes

[Español](CHANGELOG.md) · English

## 0.5.0 — Agentic Studio

- New name and icon on macOS, iPhone and iPad, with migration of existing data and credential identity.
- Editable projects with individual working folders and permissions; recoverable project removal.
- Shared desktop/mobile layout and an authorized project selector.
- Sequential engine switching, unloading the previous model, global resource stop and explicit complete LM Studio shutdown.
- Estimated available memory with a breakdown and conservative MoE budgeting.
- Fixed DeepSeek CPU/mmap loading without repacking and added a validated JSON tool protocol.
- Installer with selectable destination, model discovery and OAuth setup.
- Security fixes AS-2026-01 through AS-2026-05: file paths and links, TLS negotiation, connection limits, local bootstrap, database permissions and mobile input validation. See [the security notes](docs/en/releases/0.5.0-security.md).

README and SECURITY describe verified functionality, limitations and signing requirements. The version number does not imply Apple notarization or App Store distribution. Previous versions are documented separately in the `historial-versiones` branch.
