# URANO U13E2B — Ensayo nativo con vídeos reales y Companion

Fecha 2026-11-06. **Estado: PR DRAFT. Adaptador preparado, pero NO ejecutado con muestras reales ni demostrado render/export real de esas muestras.** Esta rama se creó directamente desde main después de la PR #100 de Chema; no reapila bases U10–U12b antiguas.

## Reutilización del circuito ya existente

La prueba `tests/e2e_native_stage.py` ya recorre navegador → Engine/receta → Companion local → MP4, comprueba reproducción, edición de planos, exportación, decodificación FFmpeg y reapertura. No introducir un motor de render alternativo. Conserva sin cambios conceptuales su modo sintético predeterminado para regresión CI.

Novedad: opciones `--real-camera` (dos veces) y `--real-master` (una vez) permiten alimentar ese recorrido con grabaciones originales existentes. Se validan ficheros, rutas absolutas, extensiones, symlinks, duplicados, máster y separación entre origen y carpeta de salida. Las raíces locales autorizadas del Companion se construyen a partir de los archivos seleccionados. No se copian los originales al directorio de trabajo. Las comparaciones de originales pasan de cargar archivos 4K enteros en RAM a SHA-256 por bloques de 4 MiB.

El E2E comprueba que el MP4 final tiene vídeo/audio y resolución positiva en modo real, que se puede decodificar completo con FFmpeg, que el Companion produjo el resultado y que al recargar se recupera. El modo sintético mantiene su aserción 1920×1080.

## Ejecución prevista, NO realizada

1. Restaurar acceso SSH de forma autorizada o disponer de un equipo con el mismo software y las muestras originales. Gateway `montara-test-gcp` sigue devolviendo timeout en puerto 22: la operación de lectura de ficheros nunca arrancó. NO modificar firewall, DNS, servidor JM ni otros servicios.
2. Inspeccionar con solo lectura el inventario histórico del laboratorio FER (presencia NO verificada): iPhone `IMG_0044.MOV`, Sony `C0188.MP4`, cámara 360 `VID_20260824_204524_00_004.mp4`. Identificar un audio maestro real relacionado con los clips. Si no está, preparar extracción de prueba exclusivamente en scratch con permiso, nunca modificar originales.
3. Disponer de un scratch aislado con espacio suficiente, navegador H.264 y FFmpeg. **No usar rutas de producción** como destino ni tocar proyectos preexistentes. Ejecutar explícitamente el E2E nativo con dos cámaras y máster, en un proceso/servidor local de pruebas con puertos efímeros.
4. Validar metadatos del MP4, sincronización, integridad de originales, revisión visual, reapertura, audio e informe JSON; después diseñar gate de 360 por separado. No extrapolar a Push/Show.

Ejemplo meramente ilustrativo (no ejecutado):
```bash
python tests/e2e_native_stage.py \
  --output /laboratorio/scratch-urano-e2b \
  --real-camera /home/fer/lab-clips/originales/IMG_0044.MOV \
  --real-camera /home/fer/lab-clips/originales/C0188.MP4 \
  --real-master /ruta/autorizada/master-real.wav
```

## Evidencia y límites

Archivos: `tests/native_real_media_input.py`, cambios acotados en `tests/e2e_native_stage.py`, `tests/test_native_real_media_input.py` y CI `.github/workflows/urano-u13e2b-native-real-media.yml`. La CI prueba las validaciones con ficheros ficticios pequeños y sintaxis del E2E; no contiene ni transporta grabaciones privadas. Sus resultados NO avalan todavía una exportación de las muestras reales.

**Arquitectura real:** al trabajar con Companion, el render final usa los originales locales; no medir como si todo se ejecutara en el servidor. Benchmarks posteriores: 1/2/4/8/10/25 usuarios y carga Companion+servidor, sin cola global obligatoria.

**Coordinación Chema:** PR #100 ya está en main con catálogo U10–U12b aislado y corrección DOM después de await. Chema también solicitó una beta de historial con Google OAuth/OIDC en issue #34; es un objetivo aparte que requiere identidad OIDC verificada en backend, sesión, autorización y URL HTTPS privada. No habilitar JM ni publicar secretos.

No se modifica main ni los servidores FER/JM, Vercel, Cloudflare, DNS, ni medios originales. La PR sigue en DRAFT hasta prueba con material real y revisión del equipo.
