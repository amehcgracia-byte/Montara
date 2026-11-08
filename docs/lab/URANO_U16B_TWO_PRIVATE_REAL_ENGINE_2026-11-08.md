# URANO U16B · Dos propietarios Google, dos Engine privados (08-11-2026)

## Objetivo acotado

Cerrar la prueba de **aislamiento de ejecución del Engine**, aprovechando código U13 probado, sin diseñar otra pila multiusuario y **sin desplegar una beta ni tocar los puertos 8101/8102/8103**.

Esta rama `fernando/urano-u16b-two-owner-private-engine` nace de U16A (#127) y depende por tanto de U15C (#126), U15B (#125) y U15A (#124). **No es una PR directamente fusionable a main fuera de su cadena de dependencias.** GitHub main puede haber cambiado desde esta base; debe revalidarse antes de integrar.

## Reutilización literal

Los siguientes módulos proceden de U13D2D (#98), en lugar de escribir otra infraestructura:
- `urano/runtime_activation.py`: guardia de activación por propietario, generación monotónica, `busy`/stale fencing.
- `urano/engine_worker_process.py`: worker privado stdio que ejecuta `create_app` del Engine dentro de SU proceso; apertura verificada del proyecto activo.
- `urano/private_worker_supervisor.py`: supervisión y cierre fail-closed de subprocesos.
- `urano/container_isolation.py`: argumentos Docker con imagen sha256 inmutable, red `none`, root read-only, capabilities dropped, no-new-privileges, UID no privilegiado, límite CPU/RAM/PID y montaje de workspace privado.
- `urano/container_worker_bridge.py`: puente contenedor↔guardia↔Engine con identidad de contenedor y limpieza verificada.

`EngineProjectRegistry` ya se reutilizó en U16A desde U13A #91. Cuando se integren las PR históricas, **evitar duplicar los mismos archivos**: decidir una única fuente de integración; no fusionar pilas antiguas a ciegas.

## Gate E2E con Engine verdadero

`tests/test_google_private_engine_docker.py` combina:
1. Dos JWT sintéticos RSA firmados por proveedor Google falso y **validados criptográficamente** por `verify_google_id_token`, cada uno con `sub` único y nonce controlado.
2. `GoogleOwnerStore` asigna UUID persistentes diferentes; `ProjectCatalog` crea proyectos distintos. Un registrador de backend vincula cada UUID a una carpeta Engine en SU workspace.
3. La imagen Docker se construye **desde este commit**, con Engine y Mixer reales fijados por sus submódulos; se obtiene el ID local `sha256:`, no se emplea etiqueta mutable para arrancar worker.
4. Dos contenedores privados se inician y abren proyectos históricos de sus dueños **en paralelo**, sin mutex global. Alice puede cambiar de un proyecto suyo anterior al más reciente mientras Bob conserva su Engine.
5. Se verifica que cada contenedor carece de rutas de los proyectos del otro en `/workspace`, que la red Docker está deshabilitada (`none`) y que la apertura por UUID extranjero se rechaza antes de solicitarla al worker.
6. Al parar los contenedores, se verifica borrado y que la guardia deja de considerarlos activos.

**Runner desechable GitHub Actions**, no GCP. No se cargan medios privados. Este gate prueba **apertura concurrente de Engine real**, **NO** render simultáneo, carga de vídeos, proxy/relink Mac Companion, seguridad frente a una eventual fuga del daemon Docker ni autorización completa de endpoints de producción.

La prueba utiliza permisos amplios `0777` en sus carpetas **sintéticas temporales** para que UID 10001 pueda escribir desde Docker; esto **NO** es un patrón de producción ni debe trasladarse al disco GCP. La fuente real y la exportación de vídeo se validaron por separado en U13E2D (#121), no se han combinado aún con este gate.

## Evidencia y siguientes puertas

Workflow `.github/workflows/urano-u16b-two-private-engine.yml`. **No declarar PASS sin confirmar el estado del workflow del commit final**. Se conserva una prueba negativa para acceso cruzado y limpieza.

Tras este gate, el siguiente desarrollo debe ser **un único adaptador privado de control de trabajos** (propietario autenticado → worker propio) con cancelación y cuota básica, sin rutas al Engine global; a continuación un E2E de Stage+Companion en dos sesiones con originales locales y recuperación. No confundir estos pasos con snapshots de montaje (coordinación con Chema).

Se mantienen intactos `app.py`, `web/cut-editor.js`, Engine/Mixer/Companion de producción, los originales y los servicios JM/FER.
