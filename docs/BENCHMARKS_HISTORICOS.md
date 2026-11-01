# Benchmarks históricos de Montara y Zucker

Recopilación: **28 de octubre de 2026**. Solo documentación; no se han ejecutado nuevos renders, cambiado motores ni subido medios o registros completos.

## Cómo interpretar los datos

- **Medición**: tiempo o recurso registrado en una ejecución anterior. **Validación funcional**: comprueba un resultado, pero puede carecer de cronómetro. **Estimación/objetivo**: no es rendimiento demostrado.
- `N/D` significa que la evidencia recuperada no registra el dato. Un commit de documentación identifica el informe, no necesariamente el binario ejecutado. No se reconstruyen commits históricos por la fecha de un archivo.
- Todos los tiempos están en segundos salvo indicación. La duración del material no es el tiempo de procesarlo. Las sumas de workers y el tiempo de CPU no son tiempo de pared.
- «Frío» en los A/B de render significa caché privada de segmentos vacía; **no** caché del sistema operativo vacía. «Caliente» reutiliza el mismo montaje. No representa un proyecto nuevo.
- No hay mediciones de Abacus, GPU remota, concurrencia de clientes ni archivos reales de 30 GB. Estos resultados no permiten fijar capacidad, precio por usuario o una promesa de velocidad.

## Hardware y procedencia

| Entorno | Hardware acreditado | Alcance |
|---|---|---|
| Z-Mac | MacBookPro16,2 Intel, 4 núcleos físicos/8 lógicos, 32 GiB; FFmpeg 9.0.1. En ronda 3: Intel Iris Plus Graphics, Metal 3 y OpenCV 4.11.0 | Declarado en los informes A/B de Zucker. VideoToolbox/Metal son aceleración local de Mac, no una GPU Linux validada. |
| M-Local | Archivo local de pruebas en macOS. El equipo inspeccionado al recopilar es MacBookPro16,2, 4 núcleos físicos, 32 GB | Los JSON antiguos de Montara no contienen inventario de hardware: no se atribuyen automáticamente todas las pruebas a esa configuración. RAM instalada histórica N/D cuando no consta. |
| M-Linux | Trabajador Linux aislado de Vercel; inventario detallado de CPU/RAM N/D en el resumen conservado | Recorrido Stage y diagnóstico de importación. Sin evidencia de GPU utilizada. |
| CI-Linux | GitHub Actions Linux; hardware efectivo y pico RAM N/D en los informes citados | Sirve para compatibilidad y recorridos completos; sus tiempos incluyen preparación de entorno. |

## 1. Zucker Editor: renders completos comparables

### A/B de prioridades 1–2, 8 de octubre

**Medición.** Referencia `7ae1d8d` con decoder CPU; cambios de prioridad 2 `055e7e6`. Entorno Z-Mac, aplicación cerrada, cuatro workers. Archivo/proyecto **Is cold outside**, originales multicámara, plan de 233 segmentos; salida **675,200 s, 1920×1080, 30 fps, H.264 a 18 Mbps**, AAC estéreo 44,1 kHz. Resolución individual de cada original: N/D en la tabla de este ensayo.

| Medida | Referencia fría | Variante fría | Variante caliente | Referencia caliente |
|---|---:|---:|---:|---:|
| Exportación completa, con comprobaciones | 1822,281 | 1738,875 | 276,624 | 460,908 |
| Fase de segmentos | 1625,032 | 1548,998 | 141,305 | 194,198 |
| Pico RSS agregado muestreado, MiB | 4684,4 | 5928,6 | 323,4 | 338,6 |
| Bytes lógicos de medios escritos | 6129807772 | 4599939415 | 3076588370 | 4606456727 |

Resultado: cuatro masters idénticos byte a byte, 1.546.590.978 bytes cada uno; decodificación completa sin errores, 20.256 frames de vídeo y 29.079 bloques de audio. Diferencia observada fría 83,406 s (4,58%); una ronda por condición, sin garantía estadística. RSS agrega procesos y puede contar páginas compartidas dos veces; no mide memoria GPU separada. Las escrituras excluyen journaling, parciales y la reescritura interna de faststart.

