# STATUS — laboratorio de Chema (main · claude/* · codex/*)

Actualizado: 2026-10-30 · lo mantiene el equipo de Chema · 40 líneas como máximo, se sobrescribe.

## Referencias
- `main`: `b509097` · `engine`: `c89e779` · `mixer`: `c7a46a6`
- Rama de Fer revisada hasta: `f77ba0e` (inventario F1–F8 en primera pasada)
- VM de pruebas: Ubuntu 24.04, 4 vCPU / 16 GB; `jm` en `127.0.0.1:8101`, `fer` en `127.0.0.1:8102`

## Integrado hoy en `main` (pruebas completas de GitHub Actions en verde: Stage, Push, Mix, Session, contenedor)
| Pieza | PR |
|---|---|
| Laboratorio de dos usuarios en VM; usuario de acceso configurable; la actualización reinicia el servicio | #10, #16 |
| Footage: quitar archivos con ×, también durante la subida; aviso de audio largo; audio y vídeo suben en paralelo | #11 |
| Validación de pistas del mezclador (laboratorio de Fer, F1.6) | #15 |
| Protocolo, STATUS, inventario y aviso automático por issues (#13 y #14) | #12, #17, #18 |
| Benchmarks históricos (Codex) | #6 |

## Siguiente
1. **Medir la base:** tiempos del flujo actual desde que se arrastran los archivos hasta el vídeo final.
2. **Fase 0, continuar mientras se sube:** configurar cámaras, nombre y logo durante la subida; el proyecto arranca solo cuando termina.
3. **Fases 1–2:** versión pequeña desde el navegador primero; después subir solo los GOP usados (F1.4, F1.5, F2). El motor necesita poder cambiar un proxy por su original (F8 FOCUS_A_C): PR en `zucker_videos`.
4. **«Jam entero → una canción»:** detectar canciones, sincronizar los vídeos, proponer la canción, mezclar esa primero y el resto después.

## Pendiente
- Actualizar la VM de `jm` a `main` con `git fetch --no-recurse-submodules` (hay un commit histórico del motor, `bf5d0066`, que ya no existe en `zucker_videos`).
- Cambiar las contraseñas web de la VM, que pasaron por chat. Cerrar sesión de `gh` en el Cloud Shell de amehc.
- Revisar las capturas del E2E de Actions; desde la sesión de Claude no se pueden descargar los artefactos.

## Decisiones tomadas
- `main` lo decide Chema; el laboratorio de Fernando informa de riesgos, sin bloquear (30-10-2026).
- F4 (reproyección 360 bilineal con material real): la investiga el laboratorio de Fernando.
- Montara, zucker_videos y ZuckerMixer son repositorios **públicos** (comprobado por API el 30-10-2026).
- Vercel no aloja el servidor de render. Las pruebas públicas temporales se hacen con un túnel de Cloudflare hacia la VM.
