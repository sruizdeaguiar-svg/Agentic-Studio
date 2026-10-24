# Agentic Studio para iPhone e iPad

Español · [English](README-en.md)


Cliente universal para iOS/iPadOS 17 o posterior. El Mac ejecuta modelos y herramientas; el dispositivo muestra conversaciones, proyectos autorizados, archivos, revisiones, actividad y parámetros, sin descargar pesos.

Abre `AgenticMobile.xcodeproj` en Xcode, selecciona el target AgenticMobile y configura tu propio equipo de firma. El proyecto público tiene el equipo vacío y no contiene certificados ni perfiles personales. `../build-ios.sh` genera el paquete de simulador y la IPA ARM64 **sin firmar**. Esta IPA necesita firma válida para instalarse en un dispositivo físico.

En el Mac abre Conexiones → Red local, selecciona los proyectos autorizados y muestra su QR. En el dispositivo pulsa **Escanear QR del Mac**. El código caduca a los cinco minutos y es de un uso; la app verifica la huella TLS. También admite pegar el enlace. Cámara y red local se solicitan únicamente cuando son necesarias. No requiere acceso a Fotos ni micrófono.

Los permisos y herramientas se aplican en el backend del Mac. El móvil no administra OAuth, motores, carpetas ni permisos globales. Al cambiar los permisos se revoca la vinculación; detener la pasarela revoca todos sus clientes.

La interfaz web se recibe del Mac. Las pruebas automáticas cubren tres tamaños de pantalla, permisos, vinculación, HTTPS y revocación. La compilación no sustituye una prueba física del dispositivo. La versión 0.5.0 se ha instalado en un iPad autorizado y su nombre e icono han sido confirmados por el usuario; el escaneo y la respuesta se verificaron físicamente en la versión anterior.

No compartas la pantalla del iPad mediante Device Hub mientras utilizas la cámara. Esa conexión puede reservar sus recursos multimedia. Consulta las limitaciones de Device Hub en la documentación de Apple si aparece vídeo negro. Las pruebas de esta app no requieren abrir Device Hub.
