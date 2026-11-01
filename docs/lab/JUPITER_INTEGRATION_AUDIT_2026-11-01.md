# JÚPITER — Auditoría selectiva de integración (2026-11-01)

## Punto de partida
Fernando HEAD `1d56102`: merge de main `f91dbac`, 46/46 tests específicos y comprobación sintaxis Python/JS; submódulos `engine=ff9baf45`, `mixer=2c0c07cd`. **No validación E2E.** Acuerdo `main:docs/COLLABORATION.md`: ramas cortas desde main; PR por pieza; Chema decide integración, nunca merge global de rama experimental.

## A. Avances relevantes verificados en main
- `local_media/proxies.py`: caché/single-flight POSIX ya incorporada parcialmente (PR #8 según inventario).
- `mixer_adapter/source_access.py`: validación de rutas servidor y uploads completos existente; **no** tiene propiedad por usuario (declara limitación).
- `deploy/vm/run_history.py`: **ya existe** `shots(folder)`, con duraciones, recuento de planos y proporción 360 por cámara. El estado anterior que pedía añadir cámara estaba desactualizado.
- `docs/lab/STATUS-JM.md` 1 nov: Companion Mac con mezcla local medida, y la ruta de puntuación de planos sobre proxies (PR #59). Evitar duplicar trabajos del otro laboratorio.

## B. Clasificación de inventario
| Pieza | Estado | Decisión |
|---|---|---|
| F1.1, F5 proxies+caché | Integración parcial ya descrita en inventario | Auditar deltas exactos solo si hay regresión |
| F1.6 mixer source_access | Ya en main | No PR nueva; propiedad multiusuario pendiente de diseño |
| F1.2 preview HTTP y F1.3 bridge | Prototipos, no integrados ni probados E2E | No integrar tal cual |
| F1.4 carpeta navegador | Diseño validado manualmente en Chromium | Candidato de arquitectura, no PR inmediata |
| F1.5 + F2 SATURNO GOP | 39.8% bytes menos controlados, no WAN | Fase 2; requiere flujo/plan real |
| F2.5 passthrough 360 | Evidencia de control de frames | Candidato test regresión engine tras evaluación de Chema |
| F3 cgroup | No afecta hoy VM no limitada bajo host | Condicional a contenedores |
| F4 360 v360 | Bench real 38.46% solo microbenchmark | No extrapolar a native_remap |
| EX-05/06 OpenCV native_remap | 17.59% menos mapa+remap 1080p CPU, calidad relativa alta, revisión JPEG favorable; sin E2E | Candidato de revisión del motor, no cambio global |
| F7 ffprobe cadencia | Pequeño coste | Baja prioridad |
| FOCUS SYNC | Error sintético de global-vs-consenso con guard candidato | Revisar en motor con regresión antes de PR |

## C. Selección de próxima PR
**No anunciar una PR lista sin diff y pruebas de la pieza.** Candidato más acotado: regresión del selector `web/montara.js` hallada en Fernando (commit `3bbee90`), pero primero comprobar si el bug persiste en main. Si ya está resuelto, no abrir PR. Alternativa de muy bajo riesgo: PR únicamente de pruebas/documentación o metadatos de rendimiento solo cuando se detecte una carencia concreta; no duplicar `shots()`.

## D. Riesgos
- Rama experimental con centenares de commits y prototipos: PR pequeñas desde main.
- Motor y mixer en subrepositorios: no introducir cambios por el puntero del submódulo sin la PR propia.
- Tests parciales no certifican producto; E2E Linux y revisión visual de capturas necesarias.
- No exponer rutas, credenciales ni logs de usuarios en repos públicos.

## E. Siguiente paso
1. Comparar exactamente selector de cámaras `main` vs variante Fernando y determinar si hay un defecto no resuelto.
2. Si el defecto ya está corregido, cerrar candidato y pasar a EX-06 opt-in vía Chema o F2.5 test regresión.
3. Crear una **sola PR corta desde main** con evidencia y controles pertinentes cuando haya diferencia funcional probada.
