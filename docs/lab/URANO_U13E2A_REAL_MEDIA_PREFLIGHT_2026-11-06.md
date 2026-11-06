# URANO U13E2A — Preparación con medios reales (sin modificación de originales)

**Fecha:** 2026-11-06 · **Estado:** PR draft, gate de inspección previo al procesamiento. NO demuestra aún exportación y no es una beta.

## Decisión: muestras reales como aceptación principal

El capitán ha confirmado que dispone de muestras auténticas de diferentes dispositivos. **U13E2 no dará por superado un render sólo por usar material sintético.** Los vídeos generados por FFmpeg permanecen como regresión reproducible y sin datos privados para CI. La prueba de aceptación de edición/export prioriza iPhone, Sony y 360 del laboratorio FER.

Inventario histórico **no verificado en vivo**:
- iPhone 4K: `IMG_0044.MOV`
- Sony: `C0188.MP4`
- 360: `VID_20260824_204524_00_004.mp4`
- Zona histórica: `/home/fer/lab-clips/originales`; **no asumir existencia** hasta comprobar el servidor con Gateway.

La conexión Gateway a `montara-test-gcp` **falló por timeout TCP 22** en el intento de 06-11. Ninguna operación comenzó. No tocar JM, la configuración SSH, DNS ni firewall sin coordinación expresa; esperar acceso adecuado o un entorno alternativo autorizado. No copiar vídeo privado a GitHub, CI, Cloudflare ni contenedores remotos.

## Implementación U13E2A

`urano/real_media_preflight.py` es un inspector **solo lectura**, con entrada explícita: carpeta origen, carpeta de trabajo disjunta, cámaras relativas y master opcional. Usa `ffprobe` para identificar códec, dimensiones, promedio y nominal de FPS, rotación, canales de audio, duración y tamaño, sin cargar, alterar, mover ni subir los bytes de vídeo. Comprueba espacio libre mínimo del volumen de trabajo (por defecto 8 GiB), registra falta de audio maestro, rechaza rutas absolutas/traversal, symlinks y directorios fuente/destino solapados. Emite JSON sin rutas absolutas ni nombres de usuarios.

**Importante:** no crea directorio temporal, ni proyecto ni render. El volumen de trabajo debe ser un directorio exclusivo **preexistente**; no utilizar `/home/fer/montara` como salida ni permitir escribir en originales. Su estado de aceptación significa que se puede *plantear* la siguiente prueba, no que el Engine real ya haya exportado vídeo.

Ejemplo de uso exclusivamente después de verificar existencia y permisos:
```bash
python -m urano.real_media_preflight \
  --media-root /home/fer/lab-clips/originales \
  --work-root /ruta-exclusiva-y-existente-de-laboratorio \
  --camera IMG_0044.MOV --camera C0188.MP4 \
  --min-free-gb 8
```
No usar esta llamada como una orden de ejecución automática en una VM compartida.

## Pruebas y siguientes puertas

`tests/test_urano_real_media_preflight.py` comprueba en CI metadata FFprobe simulada, que no se escriben originales/destino, rechazo de rutas externas y enlaces, audio maestro obligatorio, comprobación de espacio y salida de valores técnicos. **No incluye archivos multimedia privados ni pruebas de rendimiento**.

Siguiente trabajo U13E2B (pendiente): una vez recuperado acceso y validados los archivos, ejecutar el pipeline de **sync → cut → edit → export** con proyecto temporal independiente, vídeos reales, observabilidad de CPU/RAM/disco, cancelación segura y `ffprobe` del MP4 final. Luego U13E3 conectar Companion y validar el reparto local/remoto y relink antes de dimensionar capacidad de 1/2/4/8/10/25 usuarios.

## Coordinación importante con Chema

IA de Chema respondió en [issue #34](https://github.com/amehcgracia-byte/Montara/issues/34#issuecomment-6689088833) y confirmó integración selectiva U10–U12b mediante [PR #100](https://github.com/amehcgracia-byte/Montara/pull/100) fusionada en `main` `ae9e38b`. Corrigió JS `event.currentTarget` después de `await`, añadió prueba HTTPS/Chromium `tests/e2e_urano_dashboard.py` y dejó el catálogo dentro de app Flask de laboratorio; **no montado en web principal**. Reutilizar U10 y las rutas históricas Engine, sin duplicar el catálogo ni importar accidentalmente código antiguo que revierta su corrección. PRs U13 #91–#99 siguen sin integrarse en `main`. Agradecimiento comunicado al equipo por issue #34.

**Seguridad:** sin acceso público ni credenciales Chema, sin despliegue, sin mutaciones en VM; preservar originales y evitar una cola global entre usuarios. No extrapolar pruebas servidor-only a producto Companion+servidor.
