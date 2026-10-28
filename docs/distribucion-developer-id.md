# Distribución macOS con Developer ID: plan y criterios de aceptación

Estado: propuesta para 0.5.2; **no implementada ni validada con certificados**. La versión existente sigue firmada ad hoc y sin notarizar. Las 13 comprobaciones funcionales documentadas en [clean-macos-vm.md](clean-macos-vm.md) son resultados anteriores en VM; no prueban aceptación de una descarga normal ni validan este plan. No modificar una instalación existente para hacer estas pruebas.

## Hallazgos en el código 0.5.2

- `scripts/package-installer.py` introduce Python y Codex después de construir la app, firma con `--deep --sign -`, copia la app en `Contents/Resources/Payload` y firma el instalador ad hoc. El ZIP contiene una app instaladora, no un archivo .pkg. Developer ID Installer solo sería necesario si se adopta un .pkg firmado.
- `native/Installer.swift` verifica la firma del payload, pero durante una actualización reescribe el Info.plist de la copia para conservar StudioWorkspace y StudioCredentialIdentity y la vuelve a firmar ad hoc. Esto invalida el resultado Developer ID y su ticket. Una actualización no debe modificar ni volver a firmar el bundle distribuido.
- El manifiesto de dependencias es un archivo de caché editable. Las comprobaciones SHA-256 deben contrastarse con los valores fijados en el código y con fuentes revisadas; un hash suministrado junto al archivo no autentica su procedencia por sí solo. Revisar también la extracción de tar: los nombres y destinos de enlaces simbólicos y duros deben quedar confinados, además de las rutas de los miembros.
- Un cambio de identidad de firma puede afectar el acceso a ítems antiguos del llavero, incluso conservando el nombre del servicio. Hay que comprobarlo con datos de prueba y prever reconexión OAuth si macOS deniega acceso; no exportar secretos para sortear la protección.

## Cambios necesarios antes de distribuir

1. Mantener la instalación y el rollback existentes, pero trasladar la configuración de migración fuera de ambos bundles firmados. Diseñar una ubicación por usuario, escritura atómica, permisos restrictivos, validación de rutas y resolución de conflictos entre instalaciones. Leer tanto la ubicación heredada como la identidad de credenciales; preservar también el acceso a volúmenes y sus marcadores. No borrar ni mover datos. Probar instalación limpia, actualización normal y legado con rutas personalizadas, fallo interrumpido y reversión. Hasta probar esta migración, no declarar lista la actualización firmada.
2. Tras completar todas las modificaciones del payload, inventariar **todos** los Mach-O reales, incluidas extensiones Python, librerías dinámicas, ejecutables auxiliares y Codex; inspeccionar arquitecturas, enlaces simbólicos y dependencias. Firmar de dentro hacia fuera explícitamente, con Developer ID Application, sello temporal y Hardened Runtime para ejecutables donde corresponda; firmar la app de producto y verificarla antes de copiarla. No usar `--deep` como estrategia de firma. Conservar permisos y enlaces en las copias. Determinar entitlements mínimos mediante pruebas reales: no activar indiscriminadamente excepciones de Hardened Runtime ni desactivar library validation sin evidencia.
3. Firmar explícitamente el instalador después de insertar el payload ya firmado y de terminar sus recursos. La ubicación del payload bajo Resources exige comprobar cómo lo trata codesign y el servicio de notarización. Verificar recursivamente tanto la app como todos los ejecutables anidados y confirmar identidad, Team ID, timestamp y runtime. Resolver cualquier incompatibilidad estructural antes de publicar; no modificar ningún recurso después de firmar.
4. Para ZIP: crear con `ditto`, enviar a notarizar el ZIP con el instalador dentro, esperar Accepted, descargar y revisar el log incluso con Accepted. Grapar el ticket al instalador .app, validar el ticket, y recrear el ZIP final desde la app grapada. Comprobar que el ZIP final extrae una copia idéntica y verificable; calcular y publicar SHA-256 **después** de recrearlo. No se grapa un ZIP. Mantener la guía fuera o añadirla al ZIP final antes del hash. Si se elige .dmg o .pkg, usar el flujo correspondiente para el contenedor final; un .pkg requiere Developer ID Installer.
5. Verificar la firma y el ticket del producto instalado tras la copia, además de los del instalador. El análisis de la firma no sustituye una prueba gráfica con cuarentena ni comprueba por sí solo que la migración funcione.

## Operaciones reservadas al titular autorizado

