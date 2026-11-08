# URANO U16C — Aceptación de Stage real con dos propietarios y cancelación (08-11-2026)

**Resultado:** PASS de prueba integrada **de Stage/Ingest**, no aceptación final del producto multiusuario con Companion.

## Contexto y dependencia

- Rama `fernando/urano-u16c-two-owner-stage-acceptance`, basada en U16B **#128**, que sigue apilada sobre U16A **#127**, U15C **#126**, U15B **#125**, U15A **#124**. Ninguna fusión a `main` ni despliegue JM/FER/8103.
- Reutiliza `urano/container_isolation.py`, `GoogleOwnerStore`, `verify_google_id_token` y `ProjectCatalog` sin diseñar otro stack. El Engine/Mixer se construye del `Dockerfile` y submódulos fijados en el commit de prueba.
- No modifica código de `Engine`, `Mixer`, `Companion`, `app.py` ni el editor de Chema; los ficheros añadidos son **solo test/CI/docs**.

## Prueba realizada de verdad

GitHub Actions **[run 42515323777](https://github.com/amehcgracia-byte/Montara/actions/runs/42515323777)**, **SUCCESS**, commit de código `a07916b01244509307d0db62be43b75ce45bc965`:

1. Google sintético emite dos ID tokens firmados con RSA. `verify_google_id_token` verifica firma, nonce, audiencia, etc. `GoogleOwnerStore` asigna **dos UUID distintos** y el catálogo guarda un proyecto por propietario.
2. En un **runner de GitHub desechable** se crean dos `/workspace` privados y se lanzan en paralelo dos contenedores Docker del **Engine real**, red `none`, imagen inmutable, límites básicos CPU/RAM, UID no privilegiado. Vídeos H.264 sintéticos de 20 s y master WAV generados mediante FFmpeg **dentro del contenedor**; se llaman los endpoints reales de registro de entrada y `POST /api/v1/stages/ingest/run`. Ambos Ingest llegan a `done`, metadata de `ffprobe` y archivos normalizados presentes. **2/2 PASS**.
3. En un tercer workspace efímero, se inicia otro Ingest real hasta que `/run` responde HTTP **202**. El test detiene el contenedor con `docker rm -f` y verifica que ya **no existe**; nunca interpreta la cancelación como Ingest completo.
4. Se **reabren 3 proyectos** en nuevos procesos Engine, usando su archivo `project.json` y comprobando el proyecto que realmente queda cargado. Los originales sintéticos y metadata de Bob siguen presentes tras cancelar el trabajo de Alice. **3/3 PASS**.
5. Los contenedores ven únicamente sus workspaces montados. Los archivos se crean con permisos amplios **solo para fixtures desechables CI**, no es diseño para datos privados de clientes.

Resumen impreso por el gate:

```json
{
  "passed": true,
  "verified_google_owner_count": 2,
  "stage_concurrent_ingest_successes": 2,
  "independent_engine_containers": true,
  "cross_owner_media_filesystem_isolated": true,
  "cancelled_stage_after_accepted": true,
  "cancelled_worker_removed": true,
  "projects_reopened": 3,
  "ingest_resume_after_cancel_verified": false,
  "concurrent_full_stage_export": false,
  "companion_two_user_render": false
}
```

## Lo que NO hemos demostrado

- No hay todavía **endpoint/orquestador autorizado completo** desde una cookie de Google real hasta un trabajo Stage; el test emplea un controlador de infraestructura de confianza con propietarios derivados de tokens ficticios.
- El Ingest cancelado **no** se ha probado reanudable automáticamente: se comprobó que el proyecto persistió y pudo volver a abrirse. El status residual `running` y las políticas de recuperación de tareas interrumpidas requieren un gate explícito.
- No hemos ejecutado **SYNC/CUT/EDIT/EXPORT** de ambos usuarios en paralelo, ni render final en Companion desde dos Macs o clientes independientes.
- La validación previa **#121** de Stage→Companion→MP4 con originales Sony derivados se completó en un **único entorno**; no autoriza a concluir multiusuario funcional en producción. Esta U16C no incorpora ni sustituye esa prueba.
- No se han probado fugas de memoria, escapes del contenedor, límites globales de disco, colas, cuotas/abuso, carga real de un músico, ni snapshots de decisiones manuales.
- Ningún worker productivo fue conectado a `main`, puertos 8101/8102/8103, R2, D1, Workers o Cloudflare. **Sin despliegues.**

## Veredicto y siguiente paso mínimo

**Aislamiento del Engine hasta INGEST concurrente: VALIDADO EN CI.**
**Aceptación end-to-end Stage/Companion multiusuario: AÚN NO CERRADA.**

Para cerrar esa aceptación sin otras microetapas: una única prueba a nivel aplicación en entorno privado, con dos cuentas/sesiones autorizadas y workers per-owner, dos proyectos Stage completos hasta receta (o una limitación documentada si el Engine no permite aislamiento integral), Companion en cliente independiente, export MP4 y recuperación/cancelación. Este trabajo debe coordinarse con cambios de cortes/snapshots de Chema y revisar seguridad de cada ruta de media. No abrir beta por este gate.

Todas las pruebas generaron medios **sintéticos**, sin secretos ni materiales originales. CI de esta PR debe pasar de nuevo tras el commit documental.
