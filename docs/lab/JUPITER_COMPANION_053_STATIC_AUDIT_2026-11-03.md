# JÚPITER-A — Auditoría estática de cierre del Companion 0.5.3
Fecha 2026-11-03. **Solo revisión de código GitHub; sin implementación, tests de runtime, Mac ni VM.**
Referencia `main`: `b718470c7d6ffb3a029a02a56785a1c489bc6890`. Auditado: `companion/install.sh`, `companion/companion.py`, `companion/local_mix.py`, `docs/lab/STATUS-JM.md`, issue #34 y PR #59/#63/#65/#67/#68.

## Hechos confirmados
- `companion.py` versión **0.5.3** en puerto local 47820, con `/mix-song`, `/mix-progress/<id>`, `/health`. Orígenes autorizados por regex y manejo local de originales.
- `install.sh --mixer` instala en entorno privado y descarga la revisión de ZuckerMixer apuntada por el submódulo de Montara, además de adaptadores `single_song`, `extract`, `render_progress`, `track_types`.
- `local_mix.py` extrae ventanas con FFmpeg, alinea/pad de pistas, llama `SingleSongMix.render`, elimina el directorio temporal en `finally`.
- `/mix-song` comprueba hash SHA declarado del mixer (plan frente a `MIXER_COMMIT`), resuelve originales y limita concurrencia por semáforo (1 por defecto), subproceso máximo 3600 s. Resultados MP3 transmitidos desde Companion al navegador, y posteriormente hacia servidor.
- STATUS-JM declara 171 MB instalados, 12/12 canciones locales, 47.5 min música procesados en 12.4 min en Mac Intel i7 de 4 núcleos, prueba de audio bit a bit idéntico con servidor. **Son resultados de Chema**, no repetidos en este laboratorio. No equivalen a prueba E2E comparativa contra 140 min estimados de subida.

## Riesgos y preguntas (no afirmaciones de vulnerabilidad confirmada)
1. **Actualización no transaccional:** instalador elimina `$MIX/mixer` y mueve descargado antes de instalar dependencias y verificar imports; en un fallo intermedio, el mixer anterior puede quedar dañado. Se actualiza `MIXER_COMMIT` tras verificación, lo cual permite detectar instalación parcial, pero no preserva automáticamente versión anterior. Probar rollback/instalación atómica antes de comercializar.
2. **Dependencias no bloqueadas:** `pip install numpy scipy soundfile pyloudnorm flask` sin versiones ni hashes. Riesgo de divergencia a lo largo del tiempo entre Mac y servidor o entre reinstalaciones. Fijar lock por arquitectura y versión Python, generar SBOM, comprobar licencias.
3. **Superficie HTTP local:** `origin_ok` admite subdominios generados de trycloudflare y vercel, `/mix-song` revisa Origin y plan/mixer SHA, pero no se ha observado token de sesión específico. Investigar amenazas de sitios con origen permitido no confiable, DNS rebinding/Host header, acceso local, CSRF, exposición de rutas y DoS; verificar flujo extremo antes de clasificar vulnerabilidad. No probar explotación en máquinas reales sin aprobación.
4. **Caché ilimitada:** `CACHE` almacena proxies/segmentos; `mix_song` sí elimina JSON, MP3 y progreso al finalizar. Medir consumo después de 12 canciones y tras fallo/corte. Falta quota/TTL, no confundir snapshot de progreso limitado con disco limitado.
5. **Fallback y recursos:** documentado fallback de servidor, falta ensayar errores de red, timeouts, suspensión, borrado de originales, cancelación de subprocess y dos canciones simultáneas; hoy `subprocess.run(timeout=3600)` tiene límite por proceso y limpieza de archivos, pero no equivale a cancelación fina o límite de memoria.
6. **Licencia y compatibilidad:** worker local evita Matchering, no asumir compatibilidad universal ni que todos los modos de masterizado local/remoto sean idénticos; probar Intel, Apple Silicon, macOS, sample-rate, stereo L/R, offsets, EQ, FX y mezcla con referencia. La versión de ZuckerMixer está controlada por SHA, pero no lo está el entorno Python completo.

## Gates mínimos y secuencia sin duplicación
**A0** documentar flujo/contrato exacto de render y fallback desde frontend/servidor; comprobar si existen tests para estos casos. **A1** experimento de instalación limpia/segunda instalación/interrupción en máquina aislada y captura de tamaño real (no usar el Mac de Chema sin coordinación). **A2** matriz de paridad PCM y MP3, con audio reference e instrumentos. **A3** validación de límites de orígenes/autenticación, cuota de caché y recuperación de cancelaciones. **A4** decisión de Chema: priorizar cierre y luego pasar a Stage EX-14D. No implementar como parte de esta auditoría.

## Coordinación
No tocar ZuckerVideos ni su pin. La rama local de optimizaciones nativas `fernando/ex06-engine-lab` está a la espera de permisos de escritura en el repositorio del motor, según la comunicación del 03-11 en issue #34; no duplicar ese trabajo. PR #68 es un experimento anterior, no una integración de producción. Todos los cambios potenciales requieren coordinación con Chema.

*Próximo foco macro: EX-14D Stage export — lectura del exportador, trabajo por segmento y telemetría; ningún render largo si no hay presupuesto/recursos controlados.*
