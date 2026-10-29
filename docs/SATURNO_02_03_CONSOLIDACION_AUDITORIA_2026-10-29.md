# SATURNO-02 y SATURNO-03 — consolidación de evidencia y auditoría de reproducibilidad
**Fecha:** 2026-10-29 · **Estado:** experimentos sintéticos reproducidos localmente; **NO** integración Montara/Zucker completa. **Solo rama experimental**.

## Inventario y procedencia

Se recuperaron los scripts y resultados originales del entorno de trabajo, y se repitieron en Linux x86_64 con FFmpeg **7.1.5**. El archivo ZIP `MONTARA_SATURNO_02_03_REPRODUCIBLE_2026-10-29.zip` se adjuntó en la conversación y contiene 22 entradas de código, informes, JSON y logs junto a un manifiesto de hashes SHA-256. **El ZIP no está alojado en GitHub ni sus scripts se han incorporado individualmente a esta rama**; pedir copia al propietario del experimento antes de afirmar reproducibilidad independiente. SHA-256 del ZIP: `7de2e1b27117aab61f9304b528e354209c1bb8b6ab4bbe95f1f20ca9d8eab5e7`.

Los scripts originales emplean rutas absolutas `/mnt/data/saturno02` y `/mnt/data/saturno03`, por lo que deben ejecutarse en un espacio QA compatible o adaptarse explícitamente a un entorno nuevo. Los medios sintéticos son **regenerables pero no archivados**: no atribuir el mismo hash a fuentes regeneradas sin verificarlo.

## Registro de ejecución de esta consolidación

Ejecutados secuencialmente y con **código de salida 0**:
1. `python /mnt/data/saturno02/battery.py`: genera cinco medios sintéticos y un caso A/V AAC, sus copias y versiones decodificadas. **Advertencia:** su medición `copy_frames` vuelve a recortar antes de contar; no es el recuento bruto del archivo copiado.
2. `python /mnt/data/saturno02/audit_v3.py`: referencia independiente seleccionando por PTS y contrastando hashes de píxeles; exige 5/5 casos exactos y control negativo sobre audio.
3. `python /mnt/data/saturno03/isolated_trial.py`: compara los fotogramas y muestras presentes en paquetes stream-copy con referencias de origen; calcula posiciones **usando el original en el productor**, no un algoritmo autónomo de selección de dependencias.
4. `python /mnt/data/saturno03/isolated_final_v2.py`: reconstrucciones de vídeo/audio para pruebas aisladas de contenido.
5. `python /mnt/data/saturno03/av_chroot_v3.py`: combina H.264 + audio ALAC 16-bit en MP4, dentro de `chroot` Linux x86_64 con UID/GID 65534; comprueba 60/60 fotogramas, 96.000 muestras, y negativa de acceso a la ruta del original.

### Matriz de evidencia
| Caso | SAT-02, referencia de píxeles tras decode-trim | SAT-03A paquete incluye secuencia exacta | SAT-03C MP4 con A/V en chroot |
|---|---|---|---|
| H.264 GOP1 | Sí | Sí | No probado |
| H.264 GOP120+B | Sí | Sí | **Sí: 60 fotogramas, 96.000 muestras de referencia** |
| HEVC GOP120+B | Sí | Sí | No probado |
| VFR sintético | Sí | Sí | No probado |
| Equirectangular sintético | Sí, sin remap | Sí | No probado |

**Corrección metodológica obligatoria:** la batería original `battery.py` reaplicaba un recorte al archivo por copia antes de contar fotogramas. Por ello el conteo `copy_frames=60` NO describe el contenido bruto del paquete, que puede conservar referencias y material extra. La auditoría V3 compara decodificación fuente y recorte con un filtrado consistente; resultados históricos de recuentos VFR pueden variar por método y requieren inspección específica. **No comparar archivos MP4 byte a byte cuando solo se ha demostrado identidad de píxeles/audio decodificados.**

La prueba de `chroot` es aislamiento de rutas, **NO** una sandbox completa ni defensa contra atacante privilegiado; necesita root para prepararse y se ejecutará únicamente en VM de QA. La causa exacta de un fallo inicial de 59/60 fotogramas y un hash PCM distinto no quedó causalmente aislada; la parametrización final explícita 30 fps CFR y ALAC 16-bit pasó en este fixture. **No aplicar CFR a VFR genérico.**

## Gates para SATURNO-03 definitivo
- [x] Referencia de píxeles y muestras en medios sintéticos, controles negativos
- [x] MP4 unido A/V bajo prueba limitada de aislamiento de rutas
- [ ] Paquete automatizado calculado por dependencias codec/PTS sin heurística basada en cotejar hashes del original tras generar paquetes
- [ ] Confinamiento verificado para todas las fuentes/activos/cachés de proyecto; no solo la ruta probada
- [ ] Audio/vídeo sincronizados frente a tiempo absoluto de referencia común, además de igualdad de secuencias
- [ ] Export **real** de Zucker desde paquete reducido y proyecto clon QA sin acceso a medios completos
- [ ] Prueba de 360 con motion + B-frames/HEVC/VFR reales
- [ ] Transferencia de red, preparación, render, verificación, descarga, disco, factura

## Política de revisión
Señalar claramente hipótesis, resultados históricos, ejecución reproducida y ausencia de medición. **No fusionar al motor ni main** como parte de este archivo; no incluye modificación alguna del motor. El informe de `docs/SATURNO_00_REVISION_CIENTIFICA_TRANSFERENCIA_RENDER_2026-10-29.md` continúa siendo el fundamento teórico. El PR #6 trata exclusivamente benchmarks históricos y **no contiene** estas nuevas pruebas.
