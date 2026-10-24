# Instalador macOS / macOS installer

## Español

Agentic Studio 0.5.2 para Apple Silicon incluye Python y el cliente oficial Codex. No necesita Xcode, Homebrew ni ChatGPT para ejecutarse. Los motores y modelos locales son opcionales y se instalan por separado.

1. Descarga el ZIP y el archivo SHA256SUMS de la misma versión en GitHub Releases.
2. Comprueba el SHA-256, descomprime y abre «Instalar Agentic Studio».
3. Elige la carpeta de destino y el acceso al Escritorio. Los datos se guardan por separado en Application Support del usuario.
4. El asistente permite seleccionar carpetas de modelos y conectar OpenAI mediante OAuth en el navegador. No contiene cuentas ni conversaciones preconfiguradas.

**Estado de distribución:** firma ad hoc, sin notarización Apple. Gatekeeper puede bloquear el instalador descargado. La prueba de línea de comandos no demuestra que macOS acepte la apertura normal. No se desactiva Gatekeeper ni se elimina la cuarentena para validar el paquete. La solución de distribución requiere una identidad Developer ID Application y notarización; una identidad Apple Development no la sustituye.

Si la verificación de firma del instalador falla, conserva la instalación anterior y descarga otra copia íntegra. No ejecutes el Python incluido sin `-B`: generar cachés dentro de un paquete firmado altera sus recursos. La app desactiva esos cachés automáticamente.

Las actualizaciones conservan los datos y una copia de la app anterior. Cierra solo Agentic Studio antes de actualizar. No hace falta cerrar motores o apps ajenas.

Código fuente, resultados y límites: https://github.com/sruizdeaguiar-svg/Agentic-Studio

## English

Agentic Studio 0.5.2 for Apple Silicon bundles Python and the official Codex client. Running it does not require Xcode, Homebrew or ChatGPT. Local inference engines and models are optional, separate installations.

1. Download the ZIP and SHA256SUMS from the same GitHub release.
2. Verify SHA-256, extract the ZIP and open “Instalar Agentic Studio”.
3. Choose the destination and optional Desktop shortcut. User data is stored separately in Application Support.
4. Setup lets you choose model folders and connect OpenAI through browser OAuth. No accounts or conversations are preconfigured.

**Distribution status:** ad-hoc signed, not Apple-notarized. Gatekeeper may block the downloaded installer. A command-line test does not prove normal downloaded-app launch acceptance. Validation does not disable Gatekeeper or remove quarantine. Distribution requires a Developer ID Application identity and notarization; Apple Development signing is not a substitute.

If signature verification fails, retain the previous installation and download a fresh, intact copy. Do not run the bundled Python without `-B`: writing caches inside a signed bundle changes its sealed resources. The application automatically disables those caches.

Updates preserve user data and a backup of the previous app. Close only Agentic Studio before updating; other applications and engines do not need to be closed.

Source, results and limitations: https://github.com/sruizdeaguiar-svg/Agentic-Studio
