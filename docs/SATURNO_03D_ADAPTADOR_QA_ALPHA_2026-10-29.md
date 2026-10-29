# SATURNO-03D — Adaptador QA alfa (29 octubre 2026)

**Estatus:** prototipo externo probado **10/10 tests** en Linux local, **NO** exportador funcional de Zucker ni prueba E2E. No cambia `main` ni submódulos.

El paquete de código `SATURNO_03D_ADAPTADOR_ALPHA_2026-10-29.zip` está adjunto a la conversación, **no al repositorio**. SHA-256: `2ecf8044143ec16eebeda0ea8746b001b395e8e4c95dba17644cda693b042516`.

**Contenido:** `adapter.py`, `test_adapter.py`, `README.md`. El script comprueba cobertura temporal declarada de cada intervalo, hashes SHA-256 de fragmentos, rutas de paquetes y correspondencia con registros de proyecto; genera `project.qa.json`, `edit_plan.qa.json` y `GATE.json` en directorio nuevo. Nunca cambia archivos fuente ni invoca FFmpeg/Zucker. El gate sigue **NOT_E2E_VERIFIED**.

**Controles negativos ejecutados:** digest falso, intervalo insuficiente, material esférico, motion, traversal, falta de master, fuente no mapeada, staging dentro del paquete, plan vacío. **10/10 tests**.

**Limitaciones bloqueantes:**
- Solo admite **un fragmento por original**, no disjuntos.
- El offset de tiempo usa `clip_start_sec - source_start_sec` sin verificar el primer PTS real del archivo stream-copied; por tanto NO garantiza la selección del fotograma correcto.
- **El audio master NO queda remapeado ni aislado**; `project.qa.json` conserva su ruta de origen.
- El motor tiene cachés, preprocesado y rutas 360 adicionales; `project.qa.json` no es un formato de importación certificado.
- La prueba 10/10 demuestra validaciones y staging, no render de Montara ni ahorro de bytes.

**Siguiente gate:** adaptar un A/B QA aprobado por José Manuel para comprobar PTS, master audio y lectura del motor con su fixture `much-to-me`. Si no hay runtime/medios reales y acceso autorizado, informar BLOCKED en lugar de afirmar PASS.

Código detallado y ejecución local disponibles en el ZIP de la conversación. Para evitar pérdida de trazabilidad, archivar código como fuentes versionadas en el próximo paso antes de revisión/PR.
