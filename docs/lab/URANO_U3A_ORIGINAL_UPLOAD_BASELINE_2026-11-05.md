# URANO U3A — prueba de caracterización de la subida heredada de originales

**Fecha:** 2026-11-05. **Estado: PASS de caracterización (comportamiento actual, NO objetivo comercial).**

## Decisión de diseño

Fernando establece que **Companion debe ser la vía obligatoria para procesar archivos de vídeo locales**, y que el fallback de subida de originales no se considera viable para el producto por costes de tráfico y almacenamiento. Antes de retirar el fallback, U3A captura de forma reproducible sus rutas y fallos actuales.

## Qué se ha implementado

- `tests/urano_u3a_upload_baseline.cjs` en `fernando/companion-windows-w1`, commit `bbe91e6`: ejecuta mediante Node `vm` las **funciones efectivas** `uploadSmall`, `upload` y `uploadInParts` extraídas sin modificar de `web/montara.js`.
- `.github/workflows/urano-u3a-upload-baseline.yml`, commit `90e0779`: Node 22 en Linux runner, trigger cuando cambian la prueba, `web/montara.js` o workflow.
- **Sin red real**: XMLHttpRequest, `sendResumableUpload` y Companion se sustituyen por dobles de prueba que registran nombre, ruta y tamaño enviados; no se leen vídeos reales. Se usa un objeto falso con tamaños numéricos 10/300 MiB.

## Escenarios y observación del código actual

| Escenario | Transferencia observada |
|---|---|
| Companion no disponible, vídeo 10 MiB | Original por `/montara/uploads` |
| Companion no disponible, vídeo 300 MiB | Original por `/montara/uploads` |
| Companion localiza `missing` de vídeo 10 MiB | Original por `/montara/uploads` |
| Companion localiza `missing` de vídeo 300 MiB | **Sin transferencia** (bloqueo específico >200 MiB) |
| Companion devuelve `null` en vídeo 300 MiB | Original por `/montara/uploads` |
| Error lanzado durante proxy (simulado FFmpeg) de vídeo 300 MiB | Original por `/montara/uploads` |
| Companion crea proxy válido | Solo proxy de 2 MiB por `/api/v1/wizard/upload` |

**Resultado:** CI [41940712720](https://github.com/amehcgracia-byte/Montara/actions/runs/41940712720) **completed/success**. Todos los casos de caracterización se ajustan a las expectativas actuales. Verde significa que la **línea base se reproduce**, NO que sea seguro subir originales ni que la política Companion-first esté implementada.

## Alcance

- Estas pruebas verifican exclusivamente el comportamiento aislado de esas funciones JavaScript de carga inicial de la web; no son E2E de navegador/servidor.
- No cubren todavía rutas separadas de Show, carga de audio Stage, fuentes de enlace Push, autorización/identidad backend, archivos reales ni tráfico de red real.
- El mock `sendResumableUpload` no verifica negociación de rangos, tiempos ni carga del servidor. No se afirma que el backend bloquee originales.
- PR #74 continúa draft; no se modifica `web/montara.js`, Companion, Engine/Mixer ni producción.

## Siguiente hito U3B

Proponer una **política de clasificación de contenidos** (vídeo original local frente a proxy/derivado/audio corto/imagen/voz/enlace externo), con guardas visibles en la interfaz y verificaciones de backend donde sea viable. Cuando estén aprobadas las excepciones, modificar las expectativas del test al nuevo comportamiento deseado (cero subidas de originales sin Companion), añadir pruebas de regresión de Show/Stage/Push y probar la implementación solo en rama experimental.

**Pendientes aparte:** distribución/licencia FFmpeg y modelo de identidad multiusuario URANO.
