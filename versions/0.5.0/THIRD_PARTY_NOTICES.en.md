# Third-party components

[Español](THIRD_PARTY_NOTICES.md) · English

The client and server source uses Python's standard library and Apple system frameworks. The macOS package includes official dependencies whose versions and hashes are pinned in `scripts/fetch-runtimes.py`:

- CPython, distributed through Astral's python-build-standalone, with its licenses in the portable distribution.
- OpenAI Codex, under Apache License 2.0; LICENSE and NOTICE are included alongside the executable.

llama.cpp, oMLX, vLLM, LM Studio and model weights are not redistributed in this package. Their licenses and requirements apply separately. Remote MCP services and OpenAI have their own access terms.
