# JÚPITER — EX-14H-14B fidelidad Stage 360 15 s, dos ventanas y aviso VM

Fecha: 2026-11-03. VM 8 vCPU, 31 GiB RAM; laboratorio FER en checkout aislado del motor `0f9ec03`. Original 360 HEVC 3840x1920, duración 911.64 s. Fixture master audio 20.0 s. Dos ventanas, desde 600 s y desde 840 s, duración 15 s cada una; Reel horizontal 1080p30, 450 cuadros, A/B flags opt-in EX07/EX13 OFF/ON. Instrumentación SHA256 de BGR decodificado, mapas de coordenadas y BGR reproyectado antes de H264.

## Resultado
| Tramo | A Stage (s) | B Stage (s) | Segmento A (s) | Segmento B (s) | B ahorro Stage observado |
| --- | ---:| ---:| ---:| ---:| ---:|
| 600–615 s | 54.789 | 48.647 | 47.167 | 41.225 | 11.21% |
| 840–855 s | 56.174 | 46.873 | 48.598 | 39.478 | 16.56% |

**Fidelidad PASS 2/2 ventanas**:
- Entrada HEVC BGR idéntica A vs B, 450/450 cuadros por ventana.
- Mapas de coordenadas idénticos A vs B: 450/450 por ventana, 900 equivalencias de mapas.
- BGR preencoder idéntico A vs B, 450/450 por ventana, 900 equivalencias de fotogramas.
- Audio PCM SHA256 idéntico en las 4 exportaciones: `267b89c2ce251dfe3511c50335acd4297a2bbfa7f2a26503bd576d3f3d0c6b12`. Vídeo de salida válido 450 cuadros; los hashes finales RGB difieren A vs B tal como se vio en los estudios de los filtros/encode posteriores a remap.
- Para cada ejecución 450 mapas, cámara en movimiento. Los dos tramos comparten un camino virtual y por ello su stream de mapas tiene el mismo hash `4d41d24f4d09dc3cb2542251b414e604d0adbcae44105e7dc40ae73ec1ea6b63`, aunque sus entradas BGR reales difieren.

**ADVERTENCIA:** los tiempos contienen hashing de cientos de MB de BGR/mapas; un A/B por tramo, no hay estimación definitiva de rendimiento. Para valorar velocidad, realizar modalidad `--mode performance --duration 15` sin hooks y ABBA en cada ventana. El 11.37% de EX14H11F es referencia previa sin instrumentación a 2 s.

## Integridad y limpieza
Se imprimieron `EX14H14B_RESULT`, `temp_media_cleaned=true`, `EX14H14B_COMPLETE` y `EX14H_14B_FIDELIDAD_COMPLETADA`. El script terminó las cuatro exportaciones y limpió sus temporales correctamente. Comprobó más de 12 GiB libres durante ejecución, 18.66 GiB al inicio.

## Incidente de VM separado
FER informa de que GCP apagó la VM inesperadamente **antes** de esta ejecución, pese a sesión SSH web activa. No hay aún atribución causal ni hora exacta UTC. Issue diagnóstico a Chema/IA: https://github.com/amehcgracia-byte/Montara/issues/71. No atribuir el apagado a EX14H14B; se completó después del reinicio. Priorizar auditoría de apagado antes de nuevas pruebas largas.

## Próximas puertas
- Diagnóstico VM/autoshutdown (#71), antes de benchmarks no supervisados.
- ABBA de rendimiento a 15 s cuando la VM esté estable.
- Opción 18 s con audio máster 20 s, también tras estabilidad. No empezar con 20 s justo en el límite de duración del audio sin revisar tolerancias/mux.
