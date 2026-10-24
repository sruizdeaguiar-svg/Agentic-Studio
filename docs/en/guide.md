# Agentic Studio user guide

[Español](../guide.md) · English

## First launch

The installer lets you choose a destination and Desktop shortcut. Data is stored separately; updates preserve its location. In **Instalación y ajustes**, review discovered model folders and configure OpenAI if needed. OAuth is completed in the account owner's browser; never paste tokens into a conversation.

## Projects and the agent

Create a project, choose its working folder and set write/execute permissions to deny, review or allow. Modifying a project changes its scope and revokes affected mobile sessions. Project deletion is recoverable and does not delete external files.

In **Conversación**, choose a provider/model and enable the agent. The side panel shows files and proposals. Inspect file content and commands before approving them. Activity shows tools, results and reasoning text supplied by the provider; it does not prove the model's claims are correct. A missing folder or unavailable sandbox blocks the action and requires user intervention.

## Models and memory

In **Motor**, select a compatible model and review context, KV cache, batch size, memory limits and MoE options. Loading a local model starts the owned server. Changes are sequential so the previous owned model is unloaded before the next one starts. Unrelated engines are not stopped automatically. The explicit LM Studio control requests model unload, server stop and application quit.

**Parar todos y liberar RAM** stops app-controlled resources, adapters and the gateway and cancels downloads. macOS manages system caches; the app does not promise to recover all RAM or eliminate swap. A MoE model with few active experts may still require all weights in memory. Available-memory values are estimates.

In **Modelos**, search public Hugging Face repositories, review files, size and destination, and approve a download. Revision and hashes are checked before the final file is published. Downloaded repository Python code is not executed.

## MCP and the browser

Configure them per project. Review the command or endpoint before connecting MCP. New tools remain denied until permissions are saved. For HTTP/OAuth, review the resource, issuer and scopes before granting access. A remote tool may have external effects even if its description claims read-only behavior.

The agent browser has an ephemeral session and explicit allowed origins. Reading, clicking and typing have permissions. It does not allow file uploads, password entry or access to the application's native bridge.

## iPhone/iPad and shutdown

Authorize projects in **Conexiones → Red local** and scan the QR from the device. Each client has its own active project and can open only authorized projects. Review its proposals as you would on the Mac. Disabling the gateway revokes all clients.

Use **Cerrar** to exit the app and its owned processes. Conversations persist. Closing the application does not delete external files or servers.

## Versions and security

`main` contains the current release. Earlier versions are kept in [historial-versiones](https://github.com/sruizdeaguiar-svg/Agentic-Studio/tree/historial-versiones). Read [current changes](../../CHANGELOG.en.md) and [security guidance](../../SECURITY.en.md) before upgrading.

## Optional memory admission override

In Motor, enable **Cargar aunque supere la estimación de memoria** for the selected model. It is off by default and saved per model. It skips the panel's admission budget; for oMLX it also passes `--memory-guard off` without a conflicting ceiling. Context, explicit KV cache, concurrency and project permissions remain enforced. The OS or engine may still reject allocations; enabling the option does not guarantee a model will fit. No large-model load is performed simply by saving the option.
