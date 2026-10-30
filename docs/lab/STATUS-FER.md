# STATUS — laboratorio de Fernando (fernando/continuacion-montara)

Actualizado: 2026-10-30 · **lo mantiene el equipo de Fernando**. Primera versión sembrada por el equipo de Chema a partir de `docs/JUPITER_GCP_LAB_BOOTSTRAP_2026-10-30.md`; sobrescribidla en vuestro próximo hito. 40 líneas como máximo.

## Referencias
- Rama: `1a5f3bd` · `engine`: `60a7b7e` · `mixer`: `c7a46a6`
- Respecto a `main`: 223 commits por delante y 10 por detrás. Unos 186 archivos distintos, la mayoría en `docs/` y `experiments/`.
- VM: checkout experimental en `/home/fer/montara-jupiter`; instalación web en `/home/fer/montara` (`127.0.0.1:8102`)

## Hitos recientes
| Pieza | Estado |
|---|---|
| JÚPITER-GCP-01: checkout aislado, Python 3.11.18, dependencias | `validado-lab`: 11 tests de proxies superados |
| SATURNO-24: render Stage con GOP selectivo | `validado-lab` en un caso controlado: salida idéntica fotograma a fotograma; 39,8 % menos bytes de medios |
| SATURNO-25: preparación, ZIP y transferencia HTTP local | `validado-lab` en loopback; **sin red real (WAN)** |

## Siguiente
- (por completar por el equipo de Fernando)

## Pendiente conocido
- Actualizar el documento JÚPITER-GCP-01: proyecto correcto, túneles, estado de la instalación anterior y sincronización de `1a5f3bd`.
- Traer los 10 commits de `main`: una fusión de prueba da 2 conflictos (`local_media/proxies.py` y `tests/test_proxy_singleflight.py`). El cambio de motor `60a7b7e`→`c89e779` es avance directo, pero cambia el comportamiento.
