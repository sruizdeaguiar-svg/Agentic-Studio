# Project structure

[Español](../architecture.md) · English

`main` contains the current release source. Historical snapshots are kept separately in `historial-versiones`. Git records folders through their files; empty private data directories are not included.

```text
Agentic-Studio/
├── native/                     # Native macOS app, installer and icon
│   ├── Studio.swift            # Window, backend, Keychain and native controls
│   ├── AgentBrowser.swift      # Project/origin-isolated browser
│   ├── Installer.swift         # Installation and data migration
│   ├── MakeIcon.swift          # Icon generation
│   └── tests/                  # TLS trust checks
├── prototype/                  # Application server and web client
│   ├── server.py               # API, projects, agent and engine lifecycle
│   ├── secure_files.py         # Protected project file access
│   ├── bounded_http.py         # Bounded connections and TLS negotiation
│   ├── agent_extensions.py     # stdio MCP and browser broker
│   ├── remote_mcp.py           # HTTP MCP and OAuth/PKCE
│   ├── openai_oauth.py         # Official OpenAI adapter
│   ├── model_hub.py            # Hugging Face discovery and downloads
│   ├── runtimes.py             # Engine discovery/configuration
│   ├── runtime_probe.py        # Model probing
│   ├── vllm_boot.py            # vLLM Metal startup
│   ├── vllm_runtime.py         # Memory/KV compatibility
│   ├── web/                    # Desktop/mobile HTML, JS and CSS
│   └── tests/                  # Fictitious-data regression tests
├── ios/
│   ├── AgenticMobile/          # SwiftUI client, scanner and pinned TLS
│   │   └── Assets.xcassets/    # App icon and asset catalog
│   ├── AgenticMobile.xcodeproj/# Xcode project without a personal team
│   ├── README-es.md
│   └── README-en.md
├── scripts/                    # Dependencies, packaging and clean export
├── docs/                       # Guides, release security notes and images
│   └── en/                     # English documentation
├── build-app.sh                # Build macOS app
├── build-installer.sh          # Build portable installer
├── build-ios.sh                # Build simulator and unsigned IPA
├── install-app.sh              # Local development installation
├── README.md / README.en.md
├── SECURITY.md / SECURITY.en.md
├── CHANGELOG.md / CHANGELOG.en.md
└── LICENSE
```

The server enforces project permissions and performs approved actions. Models and providers generate responses or tool requests. The iOS client connects to the Mac gateway; it does not include a second server or model weights.

Compiled packages are published as Release assets. Databases, conversations, models, credentials, QA logs and personal signing material are not part of the public source. The local working folder may retain these items outside the export.

See the [README](../../README.en.md) for build/test instructions and [SECURITY](../../SECURITY.en.md) for security limits.
