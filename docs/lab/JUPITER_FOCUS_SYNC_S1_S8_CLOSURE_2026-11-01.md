# JÚPITER — cierre FOCUS SYNC S1–S8 (2026-11-01)

## Decisión
**Cerrar investigación exploratoria, no afirmar certificación de producción ni aplicar parches a `engine/`.**

## Pruebas
- S1–S3 (envolventes sintéticas): control offset +12.0047 s; derivas artificiales +50/100/250 ms sobre 80 s provocaron selección de máximos globales equivocados (aprox. −64.6/−69.7/−69.5 s) con confianza alta y `unstable_sync=False`. Causa experimental: candidatos con solapamientos cortos (~10–15s) que superan la correlación del alineamiento verdadero. Guard candidato global-vs-consenso >150ms marca los tres, no los controles probados; es hipótesis, no umbral aprobado. Una puerta rígida de 80% de solapamiento **falla** en muestras de solapamiento legítimo y no arregla todos los casos.
- S4 (audio Sony real; clip derivado de misma grabación): offset inicial +12s, error +4.7ms sin deriva; +27.9ms con deriva artificial 50/100ms; con 250ms offset erróneo +65.5035s y confianza 5.28 (<umbral 6), guard global-consenso lo marca.
- S5 (dos cámaras reales originales): Sony 0–45s y 44–89s sitúan Sony t=0 en iPhone t≈703.704s y ≈703.706s, con correlaciones .8630/.8812 y solapamiento total; diferencias de 1.8ms entre estimaciones sobre ventanas. No certificar precisión sub-hop.
- S6 (dos cámaras reales): cinco ventanas de 25s, inicios Sony 0/16/32/48/64s. Offsets de origen iPhone 703.7039, 703.7025, 703.7010, 703.6996, 703.6981s; correlaciones .8567/.8831/.8356/.8160/.9224. Amplitud observada 5.8ms y pendiente ajustada −5.44ms/min **no certifican deriva física**, porque hop onset 512/22050s≈23.22ms y las ventanas se solapan.
- S7: hoja JPG 3 parejas (Sony 10/45/80s; iPhone 713.7039/748.7039/783.7039s). Inspección visual compatible con misma actuación, ángulos distintos, no prueba lip-sync al frame.
- S8: MP4 aportado por Fernando e inspeccionado: 5.000s, 1280×360, 25fps, 303995 bytes, iPhone a izquierda y Sony a derecha, audio solo Sony. Fotogramas revisados aprox. 0.5/2.5/4.5s; gestos de flautista/batería y escena compatibles, sin contradicción visual grosera. **No demuestra sincronía frame-accurate** ni verifica auditivamente un mix de ambos micrófonos.

## Recomendación a Chema
1. Tratar como bug de fiabilidad la ausencia de comprobación de coherencia offset global vs consenso en `verify_sync_stability`; ensayar guard con casos de solapamiento breve, deriva y falsos positivos antes de integrar.
2. No usar umbral rígido de >=80% de solapamiento ni sustituir automáticamente offset por consenso.
3. Tratar corrección de offset inicial y compensación/detección de deriva de reloj como problemas separados; contraste E2E antes de declarar producción.
4. JÚPITER no edita `engine/`, ni los trabajos del Companion de Chema.

## Estado
**FOCUS SYNC exploratorio CERRADO**. Siguiente frente bajo priorización de Fernando/Chema. Evidencias reproducibles en `experiments/media_optimization/focus_sync_*_s*.py` e issue #58.