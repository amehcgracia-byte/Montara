# Montara — colaboración entre laboratorios

Acordado el 30-10-2026 por José Manuel (Chema) y Fernando. Esta página es la norma; `docs/lab/` es el estado.

## Responsables principales (no exclusivos)

| Equipo de Chema (`main`, `claude/*`, `codex/*`) | Equipo de Fernando (`fernando/continuacion-montara`) |
|---|---|
| Desarrollo e integración del producto | Investigación y optimización de rendimiento |
| Stage, Show, Mixer y experiencia de usuario | Proxies, cachés, acceso a archivos locales y transferencia selectiva |
| Flujo de subida y continuidad de la edición durante las transferencias | Arquitectura híbrida local/servidor/GPU y futuro companion Windows/macOS |
| Validación E2E y decisión de qué entra en `main` | Benchmarks reproducibles, compatibilidad y documentación de resultados |

**Área compartida:** subida y edición durante la transferencia. Antes de desarrollar en ella, leer la familia «Subida, proxies, acceso local y transferencia selectiva» de `docs/lab/INVENTORY-FER.md`.

Ambos equipos pueden investigar, proponer y revisar cualquier cosa. Una observación técnica no autoriza a modificar el otro laboratorio.

## Fuentes de verdad

- **Código y resultados:** ramas y PR de GitHub. Entire y las transcripciones de agentes no los sustituyen.
- **Estado:** `docs/lab/STATUS-JM.md` y `docs/lab/STATUS-FER.md`. Cada uno tiene 40 líneas como máximo y lo sobrescribe su propio laboratorio en cada hito.
- **Inventario:** `docs/lab/INVENTORY-FER.md`. Indexa los experimentos de Fernando por familias. Se audita una vez y después se mantiene de forma incremental.
- **Avisos:** el workflow `Lab digest` publica cada rango de commits nuevo de `main` y de `fernando/continuacion-montara` en un issue fijo por rama. Es determinista: no depende de que ningún agente se acuerde.

## Presupuesto de lectura para agentes

1. Empezar por esta página y los dos STATUS.
2. Después, `git log --oneline --no-merges <último-revisado>..origin/<rama>` y `git diff --stat` del mismo rango.
3. Los informes largos solo se abren al decidir sobre esa pieza.
4. Una revisión responde A–E en una pantalla como máximo:
   - **A.** novedades
   - **B.** duplicidades
   - **C.** reutilización
   - **D.** riesgos de integración
   - **E.** recomendaciones

   Si no hay nada, responde «sin cambios relevantes».

## Estados de madurez

`investigado` · `implementado` · `validado-lab: <comando exacto>` · `candidato` · `integrado: PR #n` · `validado-producción`.

Una funcionalidad del producto solo está «terminada» cuando `tests/e2e_journey.py` pasa en Linux y alguien ha mirado sus capturas (ver `CLAUDE.md`). Un benchmark útil sigue siéndolo sin E2E; simplemente no se presenta como funcionalidad.

## Git

- **Chema decide e integra en `main`** sin esperar autorización del otro laboratorio. Basta con informar: el issue «Lab digest · main» lista los commits, y el laboratorio de Fernando señala riesgos si los ve.
- Nadie modifica la rama `fernando/*` sin coordinarlo con Fernando.
- La integración se hace pieza a pieza, como en la PR #8: rama corta desde `main` y una PR por pieza. La rama experimental nunca se fusiona entera.
- Cada PR indica los commits de `engine/` y `mixer/` y las pruebas exactas que se ejecutaron.
- Un cambio de submódulo demuestra `git merge-base --is-ancestor <viejo> <nuevo>` o declara qué se pierde. Los cambios del motor pasan por `zucker_videos` (ver `CLAUDE.md`).
- Nada de `git push --force` para sincronizar.
- Solo se comparan resultados con el mismo motor, el mismo mezclador y el mismo tipo de máquina, con la salida de `deploy/vm/manifest.sh` adjunta.

## VM compartida

- Un usuario Linux por laboratorio. Los servicios escuchan solo en `127.0.0.1`.
- El trabajo pesado pasa por `montara-bench <experiment_id> <comando>`.
- Nadie toca el HOME ni los servicios del otro laboratorio.
- Cada acción de administrador (`sudo`) queda en una línea de `docs/lab/VM_LOG.md`, con quién la autorizó.

## Secretos

**Los repositorios Montara, zucker_videos y ZuckerMixer son públicos.** Todo lo que se sube, los issues y los logs de Actions los puede leer cualquiera.

- Nada de contraseñas, tokens, llaves, rutas privadas ni transcripciones de agentes en Git, issues o Entire.
- Una contraseña que ha pasado por un chat se cambia.
- El acceso a GitHub desde la VM usa una credencial limitada a este repositorio, no una llave personal.
