# JÚPITER-17 — Perfilado focalizado de interpolación 360 (28-10-2026)

## Hipótesis falsable
Sustituir la interpolación `lanczos` por `linear` (bilineal) o `cubic` (bicúbica) dentro del filtro FFmpeg `v360` puede acelerar la reproyección de planos 360. **Condición necesaria** para cambiar Montara: mantener calidad aceptable en sujetos, texturas, movimiento y todos los formatos relevantes. No extrapolar a render total.

## Código auditado, pin inmutable
`amehcgracia-byte/zucker_videos@60a7b7e9` `core/stages/export.py:3747-3780` `_export_source_filter` emite `v360 ... w=1920:h=1080:interp=lanczos` para `equirect` y `raw_insv`. `_v360_motion_commands` ~3479-3540 usa `sendcmd [expr]` para movimiento por frame. `_spherical_export_source_info` ~2157-2265 cachea fuentes equirect para planos no-nativos, con `interp=lanczos` para conversión dfisheye; `_spherical_uses_original_motion` ~2138 evita preparación redundante para movimiento original. No reinventar estos mecanismos.

## Ejecución real en Linux del asistente (NO motor completo)
FFmpeg 7.1.5, filtro `v360` instalado. Fuente sintética 2 s a 1920x960, 24 fps, H.264 testsrc2. Reproyección fija yaw 35°, pitch 12°, FOV 100°x62°, salida 960x540 yuy420. Tres variantes de interpolación. FFmpeg `-h filter=v360` confirmó `line/linear`=bilinear, `cube/cubic`=bicubic y `lanc/lanczos`=Lanczos.

Primer ensayo, archivo sin compresión NUT (incluye I/O 37.3 MiB): lanczos **0.556 s**, cubic **0.517 s**, linear **0.284 s**. Mismos tamaños de salida. Comparación contra Lanczos con filtros FFmpeg PSNR y SSIM: cubic PSNR **54.235742 dB**, SSIM All **0.997110**; linear PSNR **49.619590 dB**, SSIM All **0.997434**. **Esas métricas solo son distancia a Lanczos, NO pruebas de fidelidad a una verdad-terreno.** La inversión de ranking PSNR y SSIM muestra por qué no debemos usar una única métrica de calidad.

Ensayo repetido sin I/O de archivo, salida `-f null -`, mismo origen y `v360`, 15 ejecuciones en orden seudoaleatorio de 5 por método (semilla 1729), wall seconds incluyendo inicialización y decodificación:
- lanczos: [0.290,0.310,0.327,0.306,0.330] → mediana **0.310 s**
- cubic: [0.292,0.303,0.412,0.356,0.282] → mediana **0.303 s**
- linear: [0.184,0.193,0.186,0.198,0.189] → mediana **0.189 s**

Linear requiere ~39% menos tiempo **solo en esta prueba sintética de reproyección**. Bicubic no ofrece una mejora robusta frente a Lanczos (2% en mediana, ruido de medición comparable). Carga muy breve: no hay inferencia estadística sobre vídeos reales, ni escenas granulares, ni motion, ni calidad perceptual. El ensayo usa 960x540 y fuente 1920x960, mientras motor final usa 1920x1080 desde originales 5K/6K; diferencia crítica. No confundir proporción de reproyección con aceleración total del render.

## Decisión
**DESCARTAR bicubic como prioridad de optimización por ahora; mantener bilinear como hipótesis para borradores/preview o selector de calidad, jamás reemplazo universal del modo final sin validación.** No tocar los motores ni los pins. No usar viewport tiles streaming como sustituto de esta prueba.

## Próximo gate con alto valor
1. Montar fixture equirect **5K/6K** o material 360 autorizado con caras, cables, letras y detalle fino; rutas real y proxy, vistas estáticas y con movimiento `sendcmd`. Calidad comparar contra Lanczos y capturas de bordes; si se puede, referencia perceptual, no solo SSIM.
2. Probar costo total (decode→v360→filtros→libx264→mux) en export `1920x1080`, no solo `-f null`. Medir cold/warm, memoria, tiempos, salida y artefactos en 3+ rondas reproducibles.
3. Si impacto sustancial y calidad viable, preferir `linear` **solo en draft/preview**, versionando la receta de caché y comprobando el contrato de export final. En el motor ya hay modo draft y la distinción de pixeles para movimiento original.
4. Si la decodificación domina, este cambio podría no ahorrar casi nada: abortar pronto si el A/B integral lo demuestra.

**Observación científica:** la conclusión útil por ahora no es «Montara 39% más rápido», sino «la reproyección bilineal aislada fue más rápida en este fixture; merece comprobación en la exportación real; bicubic no parece prioridad».
