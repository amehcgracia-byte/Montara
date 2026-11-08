# URANO U22 — Acta de aceptación y cierre de laboratorio (08-11-2026)

## Objetivo del cierre

Cerrar la investigación **de arquitectura híbrida** de MONTARA con hechos verificables, sin confundir experimentos sintéticos de CI con un sistema multiusuario público. La CPU de exportación corresponde **al Companion local del cliente**, mientras que el servidor recibe los proxies/metadata necesarios para Stage; los originales pesados deben permanecer en su equipo.

**Puerta U22:** ejecutar **en un mismo workflow** la cadena de dos usuarios privados, dos contenedores Engine reales, Stage Ingest concurrente hasta `done`, recuperación de los **mismos** descriptores autorizados en cada sesión, traducción en **dos Companions distintos** y generación de dos MP4 reales con originales sintéticos verificados por huella. No inventar tiempos de WAN ni capacidad de 25 usuarios.

## Pruebas acumuladas

| Bloque | Evidencia anterior | Resultado |
| --- | --- | --- |
| Identidad y aislamiento Google sintético | U15/U16, PR #124–#129 | Contratos OIDC, privacidad y dos Engine aislados |
| Dos Stage reales bajo sesión de propietario | U20, PR #135, CI 42529394264 | **PASS** |
| Descriptor privado → render original Companion local, dos clientes | U21, PR #136, CI 42530860841 | **PASS** |
| CPU local observada separada por procesos | U17A, PR #130 | **PASS solo en una máquina CI**, no hardware distribuido |
| Tráfico navegador↔servidor y descarga Companion local | U17C, PR #132 | **PASS HTTP loopback**, no red WAN |
| Preflight de HTTPS remoto + Companion loopback | U18, PR #133 | **PASS en tests simulados**; no se ha visitado el servidor real |
| **Enlace único U22 Stage-DONE→mismo descriptor→MP4** | Workflow `urano-u22-integrated-closure.yml` | **Pendiente de confirmar CI del commit final** |

## Prueba U22

`.github/workflows/urano-u22-integrated-closure.yml` instala Engine y renderer en un runner Linux temporal, construye una única imagen Docker fijada por SHA y hace:

1. Verificación de dos identidades **Google ficticias firmadas/verificadas**, CSRF y sesión válida desde Flask HTTP.
2. Dos Engine Docker con filesystem aislado, activación de proyectos propios, rechazo de acceso extranjero, dos `ingest_start` reales y espera de `ingest_status=done`.
3. Extracción de **solo** `plan` JSON devuelto por `GET /companion-handoff` en la misma sesión del propietario. Los descriptores reales pasan a `e2e-output/u22/handoffs/{alice,bob}.json`; **no** se copian medios, ficheros de proyectos, tokens o rutas Docker.
4. Validación de IDs de proyecto diferentes, corte permitido, `render_ready=false`, ausencia de rutas locales, nombres de input y material privado.
5. Dos procesos Companion independientes en el mismo runner Linux que reciben **esos planes exactos**, construyen identidad con huella de un original sintético **en cada área local**, traducen cortes básicos a `video_recipe` y llaman `POST /video-renders/handoff`. El renderer existente verifica las huellas, genera MP4 con audio y se comprueba por FFprobe + decodificación FFmpeg. Peticiones de origen ajeno o huella falsa se rechazan.
6. Solo se publican como artifact `summary.json` de cada cliente, **no** los MP4, originales, manifest local, handoffs ni secretos.

**Limitación técnica importante:** las cámaras sintéticas del Stage se crean dentro del laboratorio Docker, mientras que los originales sintéticos del render se generan en las áreas locales del runner. **No** son el mismo archivo físico ni hay una transferencia proxy desde un Mac al servidor remoto. Los descriptores sí son los que se han obtenido después del Stage real, pero el enlace fuente↔cliente se asocia por `source_slot` en el ensayo; la identidad completa de origen entre ambos lados de la red aún no ha sido verificada. El ensayo no prueba que el cliente correcto haya aportado los proxies concretos de Stage ni valida identidad original extremo a extremo.

## Bloqueadores obligatorios antes de decir «MONTARA distribuido listo»

1. **Dos clientes físicos**, con Companion ejecutándose cada uno en un equipo realmente distinto, y **servidor HTTPS remoto de ensayo autorizado**. Ahora GitHub comparte una CPU; **la aceptación distribuida real aún no está ejecutada**. Aunque haya dos servidores GCP registrados, no contamos con los dos clientes físicos conectados.
2. **Google/OIDC real** y control de acceso en un despliegue aislado, con provisión persistente de workers, tiempos, recursos y reanudación. El Google de CI es firmado **ficticio**.
3. **Huellas y transporte de fuentes/proxies de extremo a extremo**, desde Companion local hasta Stage remoto y vuelta a receta, sin originales completos. En U22 el fixture de Stage se crea artificialmente en Docker.
4. **Fail-closed del fallback de originales**: el frontend antiguo puede subir un original cuando Companion falla. Debe cambiarse por un modo híbrido que *no* suba originales sin autorización explícita, tanto en frontend como backend. La nueva ruta `/video-renders/handoff` solo admite originales verificables localmente, pero no bloquea los antiguos endpoints.
5. Gestión operativa de cancelación, reintento, desconexión, cuotas CPU/RAM/disco/tráfico, observabilidad y revisión de permisos. Se han probado cancelaciones y recuperación parcial en U16C, pero no todo el ciclo comercial completo en equipos distribuidos.
6. **Consolidación y revisión de las PR apiladas** con Chema antes de merge. No hay pruebas integradas de todas las opciones avanzadas del editor: U21 traduce **cortes básicos** YouTube/Stage, no todas las recetas de movimiento, panorama, reencuadre o luces. Sin paridad demostrada.

## Decisión de cierre honesta

Con U22 en verde se puede etiquetar **«URANO / investigación híbrida: laboratorio integral superado»**, y empezar trabajo de beta/integración de producto. **No** se debe etiquetar «arquitectura distribuida certificada» ni «lista para clientes» sin los puntos anteriores. La escalera de 2→4→8→10→25 concurrentes es una campaña posterior de rendimiento **con CPUs clientes separadas**. Los 25 no son condición de cierre de investigación.

## Conservación del entorno

- Sin merge a `main`, sin despliegue, sin escribir en GCP, ni contactar 8101/8102/8103.
- Ningún archivo original, token o MP4 se añade a los artifacts de GitHub.
- Todo el trabajo queda en la rama `fernando/urano-u22-integrated-closure-gate`, basada en U21 #136 → U20 #135 → U19 #134. Los laboratorios de benchmarks U17/U18 están en otra pila de PR y se integrarán **selectivamente**.

**Pendiente de anotar evidencia concreta del workflow final y de Chema; el acta no implica aprobación de despliegue.**
