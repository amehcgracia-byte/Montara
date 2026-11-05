# URANO — U0 · alcance y preguntas de arquitectura (arranque sin cambios productivos)

**Fecha:** 2026-11-05. **Estado:** propuesta de investigación, **no** diseño aprobado. Handoff de origen: [JÚPITER W3S](JUPITER_WINDOWS_W3S_TECHNICAL_HANDOFF_2026-11-05.md). Las decisiones de JM/Chema tienen precedencia; esta nota no las sustituye.

## Hechos ya validados (acotados)

- Companion ejecuta en localhost una API para localizar originales, crear proxies H.264 SDR y entregar archivos. Tests Windows/CI y aceptación visual de bandeja resumidos en W3S.
- FFmpeg es un ejecutable externo invocado desde Companion. La dependencia quedó empaquetada en un **laboratorio CI temporal**, no en una release.
- La rama de trabajo `fernando/companion-windows-w1` y PR #74 permanecen experimentales, no fusionadas. No asumir instalación o soporte para clientes comerciales.
- Legal de distribución se ha aplazado por decisión del usuario, manteniendo explícitamente el bloqueo de **publicación externa**.

## Hipótesis de arquitectura a evaluar, no hechos cerrados

1. **Web:** interfaz, cuentas, gestión de proyectos, edición de recetas/timeline y selección del modo de trabajo. Definir qué elementos se persisten y dónde.
2. **Companion local:** acceso a archivos originales autorizados por el usuario, proxy local, análisis de vídeo y render/transfer cuando convenga. No afirmar acceso permanente a carpetas ni privilegios automáticos.
3. **Cloud/Stage:** tareas remotas bajo límites de CPU/RAM/almacenamiento; decidir disparadores, autenticación, cola, costes, almacenamiento temporal, política de borrado, caché y escalado.
4. **Modos de entrada:** archivos locales, YouTube, reels y modos mixtos. Confirmar capacidades y derechos/permisos de uso; no fijar flujo funcional sin auditoría del código y UX.
5. **Seguridad:** orígenes CORS ya tienen filtros iniciales en Companion, pero no equivalen a autenticación/consentimiento; diseñar control real de acceso a API local, CSRF/DNS rebinding, sesiones, autorización por carpeta y protección de rutas.
6. **Fiabilidad:** ciclo de vida de jobs, límites de concurrencia, render recuperable, idempotencia, apagado graceful y estrategia de actualizaciones firmadas.

## Decisiones que URANO debe responder

| Pregunta | Por qué importa | Cómo contrastarla |
|---|---|---|
| ¿Qué trabajos quedan locales y cuáles pasan a nube? | Privacidad, costes, CPU y velocidades de subida | Benchmark de 3 tipos de vídeo y matriz de costes |
| ¿Dónde vive el proyecto editable? | Recuperación y colaboración | Revisión del modelo de proyectos y persistencia |
| ¿Cómo se identifican originales y proxies tras reinicio? | No perder enlaces y permitir medios externos | Pruebas de rutas y fingerprints |
| ¿Cómo se autentica el navegador con Companion? | Evitar acceso local no autorizado | Threat model de API y prueba aislada |
| ¿Cómo interactúan YouTube/reels con las rutas locales? | Derechos, experiencia de usuario, ancho de banda | Inspección de entradas y flujo real |
| ¿Qué debe validar JM antes de integrar PR #74? | Evitar regresiones de producción | Checklist, revisión de cambios y CI |

## Prioridad U0 (siguiente sesión técnica)

Hacer **inventario del frontend, endpoints, flujos de exportación, proyecto y despliegue** sobre el código real del repositorio, separando **hechos**, **suposiciones** y **decisiones abiertas**. No refactorizar ni añadir servicios antes de completar ese mapa. Mantener W3R como requisito previo a distribución pública, no como freno a la investigación.

**No requiere acciones del usuario ahora; no usar su Windows para depurar.**
