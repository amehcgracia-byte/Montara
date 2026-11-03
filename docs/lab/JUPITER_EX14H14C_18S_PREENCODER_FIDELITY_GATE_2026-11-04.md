# JÚPITER — EX-14H-14C: fidelidad 18 segundos A/B, cierre de gate sobre HEVC original

**Registro:** 2026-11-04. Ensayo FER GCP 8 vCPU, motor experimental aislado `0f9ec03`, sin cambios a rama productiva. Se reutiliza el runner `ex14h14b_long_360_windows_abba.py`, por lo que el log imprime `EX14H14B_*` aunque esta fase se denomina EX14H14C.

## Diseño y alcance

Fuente real HEVC original 360 equirectangular 3840×1920, duración 911.64 s. Tramo 600–618 s (18 s, 540 frames 30 FPS), Stage Reel 1920×1080, master audio 20 s. A = flags opt-in fast_wrap/smart_unwrap desactivados, B = activados. Instrumentación SHA256 del flujo BGR decodificado, mapas x/y, BGR reproyectado preencoder, además del audio PCM. Corridas secuenciales A-B, sin edición de producción. Disco libre inicial 18.66 GiB, MemAvailable 30.35 GiB.

## Resultado PASS

- **A**: Stage wall 59.284 s, segmento 52.199 s, 540 cuadros, `map_calls=540`, output 39510531 bytes.
- **B**: Stage wall 52.144 s, segmento 45.092 s, 540 cuadros, `map_calls=540`, output 39509652 bytes.
- **Input BGR exact A/B** SHA256: `59b66a39db04b0c0ae84e49f2e528e85f7f6661b606010ea147a03d2c853e3f9`.
- **Mapas exactos A/B** SHA256: `10ca1aaec3b51f84fac17ea03fbdefb08ef16f6c0c80a866a213a497cf9bc42c`.
- **BGR reproyectado preencoder exacto A/B** SHA256: `56134402afa56fd244233010c04cf31255e8bcc3c54b41105aa4826a41e1ef30`.
- **Audio PCM exacto A/B** SHA256: `7baf85bb2f845114595444b4f109180f8c0ddeaedb1340f8f97e82c469eb9be4`; 3457024 bytes.
- Ambas exportaciones 540 cuadros, sin warnings. Los hashes RGB de salida MP4 codificada/decodificada son diferentes, como se vio incluso A/A y B/B en pruebas anteriores. No se ha validado equivalencia bit-exact del MP4.
- Fin `EX14H14B_RESULT` con `temp_media_cleaned=true`, `EX14H14B_COMPLETE`, `EX14H_14C_FIDELIDAD_COMPLETADA`.

Los timings de estas 2 corridas **contienen hashing pesado y no son mediciones de rendimiento**. Benchmark independiente 18 s `--mode performance` mostró 47.7385 s A, 40.9075 s B, ahorro 6.831 s, **14.31%** Stage, **16.53%** segmento. Dos ABBA sin instrumentación de 15 s anteriores mostraron mejoras Stage **10.92%** (600–615s) y **12.69%** (840–855s), combinada **11.80%**. ABBA 2s anterior 11.37%.

## ¿A mayor duración, mayor % de mejora?

No confirmado. La serie 2/15/18 s sugiere posibilidades pero mezcla ventanas, ruido de rendimiento, características de decodificación y overhead fijo. Los 15s con igual duración ya difirieron 1.77 puntos porcentuales. La reducción fija/pixel puede amortizar costes por segmento, pero se requieren ABBA repetidos, varias duraciones sobre mismo tramo/movimiento, fuentes diversas y control de frecuencia/carga para estimar función duración vs mejora. No presentar la pendiente de estos 4 puntos como ley física.

## Decisión

**Gate de fidelidad y aceleración Stage sobre este único HEVC original superado** hasta 18s de movimiento virtual y 540 cuadros. Aún falta validación de fuentes 360 distintas, perfiles de movimiento/presets, exportación multicámara real y evaluación perceptual del vídeo final. EX07/13 permanecen opt-in y sin merge por Chema. EX06 bilinear sigue separado por alterar vídeo. Siguiente dirección recomendada: diversidad de material real 360 y luego jam completa, en lugar de continuar variando duración del mismo archivo. Issue de apagado externo GCP #71 sigue relevante.
