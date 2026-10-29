# SATURNO-04 — Umbrales de decisión local vs nube (2026-10-29)

**Estado:** modelo determinista de escenarios, NO benchmark de Montara y NO evidencia de exportación desde paquete parcial.

## Fórmulas
Usando GB decimales y Mbps efectivos: `transfer_s=GB*8000/Mbps`.

- `T_local = local_render_s`
- `T_remote_full = queue + upload(source) + remote_render + download(output) + verify`
- `T_remote_partial = prepare + queue + upload(package) + remote_render + download(output) + verify`
- `T_fixed = prepare + queue + remote_render + download(output) + verify`
- `package_break_even_GB = max(0, (T_local - T_fixed)*upload_mbps/8000)` (0 indica que no existe paquete positivo rentable si `T_fixed >= T_local`).
- `upload_break_even_Mbps = 8000*package_gb/(T_local-T_fixed)`, solo si `T_local > T_fixed`.

## Hipótesis numérica por defecto
80 GB originales; 10 GB paquete; 100 Mbps subida y bajada; salida 2 GB; local 3600s; preparación 300s; cola 120s; render remoto 900s; verificación 30s.

Resultados: local **3600s**, full **7610s**, partial **2310s**, umbral paquete **26.125 GB**, umbral subida **38.2775 Mbps**. Si se intentara paquete parcial de 80 GB, tardaría **7910s**, esto es 300s más que full por el overhead de preparación; distingue estrategia parcial de completa.

**Auditoría de tests:** el primer test de `remote_full_seconds` esperaba erróneamente 7590s; corregido a 7610s al comprobar suma exacta. 13/13 tests superados en la versión local de desarrollo, incluidos frontera exacta, paquetes iguales, ancho de banda y números inválidos. Se ha versionado fuente y batería equivalente en `experiments/saturno_04/{decision.py,test_decision.py}`; la ejecución CI de ese commit NO está verificada.

## Confiabilidad y límites
- Es un modelo exploratorio sin parámetros reales de RunPod, de la red del usuario ni del render específico de Zucker. `cloud_usd_hour` y `storage_usd_gb_month` son **hipotéticos**, sin IVA, egress, fallos, mínimos de almacenamiento o costes fijos.
- La factura no equivale necesariamente al tiempo end-to-end: el horario efectivo de cobro del pod requiere verificarse en el proveedor.
- El código restringe `package_gb <= source_gb` y parámetros positivos; no intenta modelar compresión que crezca, cero coste, ni tasa variable.
- Un paquete parcial que rinda un resultado equivalente en Zucker real **NO está demostrado**. El escenario de 10 GB es un supuesto, no una tasa de compresión probada.
- Las siguientes medidas que faltan son: tiempo local real con fixture congelado, tamaño de paquete utilizable, duración de preparación, tasa efectiva de red, tiempo remoto para mismas entradas, cola, integridad y coste total.

## Uso
```bash
cd experiments/saturno_04
python -m pytest -q test_decision.py
python decision.py
python decision.py --package-gb 20 --upload-mbps 50 --local-render-s 2400
```

**Referencias:** base del trabajo de campo en `docs/SATURNO_00_REVISION_CIENTIFICA_TRANSFERENCIA_RENDER_2026-10-29.md` y puerta real `docs/SATURNO_03D_ZUCKER_REAL_E2E_GATE_2026-10-29.md`.

**Gobernanza:** sin editar submódulos, main o utilizar créditos RunPod. Se trata de soporte para decisiones, no aprobación de despliegue.
