# Verificación en macOS virtualizado limpio · 0.5.2

Español · [English](en/clean-macos-vm.md)

## Entorno real

Se ejecutaron dos copias independientes de macOS **26.6.2 (25G83)**, hardware `VirtualMac2,1`, con Tart 2.41.1 sobre Apple Virtualization.framework. Cada VM usó 2 CPU y 4096 MiB de RAM. No se compartieron carpetas del anfitrión, portapapeles, audio ni accesorios USB. Solo se usaron proyectos y archivos ficticios.

Imagen: `ghcr.io/cirruslabs/macos-tahoe-vanilla@sha256:eeec54bfe1f076e27786c5d92b89187a05b1d109b5071eb2dcdf02d596e34640`.

La imagen vanilla de Cirrus Labs no incluye software adicional, pero configura inicio automático y acceso remoto para automatización. No es una instalación de fábrica sin ajustes. Se comprobaron la ausencia de Xcode, Command Line Tools, Homebrew y ChatGPT, y el fallo esperado de `xcode-select -p`. No se instaló ninguna de esas dependencias para ejecutar las pruebas.

## Resultados funcionales

El instalador público 0.5.1 se descargó directamente desde GitHub dentro del huésped. Su SHA-256 coincidió con el publicado. La 0.5.2 se probó en otra copia limpia; el hash del paquete final es:

`b971d62e316b766534de05b77374fd93d8de107ea6a84628830e3209e7db131c`

| Comprobación 0.5.2 | Resultado |
| --- | --- |
| Rechazo de otra aplicación en el destino, sin bloqueo | Correcto, salida 2 |
| Instalación nativa en carpeta con espacios y acceso del Escritorio | Correcto |
| Permisos de ejecución de app, Python y Codex | Correcto |
| Arranque del backend nativo y enlace exclusivo a loopback | Correcto |
| Proyectos, conversaciones y configuración inicial vacíos | Correcto |
| Datos fuera del checkout, dentro del usuario huésped | Correcto |
| Motores opcionales ausentes tratados sin impedir el arranque | Correcto |
| Auxiliar OpenAI incluido disponible | Correcto |
| Codex incluido arranca en el sandbox del producto, sin cuenta | Correcto |
| Proyecto ficticio: escritura y lectura de archivo | Correcto |
| Configuración inicial guardada sin modelos | Correcto |
| Salida de la app detiene su backend propio | Correcto |
| Actualización conserva el hash de la base de datos | Correcto |

La interfaz y el icono de la app instalada se observaron dentro de la VM. El indicador del backend mostró aproximadamente 49 MiB en una observación en reposo de 0.5.1; no es una medida del consumo total de la app ni de inferencia.

Se reprodujo un defecto de 0.5.1: el modo de instalación por línea de comandos no terminaba cuando otra aplicación ocupaba el destino. El test alcanzó su límite de 15 segundos. La 0.5.2 rechaza ese caso inmediatamente con código 2, conserva la otra app y mejora el diagnóstico de verificación de firma. El ZIP incorpora una guía de instalación bilingüe.

El primer ensayo de QA ejecutó el Python incluido sin `-B`, escribiendo cachés y alterando recursos firmados del payload. Fue un error de la prueba; se conservó el resultado y se repitió desde una extracción nueva con los cachés desactivados. El backend del producto ya los desactiva. No se atribuye ese fallo a la instalación normal.

## Gatekeeper: pendiente de resolver

La receta upstream desactiva Gatekeeper. Se reactivaron las evaluaciones antes de los ensayos funcionales; esa restauración dejó la política de la imagen en **solo App Store**. Una copia nueva con cuarentena de prueba fue rechazada por `spctl` (salida 3), y la apertura normal mostró el bloqueo. No se eliminó la cuarentena ni se desactivó Gatekeeper para superar esa prueba. No se acredita aquí aceptación bajo la política «App Store y desarrolladores identificados».

Además, `syspolicy_check distribution` en 0.5.2 informó **Adhoc Signed App** y **Notary Ticket Missing** (fatal). La firma ad hoc sigue sin ser adecuada para distribución general. El Mac de construcción solo dispone de una identidad Apple Development; falta Developer ID Application y notarización de Apple. **La aceptación normal de una descarga no está resuelta**, aunque el funcionamiento por línea de comandos del paquete sí esté comprobado.

## Reproducir el ensayo funcional

Usa una VM desechable nueva sin esas dependencias, con sesión gráfica iniciada y Gatekeeper activado. Descarga y extrae el ZIP. Copia `scripts/validate-macos-vm.py` desde el código fuente y ejecuta:

```sh
PYTHONDONTWRITEBYTECODE=1 \
  './Instalar Agentic Studio.app/Contents/Resources/Payload/Agentic Studio.app/Contents/Resources/python/bin/python3' \
  -B validate-macos-vm.py \
  --installer './Instalar Agentic Studio.app' \
  --report ./vm-report.json
```

La prueba rechaza un Mac físico o un huésped con dependencias detectadas. Necesita un usuario sin datos previos de Agentic Studio. No elimina datos existentes ni invoca la parada global de motores. Esta prueba por CLI se separa de la evaluación de distribución/cuarentena; no sustituye esa evaluación.

No se verificaron en la VM un consentimiento OAuth con una cuenta real, inferencia con modelos locales, macOS 12 ni todos los dispositivos iOS. El cliente iOS permanece en 0.5.0 y no cambia en esta versión.
