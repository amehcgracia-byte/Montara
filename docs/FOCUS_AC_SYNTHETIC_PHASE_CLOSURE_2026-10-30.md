# FOCUS A/C — cierre fase sintética (2026-10-30)

## Hallazgo final: no había error en la duración de exportación
El operador inspeccionó el manifiesto: 6 segmentos suman **20.0 s**; MP4 final **40.2 s** (H.264 1920×1080 30fps; AAC mono 48000Hz). El exportador Zucker anclado declara en `core/stages/export.py` `INTRO_DURATION=10.0` y `OUTRO_DURATION=10.2`. Por tanto **20.0 + 10.0 + 10.2 = 40.2 segundos** exactamente.

`performance.phases.intro_sec=12.777`, `outro_sec=4.602` representan **tiempos de proceso**, no duraciones en pantalla; no utilizarlos para reconciliar duración. La auditoría inicial `REVIEW_REQUIRED` era un falso negativo por comprobar 20.0 contra 40.2 sin incluir bookends. Se corrigió el script `focus_ac_final_export_audit.py` para esta modalidad YouTube con branding; **pendiente ejecutar de nuevo el script corregido** con nuevo nombre de reporte, sin sobrescribir el antiguo. No afirmar que el nuevo resultado fue ejecutado si no lo ha sido.

## Evidencia completada
- Dos originales sintéticos 1280x720, proxies 360p, 20 segundos.
- `EditStage.run` auténtico sobre proxies: PASS; seis segmentos; campos semánticos originales/proxy idénticos (0 diferencias en comparación acotada).
- `ExportStage.run` auténtico: MP4 de 50,838,395 bytes tras **45.325 s**.
- Manifiesto: **6/6** `rendered_from=original`, **6/6** `cached=false`; FFmpeg encoder aplicado a originales, no a proxies.
- Comprobación de contenedor: H.264 1920x1080 30fps, AAC mono 48k, 40.2 s.
- Git limpio al fin de las ejecuciones.

## Estado y límites
**Fase sintética funcionalmente demostrada**: proyecto proxy-authored, export desde originales, duración explicada, metadatos esenciales correctos. No se han validado audio escuchado, identidad visual fotograma a fotograma ni todas las variantes del producto. No demuestra aún flujo completo con iPhone 4K rotación, Sony 1080p, cámara 360 HEVC ni sincronización real multicámara. No confundir mejora de tiempo con prueba causal de speed-up.

## Chema
Reservar informe consolidado hasta pruebas reales; OPT-08 aparte. No tocar main, engine ni mixer.
