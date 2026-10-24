# Componentes externos

Español · [English](THIRD_PARTY_NOTICES.en.md)


El código fuente del cliente y su servidor usa las bibliotecas estándar de Python y los frameworks del sistema Apple. El paquete macOS incorpora dependencias oficiales con versión y hash fijados en `scripts/fetch-runtimes.py`:

- CPython, distribuido por python-build-standalone de Astral, con sus licencias en la distribución portátil.
- OpenAI Codex, bajo Apache License 2.0; LICENSE y NOTICE se incluyen junto al ejecutable.

Los motores llama.cpp, oMLX, vLLM y LM Studio y los pesos de los modelos no se redistribuyen en este paquete. Sus licencias y requisitos son independientes. Los servicios MCP remotos y OpenAI están sujetos a sus propias condiciones de acceso.
