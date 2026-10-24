# Cambios

Español · [English](CHANGELOG.en.md)


## 0.5.0 — Agentic Studio

- Nuevo nombre e icono en macOS, iPhone e iPad, con migración de datos y credenciales existentes.
- Proyectos editables con carpetas y permisos propios; eliminación recuperable.
- Interfaz móvil compartida con escritorio y selector de proyectos autorizados.
- Cambio secuencial de motores, descarga del modelo previo y parada global de recursos; cierre completo de LM Studio mediante control explícito.
- Memoria disponible estimada con desglose y presupuesto conservador para MoE.
- Corrección de la carga CPU/mmap de DeepSeek MoE sin repack y protocolo de herramientas JSON validado.
- Instalador con carpeta de destino, detección de modelos y asistente OAuth.
- Correcciones de seguridad AS-2026-01 a AS-2026-05: rutas y enlaces, negociación TLS, límites de conexiones, bootstrap local, permisos de base de datos y validación móvil. Detalle y pruebas en [las notas de seguridad](docs/releases/0.5.0-security.md).

Las funciones verificadas, las limitaciones y los requisitos de firma se describen en README y SECURITY. El número de versión no implica notarización ni distribución en App Store.