El titular o administrador autorizado debe confirmar la pertenencia al Apple Developer Program, obtener y proteger la identidad **Developer ID Application** y su clave privada, habilitar un perfil de notarización en el llavero o credenciales de App Store Connect API, y autorizar la firma y el envío a Apple. Una identidad Apple Development no sirve para esta distribución. No incorporar claves, contraseñas ni certificados exportados al repositorio. Para .pkg se requiere además **Developer ID Installer**. Usar Xcode compatible para `notarytool` y `stapler` en el Mac de compilación; el Mac de destino no necesita Xcode.

Una vez implementado el flujo de firma y generado el ZIP previo, en el Mac autorizado:

```sh
security find-identity -v -p codesigning
xcrun notarytool submit "RUTA/previo.zip" --keychain-profile "PERFIL" --wait
# Con el ID devuelto, también si el estado es Accepted:
xcrun notarytool log "ID-ENVIO" --keychain-profile "PERFIL" "notary-log.json"
xcrun stapler staple "RUTA/Instalar Agentic Studio.app"
xcrun stapler validate "RUTA/Instalar Agentic Studio.app"
codesign --verify --deep --strict --verbose=4 "RUTA/Instalar Agentic Studio.app"
codesign --display --verbose=4 "RUTA/Instalar Agentic Studio.app"
ditto -c -k --sequesterRsrc --keepParent "RUTA/Instalar Agentic Studio.app" "RUTA/final.zip"
shasum -a 256 "RUTA/final.zip"
```

No continuar si el envío no termina en Accepted, si hay errores de firma, o si el log revela problemas no resueltos. Conservar ID de envío, log, versión de herramientas, identidades públicas, Team ID, hash final y resultados; no guardar secretos. El código y los comandos aquí no ejecutan esa firma.

## Prueba de descarga normal: pendiente

Usar primero una VM limpia y después al menos un Mac físico compatible, con una cuenta de prueba y copia de seguridad. Registrar versión/build de macOS, arquitectura, política mostrada en Ajustes del Sistema > Privacidad y seguridad, red y URL de descarga. Seleccionar **App Store y desarrolladores identificados**, manteniendo Gatekeeper activo; no añadir excepciones, usar Abrir de todos modos, desactivar Gatekeeper ni borrar cuarentena.

1. Descargar el ZIP final desde la URL de distribución real con Safari. Anotar fecha y hash, y compararlo con el publicado por un canal confiable. Comprobar que `xattr -p com.apple.quarantine "RUTA/final.zip"` devuelve un valor. Si no existe, la prueba no demuestra el recorrido normal de descarga: investigar y repetir con un archivo nuevo.
2. Abrir el ZIP en Finder y comprobar el atributo de cuarentena en el instalador extraído. Si falta, registrar el resultado y repetir: no fabricarlo ni quitarlo para obtener una aceptación.
3. Abrir el instalador mediante doble clic normal en Finder. Registrar las ventanas y cualquier bloqueo, sin aplicar excepciones. Instalar en una carpeta de prueba y abrir la app instalada normalmente. Verificar inicio, backend, Python, Codex y ausencia de modificaciones de recursos; revisar la firma después del primer uso.
4. En paralelo recoger `xcrun stapler validate`, `codesign --verify --deep --strict --verbose=4` y, si está disponible, `syspolicy_check distribution` para el instalador y la app instalada. Anotar salidas y códigos. Las herramientas son diagnósticas y no reemplazan la apertura gráfica. Un ticket del payload puede estar disponible en línea; si se requiere funcionamiento offline, diseñar y probar expresamente el grapado apropiado para ambos bundles antes de su empaquetado final.
5. En otra cuenta o equipo con una instalación anterior y datos **ficticios**, guardar copia y hash de la base de datos con la app cerrada. Actualizar mediante el mismo ZIP descargado; confirmar contenido y hash antes de abrir la app, la ruta y el acceso a credenciales, arranque, firma y copia anterior. Confirmar que una app ajena en destino permanece intacta. Probar restauración ante fallo. No usar datos reales como única copia.

Registrar por separado la prueba **solo App Store**: esta política más restrictiva puede bloquear software Developer ID distribuido fuera de la tienda y no demuestra el resultado con desarrolladores identificados. El ensayo de 0.5.2 en VM usó esa política y bloqueó el instalador; la aceptación normal con desarrolladores identificados permanece pendiente. Repetir en macOS mínimo soportado y en versiones actuales que se anuncien, y registrar explícitamente cualquier combinación no probada.

Referencias de Apple: [Notarización](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [flujo personalizado](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow), [errores frecuentes](https://developer.apple.com/documentation/security/resolving-common-notarization-issues), [Developer ID](https://developer.apple.com/developer-id/).
