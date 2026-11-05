# URANO U3 — Companion prioritario, retirada controlada del fallback de originales

**Fecha:** 2026-11-05. **Estado:** orientación funcional indicada por Fernando + inventario de código; **no** cambio aprobado en producción ni eliminación implementada.

## Decisión de producto comunicada por Fernando

> La subida directa de archivos originales **no se considera una alternativa viable para la arquitectura comercial** por tamaño, almacenamiento y tráfico. Se prevé que Companion sea obligatorio para archivos locales pesados y que el fallback actual termine retirándose.

**Interpretación operativa:** tratar esta dirección como **preferencia de arquitectura fuerte y escenario de diseño objetivo**, sujeto a revisar excepciones y a validación con JM antes de cambiar el comportamiento existente. No presentar el fallback como alternativa comercial equivalente. Conservar el uso de FFmpeg y los flujos locales previamente validados. El bloqueo público por licencias de FFmpeg sigue siendo independiente.

## Rutas comprobadas en código (rama `fernando/companion-windows-w1`)

| Flujo | Archivos y función | Qué ocurre | Propuesta U3 |
|---|---|---|---|
| Carga inicial, Companion disponible | `web/montara.js:uploadSmall` y `web/companion.js:smallVersion` | Localiza original por fingerprint, crea proxy H.264 o audio convertido y sube **derivado** | **Conservar** y convertir en ruta requerida para vídeos locales |
| Carga inicial, Companion no detectado | `web/montara.js:upload` | Usa `/api/v1/wizard/upload` para pequeños o `/montara/uploads` para grandes | **Eliminar para vídeos originales** tras diseñar error guiado «Abre Companion» |
| Companion detectado pero fallo de proxy | `web/montara.js:uploadSmall` | Algunos estados `null` reenvían original; solo `missing` >200 MiB se bloquea expresamente | **Bloquear fallback de original** para vídeo; distinguir fallo, cancelación y falta de fuente |
| Cargas reanudables | `web/resumable-upload.js`, `resumable_upload.py` | Envía en trozos de 4 MiB con `Upload-Offset` y `upload.json` | **Conservar infraestructura** para proxies, audio acotado y derivados; no confundir protocolo con política de admitir originales |
| Stage, sesión de audio | `web/full-session.js`, `web/companion.js` | Envía rangos de original transformados a FLAC/WavPack/Opus; mezcla local puede enviar MP3 final | **Conservar**; distinguir fragmento necesario de subida completa de fuente original |
| Show, biblioteca adicional | `web/show-media.js:uploadShowMedia` | Importa material mediante FormData hacia `/api/v1/show/library/pictures`, `/show/library/media` o voz `/show/voices` | **Revisión separada**: imágenes/voz cortas pueden justificar excepción; vídeo grande debería seguir política Companion |
| Push, pack de reels | `web/push-pack.js` | Acepta URL pública o vídeo subido por el flujo compartido | **No prohibir URLs** al bloquear subida de originales locales; revisar importación del enlace y derechos por separado |

El comentario `file.size > 8 MiB` en `montara.js` solo determina si se usa el protocolo reanudable; **no constituye una barrera contra subir originales**. El límite de 200 MiB solo se aplica al caso `small.missing` y no es la política pretendida.

## Modelo objetivo propuesto (para revisión JM)

```text
Usuario selecciona archivo local de vídeo
       |
       v
¿Companion operativo y archivo localizable?
   | no -> detener carga, mostrar acción para abrir Companion y reintentar
   | sí
   v
Generación local de proxy (FFmpeg)
   | fallo -> detener, explicación y reintento; NUNCA enviar original automáticamente
   | correcto
   v
Enviar solo proxy/derivados con subida reanudable si corresponde
   |
   v
El servidor procesa proyecto y conserva la procedencia original para exportación
```

Para vídeo de **enlace de Internet**, biblioteca reutilizable y medios livianos **no imponer todavía** exactamente este flujo: se necesita una política según origen y tipo de archivo, no solo según modo Stage/Push/Show. El usuario debe entender cuándo un recurso sale de su ordenador, y en qué representación. Los originales locales deberán quedarse locales salvo consentimiento explícito en una futura función opcional que el producto decidiera incorporar (no contemplada ahora).

## Matriz de pruebas mínimas para retirar fallback

| Caso | Resultado objetivo propuesto |
|---|---|
| Companion no iniciado | No iniciar POST de bytes de vídeo original; indicar cómo abrirlo |
| Companion no encuentra archivo | No subir original, independientemente del tamaño; reintentar localización |
| FFmpeg falla durante proxy | Error explícito, no subida original; permite nuevo intento |
| Proxy cancelado por usuario | Ninguna subida ni proceso residual |
| Vídeo de 10 MiB y de 2 GiB | Misma regla para originales, sin umbral arbitrario de 200 MiB |
| Proxy final válido | Se permite subir proxy al backend; se registra metadata de fuente |
| Stage audio Opus/FLAC/segment | Derivado permitido; no bloquear reenvíos imprescindibles de audio acotado |
| Show imagen/voz | Evaluar límite de tamaño y necesidad de excepción antes de bloqueo |
| Show vídeo importado | Debe pasar control de política; el actual FormData puede esquivarlo |
| Push con URL | Funciona sin requerir Companion para un recurso que no nace local |
| Reinicio de navegador/Companion | Se conserva la posibilidad de recuperar archivo/proxy y reintentar sin duplicar originales |
| Acceso directo a API backend | Debe rechazar originales si el producto exige prohibición real, no solo UI; depende de distinguir derivado/original sin confiar ciegamente en nombre o metadatos cliente |

## Seguridad y datos: trabajo paralelo

- Companion escucha solo en localhost con verificación de `Origin` en rutas revisadas; **CORS/Origin no son autenticación**. Diseñar consentimiento/autorización y control del recurso local en una futura etapa de seguridad.
- `full_session.py` y `resumable_upload.py` nacieron de un despliegue privado; la persistencia por sesión no equivale a aislamiento multiusuario.
- Los originales deben permanecer recuperables para exportación y el backend no debe reclamar que almacena el original si solo recibió proxy; registrar `fingerprint`, ubicación lógica, tamaño y modo de exportación **sin exponer rutas privadas innecesariamente**.

## Próximos pasos recomendados

1. **U3A:** test aislado de navegador con mocks de Companion/red que demuestre los fallbacks actuales y capture exactamente qué bytes salen en cada fallo. No modificar producción.
2. **U3B:** proponer guardas en frontend para vídeo local y para Show; coordinar criterios de excepciones con JM y añadir regresiones de Stage/Push/Show.
3. **U3C:** evaluar **validación real desde servidor**, separando fuentes por tipo y evitando falsos positivos o manipulación de nombres; no declarar bloqueada la subida de originales solo por un cambio del cliente.
4. **U4:** arquitectura de identidad, trabajos y permisos, flujo local/nube y costes. Mantener claro qué cargas se ejecutan en máquinas del usuario y cuáles en nube.

## Cierre

**U3, definición de objetivo e inventario: preparado.** **Retirada efectiva del fallback: PENDIENTE**, no tocar aún `fernando/companion-windows-w1`, Engine/Mixer o producción. Documentación en `fernando/continuacion-montara` y revisión con JM antes de cambios invasivos.
