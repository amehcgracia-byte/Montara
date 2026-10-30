# FOCUS A/C — Proxy físico, resultado del laboratorio (2026-10-30)

## Estado: PASS_PHYSICAL_PROXY_GATE (limitado)

Operador ejecutó `experiments/media_optimization/focus_ac_physical_proxy_gate.py` en `fernando/continuacion-montara` bajo `montara-bench FER-FOCUS-AC-PHYSICAL`. VM actualmente 8 vCPU, 31 GiB RAM. Resultado local `/home/fer/montara-focus-ac-physical-01/report.json`. Git limpio.

- Cámara A: original 20.0 s, proxy físico 640×360 20.01 s, 1,113,753 bytes. SHA-256 del original: `834ab1a042cb55a7663843ff5995faaf8f13d5c9bbef77ad79899a58d8e6539a`.
- Cámara B: original 20.0 s, proxy físico 640×360 20.01 s, 1,114,064 bytes. SHA-256 del original: `41e38b14097231eab2000d9e3e8ed7b4c4c2b538c98fc2b8a9fd95fc52b6e07b`.
- Los 6 segmentos resolvieron originales/proxies con `_segment_source_info` y preservaron tiempos.
- Hash del project.json fuente `18a009f949a0baeb117ec205e3a65ccdf5a05f25f20e12eaadb38a4aa3898fce`; hash del plan `7d67f2c367e4d763dfb204bb9208627299b3897ef7d9618f47e2fdbf0d7316b7`.
- El script no cambió los archivos de origen ni renderizó el montaje.

## Interpretación y próximos criterios

**No es certificación proxy-edición-original-render.** El plan se creó sobre originales sintéticos 720p, no sobre los nuevos proxies 360p. No se han comprobado decisiones de edición generadas a partir de proxy, identidad de frames finales, sonido, rotación, HDR ni reproyección 360.

**Siguiente paso**: al recibir clips reales de Chema, validar procedencia y características, congelar un único plan creado con proxies, ejecutar A/B controlado en medios aislados (no servicios persistentes), conservar identidad/timing y comparar fotogramas, audio, cronología y metadatos. Reutilizar pruebas SATURNO-24 y FOCUS A/C; evitar duplicar test suites. Dar aviso explícito al operador antes de renders pesados; bloqueo `montara-bench` y protección ante autoapagado a 40 min.

No editar `main`, `engine`, `mixer`, HOME de jm ni secretos públicos.
