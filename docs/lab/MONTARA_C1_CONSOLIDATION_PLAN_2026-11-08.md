# MONTARA · C1 — Auditoría de consolidación e integración selectiva

**Fecha:** 2026-11-08 · **Estado:** propuesta de integración, **no** implementación ni despliegue.
**Fuente de verdad revisada:** `main` SHA `765a34ceec33311cd520856d46fec15adfc6c0a1`.
**Rama de este informe:** `fernando/consolidacion-c1-roadmap-20261108`, creada **directamente de main**, no de ninguna pila URANO.
**Autoridad sobre main/servicios de Chema:** revisión y decisión humana; **prohibido merge automático o tocar las instancias compartidas**.

## 1. Resumen ejecutivo: qué hemos comprobado

- GitHub muestra **36 PR abiertas** en el momento de la consulta (incluye borradores históricos). No son 36 entregables pendientes: muchas son fases solapadas, laboratorios o PR encadenadas. El número no debe interpretarse como deuda de merge.
- U22 (#137), HEAD `2893cc44b309c08c0c76f9abf529fd5a6cac0d9b`, pasó [CI integrado 42531692743](https://github.com/amehcgracia-byte/Montara/actions/runs/42531692743): dos dueños, dos Docker Engine privados, Stage Ingest `done`, sus descriptores autorizados y dos MP4 locales **en un runner compartido**. **No** es arquitectura distribuida real ni Google productivo.
- `main` ya incluye `urano/project_catalog.py`, `tests/e2e_native_stage.py` y `companion/companion.py` (versión 0.6.10 al revisar código). **No** incluye `urano/container_worker_bridge.py`, `urano/google_oidc.py`, `urano/google_lab_app.py` ni `companion/urano_local_handoff.py`. El camino de producto no llega aún a la web real.
- Existen **DOS pilas nuevas independientes**: identidad/workers/Stage/Companion (#124–#129, #134–#137) y aceptación/métricas/preflight (#121, #130–#133). Sus bases distintas impiden recomendar un merge en bloque sin revisión.
- **Conflicto de merge confirmado** por GitHub para la PR Windows **[#74](https://github.com/amehcgracia-byte/Montara/pull/74)** contra `main`: `mergeable=false`, `mergeable_state=dirty`. Su modificación de `companion/companion.py` se solapa además con la de U21 [#136](https://github.com/amehcgracia-byte/Montara/pull/136). Este segundo solapamiento es **riesgo de integración manual**, no conflicto Git demostrado entre ambas ramas.
- Los `mergeable=true` de otras PR apiladas solo significan ausencia de conflictos en **su base actual**, no compatibilidad futura con `main` ni con la PR de Windows. #137 mostraba `mergeable_state=unstable` pese a CI propia U22 verde: comprobar todos los checks/regresiones antes de aprobar.
- [#123](https://github.com/amehcgracia-byte/Montara/pull/123), «Document verified 0.71 installation», sigue abierta. Documenta instalación en JM, Companion 0.6.10 en Mac, Engine `b5e48317`, Mixer `f15ff91` y casos reales de vídeo. Es evidencia de *la instalación declarada*, no permiso para reemplazar código de main ni replicar el despliegue. Revalidar versiones antes de una prueba en servidor.
- Auditoría anterior [#108](https://github.com/amehcgracia-byte/Montara/pull/108) registró disco casi lleno; [issue #54](https://github.com/amehcgracia-byte/Montara/issues/54) sigue abierta. Se comunicó liberación de espacio posteriormente, **sin nueva medición en esta auditoría**. No copiar ni renderizar medios en esa VM sin verificar capacidad/retención.

## 2. Mapa de dependencias (orden lógico, NO orden de merge)

### A. Camino funcional principal

```text
main actual (catálogo parcial y web/Companion actuales)
  └─ #124 U15A OIDC validación de identidad
      └─ #125 U15B login PKCE/sesión
          └─ #126 U15C navegador Google simulado
              └─ #127 U16A vínculo propietario↔Engine
                  └─ #128 U16B dos workers Docker aislados
                      └─ #129 U16C ingest/cancel/reabrir
                          └─ #134 U19 activación desde cookie HTTP del owner
                              └─ #135 U20 Stage por owner + descriptor seguro
                                  └─ #136 U21 traductor y endpoint local Companion
                                      └─ #137 U22 aceptación en un solo workflow
```

*Decisión:* considerar #137 como **punta de referencia** del laboratorio; **no** fusionar los diez PR secuencialmente a main. Extraer el contrato mínimo actual en unidades pequeñas y revisables, con diffs contra el main más reciente. Los cambios de U19/U20/U21 necesitan revisión de seguridad y adaptación al app/web real, no solo copiar el laboratorio.

### B. Medición y conexión, NO camino necesario para ejecutar producto

```text
#121 E2E actual con originales locales (base main)
  └─ #130 U17A benchmark de dos stacks (misma máquina)
      └─ #131 U17B telemetría PID por host
          └─ #132 U17C bytes HTTP loopback
              └─ #133 U18 preflight HTTPS/localhost simulado
```

*Decisión:* conservar harness e informes como **tests/herramientas internas**. Integrar solo los medidores necesarios para comparar CPU local vs servidor y detectar transferencias; evitar ampliar la superficie pública, instalar componentes en usuarios o atribuir métricas de localhost a WAN.

### C. Anteriores/alternativas: consulta y selección, no acumulación

- #86, #88–#90: historial de catálogo/sesiones/UI anterior; **comparar con catálogo ya presente en main** para no reintroducir clases/campos duplicados.
- #91–#99: fases de guardia de runtime/worker/aislamiento y ensayos Docker; algunas ideas reaparecen en U16/U19–U22; conservar los **contratos negativos útiles**, sin duplicar implementaciones.
- #102/#104/#112/#121: versiones de preflight/E2E de vídeo. **#121 es la referencia posterior**; no fusionar variantes viejas de `tests/e2e_native_stage.py` encima de él.
- #108: auditoría histórica estática; datos sobre disco, API y Stage deben revalidarse.
- #84: benchmark Cloudflare; **no** decidir proveedor cloud en esta consolidación.
- #68: experimento CPU 360; no bloquear beta inicial por esta investigación.
- #123: documentación release 0.71; revisar y registrar la versión efectiva, sin alteración de runtime.
- #74: Windows y protección de subida explícita; extraer primero **la política de no-fallback silencioso** y los tests relacionados, posponiendo integración global Windows hasta estabilizar Mac/servidor.

## 3. Matriz concreta de riesgos y conflictos

| Zona | Fuentes a reconciliar | Evidencia y resolución prevista | Gravedad |
| --- | --- | --- | --- |
| `companion/companion.py` | main 0.6.10 ↔ #74 Windows ↔ #136 U21 | **#74 tiene conflicto real con main**. Windows modifica búsqueda de originales, manejo FFmpeg, progreso y lifecycle; U21 agrega import local y `POST /video-renders/handoff`. Reaplicar **manualmente ambos cambios necesarios** sobre la versión instalada; ejecutar suites Mac/Linux y Windows sin sobrescribir el resto. | P0 |
| `web/montara.js` y `web/companion.js` | main ↔ #74 | En main existe fallback de subida de original si Companion no funciona. En #74 hay confirmación **explícita** por intento en frontend, pero eso solo no garantiza que el backend bloquee la ruta. Definir modo híbrido **fail-closed**; autorizar upload manual solo en un modo experimental controlado y con tamaño/cuota. Comprobar backend y tests E2E. | P0 |
| `urano/project_catalog.py` y sesiones | main ↔ #86/#88–#90 ↔ #124–#137 | Main ya contiene catálogo. Comparar esquema y migraciones, conservar compatibilidad de IDs/datos; no aplicar un catálogo histórico completo ni duplicar sesión vieja y OIDC nuevo. | P0 |
| `urano/google_lab_app.py`, `urano/http_owner_runtime.py` | #126/#127/#134/#135 | Se modifican secuencialmente dentro de la misma cadena; tomar la **versión final coherente**, no cherry-picks independientes. Cambiar el uso de app laboratorio por integración explícita y revisada con la web productiva. Validar cookie, PKCE, CSRF, Origin, revocación, allowlist y errores no filtrados. | P0 |
| `urano/container_worker_bridge.py`, `urano/engine_worker_process.py` | #128 ↔ #135 | Dependen del supervisor, guardia y bindings. Reunir el árbol completo de imports y contratos; evitar abrir Docker/Engine arbitrario desde navegador. Probar aislamiento, timeout, cancelación y cierre. | P0 |
| `tests/e2e_native_stage.py` | main ↔ #102/#104/#112/#121 ↔ #132 | #121 y #132 cambian el mismo test **en una cadena conocida**; solo portar versión final tras comprobar selector/cámaras del Stage actual y configuración Chrome/FFmpeg. No mezclar las alternativas históricas. | P1 |
| `companion/urano_local_handoff.py` | #136 y `video_recipe.py` de main | No está en main; traducir solo cortes básicos bajo esquema cerrado. Los slots de fuente del Stage no están enlazados criptográficamente al original local del usuario: falta contrato proxy↔original↔plan antes de beta. | P0 |
| Submódulos Engine/Mixer y CI | Main instalado vs ramas de laboratorio | En U22 Stage y Companion usan **fuentes sintéticas distintas**, se identifican solo por `source_slot`. No aumentar CPU de GCP ni cambiar SHA de submódulos/FFmpeg en un merge de consolidación. | P0 |
| Entorno GCP y almacenamiento | #54, #71, informe U14 y estado operativo | Revisión **solo lectura** de espacio, inodos, retención, versiones, servicios; no generar nuevos renders ni eliminar nada sin confirmar margen y permiso. | P0 previo a prueba remota |

**Nota de precisión:** «riesgo/solapamiento» no equivale a un conflicto Git confirmado. El único `dirty` contrastado explícitamente aquí es #74 contra su base main.

## 4. Plan de integración selectiva: unidades y puertas de aceptación

**C0 — Congelar referencia, organizar y documentar (este trabajo).**
- Base `main@765a34c`; informe + manifest de dependencia, sin cambios runtime.
- Mantener PR U22 #137 como evidencia; no retargetear y no cerrar/mergear de forma automática los borradores.
- Antes de portar una línea, refrescar main SHA y resolver diferencias con versiones instaladas y las modificaciones de Chema.

**C1 — Identidad/catálogo y contrato de acceso.**
- Rama nueva derivada de **main actual en ese momento**; adaptar las piezas mínimas de #124–#127 + #134 para una sesión real que no permita escoger `owner_id`, ruta física ni contenedor.
- Decidir si la UI de laboratorio se conserva aislada; **no** habilitar login falso en producción. Google real solo con dominio HTTPS autorizado y configuración de prueba controlada.
- Puerta: dos sesiones, historial persistente, logout/revocación, acceso cruzado 404, CSRF/Origin, esquema compatible y tests del main intactos.

**C2 — Provisión persistente de Engine privado + Stage limitado.**
- Integrar los contratos del worker de #128/#129/#135 con límites de CPU/RAM/disco, espacio de trabajo por propietario, ciclo start/stop/timeout/reintento y estados de trabajo. Nunca exponer un proxy HTTP arbitrario de Engine.
- El registro de workers de U19 es en memoria **del proceso de laboratorio**; definir supervisión/persistencia antes de un entorno real multiworker.
- Puerta: dos proyectos reales procesan Stage en workers aislados y retoman/cierran sin interferencias; error/cancel deja estado inequívoco, logs sin secretos, pruebas Docker confinadas a CI.

**C3 — Companion local y prohibición de upload involuntario.**
- Reconciliar sobre Companion actual: #136 + solo piezas de Windows #74 que correspondan, preservando versión y mejoras de sincronía/calidad del main.
- Portar los tests de #121/#132 y las salvaguardas del frontend para **no subir originales automáticamente**. Control también en backend, con modo manual opcional solo si usuario lo solicita explícitamente.
- Enlace `source_slot` de plan Stage ↔ huella del mismo original ↔ proxy que Stage procesó, sin transmitir archivo original completo.
- Puerta: sin Companion falla con mensaje claro **y cero bytes de original al servidor**; con Companion render local válido; huellas/owner ajenos fallan; Mac inicial y Windows por separado.

**C4 — Entorno privado de aceptación distribuida (NO en JM/FER productivos).**
- Antes de actuar: autorización para servidor HTTPS **aislado**, verificación solo lectura de disco/servicios y dos ordenadores **físicamente distintos** con Companion. Reusar telemetría U17B/C selectivamente.
- Puerta: dos usuarios reales admitidos, proyectos, subida **solo de proxies/metadata**, Stage, receta correcta y export MP4 local; recuperación, cancelación, reinicio, límites y separación de métricas CPU de cliente/servidor. Confirmar bytes reales y latencia WAN, nunca extrapolar CI local.
- Cumplida C4, declarar **beta técnica controlada**, no antes.

**C5 — Go/no-go de beta con Chema y primeras personas invitadas.**
- Revisar licencias y distribución de FFmpeg, gestión de secretos, TLS, backups, retención/disco, permisos, logs, condiciones de uso y calidad de salida (especialmente issues #115/#58/#110).
- Resolver bloqueos críticos, comprobar instalación de Companion en Mac; Windows puede llegar después si beta inicialmente Mac.
- No exigir 25 usuarios concurrentes. Escalera **2→4→8→10→25** pertenece a medición de capacidad híbrida posterior, con CPU cliente local separada.

## 5. Política de merge y rollback

1. **No merge por cascada** de #124…#137 ni de #121…#133; preservar ramas originales y CI como evidencias.
2. Crear PRs **pequeñas desde main actualizado**, por unidad C1/C2/C3, sin borrar ni reemplazar `app.py`, `companion/companion.py` o `web/montara.js` enteros cuando Chema haya cambiado funciones.
3. No tocar `main`, submódulos, instalación, discos, puertos **8101/8102/8103** ni dominios sin revisión y autorización explícita; CI aislada en GitHub.
4. Exigir checks locales del subsistema, seguridad multiowner, E2E base del main, Windows si se toca Windows, y comparación de salida/versión del Companion antes de aprobar.
5. Cambios activados por **flag apagada por defecto** al principio; si hay regresión, desactivar flag y revertir una unidad pequeña, no una pila de 20 PR.
6. Todas las nuevas PR referenciarán este documento, el SHA de main usado, la lista exacta de archivos importados y el veredicto de CI. Chema controla la coordinación de merges/despliegues.

## 6. Cosas expresamente aplazadas (evitar otra URANO interminable)

- 4/8/10/25 concurrentes: no requisito de primera beta.
- Cambio de proveedor cloud, pagos y facturación.
- Compatibilidad total Windows si la primera beta puede acotarse a Mac.
- Funciones avanzadas 360/reencuadre/efectos si el flujo básico ya es útil, salvo que una regresión las rompa.
- Auditoría de seguridad extensa: **sí** una revisión esencial SSH/TLS/secrets/owner/archivos/cuotas/backups/retención, sin sobredimensionar.
- Reaplicar benchmark o notas históricas por duplicado, cuando ya existen sus conclusiones y suites.

## 7. Decisión y siguiente acción

**Recomiendo preparar la PR C1 de identidad/sesión/proyectos** sobre `main` actualizado, en *draft*, no desplegada; con especial atención a no duplicar `project_catalog.py`. Tras superar sus contratos y revisión con Chema, continuar C2 worker/Stage y C3 Companion/local-upload. En paralelo y sin código nuevo, validar **solo lectura** el estado del espacio disponible en GCP antes de pedir autorización de C4.

**No significa que el usuario deba hacer una instalación ahora, ni que esté listo un servidor distribuido.** Este documento es la hoja de ruta de integración, no evidencia de merge o de aceptación entre dos máquinas físicas.
