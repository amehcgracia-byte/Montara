# SATURNO-16 — seis ventanas 360: resultados verificados

Fecha: 2026-10-29. Fuente: https://github.com/amehcgracia-byte/Montara/actions/runs/40909761086 (job 123574209594).
Workflow terminado: success. `SATURNO16_SUMMARY`: `SIX_WINDOWS_AB_EXACT`; error=null.

Pregunta: ¿añadir solo `-fps_mode passthrough` elimina la divergencia A/B en las seis ventanas 360 divergentes?

| Segmento | Frames | A/B sin control | A/A passthrough | A/B passthrough |
|---|---:|---:|---:|---:|
| 0003 | 278 | 47 | 278 | 278 |
| 0006 | 96 | 17 | 96 | 96 |
| 0008 | 242 | 41 | 242 | 242 |
| 0012 | 263 | 45 | 263 | 263 |
| 0016 | 290 | 49 | 290 | 290 |
| 0019 | 90 | 16 | 90 | 90 |
| TOTAL | **1259** | **215** | **1259** | **1259** |

Todos los cinco procesos por segmento produjeron la cantidad requerida de cuadros. Primera diferencia A/B sin control: índice 1 en los seis casos. Comparación passthrough A/A repetida exacta y A/B exacta en los seis. FFmpeg instalado en runner; entrada y paquete según receta verificada por script. No se modificaron motores. Ninguna reproyección ni renderización del montaje en este experimento.

**Conclusión limitada:** la intervención de una sola opción recupera igualdad BGR de las seis ventanas que divergían en SATURNO-12. No certifica igualdad de píxeles después de la reproyección, el resultado MP4 completo, la portabilidad selectiva de GOP, ni las métricas reales del hito D.

**Siguiente gate:** control QA *solo en memoria* del decodificador 360 usado por el renderizador real, para verificar el comportamiento tras reproyección y export A/B del plan guardado. Diseñar antes la instrumentación, con comprobación de que solo se modifica esa opción; no editar `engine`.

**Mejora operativa propuesta:** futuros workflows deben escribir un resultado compacto persistente en una ruta previsible de la rama al terminar, con run ID y commit probado, para que el asistente consulte `fetch_file` sin necesitar que el usuario facilite el enlace. Requiere permisos `contents: write` y push restringido a esta rama; evitar `workflow_dispatch` duplicado y bucles por paths.
