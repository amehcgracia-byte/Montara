# SATURNO/JÚPITER — iPhone HEVC 4K HDR VFR: preparación CPU-first (encargo recibido 2026-10-30)

## Origen, prioridad y coordinación
Encargo técnico transmitido por José Manuel/Chema al equipo de Fernando. **Pendiente de ejecutar**: no existen mediciones de iPhone real en esta misión.
Se incorpora a la cola de `JÚPITER-OPT` como línea de **impacto potencial alto en tiempo hasta poder editar**, sin abandonar el trabajo actual de exportación. Chema mantiene propiedad de `main`, `engine` y Companion; Fernando analiza y prepara pruebas/parches propuestos en su rama. No editar submódulos desde Montara.

## Diagnóstico sustentado por código
Consultado `amehcgracia-byte/zucker_videos` en `c89e7791ff6200e29c4281b79e84307277f9527f`, `core/normalization.py`:
- `proxy_transcode_compliant` solo permite reutilizar el original como proxy si es H.264 CFR SDR <=8 bits, sin rotación/proyección y <=1920×1080.
- `normalization_filter(..., proxy=True)` aplica al HDR `SDR_TONEMAP_FILTER` con zscale+tonemap, escalado y normalización de FPS.
- `_normalization_command` construye FFmpeg con codificación H.264 y audio AAC; el camino software utiliza libx264. `normalize_video_record` ya incluye caché y una ruta hardware/fallback; **no asumir que una nueva caché aporta valor**.
- Conclusión **no demostrada**: HEVC decode o HDR tonemap sean los componentes dominantes en la VM. Requiere perfil.

## Hipótesis y pruebas acotadas
**A — Referencia:** 2–3 clips **reales** iPhone HEVC 4K HDR, 30/60 fps, idealmente 1–5 min, y control Sony H.264 1080p de duración comparable. Verificar códec, transferencia HDR, PTS/VFR, rotación y audio con ffprobe. Usar copia privada fuera de Git, no exponer rutas personales.
Medir la normalización exacta en la VM de 4 vCPU con `montara-bench` y manifiesto de máquina `deploy/vm/manifest.sh`. Registrar tiempos, RAM y CPU. **No ejecutar lotes largos sin aviso de recursos y duración al operador**.

**B — Experimentos aislados, una variable cada vez, solo si A lo justifica:**
1. Hilos decodificador/filtro (threads/filter_threads/filter_complex_threads) con control de oversubscription.
2. Ubicación del escalado 4K→720p/480p en filtro, preservando orden correcto del tone mapping cuando sea necesario.
3. Coste de HDR→SDR (zscale+tonemap frente a alternativa para proxy de análisis), con controles de exposición/color adecuados para algoritmos visuales; no asumir que tono distinto es aceptable.
4. Peso del codificador H.264 (preset/CRF) y coste de VFR→CFR.
5. Eventual proxy local mediante Companion/WebCodecs **solo coordinado con Chema**, fuera del alcance inmediato.

## Criterios de aceptación
- Desfase/sincronización igual dentro de tolerancia de 1 fotograma y sin deriva acumulada (comprobar inicio, medio y final; no confundir 30 con 60 fps).
- Plan de cortes Stage igual para la referencia y el candidato.
- Render final desde original, sin cambios visibles frente al flujo validado; comprobar también alineación audio/vídeo y metadatos.
- Al menos 3 ejecuciones comparables para variantes que se propongan como mejoras; registrar alternancia de orden, entorno y concurrencia.
- Ninguna reducción significativa de calidad del análisis visual del proxy, ni comportamiento erróneo HDR/rotación.

## Entregables y límites
Informe en docs/; STATUS-FER actualizado; añadir familia a `docs/lab/INVENTORY-FER.md` coordinando su propietario; candidato en rama/propuesta para revisión de Chema si gana; Chema integra cambios al motor mediante PR.
No GPU de pago sin acuerdo, todos los experimentos pesados bajo `montara-bench`, no tocar HOME/servicios de jm, ni datos privados/secrets en repositorio público.

## Relación con JÚPITER-OPT-04
- OPT-04 analiza coste de render de segmentos originales en exportación, especialmente condiciones de stream copy. No confundir con normalización del proxy previa a sincronización.
- Priorizar un baseline de iPhone real cuando se disponga de clips; **hasta entonces** continuar tareas CPU ligeras y útiles, y no crear clips HEVC sintéticos como sustituto de la evidencia del iPhone real.
- El criterio rector es mejorar tiempo perceptible de usuario y coste total, no solo microbenchmarks.
