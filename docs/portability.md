# Descarga, compilación y portabilidad

Español · [English](en/portability.md)

## Requisitos separados

**Usar el instalador:** Mac Apple Silicon. Los binarios propios de la versión 0.5.1 se compilan con destino mínimo macOS 12. El paquete incluye Python y el cliente oficial Codex; no requiere Homebrew, ChatGPT, Python del sistema ni Xcode para ejecutar la aplicación. Los motores locales y sus modelos son opcionales y se instalan por separado, con sus propios requisitos de macOS.

**Compilar el código:** macOS con Xcode completo seleccionado y sus herramientas de línea de comandos. El empaquetado requiere acceso a GitHub para obtener las dependencias oficiales fijadas por SHA-256. La compilación iOS requiere el SDK de iOS; la instalación en dispositivo físico requiere tu propia firma. No se incluyen credenciales ni un equipo de firma personal.

El paquete todavía usa firma ad hoc y no está notarizado por Apple. Una descarga con cuarentena puede quedar bloqueada por Gatekeeper. Las pruebas automatizadas no eliminan la cuarentena ni desactivan esa protección. No se promete una instalación con doble clic sin intervención de macOS.

## Compilar desde cero

```sh
git clone https://github.com/sruizdeaguiar-svg/Agentic-Studio.git
cd Agentic-Studio
./build-app.sh
./build-installer.sh
./build-ios.sh
```

La app compilada utiliza Application Support del usuario por defecto; puede moverse sin depender de la ubicación del checkout. `build-app.sh` crea una compilación de desarrollo que necesita el Python de las herramientas de desarrollo si no se ha empaquetado el runtime. Para distribuir a un Mac sin herramientas, utiliza el instalador generado por `build-installer.sh`.

Para comprobar descargas con caché vacía:

```sh
AGENTIC_INSTALLER_DEPENDENCIES="$(mktemp -d)/dependencies" ./build-installer.sh
```

`STUDIO_QA_WORKSPACE` permite una ubicación explícita de datos para desarrollo; no es necesaria para instalar. `AGENTIC_VLLM_PYTHON` y `AGENTIC_OMLX_ROOT` permiten instalaciones de motores fuera de las ubicaciones habituales. La ausencia de motores no impide abrir la app y configurar OAuth.

## Prueba reproducible del instalador

En un Mac con sesión gráfica, ejecuta desde el código fuente:

```sh
python3 scripts/validate-portable-install.py \
  --installer '/ruta/Instalar Agentic Studio.app' \
  --report '/tmp/agentic-portability-report.json'
```

La prueba usa una carpeta temporal y un HOME/entorno Foundation vacíos. Bloquea acceso a los datos del usuario real, volúmenes externos, Homebrew, motores y ChatGPT instalados, Xcode y Python del sistema. Instala en una carpeta con espacios, comprueba los permisos de ejecución, arranca la app y su backend, verifica estado vacío y configuración inicial, inicializa el Codex incluido sin cuenta, realiza lectura/escritura ficticia y comprueba una actualización que conserva la base de datos. No utiliza conversaciones ni credenciales del usuario real.

Esto prueba independencia de rutas y configuración en el sistema anfitrión. **No equivale a probar un Mac recién instalado o una máquina virtual limpia, ni acredita ejecución real en macOS 12.** La versión mínima se comprueba en las instrucciones de compilación y en los metadatos Mach-O; los sistemas antiguos y Gatekeeper requieren verificación separada.

## Correcciones de 0.5.1

- Destino de compilación mínimo explícito: la 0.5.0 declaraba macOS 12 en Info.plist, pero sus binarios propios exigían macOS 27.
- Preservación de permisos de ejecución al copiar el paquete. El instalador público 0.5.0 perdía esos permisos en su payload.
- Ubicación de datos independiente de la carpeta de compilación.
- Preferencia por el Codex incluido; la app de ChatGPT del anfitrión ya no es la dependencia preferida del instalador.
- Descubrimiento de vLLM sin fijar exclusivamente una versión menor de Python y tratamiento de motores ausentes o inaccesibles.

Los resultados concretos se publican en las notas de la versión. Un resultado aislado no demuestra funcionamiento con todos los motores o modelos ni sustituye una auditoría externa.
