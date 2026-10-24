# Seguridad de Agentic Studio

Español · [English](SECURITY.en.md)


La versión 0.5.0 incorpora una revisión de seguridad previa a publicación y pruebas de regresión. Los hallazgos, correcciones y límites están en [las notas de seguridad de la versión](docs/releases/0.5.0-security.md).

Para informar de un fallo, utiliza el canal privado de reporte de vulnerabilidades del repositorio cuando esté habilitado. No publiques tokens, conversaciones, documentos del proyecto, claves de la pasarela ni credenciales OAuth en una incidencia pública. Si no hay canal privado disponible, abre una incidencia sin detalles de explotación ni información sensible para acordar un canal.

Usa permisos de revisión para las herramientas nuevas y autoriza únicamente las carpetas y orígenes necesarios. Un MCP remoto y un proveedor de inferencia externo reciben los datos que se envían a sus herramientas o modelos. Detener la pasarela revoca las sesiones móviles; no expongas sus puertos a Internet.
