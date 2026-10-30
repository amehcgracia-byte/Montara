# JÚPITER-E2E-01 — Stage sintético, primer recorrido integral (2026-10-30)

## Alcance y entorno
- Laboratorio GCP compartido montara-test, Ubuntu 24.04.5, usuario `fer`.
- Rama: `fernando/continuacion-montara` HEAD `c22ba79`.
- Submódulos: engine `c89e7791ff6200e29c4281b79e84307277f9527f`, mixer `c7a46a6d8388c6e0703ef54983f2d627ea189f32`.
- Playwright Chromium headless `141.0.7390.37`; se instalaron los paquetes del sistema necesarios para su arranque (libnspr4, libnss3, libatk1.0-0t64, libatk-bridge2.0-0t64, libatspi2.0-0t64, libxcomposite1, libxdamage1). `apt` no solicitó reiniciar servicios.
- Script `tests/e2e_journey.py`, con `--mode stage --synthetic --output /home/fer/montara-e2e-01`, ejecutado dentro de `montara-bench FER-JUPITER-E2E-01`. Servidor temporal en puerto aleatorio con datos separados, no los servicios 8101/8102.
- Se observó carga concurrente de FFmpeg/Gunicorn en el entorno de `jm` durante el E2E; el bloqueo de laboratorio solo coordina participantes que lo usan. **No utilizar estos tiempos como benchmark de rendimiento aislado**.

## Resultado observado — PASS
Transcripción del `summary.json` mostrado por el operador:

```json
{
  "mode": "stage",
  "media": "fixtures",
  "branding": "montara",
  "passed": true,
  "duration": 40.2,
  "captioned": false,
  "size": "1920x1080",
  "frames_swapped": false,
  "mixed_master": null,
  "measured_browser_journey_seconds_including_ui_waits_and_download": 410.831,
  "measured_engine_stage_seconds": {
    "cut": 0.031,
    "edit": 24.659,
    "export": 195.097,
    "ingest": 38.829,
    "sync": 54.539
  },
  "cuts": 5,
  "camera_usage": {
    "camera-a.mp4": 3,
    "camera-b.mp4": 3
  },
  "excluded": []
}
```

- Se generaron dos cámaras sintéticas y un máster de audio; el test recorrió interfaz, importación, sincronización, edición y exportación.
- Resultado validado por el test: vídeo final de 40,2 s a 1920×1080; uso de ambas cámaras, sin exclusiones.
- Duración del recorrido navegador (incluye esperas UI y descarga): 410,831 s. Tiempo export registrado: 195,097 s. Estos contadores no son descomposición exacta del wall-time total, ni prueba de rendimiento sin concurrencia.
- Las evidencias locales (capturas, logs y exportación) permanecen fuera de Git en `/home/fer/montara-e2e-01`; no subir vídeos ni datos temporales al repositorio.

## Próximos pasos y límites
1. Revisar el resultado y el peso del vídeo exportado; si procede, ejecutar pruebas independientes de `push` y `mix`, preferiblemente por separado y **avisando previamente del posible tiempo de ejecución**. No repetir Stage innecesariamente.
2. Coordinar una ventana de bajo uso de CPU antes de medir rendimiento comercial; el lock por sí solo no protege renders lanzados por servicios persistentes ajenos.
3. F4 v360 queda con instrumental validado en smoke, pendiente de vídeo 360 real de alta resolución.
4. Esta prueba no certifica workflows de originales reales, Companion, 360 real ni capacidad multiusuario.
