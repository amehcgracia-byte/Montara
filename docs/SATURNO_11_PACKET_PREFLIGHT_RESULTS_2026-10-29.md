# SATURNO-11 — Entradas del plan real equivalentes, todos los GOP necesarios

Run [40886014059](https://github.com/amehcgracia-byte/Montara/actions/runs/40886014059),
job 123489800215, commit 05567cc0e6c8a232115ad48178f4852ff9d2393d.
Resultado **PASS_INPUT_PREFLIGHT**. NO es todavía export A/B completo.

## Resultados reales
| Fuente | Bytes original (incluye audio de cámara) | Bytes paquete vídeo | GOP retenidos | Paquetes retenidos |
|---|---:|---:|---:|---:|
| Sony | 2387940 | 1595299 | 10/10 | 2325/2325 |
| Fija | 1416641 | 599803 | 10/10 | 2376/2376 |
| 360 | 1272853 | 454633 | 10/10 | 2400/2400 |

Los 19 planos pasan la comparación de entradas decodificadas (7/5/7).
Payload comprimido y PTS/DTS de TODOS los paquetes conservados exactos.
Duración del contenedor igual para cada fuente. Coeficientes de color nativos exactos.
La ruta de decodificación 360 se prueba con el mismo seek, fps30/bgr24 y número
de frames. No se confunde con la reproyección/compresión final, aún pendiente.

## Hallazgo importante y límites
La unión conservadora de ventanas de montaje/color y GOP de inicio/final requiere
los diez GOP de CADA fuente. **No se ha omitido ningún paquete de vídeo**.
La fracción de payload de vídeo retenido es 1.0. No llamar a esto ahorro por
recortes de imágenes: el ahorro medido viene de retirar audio de cámara, que ya
no se necesita al exportar el plan fijo con su máster sincronizado.
El método NO demuestra minimalidad del grafo de referencias H264 ni imposibilidad
de otro empaquetado. Tampoco permite extrapolar esta proporción de ahorro a 4K,
otros GOPs o al proyecto hipotético de 80 GB.

## Tamaño medido
- Originales de tres cámaras + máster: 6678870 bytes.
- Paquete de vídeo + máster completo: 4251171 bytes (**36.349 % menos**).
- Plan/proyecto serializados del paquete: 472057 bytes.
- Medios + esos JSON: 4723228 bytes (**29.281 % menos**).
- Todavía no incluye transport manifest ni assets adicionales. No es coste de red.
- Preparación + comprobación de ventanas: 10.8355 s (no solo empaquetado).

El máster completo de 1601436 bytes se cuenta, porque el plan usa toda la canción.
Este paquete sirve a un export de plan fijo, no promete resincronizarlo sin audio
de cámara. El preflight recalcula color bajo identidad B, pero no está aislado:
el siguiente ensayo C debe ocultar originales/caches y cubrir la ruta nativa 360.

## Siguiente ensayo justificado
SAT-12 generará A/A del MISMO plan y solo si es estable ejecutará B aislado.
No repite UI, ingest, sync ni decisiones creativas. Acreditará portabilidad del
montaje multicámara/360 para ESTE paquete, manteniendo explícito que conserva
todo el vídeo comprimido. Medirá ZIP y tiempos de render, sin afirmar economía remota.

Evidencia estructurada: experiments/saturno_10/packet_results_40886014059.json.
No hay cambio en main/motores ni autorización para modificar producción.
