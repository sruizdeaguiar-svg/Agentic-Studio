# Estructura del proyecto

Español · [English](en/architecture.md)

La rama `main` contiene el código de la versión actual. Las instantáneas históricas están separadas en `historial-versiones`. Git conserva las carpetas a través de sus archivos; no se incluyen directorios vacíos de datos privados.

```text
Agentic-Studio/
├── native/                     # App nativa macOS, instalador e icono
│   ├── Studio.swift            # Ventana, backend, llavero y controles nativos
│   ├── AgentBrowser.swift      # Navegador aislado por proyecto/origen
│   ├── Installer.swift         # Instalación y migración de datos
│   ├── MakeIcon.swift          # Generación del icono
│   └── tests/                  # Comprobación de confianza TLS
├── prototype/                  # Servidor y cliente web de la aplicación
│   ├── server.py               # API, proyectos, agente y ciclo de motores
│   ├── secure_files.py         # Acceso protegido a archivos del proyecto
│   ├── bounded_http.py         # Conexiones y negociación TLS acotadas
│   ├── agent_extensions.py     # MCP stdio y puente de navegador
│   ├── remote_mcp.py           # MCP HTTP y OAuth/PKCE
│   ├── openai_oauth.py         # Adaptador oficial de OpenAI
│   ├── model_hub.py            # Búsqueda y descargas de Hugging Face
│   ├── runtimes.py             # Detección y configuración de motores
│   ├── runtime_probe.py        # Sondeo de modelos
│   ├── vllm_boot.py            # Arranque de vLLM Metal
│   ├── vllm_runtime.py         # Compatibilidad de memoria/KV
│   ├── web/                    # HTML, JS y CSS de escritorio y móvil
│   └── tests/                  # Regresiones con datos ficticios
├── ios/
│   ├── AgenticMobile/          # Cliente SwiftUI, escáner y TLS fijado
│   │   └── Assets.xcassets/    # Icono y catálogo de recursos
│   ├── AgenticMobile.xcodeproj/# Proyecto Xcode sin equipo personal
│   ├── README-es.md
│   └── README-en.md
├── scripts/                    # Dependencias, empaquetado y exportación limpia
├── docs/                       # Guías, seguridad de la versión e imágenes
│   └── en/                     # Documentación en inglés
├── build-app.sh                # Compilar app macOS
├── build-installer.sh          # Crear instalador portátil
├── build-ios.sh                # Compilar simulador e IPA sin firmar
├── install-app.sh              # Instalación local de desarrollo
├── README.md / README.en.md
├── SECURITY.md / SECURITY.en.md
├── CHANGELOG.md / CHANGELOG.en.md
└── LICENSE
```

El servidor aplica los permisos de proyecto y ejecuta las acciones aprobadas. Los modelos y proveedores generan respuestas o solicitudes de herramientas. El cliente iOS se conecta a la pasarela del Mac; no incorpora un segundo servidor ni pesos.

Los paquetes compilados se publican como archivos de la versión en Releases. Bases de datos, conversaciones, modelos, credenciales, registros de QA y firmas personales no forman parte del código público. La carpeta local de trabajo puede conservar esos elementos fuera de la exportación.

Para compilar y comprobar el proyecto, consulta el [README](../README.md). Para los límites de seguridad, consulta [SECURITY](../SECURITY.md).
