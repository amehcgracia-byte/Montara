# PUENTE JÚPITER → URANO · Libro de integraciones pequeñas

Actualizado el **05-11-2026** por laboratorio FER. Estado **registrado en el momento de escribir**, puede variar: leer GitHub Actions y PR antes de fusionar. **Ninguna de estas PR ha sido fusionada por FER**, ni se ha desplegado en JM/FER VM. FUENTES: [matriz de triaje](PUENTE_JUPITER_URANO_INTEGRATION_TRIAGE_2026-11-05.md), [issue de coordinación #34](https://github.com/amehcgracia-byte/Montara/issues/34), [issue #56](https://github.com/amehcgracia-byte/Montara/issues/56), [colaboración](../../docs/COLLABORATION.md).

## 1. [Montara PR #79](https://github.com/amehcgracia-byte/Montara/pull/79) · Windows discovery desde 0.66

- Rama `fernando/integrate-windows-discovery-066`, base `bec8f85b`, HEAD `e2dacec`. **Draft**, mergeable técnicamente, sin merge.
- Diferencial único: `companion/companion.py` (despacho solo Windows y rechazo de symlinks/junctions), `companion/windows_support.py`, `tests/test_companion_windows_support.py` y workflow dedicado.
- CI de revisión: Windows discovery **5/5 PASS** + compilación; [run 42089713726](https://github.com/amehcgracia-byte/Montara/actions/runs/42089713726); E2E Linux [run 42089713664](https://github.com/amehcgracia-byte/Montara/actions/runs/42089713664) **SUCCESS** (Stage, Push, Mix, Session, contenedor).
- **No confundir** CI y contrato con prueba física completa: quedan aceptación del código integrado con selector nativo/USB/OneDrive en Windows real, revisión de capturas CI E2E y revisión JM de producto, según alcance y gate de PR. No exige rescatar la rama FER completa.

## 2. [Montara PR #80](https://github.com/amehcgracia-byte/Montara/pull/80) · U3C originales

- Rama `fernando/integrate-u3c-video-consent-066`, basada en `main` 0.66 `bec8f85b`, HEAD `08a3f40` al registrar.
- Web no sube originales de vídeo sin decisión explícita cuando Companion falta/falla; conserva opción **manual solo experimental** y rutas de audio.
- CI focal [run 42095383014](https://github.com/amehcgracia-byte/Montara/actions/runs/42095383014) PASS 12 casos simulados.
- Primera ejecución E2E [42092808118](https://github.com/amehcgracia-byte/Montara/actions/runs/42092808118): Stage, Mix, Session, contenedor OK; **Push falló** por timeout de 120 s tras evitar subida original sin Companion. Hipótesis causal: test de Push usa deliberadamente importación sin Companion y no aceptaba el nuevo `window.confirm`.
- Corrección `08a3f40`: **solo el test** `tests/e2e_journey.py` acepta la subida experimental con verificación del contenido de la confirmación; el código de producto sigue requiriendo consentimiento. Segunda ejecución [42095382907](https://github.com/amehcgracia-byte/Montara/actions/runs/42095382907) **en progreso al registrar**, no declarar PASS E2E hasta resultado.
- Protección U3C es **frontend**, no control de backend / tenencia SaaS. No fusionar si falla revalidación ni interpretar esto como cierre URANO multiusuario.

## 3. [zucker_videos PR #59](https://github.com/amehcgracia-byte/zucker_videos/pull/59) · Calidad y duración FFmpeg

- Rama `fernando/fix-shot-quality-duration-066`, desde `claude/recover-montara-engine` (descendiente del pin efectivo Montara 0.66 `bfb964c3`). **Draft**, no cambia pins.
- Solicitud no resuelta según respuesta de Chema en issue #56: la puntuación de escenas usa proxy cuando existe, pero `_extract_quality_frames` no tenía `-t`. Corregido añadiendo duración de salida solo si finita y positiva.
- **Hallazgo adicional durante el review:** caché de calidad anterior identificaba archivo, no duración. Una extracción acotada no debe heredar scores anteriores de otra ventana; ahora `sampling_window_sec` forma parte del fingerprint de cache. Produce una nueva clave y puede recalcular una vez las puntuaciones; conserva caché para llamadas idénticas posteriores.
- Dos pruebas focales: contrato de `-t` y fallback sin duración; dos duraciones del mismo medio no comparten cache y la segunda visita a la misma ventana sí la reutiliza. **No afirmar PASS** hasta CI del editor.
- Gates: tests de motor, regresión con vídeo real/ventanas VFR o B-frames, comprobar que no cambia selección de planos por error y coordinación JM. No fusionar automáticamente.

## 4. Decisión de secuencia

1. Cerrar gates #79 (especialmente aceptación real Windows y revisión de artefactos) y #80 (E2E completo). Cada PR independiente.
2. Cuando estén aprobadas: merge controlado a `main` actual, verificar pin y rollback por PR; **no** mezclar Windows y política upload.
3. Editor #59 está separado y solo se considera para el motor tras sus pruebas y revisión de fotogramas/puntuaciones.
4. Próxima mejora a revisar, pero sin desarrollarla aún: identidad original/proxy/receta `FOCUS_A_C`; comprobar diferencial respecto de Stage local export del motor 0.66.
5. Posteriormente URANO local-first con continuidad real mismo ordenador, sin inventar esquema de proyecto o SQLite por inercia.

**Regla transversal:** si un gate no está verde, se investiga el error y no se da el paso por aprobado. No confundir tests simulados con E2E real, ni un CI verde con aceptación física/visual.


## 5. Seguimiento adicional · 05-11 · pruebas y corrección de caché

- **#79:** E2E Linux run `42089713664` SUCCESS, Windows discovery run `42089713726` SUCCESS; aún falta aceptación física del selector/USB en Windows y revisión de artefactos/capturas.
- **#80:** en reejecución `42095382907`, **Push E2E PASS** tras añadir una aprobación explícita y verificable en el test Playwright; Session y contenedor privado también PASS, Stage/Mix aún en marcha en la revisión. No declarar CI completo antes de concluir.
- **Editor #59:** primer Fast run `42096222899` registró **23 fallos** (1342 aprobados). La mayoría estaban en áreas API/360 históricamente problemáticas, pero **uno atribuible al parche**: `test_audit_performance.py::test_quality_shared_across_projects_and_retimed` dejó de reconocer el key anterior de cache para duración desconocida. Se corrigió en commit `a953719`: conservar clave anterior para extracción sin duración limitada, añadir dimensión de duración únicamente cuando se aplica `-t`. Nueva ejecución de Actions iniciada `42097202010`; no afirmar que está verde. La comparación formal contra baseline sigue siendo el gate si Fast continúa con fallos.
- Política de integración: cambios identificados por test y fuente exacta; no prometer compatibilidad visual ni equivalencia de resultados solo porque una prueba de comando esté verde.

## 6. Aceptación usuario Windows y cierre de CI U3C

- FER ejecutó prueba física del helper de Windows tomado **exactamente** del SHA de PR #79 `e2dacec`, con Python 3.11.9: `WINDOWS=True`, `ROOTS_DETECTED=10`, `ROOTS_EXISTING=5`, `DRIVES_DETECTED=1`, helper reparse presente, `SELECTOR_OK=True`, `CANCEL_OK=True`. **Sin USB externo** y sin prueba física HTTP completo de originales; no declarar certificación del paquete. Evidencia comunicada por el usuario y registrada en [comentario PR #79](https://github.com/amehcgracia-byte/Montara/pull/79#issuecomment-6667761761).
- PR #80, HEAD `08a3f40`: [E2E Linux 42095382907](https://github.com/amehcgracia-byte/Montara/actions/runs/42095382907) y [U3C consent 42095383014](https://github.com/amehcgracia-byte/Montara/actions/runs/42095383014) **SUCCESS** al comprobar tras la prueba física. La primera regresión Push se resolvió con aceptación explícita del diálogo en su entorno CI. Pendiente gate de capturas/revisión de diff e integración; no se ha realizado merge.
- Editor #59 continúa con nueva ejecución del motor `42097202010` sin resultado final aún al registrar. No confundir la corrección del key de caché con una aceptación de todos los tests.


## 7. INTEGRACIÓN EN MAIN CONFIRMADA · 05-11-2026

**Se completaron dos merges separados en GitHub, SIN despliegue en VM:**

1. [Montara #79](https://github.com/amehcgracia-byte/Montara/pull/79): **MERGED** por squash `446dae8697f33290d113bcc57b2dd6bd7de63749`, de `e2dacec`. CI Windows 5/5 + compilación PASS; E2E Linux 5 jobs PASS; aceptación del selector real Windows Python 3.11.9 PASS; inspección manual de screenshots Push/3 fotogramas decodificados del artefacto de GitHub. **Alcance:** descubrimiento/selector Windows, NO Companion Windows listo para distribución; no USB real, no FFmpeg empaquetado/legal.
2. [Montara #80](https://github.com/amehcgracia-byte/Montara/pull/80): **MERGED** por squash `0db9f753a3c57c534f7578f12efac0ea310158c7`, de `08a3f40`. CI U3C 12 casos PASS + E2E Linux 5 jobs PASS; inspección manual screenshots Stage y Push y fotogramas MP4 decodificados. Protege frontend ante subida involuntaria de originales vídeo, conserva aprobación manual **solo experimental**. No sustituye autenticación/autorización del servidor en URANO.
3. Verificación de `main`: HEAD `0db9f753a3c57c534f7578f12efac0ea310158c7`; comparación con anterior `bec8f85b`: **2 commits ahead, 0 behind**; 8 ficheros: dos workflows, `companion/companion.py`, `companion/windows_support.py`, `tests/e2e_journey.py`, dos tests y `web/montara.js`. **Ningún fichero de submódulo** `engine/` ni `mixer/` aparece en comparación. No se ha actualizado ningún servicio de JM ni FER.
4. [Editor PR #59](https://github.com/amehcgracia-byte/zucker_videos/pull/59) sigue **DRAFT NO MERGED**; última CI `42097202010` concluyó `failure`, 22 fallos Fast restantes (1343 PASS). Se corrigió nuestro fallo de clave cache legacy (23→22); no se ha demostrado aún contra ejecución baseline que los otros 22 coincidan, ni inspeccionado paridad visual con vídeo real. **No mover pin de Montara**.

**Siguiente trabajo:** revisión focalizada de FOCUS_A_C / vinculación original→proxy→receta respecto a main ahora actualizado, o continuación de validación Editor #59; evitar nuevos experimentos redundantes.

## 8. PR #81 — FFmpeg stdout/stderr deadlock Windows · MERGED

**Hallazgo FER 05-11-2026:** Windows 3 s synthetic, companion 0.6.5 sin fix en puerto 47821: `health=true`, `locate=true`, pero `/proxies` no acabó (`working` 0.973333). La misma causa del laboratorio JÚPITER W3D: `stdout=PIPE,stderr=PIPE` leídos secuencialmente. La corrección W3E estaba en rama experimental pero no llegó a la PR #79.

**[PR Montara #81](https://github.com/amehcgracia-byte/Montara/pull/81): MERGED** con squash `7decf8e5a5b45497ae2b92c0355eb7708e434c7f`. Solo tres ficheros: `companion/companion.py` (merge stderr a stdout), `tests/test_companion_proxy_pipe.py` (regresión de saturación), workflow Windows. HEAD main actualizado a `7decf8e5a5b45497ae2b92c0355eb7708e434c7f`; 1 commit sobre `0db9f75`, sin modificar pines Engine/Mixer.

Gates: [Windows CI 42102443407](https://github.com/amehcgracia-byte/Montara/actions/runs/42102443407) SUCCESS; [Linux E2E 42102441945](https://github.com/amehcgracia-byte/Montara/actions/runs/42102441945) SUCCESS. Prueba física FER (comentario [#81](https://github.com/amehcgracia-byte/Montara/pull/81#issuecomment-6668550362)): con el nuevo código `locate=true`, `proxy_status=ready`, HTTP mp4, 1.924.300 bytes original / 460.393 bytes proxy (≈24 %), descarga válida, original inalterado, sin subida cloud. Script reporta intento de limpieza de directorio temporal; no se verificó desaparición física del directorio ni se probó navegador drag & drop real.

**Estado PC:** Companion 0.6.2 W3L antiguo fue cerrado y el puerto 47820 quedó libre. Intento de renombrar carpeta `Montara-W3L-Build` dio `Acceso denegado` pese a permitir crear/quitar un archivo temporal y sin procesos detectados bajo la carpeta. No modificar ACL ni reiniciar; el usuario tiene aplicaciones abiertas y desea aplazar limpieza. `Montara-Companion-Lab` y `MONTARA_PRUEBAS` permanecen sin borrar. **No se instaló, publicó ni desplegó Companion nuevo; distribución/legal FFmpeg pendiente.**

## 9. URANO #82 — contrato navegador ↔ Companion (DRAFT)

- Desde `main=7decf8e`, abierta [Montara PR #82](https://github.com/amehcgracia-byte/Montara/pull/82), HEAD `5fbc8195ec853a4af7bdadcf1a33c255ca2265c2`; **sin modificaciones en producto**, solo nuevo test Node de contrato y workflow CI.
- El test ejecuta los archivos **reales** `web/companion.js` y funciones de `web/montara.js` en un mismo contexto JS, con transporte `fetch`/`XHR` simulado. Construye `File` sintético, verifica cálculo de SHA-256 de los bordes, `/health → /locate → /proxies → /file`, recibo `.small.mp4` y envío de **proxy y no original**. Ensaya originales no localizados y fallo de proxy, en ambos casos sin subida silenciosa. Esta no es una simulación del código JS: el código frontend se ejecuta, pero **sí se simula el transporte HTTP**.
- [CI U3C para HEAD](https://github.com/amehcgracia-byte/Montara/actions/runs/42104715688) **SUCCESS** incluidas pruebas específicas y 12 escenarios previos; [E2E Linux](https://github.com/amehcgracia-byte/Montara/actions/runs/42104716079) todavía en ejecución en la última consulta de esta actualización.
- Queda pendiente prueba real navegador ↔ Companion ↔ web/backend con proxy, y trabajo en persistencia URANO. La #82 es DRAFT y NO MERGED. Usuario no necesita intervenir en su Windows ni reiniciar.

## 10. URANO — recuperación de proyecto, hallazgo U3C y PR #83

**Revisión de código main `7decf8e` (sin modificación de producción en esta fase):**

- `web/footage-memory.js` guarda `FileSystemFileHandle` de Chrome/Edge por máximo 14 días con validación de permiso/tamaño/`lastModified`; al reabrir devuelve el **File original**.
- `web/montara.js` `#restoreFiles` reconstruía `entry.small=true` del registro de subida proxy interrumpida aunque el `File` reabierto fuese el **original**, sin `path` servidor aún. La función `upload()` comprobaba `!entry.small` para exigir Companion/consentimiento: con Companion apagado esto podía saltarse la confirmación y subir el original de forma silenciosa.
- **[PR #83](https://github.com/amehcgracia-byte/Montara/pull/83)**, rama `fernando/fix-restored-original-consent-066`, HEAD `53574cddef778117318d80c46379dfbb3a79fd64`: draft. Ajusta solo el guard a que la excepción de proxy se aplique cuando `file.name` es el nombre derivado del original (`.small.mp4`) y `entry.small` procede del proxy. Añade 3 regresiones a suite U3C. [Test focalizado CI](https://github.com/amehcgracia-byte/Montara/actions/runs/42105224771) **SUCCESS**; E2E Linux `42105224431` seguía en marcha en última consulta. No confundir que la verificación de nombre sea validación criptográfica de bytes: aquí es protección de flujo frontend, no autenticación.
- [PR #82](https://github.com/amehcgracia-byte/Montara/pull/82) (test contrato browser–Companion, sin código producción): test focalizado CI **SUCCESS**, E2E Linux `42104716079` en marcha en última consulta. Ambas PR independientes, abiertas, sin fusionar al escribir este bloque.
- **Persistencia URANO aún incompleta:** `web/montara.js` conserva el proyecto en `sessionStorage['montara-open-edit']` dentro de una sesión de pestaña y reconstruye parte de fuentes desde `/project` y `/wizard/status`; `companion/companion.py` guarda `projects.json` con IDs→carpetas y crea `montara-project.json` con solo metadatos básicos/fuentes. Son **tres persistencias parciales que no equivalen a una receta local completa recuperable tras nueva sesión**, ni vinculan por sí mismas aislamiento multiusuario.
- **Siguiente gate:** cierre CI #82/#83, revisión e integración pieza a pieza; después diseñar prueba controlada de recuperación del mismo proyecto entre cierre/reinicio web+Companion usando los formatos existentes, sin inventar SQLite ni subir originales. No pedir reinicio Windows: FER tiene aplicaciones abiertas y W3L quedó aparcado sin desinstalar.

## 11. URANO U6 — topología preliminar y coordinador transversal

**Aclaración expresa del propietario:** la separación web / Companion / servidor fue un boceto inicial, no arquitectura aprobada. Puede necesitar redistribución inteligente mediante planificador central de tareas. No fijar el diseño antes de revisarlo.

Se publica [revisión U6](URANO_U6_EXECUTION_ORCHESTRATION_ARCHITECTURE_REVIEW_2026-11-05.md) en rama de laboratorio, commit `7d82ea6a9fce1f5a83485b2f003b10770e289a56`. Inventario inicial verificado: `web/montara.js` tiene coordinación de trabajo y status; `app.py` mixer jobs en memoria bajo lock; `companion/companion.py` proxies con hilos y VideoJobs; servidor privado 1 worker y estado global por persona, Vercel sandboxes por sesión en auditoría U4B. **No se encontró orquestación transversal** con selección por privacidad, CPU/GPU, tráfico y costes en los módulos inspeccionados (sin descartar estructuras en Engine o deploy no auditado).

Se comparan cuatro opciones: flujo rígido (no asumir definitivo), planificador lógico en backend existente (candidato a evaluar), cola/scheduler separado (evaluar cuando escala exija), y planificación predictiva/IA (prematura sin reglas/telemetría). Siguiente: inventario ampliado Stage/Push/Show/Engine + benchmarks ejecutores + propuesta de contrato de job duradero/propiedad antes de implementar. **No cambios de runtime ni migración de arquitectura.**

PR #82 y #83 siguen draft, test focalizado SUCCESS, E2E Linux aún en marcha al redactar. Windows FER no requiere ninguna intervención.
