# STATUS — laboratorio de Chema (main · claude/* · codex/*)

Actualizado: 2026-10-30 · lo mantiene el equipo de Chema · 40 líneas como máximo, se sobrescribe.

## Referencias
- `main`: `1a11d6a` (PR #10, #11, #12, #15, #16, #17 y #6 integradas) · `engine`: `c89e779` · `mixer`: `c7a46a6`
- Rama de Fer revisada hasta: `1a5f3bd` (2026-10-30)
- VM de pruebas: Ubuntu 24.04, 4 vCPU / 16 GB; `jm` en `127.0.0.1:8101`, `fer` en `127.0.0.1:8102`

## Abierto
| Pieza | PR | Estado |
|---|---|---|
| Laboratorio de dos usuarios en VM (scripts `deploy/vm/`, usuario de acceso configurable) | #10 | `validado-lab`: instalaciones de `jm` y `fer` activas; acceso con usuario propio comprobado por `curl` (200 con credenciales, 401 sin ellas) |
| Footage: quitar archivos con ×, también durante la subida; aviso de audio largo; audio y vídeo suben en paralelo | #11 | `validado-lab`: Playwright en servidor local; pytest de subida/acceso, 21 pasan; **sin E2E** |
| Protocolo de colaboración, STATUS, inventario, avisos | esta PR | `implementado` |
| Benchmarks históricos (Codex) | #6 | sin revisar en esta ronda |

## Siguiente
1. **Fase 0 — continuar mientras se sube:** configurar cámaras, nombre y logo con archivos aún subiendo; registrar el proyecto y arrancar solo al terminar. Solo Montara, sin motor.
2. Fases 1–2 (proxy desde el navegador primero; subir solo los GOP usados) **con el laboratorio de Fer**: ver la familia F1 del inventario.
3. «Jam entero → una canción»: detectar canciones, sincronizar los vídeos, proponer la canción, mezclar esa primero y el resto después.

## Pendiente
- E2E Linux de #11 y #10.
- README de #10: dice 2 vCPU; la VM es de 4 vCPU / 16 GB.
- Cambiar las contraseñas web de la VM, que pasaron por chat. Cerrar sesión de `gh` en el Cloud Shell de amehc.
- Auditoría de `INVENTORY-FER.md`: hecha la familia F1; quedan F2–F8.

## Decisiones tomadas
- `main` lo decide Chema; el laboratorio de Fernando informa de riesgos, sin bloquear (30-10-2026).
- F4 (reproyección 360 bilineal con material real): la investiga el laboratorio de Fernando.
- Aviso: el historial de `main` referencia un commit del motor que ya no existe (`bf5d0066`). Para actualizar, usar `git fetch --no-recurse-submodules`; el pin actual (`c89e779`) está intacto.
- Montara, zucker_videos y ZuckerMixer son repositorios **públicos** (comprobado por API el 30-10-2026; corrige lo que dijo antes la PR #10).
