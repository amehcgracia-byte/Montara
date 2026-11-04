# JÚPITER · Companion Windows 0.6.2 — auditoría inicial de brechas y plan de entrega

**Fecha:** 2026-11-04 · **Alcance:** revisión estática de `amehcgracia-byte/Montara:main`, no ejecución Windows ni cambio de código. **Estado:** investigado, aún NO implementado ni validado en Windows. No contiene rutas privadas ni secretos.

## 1. Encargo de JM (issue Montara #34)

Companion Windows sin cambiar API HTTP ni puerto 47820; instalador con doble clic y acceso directo; selector de carpeta Windows; búsqueda rápida de originales en Escritorio, Vídeos, Descargas, Documentos y unidades extraíbles con timeout; proxy 720p H.264 CFR bt709, encoder NVENC/QSV/AMF con fallback libx264; prueba real en Windows y medición.

Reutilizar el contrato y la identidad de archivos existentes; **no** editar `engine/`, `mixer/`, ni desplegar en JM. Para Stage local, evitar un nuevo motor: ya existe `companion/local_video.py` con receta revisada, verificación de originales y `ExportStage` original; requiere portabilidad e instalación Windows.

## 2. Evidencia en el código del main actual (0.6.2)

| Archivo/función | Estado actual observado | Cambio Windows que propone el laboratorio |
|---|---|---|
| `companion/companion.py::search_roots` | Busca `~/Movies`, Desktop, Downloads, Documents, Pictures, Videos; discos en `/Volumes`. `candidates` invoca `mdfind` solo en Darwin, con fallback `walked`. | Detectar carpetas conocidas Windows (incluidas ubicaciones redirigidas), unidades extraíbles y discos extra sin recorrer `C:\\` completo por defecto. Conservar identidad tamaño + hash de extremos y timeouts. |
| `companion/companion.py::choose_folder` | Diálogo AppleScript solo en Darwin; otros sistemas eligen automáticamente HOME o variable de entorno. | Diálogo real Windows mediante API nativa o PowerShell con selección explícita, cancelación distinguible; no guardar automáticamente HOME como decisión del usuario. |
| `companion/companion.py::HW_H264 / proxy_commands` | Aceleración Videotoolbox (`scale_vt`, `transpose_vt`); en Windows caería a `libx264`. `plan` excluye por ahora 360 de proxies y usa rangos de fps 24/25/30. | Probar NVENC/QSV/AMF en orden de capacidad real y con fallback probado. Mantener color bt709, CFR, rotación, audio y dimensiones fijadas por contrato. Comprobar encoder y conversión tras `ffprobe`, no confiar solo en presencia del encoder. |
| `companion/install.sh` | Bash + Homebrew + `venv/bin/python`; flujo macOS. | Instalador .bat/.ps1 de doble clic, Python+FFmpeg detectados/instalados de forma segura, acceso directo y actualización atómica cuando haya renders activos; sin afectar Mac. |
| `companion/video_jobs.py::runtime / _run` | Busca `venv/bin/python`, lanza subproceso con `start_new_session=True`. `stop_process_tree` invoca `ps` y señales `SIGTERM/SIGKILL`. | Resolver `Scripts/python.exe` en Windows; inicio, cancelación de procesos descendientes y limpieza mediante Windows Job Objects o alternativa auditada. Evitar matar procesos ajenos. |
| `companion/companion.py::local_mixer` | Busca `mixer/venv/bin/python`. | Portabilidad del marcador/entorno del mixer; no prometer mezclador Windows hasta distribuir dependencias y validar licencias. |
| `companion/local_video.py` | Reutiliza receta, editor fijado y verificación de vídeo. Usa variables `ZUCKER_DATA_ROOT` / `ZUCKER_GLOBAL_CACHE`, raíz privada `state`, branding `within-content` y `ExportStage`. | Reutilizar tal cual contractualmente; verificar dependencias del Editor/FFmpeg en Windows, pin y caché. No reescribir pipeline. |
| `companion/companion.py::Handler` | HTTP local, `/health`, `/proxies`, proyectos, búsqueda, jobs; permitido solo en localhost para el servidor. | Preservar endpoints, JSON, puerto 47820, CORS/orígenes autorizados y fingerprint; probar interfaz web real. |

**No es un inventario exhaustivo:** antes de desarrollar hay que localizar usos restantes de rutas POSIX, subprocess, señales, permisos y shells, y revisar las rutas concretas de instalación, descargas y actualización. Comparar main actual antes de cada PR.

## 3. Plan con entregables y criterios de cierre

### W1 · Compatibilidad base y detección de originales
- Añadir auxiliares multiplataforma focalizados, sin cambiar contratos HTTP.
- Elegir carpeta Windows mediante diálogo nativo; respetar cancelar.
- Buscar primero carpetas recordadas y archivos cercanos; luego carpetas típicas y discos extraíbles según plazo. Verificar `name + size + SHA-256(head64KiB+tail64KiB)`.
- **Gate:** tests Windows mockeados y prueba en Windows real con originales tanto en disco interno como externo. Medir localización y no subir original automáticamente sin consentimiento.

### W2 · Proxies Windows y medición
- Introducir detección NVENC/QSV/AMF con fallbacks genuinos. FFmpeg puede anunciar encoder sin que exista GPU/driver operativo: probar la ruta, registrar primer intento y fallback.
- Validar `ffprobe`: H.264, resolución compatible con contrato, CFR 24/25/30, bt709 y audio; revisar vídeo HDR/rotación. Si hay fallo hardware, volver a libx264 sin falsear estado `ready`.
- **Gate:** mismos originales, tiempos hardware/software, bytes/ratio y evidencia de salida reproducible. **No hay resultados de rendimiento Windows todavía.**

### W3 · Instalación y render original local
- Instalador Windows con icono/acceso directo, detección de dependencias, puerto 47820 en loopback, logs, actualización segura.
- Adaptar rutas de entornos Python, árboles de procesos y cancelación; instalar Editor exactamente fijado por Montara, no usar `zucker_videos/main` arbitrariamente.
- **Gate:** instalar, reiniciar, iniciar sesión, probar `/health`, `/locate`, `/proxies`, `/projects`, `/projects/<id>/save`, y ciclo de un export Stage local con originales y cancelación. En Linux, E2E + capturas revisadas antes de etiquetar producto terminado; validación Windows nativa adicional imprescindible.

## 4. Riesgos e instrucciones

1. **No alterar Mac:** ramas cortas, tests de regresión, sin reemplazar `companion.py` completo.
2. **Privacidad:** escaneo acotado y sin subir originales inadvertidamente; la página puede hacer fallback a subida si falla un proxy. El comportamiento debe comunicarse y respetar la política de consentimiento.
3. **Hardware:** QSV/AMF/NVENC pueden fallar por GPU, drivers, build FFmpeg o colores HDR; separar detectado/disponible/funcional.
4. **No confundir prueba estática con validación:** sin PC Windows probado no se certifica rendimiento, funcionalidad ni installer final.
5. **Prioridad:** W1 antes que W2/W3; F4 bilineal y propuesta híbrida FOCUS_A_C siguen tareas distintas después de este bloque.

**Petición a JM:** por ahora ninguna intervención en producción. Una vez validado W1 en laboratorio, entregar PR pequeña y esperar revisión selectiva.
