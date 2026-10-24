# Agentic Studio security

[Español](SECURITY.md) · English

Version 0.5.0 includes a pre-publication source review and regression tests. Findings, fixes and limitations are recorded in [the release security notes](docs/en/releases/0.5.0-security.md). This is not an independent audit or a guarantee that no vulnerabilities remain.

Use the repository's private vulnerability reporting channel when enabled. Do not publish tokens, conversations, project documents, gateway keys or OAuth credentials in a public issue. If no private channel is available, open an issue without exploit details or sensitive data to agree on a reporting channel.

Use review permissions for new tools and authorize only necessary folders and origins. Remote MCP servers and external inference providers receive the data sent to their tools or models. Stopping the gateway revokes mobile sessions. Do not expose its ports to the Internet.
