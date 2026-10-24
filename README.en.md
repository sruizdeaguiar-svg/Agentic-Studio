![Agentic Studio](docs/images/agentic-studio.png)

[Español](README.md) · English

# Agentic Studio

An agent and model workspace for macOS, with an iPhone/iPad client over your local network. It combines conversations, project file tools, local inference engines, MCP and OpenAI access through the official OAuth client.

The Mac runs models and tools. iPhone and iPad share the conversation over HTTPS without downloading model weights.

## Features

- Projects with their own working folder and independent write and execution permissions: deny, review or allow. Review file proposals before accepting them.
- An agent with file reading, search, proposed edits and sandboxed commands; local stdio or remote HTTP/OAuth MCP; a separate browser restricted to project-approved origins.
- llama.cpp, oMLX and vLLM Metal engines, compatible model discovery, context, KV cache and sampling settings, and load/unload/stop controls. Owned engines switch sequentially. An explicit control also quits LM Studio and releases resources.
- Model discovery in local folders and mounted volumes; public Hugging Face search and streamed downloads with revision, size and hash verification.
- Generation statistics, tool activity and reasoning text when the provider supplies it. Context compaction and partial file reads help limit memory use.
- Authorized project selection, conversations, files, reviews, activity and generation controls on iPad. Administrative settings remain on the Mac.

## Install on macOS

Apple Silicon, macOS 12 or later. Download the installer from Releases, extract it and open **Instalar Agentic Studio**. Choose an installation folder and optionally create a Desktop shortcut. The setup assistant detects model folders and offers OpenAI OAuth sign-in.

The package includes portable Python and the official Codex helper; using it does not require Xcode. Inference engines and models are installed separately. Configure their paths in the Engine panel. The current application interface is in Spanish; this documentation provides English usage instructions.

The current distribution is ad hoc signed and **not notarized by Apple**. It is not presented as Gatekeeper-approved software. You can inspect and build the source.

Updates preserve the existing data location and credential identity. They do not delete working folders or download models without approval.

## iPhone and iPad

Requires iOS/iPadOS 17 or later. The public IPA is **unsigned** and needs valid development or distribution signing before installation on a physical device. The Xcode project contains no personal team, certificates or provisioning profiles.

On the Mac, open **Conexiones → Red local**, select authorized projects and display the QR code. On the device, tap **Escanear QR del Mac**. Pairing is single-use, expires after five minutes and pins the server certificate. Mobile sessions last up to 24 hours. Changing permissions or stopping the gateway revokes sessions. Both devices must stay on the same local network.

The camera only reads the pairing QR. Photos and microphone access are not requested. Global settings, OAuth, model installation and permission changes remain on the Mac.

## Data and permissions

Local inference uses the configured loopback providers. **OpenAI and remote MCP servers receive the content sent to their models or tools**; these are external services. OAuth requires account-owner consent and is not an OpenAI API key or a guarantee of model availability.

Agent commands use macOS Seatbelt and fail closed if isolation cannot be established. Permissions are enforced by the backend, not granted by the model. Configured engine and MCP executables must be trusted. The client cannot sandbox a remote service: review its permissions and effects.

Available RAM is an estimate displayed separately from free memory, reclaimable cache, compression and swap. MoE admission budgets full model weights, not only active experts.

See [security guidance](SECURITY.en.md) and [security fixes in 0.5.0](docs/en/releases/0.5.0-security.md). The application does not encrypt conversations at rest.

## Build and test

On macOS with Xcode and command-line tools:

```sh
./build-app.sh
./build-installer.sh
./build-ios.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s prototype/tests -p 'test_*.py' -v
```

The installer fetches official dependencies pinned by hash. Source releases contain no models or developer data. Open `ios/AgenticMobile.xcodeproj` and select your own team to sign iOS builds.

The stdio interoperability tests are skipped unless the official MCP filesystem server is installed in an isolated fictitious QA folder configured through `STUDIO_MCP_OFFICIAL_ROOT`. Command isolation tests need macOS Seatbelt.

## Validation and limits

The regression suite uses fictitious projects and credentials. It covers authentication, folder isolation, permissions, OAuth/PKCE, MCP, TLS, mobile revocation and project lifecycle.

Sequential inference was verified with small models on llama.cpp, oMLX and vLLM Metal. The specific MoE test used **DeepSeek-Coder-V2-Lite Q4_K_M, CPU with mmap, repacking disabled and a 4096-token context**, including two load/response cycles and an actual agent file read. This does not certify all MoE models, quantizations or Metal/MLX execution. Full weights still require memory.

Screenshots show fictitious UI validation data. Local tests and packages do not replace an independent security audit or testing on every device.

## Documentation and versions

- [User guide](docs/en/guide.md)
- [iPhone/iPad guide](ios/README-en.md)
- [Current changelog](CHANGELOG.en.md)
- [Third-party notices](THIRD_PARTY_NOTICES.en.md)
- [Previous-version archive](https://github.com/sruizdeaguiar-svg/Agentic-Studio/tree/historial-versiones)

`main` contains the current release. Previous snapshots and notes are kept separately in `historial-versiones`.
