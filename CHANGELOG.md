# Cambios

Español · [English](CHANGELOG.en.md)

## 0.5.1 — Portabilidad del instalador macOS

- Preserva permisos de ejecución de la app, Python y Codex durante el empaquetado.
- Compila app e instalador con destino mínimo macOS 12 explícito, en lugar de heredar macOS 27 del equipo de compilación.
- La app usa Application Support del usuario y no depende del checkout.
- Prefiere el cliente Codex incluido y admite motores opcionales ausentes o en otras ubicaciones.
- Añade prueba nativa reproducible con usuario vacío y bloqueo de datos reales, motores, ChatGPT, Xcode y Python del anfitrión.
- 73 pruebas de regresión aprobadas. Consulta [portabilidad](docs/portability.md) para límites y reproducción. Las correcciones de seguridad anteriores se mantienen.

El cliente iOS permanece en 0.5.0. Las versiones anteriores están en la rama `historial-versiones` y sus etiquetas. El paquete no está notarizado; no se afirma una prueba real en un sistema recién instalado ni en macOS 12.
