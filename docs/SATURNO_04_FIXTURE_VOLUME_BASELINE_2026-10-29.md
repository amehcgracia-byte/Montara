# SATURNO-04 — Primera línea base de volumen del fixture (2026-10-29)
**Resultado:** inventario verificable desde el árbol Git de la rama `fernando/continuacion-montara`, prefijo `tests/fixtures/much-to-me/`. Esto mide **tamaños de blobs**, NO una ejecución del motor ni tamaño de un paquete mínimo.

| Material | Archivos | Bytes |
|---|---:|---:|
| Cámaras (Sony, fija y 360) | 3 | 5.077.434 |
| Audio (master.mp3 + 9 stems MP3) | 10 | 11.704.754 |
| **Total** | **13** | **16.782.188** |

Las cámaras individualmente pesan `cam-sony.mp4=2387940`, `cam-fixed.mp4=1416641`, `cam-360.mp4=1272853`. El master pesa `1601436` bytes. Stems: ocho ficheros de `1122795` bytes y `Keys-R.mp3=1120958` bytes. **Este material es un fixture privado, con imágenes 640×360 pixeladas, no un concierto original de 80 GB**; según `README.md` representa aproximadamente 80 s de canción.

Procedimiento: consultar GitHub Git Trees API para el commit fijado de la rama, filtrar `type=blob`, sumar `size` por extensiones. Código publicable: `experiments/saturno_04/fixture_inventory.py`. El prototipo local del inventario fue probado con 4 tests unitarios (**4/4 PASS**) en Linux; las pruebas del archivo recién versionado no se han ejecutado en CI.

**Límites:** no hay `edit_plan.json` junto al fixture para calcular intervalos usados. No se ha ejecutado `ExportStage.run`, ni medido CPU, RAM, tiempo de render, bitrate efectivo, ni generado paquete parcial compatible. Los `size` de los blobs no prueban que los medios decodifiquen sin errores ni la tasa real de transferencia.

**Mediciones pendientes, en orden:** (1) generar/congelar plan de edición real con hashes para fixture sin tocar motor; (2) ejecutar render A sobre proyecto QA y registrar tiempo, FFprobe y checksums; (3) inventariar intervalos usados por fuente y bytes requeridos con dependencias; (4) repetir en local con paquete B aislado y motor auténtico; (5) evaluar E2E remoto y costes reales al existir hardware y autorización. Separar explícitamente `measured`, `modeled` y `blocked`.

Referencias: `tests/fixtures/much-to-me/README.md`, `docs/SATURNO_04_BREAK_EVEN_DECISION_2026-10-29.md` y `docs/SATURNO_03D_ZUCKER_REAL_E2E_GATE_2026-10-29.md`.
