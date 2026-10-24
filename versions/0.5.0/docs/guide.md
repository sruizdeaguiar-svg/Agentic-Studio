# Guía de Agentic Studio

Español · [English](en/guide.md)

## Primer inicio

El instalador permite elegir destino y acceso del Escritorio. Los datos se guardan por separado; una actualización conserva su ubicación. En Instalación y ajustes revisa las carpetas detectadas de modelos y configura OpenAI si lo necesitas. OAuth se completa en el navegador del titular de la cuenta; nunca pegues tokens en una conversación.

## Proyectos y agente

Crea un proyecto, selecciona su carpeta y define escritura y ejecución como denegadas, sujetas a revisión o permitidas. Modificar un proyecto cambia su alcance y revoca conexiones móviles afectadas. Eliminar un proyecto es recuperable y no elimina sus archivos externos.

En Conversación selecciona proveedor y modelo y activa el agente. El panel lateral muestra archivos y propuestas; examina el contenido y el comando antes de aprobar. El registro de actividad muestra herramientas, resultados y el texto de razonamiento que facilite el proveedor. Ese registro no demuestra que todas las afirmaciones del modelo sean correctas. Si falta la carpeta o el aislamiento, la acción se bloquea y necesita intervención del usuario.

## Modelos y memoria

En Motor selecciona un modelo compatible con el motor y revisa contexto, KV, batch, límites de memoria y opciones MoE. La carga de un modelo local inicia el servidor propio. Los cambios son secuenciales para descargar el anterior antes del siguiente. No se cierran motores ajenos automáticamente; el control explícito de LM Studio solicita su descarga, parada y cierre de aplicación.

Parar todos y liberar RAM detiene recursos controlados por la app, adaptadores y pasarela y cancela descargas. macOS administra la caché del sistema; la aplicación no promete recuperar toda la memoria ni cero swap. En MoE, pocos expertos activos no implican que solo esos pesos deban residir en RAM. Los valores de disponible son estimaciones.

En Modelos puedes buscar repositorios públicos de Hugging Face, revisar archivos, tamaño y destino, y aprobar su descarga. La revisión y los hashes se verifican antes de publicar el archivo final. No se ejecuta código Python descargado del repositorio.

## MCP y navegador

Configúralos por proyecto. Revisa el comando o endpoint antes de conectar MCP; las herramientas nuevas están denegadas hasta guardar sus permisos. Para HTTP/OAuth revisa el recurso, issuer y scopes antes de autorizar. Una herramienta remota puede tener efectos externos aunque su descripción diga que solo lee.

El navegador del agente usa una sesión efímera y orígenes explícitos. Lectura, clic y escritura tienen permisos; no admite carga de archivos, contraseñas ni acceso al puente nativo de la app.

## iPhone/iPad y cierre

Autoriza los proyectos en Conexiones → Red local y escanea el QR desde el dispositivo. Cada cliente tiene su proyecto activo y solo puede abrir los autorizados. Revisa sus propuestas igual que en el Mac. Desactivar la pasarela revoca todos los clientes.

Usa Cerrar para terminar la app y sus procesos propios. Las conversaciones persisten; los servidores y archivos externos no se eliminan al cerrar.

## Versiones y seguridad

`main` contiene la versión actual; las anteriores se conservan en [historial-versiones](https://github.com/sruizdeaguiar-svg/Agentic-Studio/tree/historial-versiones). Consulta [los cambios actuales](../CHANGELOG.md) y [seguridad](../SECURITY.md) antes de actualizar.