Fuente versionada: [informe de implementación](https://github.com/amehcgracia-byte/zucker_videos/blob/ff5267562b0f04c08e10aadb00cd16ffd3aaa06a/docs/AUDITORIA_VELOCIDAD_IMPLEMENTACION.md). Evidencia original identificada allí como `render-performance-20261008-180618/`; disco externo no revalidado en esta recopilación.

### A/B ronda 3, 9 de octubre

**Medición.** Referencia `1ffb168`, candidato `23c8513`; Z-Mac, mismo plan de 233 segmentos, mismas fuentes y calidad que arriba. Cambios medidos: remap Metal exacto y verificación solapada. Orden anterior frío → nuevo frío → nuevo caliente → anterior caliente.

| Medida | Anterior frío | Nuevo frío | Nuevo caliente | Anterior caliente |
|---|---:|---:|---:|---:|
| Exportación completa | 1942,755 | 1512,506 | 313,773 | 381,440 |
| Fase de segmentos | 1719,919 | 1311,598 | 170,681 | 184,991 |
| Pico RSS agregado muestreado, GiB | 4,923 | 5,829 | 0,307 | 0,345 |
| Eventos watchdog | 0 | 0 | 0 | 0 |

Resultado: cuatro masters idénticos; ambos fríos decodificados completos sin errores. Metal procesó 10.004 frames, cero fallbacks; en caliente se reutilizaron 233/233 segmentos. Ahorro frío observado **430,249 s / 22,15%**. El ahorro caliente no se atribuye íntegramente a Metal: buena parte procede de variabilidad del mux, cuyo código no cambió. Una pareja por condición.

Plan SHA-256: `5f8ae890664f1f8db7465e617a954a379c4469a5c141e41d48db0c5b48f37919`. Master SHA-256 de ambas campañas: `09df8abf2b1ab69f2d8a1bc33255ebb6c70feec16385bccde5a2d31ece5a2bbc`.

Fuente: [ronda 3, snapshot del informe](https://github.com/amehcgracia-byte/zucker_videos/blob/ff5267562b0f04c08e10aadb00cd16ffd3aaa06a/docs/AUDITORIA_VELOCIDAD_RONDA3.md), evidencia identificada como `render-round3-full-20261009-retry/summary.json`. El snapshot del informe es posterior a los commits comparados.

**Objetivo, no resultado:** primera exportación inferior a 420 s. No se alcanzó: la nueva fría tarda 1512,506 s. El resultado caliente inferior a 420 s no demuestra ese objetivo para una edición nueva.

## 2. Zucker: ingestión, análisis, proxies y sincronización

### Histórico de proyectos reales, auditoría del 5 de octubre

**Mediciones recuperadas de `elapsed_seconds`; no son un A/B.** Commit ejecutado, hardware por ejecución, duraciones, resoluciones y pico RAM: **N/D**. Nombres de proyecto identifican los casos, no un único archivo de entrada.

| Proyecto | Ingestión | Sincronización | Cut | Edit | Exportación |
|---|---:|---:|---:|---:|---:|
| So much to me | 47,347 | 79,571 | 0,071 | 101,798 | 4215,235 |
| Kongroove | 1338,360 | 89,719 | 0,151 | 443,613 | 4110,452 |
| Moonlight Cable | 2811,357 | 153,142 | 0,459 | 695,105 | 4138,038 |
| Wasib Funk | 549,243 | 40,641 | 0,077 | 197,183 | En curso al auditar |

No hay error de sincronía residual cuantificado en esta tabla; un tiempo de sincronización no acredita precisión labial. Las diferencias de fuentes y cachés impiden atribuir mejoras/regresiones entre filas.

En **If u want to stay**, el log registró 19:38:00–19:52:26 (**866 s**) preparando un proxy esférico completo que las 65 tomas esféricas no necesitaban, porque leían el original. Es coste de una fase observado, no ahorro de un A/B completo. Fuente: [auditoría de carga y render](https://github.com/amehcgracia-byte/zucker_videos/blob/3e9f41347dca999b3c92d2dc3a0aa803e1486b29/docs/AUDIT_RENDIMIENTO_2026-10-05.md).

### Solapamiento de proxies y análisis, 7 de octubre

**Medición con interferencia.** Tres fragmentos de **20 s** de Kongroove: Sony 1080p, móvil 4K y 360 4K; Sony compatible sin proxy, las otras fuentes con proxy. Referencia instalada documentada `92c3549` (2.5.1); commit exacto ejecutado de la variante N/D. Mac 4 físicos/8 lógicos; RAM del ensayo N/D.

| Recorrido | Frío | Caliente |
|---|---:|---:|
| Preparar todo y después analizar | 191,708 | 0,032 |
| Analizar al terminar cada proxy | 142,203 | 0,061 |

La aplicación trabajaba simultáneamente en Chemical Winds; se detuvo la repetición inversa para no competir. **No se declara una mejora estable del 25,8%.** Encuadre Sony: 15,982 → 14,651 s; operador: 12,859 → 12,890 s; resultados del detector iguales. Fuente: [palancas de rendimiento](https://github.com/amehcgracia-byte/zucker_videos/blob/b6a15fc2e412b1ddd086f9b5000214e92f2a37cc/docs/PALANCAS_RENDIMIENTO_2026-10-07.md).

## 3. Zucker Mixer: escaneo incremental de instrumentos

**Medición sintética local documentada**, commit **`db6768eb06f02c6a766c091ee7548d105c382613`**, 7 de octubre. Cuatro WAV mono float, **60 s cada uno, 44,1 kHz**; nombres, hardware y pico RAM N/D. Resolución de vídeo no aplica.

| Operación | Tiempo |
|---|---:|
| Escaneo serial | 0,685 |
| Paralelo con escritura de caché | 0,406 |
| Reconstrucción solo con caché | 0,023 |

Envolventes exactamente iguales. Datos del sistema de archivos calientes, muestra pequeña: no predice rendimiento de sesiones enteras ni discos USB; lecturas concurrentes pueden empeorar un disco mecánico. No es benchmark de mezcla/master ni render de vídeo. Fuente: [STEM_CACHE_PERFORMANCE.md](https://github.com/amehcgracia-byte/ZuckerMixer/blob/db6768eb06f02c6a766c091ee7548d105c382613/STEM_CACHE_PERFORMANCE.md).

## 4. Montara: pruebas locales archivadas

Los siguientes resúmenes locales no guardan SHA del código ejecutado: **commit exacto N/D**. No se les asigna retrospectivamente el commit actual. Entorno M-Local; RAM de proceso N/D salvo indicación. Fuentes identificadas en el índice final.

| Caso | Entrada y resolución | Medición / resultado | Límites y errores |
|---|---|---|---|
| Whisper, dos lecturas | `speech-speed-0.mp4` y `speech-speed-1.mp4`, copias de `show-talk-15.mp4`; 15,080 s, 640×360 a 25 fps. Modelo `small`, idioma español, VAD desactivado | Cronómetro exterior: **45,71 / 22,61 s**; un modelo residente; 4 / 8 segmentos; progreso hasta 100 | No son resultados de transcripción idénticos: no se interpreta la diferencia como ahorro controlado ni precisión mejorada. Resolución/duración verificadas ahora sobre el archivo conservado, sin retranscribir. |
| Show normal, exportación corta | `show-talk-15.mp4`, 15,080 s, 640×360; resolución final N/D | `show.elapsed_sec` **23,6 s**; salida **11,967 s**, 2 cortes, 1 muletilla retirada, 0 captions, gags desactivados | `warnings=[]`. El contador interno no se sustituye por un supuesto tiempo total de navegador. |
| Proxy local 0.19, sintético | `original.mp4`, testsrc2 **4 s**, 1920×1080, 30 fps; 7.767.117 bytes | Proxy **960×540**, 4 s, 178.910 bytes; reducción **97,7%** registrada. Receta apunta al original; original modificado se rechaza; sin red | Tiempo y RAM N/D. Caso artificial favorable a compresión, no porcentaje prometido para cámaras reales. Prototipo: no prueba un asistente público integrado. |
| Mixer FX, regresión 0.17 | `keys.wav` estéreo y `vocal.wav` mono, **3 s, 44,1 kHz** | Log: sin aumento seco de 3 dB, intensidad wet exacta y ambos efectos comprobados | Validación funcional, tiempo/RAM N/D. Sin BWF/bext: offsets asignados a cero con aviso; no demuestra sincronización automática de grabadoras desalineadas. |

## 5. Montara: aceptación Linux y sesiones largas

### Multicámara Stage y Mix

- **Stage, código `713b5ba`**, 27 de octubre, M-Linux: fixture real **`much-to-me`**, máster y tres cámaras (360/fija/móvil). Exportación **100,2 s, 1920×1080**, 17 cortes, intercambio de frames ejercitado, `passed=true`. **Tiempo de render y pico RAM N/D**; 100,2 s es duración de salida. Resoluciones originales y error residual de sincronización N/D. Ver [registro versionado del runtime](https://github.com/amehcgracia-byte/Montara/blob/aee68ae/docs/YOUTUBE_RUNTIME.md).
- **Mix, resumen local de integración**: mismo identificador `much-to-me`; salida **100,2 s, 1920×1080**, 19 cortes, master mezclado, tres cámaras usadas, intercambio verificado, `passed=true`. Commit exacto y tiempo/RAM N/D. No confundir esta ejecución con la de Stage ni inferir calidad sonora solo de `passed`.
- **CI final, código `552022c`**: [ejecución 40517716811](https://github.com/amehcgracia-byte/Montara/actions/runs/40517716811), cuatro recorridos aprobados: Stage, Push, Mix y Session; 115 tests Python y 6 de ciclo de preview. Es aceptación funcional Linux, no benchmark aislado de CPU/GPU o latencia de usuario. Fuente: [preparación 0.39](PRE_ABACUS_2026-10-27.md).

### Detección de cuatro horas: sintética, no jam real

**Medición**, 27 de octubre, M-Local. `stress-4h-summary.json` no registra commit exacto. Contexto de implementación: rama de sesiones 0.39; pins de integración final Editor `60a7b7e9a39077b36f45057811abd6a833a168ef` y Mixer `c7a46a6d8388c6e0703ef54983f2d627ea189f32` (**no** prueba de que el resumen se generó exactamente con el commit final).

Dos WAV sintéticos `Kick.wav` y `Bass.wav`, PCM16 mono a 8 kHz, **14.400 s cada uno**: cuatro horas de sesión / ocho horas-pista, **460.800.088 bytes** totales. Resolución de vídeo no aplica.

| Fase | Tiempo de detector | Propuestas |
|---|---:|---:|
| Fría | **8,42 s** | 23 |
| Caché reutilizada | **3,77 s** | 23 |

Pico registrado de hijos: **76.337.152 bytes ≈ 72,8 MiB**, `ru_maxrss` en macOS; máximo de hijos, no RAM total simultánea del sistema. No es memoria medida de un render. No se midió precisión contra canciones reales. Fuentes sintéticas grandes retiradas después; resumen conservado. No extrapolar a 30 GB, 12 instrumentos, mezcla/exportación o Abacus.

### Sesión completa y subida recuperable

**Validación funcional** local y Linux, documentada en 0.39 y CI `552022c`. Dos pistas sintéticas de **390 s** cada una; dos propuestas con frontera **195 s**. Tras revisión manual: ventanas **5–20 s** y **215–230 s**, dos MP3 de 15 s, reproducción del mixer, recuperación al recargar y vista móvil. Errores JavaScript: ninguno en el resumen.

Subida de `Upload-recovery.wav` (fixture de 30 s, 48 kHz, estéreo float, superior a 8 MiB) interrumpida a **4 MiB**, reanudada al volver a elegir el archivo, SHA-256 del recibido igual al original. **Velocidad de transferencia, duración del trabajo y pico RAM N/D**. Esto prueba recuperación de una subida pequeña; no una transferencia real de 30 GB ni ausencia de subida de originales.

## 6. Errores y resultados negativos que deben conservarse

| Caso | Evidencia y resultado | Qué no permite concluir |
|---|---|---|
| Render detenido de Zucker 2.5.6 | Informe de prioridades 1–2: cancelado con 176/177 segmentos; FFmpeg Sony unos 28 minutos sin CPU, pila esperando scheduler/threads | Causa específica de VideoToolbox no demostrada; no contar como render completado. |
| Primera tentativa ronda 3 | `render-round3-full-20261009`: último progreso segmento 152, 1204,02 s; sin resultado final ni causa establecida. Repetida en carpeta nueva | Excluida del A/B válido. |
| Calidad reducida en candidatos | Ronda 3: Metal flotante cambió píxeles; reducción temprana de zoom a 1080p mostró pérdidas (VMAF medio 71,61 en toma móvil 2) | Alternativas rechazadas: sus tiempos menores no son mejoras aceptadas. |
| Tests heredados Zucker | Ronda 3: 133 pasan / 10 fallos conocidos; configuración final 135 pasan / mismos 10 | No declarar toda la suite verde. |
| YouTube remoto | Código `713b5ba`: sin JS/EJS falló; con yt-dlp 2026.10.21, EJS 0.8.0 y Deno 2.5.6 desapareció el aviso de runtime, pero ambos IDs `TfuHvz7pd24` y `bfGH-664RQ4` siguieron devolviendo `LOGIN_REQUIRED` | No hay throughput de descarga exitoso. Una muestra cacheada no acredita importación nueva; OAuth/CAPTCHA no quedaron resueltos. Fuente: [YOUTUBE_RUNTIME.md](YOUTUBE_RUNTIME.md). |
| CI instala FFmpeg lentamente | [40516025987](https://github.com/amehcgracia-byte/Montara/actions/runs/40516025987): fallo al instalar dependencias, antes de probar aplicación; posterior 40517716811 aprobado | No atribuir ese tiempo al motor de vídeo. |
| Almacenamiento GitHub | Subida de artefactos alcanzó cuota en la campaña Linux del runtime; paso no bloqueante | Job aprobado no garantiza artefactos descargables. |
| Disco del sandbox, comunicado por usuario | `FFmpegError`: requiere aproximadamente 0,8 GB; volumen limitante 0,7 GB libres | **Incidencia reportada, no benchmark recuperado**: commit, entrada, tiempo, hardware y RAM N/D. No demuestra un defecto de códec. Rutas privadas omitidas. |

## 7. Índice de evidencia local, sin subir logs ni medios

Los informes de Zucker enlazados son evidencia secundaria versionada de mediciones previas. Sus directorios originales en disco externo no estaban accesibles al recopilar; no se afirma haber reabierto los masters. En Montara sí se leyeron los siguientes resúmenes/logs y scripts de prueba locales. Los nombres son relativos al archivo de trabajo del propietario, **no archivos nuevos incluidos en este repositorio**. Hashes permiten identificar el registro exacto sin publicar rutas personales, credenciales ni logs masivos.

| Identificador del registro | SHA-256 |
|---|---|
| `work/show-render-report.json` | `c4a2105355fa5ed92a4b86f6546659b78c02791e08536d789856b8b052e41e08` |
| `work/whisper-speed-report.json` | `ea8e874d678eaa2d85a27f40f9d2bed82e30e5f86a1db10a42127549f616adac` |
| `work/proxy-019.log` | `d0c32c6fb1c50004aec85d1469f8f057911b2b9c9e81643857cd331bfe46c72e` |
| `outputs/stage-runtime-e2e/summary.json` | `a9b2b44313c8b8e00d055561f1b26f1765e10fee1453b92ab10795eaf022972f` |
| `outputs/main-integration-e2e-local/summary.json` | `84d3279820f11239876d1c2c01d013cbd7a6c72c06a3c9b17bdacdd8f0bbc4d9` |
| `outputs/pre-abacus-039/summary.json` | `cfbd2e481082c9c5a6209ee66e906cecb598fbec5b3b42e7a4eb1133f1a416e1` |
| `outputs/pre-abacus-039/stress-4h-summary.json` | `169f4a1c6c5a71f1c0315d942cf548afccaa929f46b2fface38254c99dd38a0c` |

Scripts históricos consultados: `check_whisper_warm.py`, `check_show_render.py`, `check_proxy019.py`; log adicional `mixer-levels-017-regression.log`. Solo se transcriben resultados acotados. No se publican cuentas, tokens, cookies, URLs firmadas ni identificadores privados de proyectos.

## 8. Huecos pendientes de medición

Faltan pruebas controladas actuales de Montara con la misma sesión real en Mac y Linux: offsets y deriva residual, resolución/tamaño de cada original, tiempo por fase, pico RAM del árbol, disco máximo, tráfico y render frío/caliente. También faltan concurrencia, 30 GB y costes reales del proveedor. No se proponen cifras estimadas para rellenarlos. La detección acústica sintética, las validaciones de interfaz y los renders históricos de Zucker son categorías distintas y deben seguir separadas al planificar capacidad.
