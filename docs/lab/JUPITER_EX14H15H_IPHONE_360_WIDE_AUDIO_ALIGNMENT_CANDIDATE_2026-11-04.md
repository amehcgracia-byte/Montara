# JÚPITER EX-14H-15H — candidato de alineación real iPhone / 360

Fecha: 2026-11-04. Laboratorio FER, fuentes originales sin copias ni exportaciones:
- iPhone `IMG_0044.MOV`: H.264, 3840x2160, audio AAC 44.1k mono, 986.825s.
- Esférica `VID_20260824_204524_00_004.mp4`: HEVC, 3840x1920, AAC 48k estéreo, 911.64s.

## Metodología

Búsqueda independiente del motor usando ffmpeg para decodificar PCM mono 4kHz de ventanas 360 de 30 s con inicios 40, 340 y 640 s. Audio iPhone de rango temporal desplazado desde -20 hasta +210s; filtro pasabanda Butterworth 150–1500Hz, scipy correlate FFT en modo `valid`, normalización por energía del tramo iPhone de cada posición. Se devuelven cuatro máximos de correlación absoluta separados al menos 6s.

## Datos observados

| Ventana 360 | Offset candidato principal (iPhone t=360 t + offset) | Correlación principal | Correlación segundo |
|---|---:|---:|---:|
| 40–70s | -19.033s | 0.2368 | 0.0273 |
| 340–370s | -19.049s | 0.1775 | 0.0331 |
| 640–670s | -19.017s | 0.2604 | 0.0583 |

Media offset `-19.033s`. Amplitud entre tres estimaciones 0.032s (32ms) sobre 600s de separación entre extremos. Los picos principales son significativamente más altos que los segundos candidatos (ratio aprox 4.5–8.7 según ventana). **CANDIDATO FUERTE, AÚN NO VALIDADO**.

**Advertencia de límite:** la búsqueda comenzaba en `OFFSET_MIN=-20` y el máximo aparece a solo ~1s del borde. Es imprescindible repetir con `OFFSET_MIN=-60` (con ventanas cuya posición 360 haga legal `t-60>=0`) y validar el desfase mediante correlación directa con ventanas alineadas, además de control contrafactual para +97s. Se recomienda una búsqueda de margen ancho sobre 360 starts 80, 340, 640. Para los tres segmentos comparar offset real estable y posibles desviaciones progresivas por clock drift.

El resultado contradice estimación preliminar de +97s derivada de timestamps `creation_time`; no se debe considerar esa estimación verdad de terreno. Los dos equipos pueden tener relojes desajustados o metadata que no refleja el inicio; no concluir todavía por qué.

## Riesgos / próxima puerta

1. Ampliar ventana inferior a -60 y repetir 3 momentos (sin archivos temporales).
2. Verificar que el máximo no se mueve hacia el nuevo borde; verificar correlación con señales filtradas y desfase -19 en ventanas coincidentes.
3. Revisar periodicidad musical y desplazamiento temporal, reforzar con detección de transitorios o escucha/visual si procede.
4. Solo tras validación comparar con SyncStage real e integrar proyecto iPhone+360 en entorno aislado. No usar mapas `sync:done` heredados de fixtures de 20s.
5. Mantener política de disco >12GiB libres, proteger trabajos largos contra shutdown GCP externo.

Ningún código productivo modificado.
