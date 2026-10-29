# SATURNO-16 — protocolo de seis ventanas 360

Pregunta: ¿añadir únicamente `-fps_mode passthrough` elimina las diferencias A/B del decodificador en los seis segmentos divergentes de SATURNO-12 (0003,0006,0008,0012,0016,0019)?

El script `experiments/saturno_16/six_windows.py` verifica hashes de originales, paquete y plan; conserva todos los GOP; ejecuta cinco decodificaciones por segmento (A/B exactos, A/A/B con passthrough), cuenta cuadros y compara SHA256 BGR por índice. No aplica poses, reproyección, encode ni export. No acredita ahorro selectivo ni equivalencia final. Un resultado positivo en las seis ventanas permitirá diseñar una prueba controlada del render completo sin modificar `engine`.

Se usa Ubuntu 24.04, FFmpeg apt y engine fijado a `60a7b7e9a39077b36f45057811abd6a833a168ef`. Un único workflow por modificación de su propia ruta. Evidencia: `SATURNO16_SUMMARY` y `SATURNO16_REPORT_BEGIN/END` en logs. No se suben artefactos. Tokens reales no disponibles.
