# URANO U21 — U20 descriptor → Companion local → MP4 (2026-11-08)

## Objetivo y arquitectura

**U20 (#135)** ya validó que dos sesiones de propietarios autenticados con tokens Google ficticios firmados controlan sus Engine privados, ejecutan Stage Ingest hasta `done` y reciben únicamente su descriptor de cortes autorizado (`urano-local-handoff-descriptor-v1`) sin rutas privadas.

**U21** conecta ese descriptor con el **renderizador local existente** de Companion, sin transmitir los originales al Engine para hacer la exportación y sin abrir un proxy del Engine. El render final consume CPU del ordenador cliente, no de GCP. Este es el camino híbrido que queremos comercializar.

## Cambio de producto acotado

- `companion/urano_local_handoff.py`: traductor local entre el descriptor **no ejecutable** de U20 y `video_recipe.validate()` del Companion ya existente. Convierte `source_slot`, `start_ms`, `end_ms` a segmentos en segundos y línea temporal consecutiva del master, limitados a 500 cortes, 16 fuentes y seis horas de duración total.
- Exige que todos los `source_slot` utilizados estén asociados exactamente a una identidad local **nombre + tamaño + fingerprint SHA-256 de extremos**, sin aceptar `path`, `asset` (proxy), `source_files`, órdenes, FFmpeg args ni URLs. Rechaza descriptores arbitrarios, cut extra, master no registrado, versiones incorrectas y cualquier campo inesperado.
- Genera un `recipe` que pasa **otra vez** por el validador `video_recipe.validate`, usando **la versión real instalada en Companion**, nunca una versión de Engine proporcionada por el navegador.
- `companion/companion.py`: nuevo endpoint **POST /video-renders/handoff**, activado bajo el control de orígenes que ya existe para Companion. Convierte y llama a `video_jobs.start()`, que hace una **segunda verificación local de fingerprints y tamaños** y utiliza `local_video.py` / FFmpeg existente. Su respuesta contiene solo un ID de trabajo aleatorio; el MP4 permanece en la carpeta escogida por el usuario. El antiguo `/video-renders` no se modifica.
- No hay soporte en este incremento para controles avanzados de imagen, 360, movimiento, reencuadre ni traducción de ediciones complejas: **solo cortes básicos de Stage/YouTube**, de manera estricta. No afirmamos paridad funcional de todas las recetas del editor.

## Evidencia

- `tests/test_urano_u21_local_handoff.py`: conversión positiva, tiempos exactos, rechazos de rutas, originales falsos, slots ajenos o sin mapear, master inválido, tamaño/identidad manipulados, cortes de duración imposible y campos arbitrarios.
- `tests/urano_u21_render_client.py`: genera vídeos H.264 y WAV sintéticos **en la máquina local de test**, crea un proyecto de dueño en `ProjectCatalog`, guarda cortes, obtiene su descriptor real mediante `project_handoff` U20, arranca Companion en `127.0.0.1` y solicita la exportación HTTP. Prueba origen ajeno (403), huella alterada (400), render MP4 original, manifiesto privado local, audio y vídeo con FFprobe, decodificación FFmpeg y descarga local del MP4.
- `.github/workflows/urano-u21-local-render-handoff.yml`: dos procesos de cliente independientes `alice`/`bob` lanzados en paralelo con `HOME`/carpetas/procesos/puertos locales distintos en runner desechable GitHub. El CI guarda únicamente logs/resúmenes, **no los MP4, medios, manifiestos ni rutas** como artifacts.
- **Pendiente de confirmar el estado del commit final** en GitHub Actions antes de declarar PASS.

## Distinciones cruciales

**Este gate de laboratorio no equivale a dos Macs físicos distintos con servidor remoto GCP**: los clientes utilizan dos procesos y una sola CPU física de runner; aún no incorpora Google real ni la transferencia real WAN de proxies y recetas.

El endpoint de Companion **no valida criptográficamente la identidad Google**. Esa autorización se realizó en U20 **antes de servir el descriptor**. Companion permite únicamente conexiones desde sus orígenes web admitidos y valida identidades de originales locales; el camino SaaS HTTPS producción debe mantener y verificar la sesión y control de acceso antes de llamar a este endpoint. El `project_id` remoto y la revisión no son una firma. No considerar seguros planes obtenidos de una web no fiable solo porque sean válidos sintácticamente.

**U21 no desactiva el fallback histórico de subida del original** de `web/companion.js`; la nueva ruta rechaza `asset` y solo admite huellas de originales verificables localmente. Antes de beta hay que establecer **comportamiento fail-closed** para las rutas de subida de originales en el modo híbrido real, tanto en frontend como backend, sin romper usos de laboratorio existentes.

Los medios sintéticos que se generan en el runner no representan una subida a nube desde cliente. No se obtienen datos de clientes reales, vídeos originales ni claves Google. No se modifican el Engine de Chema, el frontend actual, `main`, GCP, los puertos 8101/8102/8103 ni el entorno compartido.

## Siguiente y último cierre de fase — U22

Una sola aceptación coordinada, sin abrir otra escalera de micro-PR: integrar **autenticación real, owner/worker, Stage, proxy remoto y Companion local**, probar **dos clientes físicos con HTTPS, permisos, recuperación, fallos y cierre**, documentar límites/costes básicos y consolidar las PR para revisión de Chema. Los niveles de concurrencia **4/8/10/25** no son condición para cerrar esta etapa, pero siguen en la hoja de ruta de rendimiento futuro. Si el entorno remoto no puede autorizarse, documentarlo como blocker antes de declarar URANO distribuido terminado.

**No fusionar esta rama automáticamente**; PR apilada sobre U20 #135 y por tanto sobre U19/U16/U15. La pila alternativa de benchmark U18 #133 debe consolidarse selectivamente, no duplicando código viejo.
