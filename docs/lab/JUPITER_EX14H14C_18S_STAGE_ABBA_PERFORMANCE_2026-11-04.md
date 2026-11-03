# JÚPITER — EX-14H-14C: Stage real 360, ABBA de 18 segundos

**Registro:** 2026-11-04. Laboratorio FER, motor aislado `0f9ec03`, VM GCP 8 vCPU / ~31 GiB RAM. **No hay cambios productivos**. Reutiliza harness `ex14h14b_long_360_windows_abba.py` con `--mode performance --duration 18 --window-start 600`. El script imprime nombres `EX14H14B_*` porque se reutiliza: el ensayo se identifica en bitácora como EX-14H-14C.

Fuente original HEVC 360 3840×1920 (duración 911.64 s), ventana 600–618 s; 540 fotogramas a 30 FPS; Stage Reel horizontal 1920×1080, master audio 20.0 s. Una ejecución secuencial por vez; ABBA comparando flags opt-in EX07/13 A(false/false) vs B(true/true); sin hooks de hashes pesados en rendimiento.

## Resultado completo

| orden | Variante | Stage wall (s) | Segment FFmpeg (s) | Export wall (s) | bytes MP4 |
|---:|---|---:|---:|---:|---:|
| 1 | A | 48.168 | 40.797 | 48.163 | 39509539 |
| 2 | B | 41.173 | 34.082 | 41.168 | 39510637 |
| 3 | B | 40.642 | 33.543 | 40.637 | 39511070 |
| 4 | A | 47.309 | 40.223 | 47.304 | 39510745 |

**Stage** A mean 47.7385 s; B mean 40.9075 s; diferencia **6.831 s**, reducción **14.31%**. 
**Segment FFmpeg** A mean 40.510 s; B mean 33.8125 s; diferencia 6.6975 s, reducción **16.53%**.

Todas las 4 exportaciones: 540 cuadros válidos, `native_calls` sobre original HEVC, sin warnings, PCM audio idéntico SHA256 `7baf85bb2f845114595444b4f109180f8c0ddeaedb1340f8f97e82c469eb9be4` y 3457024 bytes. Los hashes RGB de vídeo final difieren entre A/B y también A/A, variación conocida posterior al remap. **Este ensayo no demuestra fidelidad preencoder a 18s**, pues no se instrumentó para ese fin: debe ejecutarse por separado `--mode fidelity --duration 18 --window-start 600`.

Inicio: disco libre 18.66 GiB; RAM disponible 30.37 GiB. Fin: `EX14H14B_RESULT ... temp_media_cleaned=true`, `EX14H14B_COMPLETE`, `EX14H_14C_ABBA_18S_COMPLETADO`.

## Interpretación, límites, puertas

La mejora observada en Stage es 14.31% sobre este tramo; el ensayo previo de 15 s sobre ventanas 600 y 840 tuvo reducciones de 10.92% y 12.69% (combinada 11.80%); ensayo 2 s EX14H11F 11.37%. **No inferir que la aceleración crece sistemáticamente con la duración** ni extrapolar fuera del original, proyección, CPU, flags o Stage. Solo 2 corridas por brazo; no se ha medido una Jam multicámara completa ni perceptual final.

Puerta siguiente: correr fidelidad real EX14H14C 18s / 540 frames en ventana 600 (A vs B, hashes de input BGR, mapas y preencoder BGR), audio PCM; cuando PASS, cerrar fase de este HEVC y pasar a otras fuentes 360 o jam real. Advertencia: apagado externo macOS por `gcloud instances stop` documentado en issue #71, no impedido por los checks locales.
