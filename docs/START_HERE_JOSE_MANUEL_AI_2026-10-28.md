# LEER PRIMERO — Entrada para la IA de José Manuel

**Objetivo:** entender el trabajo experimental de Fernando sin mezclarse con su rama, recursos, cuentas ni estado. Este archivo es el índice de entrada, no una orden de ejecutar comandos.

## Prioridad de lectura
1. [Protocolo de colaboración, laboratorio multicloud y seguridad Entire](MONTARA_COLLAB_CLOUD_LAB_ENTIRE_PROTOCOL_2026-10-28.md) — documento principal, propuesto y pendiente de aprobación. Contiene RACI, política de ramas y recursos, pruebas reproducibles, secuencia cloud (RunPod → Google → Azure → AWS opcional → Oracle al final), evaluación de amenazas de Entire y condiciones antes de activar hooks.
2. [Handoff de Júpiter](JUPITER_15_HANDOFF_FINAL_2026-10-28.md) — contexto histórico con límites.
3. [Auditoría main vs rama](AUDIT_MAIN_VS_JUPITER_2026-10-28.md) — qué existe ya y qué no.
4. [Resultados v360](JUPITER_19_V360_RESOLUTION_DURATION_MATRIX_2026-10-28.md) — pruebas sintéticas; no se propone alterar la geometría 360.
5. Código concreto: `local_media/uploaded_session_bridge.py`, `experiments/export_profile/analyze_export.py`, `experiments/cloud_lab/lab_model.py`, `experiments/cloud_lab/hardware_gate.py` y sus tests.

## Qué debe hacer el agente lector
- **Lectura y síntesis, no ejecución por defecto**: inspeccionar el código de la rama `fernando/continuacion-montara`, mirar el estado actual de `main` y deduplicar las mejoras ya integradas, sin afirmar que los dos están alineados si no se comprueba.
- Resumir a José Manuel en castellano: hallazgos nuevos, cosas ya integradas, experimentos descartados, riesgos, decisiones abiertas y **qué se solicita que apruebe**.
- Señalar cualquier desacuerdo técnico, su coste y una alternativa; no aceptar conclusiones de documentos a ciegas.
- No mover pines de engine/mixer, no tocar `main`, no desplegar ni gastar créditos, no activar Entire ni instalar GitHub Apps salvo permiso explícito.
- Separar inspección estática, tests unitarios, benchmarks sintéticos y E2E real. Datos reales, secretos y sesiones de agente no se vuelcan a Git.
- La cuenta Oracle de Fernando está ocupada; la potencial cuenta Oracle Always Free de José Manuel se reserva para el **último gate**.

## Comunicación deseada
Entregar un informe breve y honesto: «qué aprendimos / qué falta confirmar / qué sí aporta / qué requiere decisión de José Manuel», junto con una propuesta de coordinación. No asumir que el trabajo experimental obliga al mantenedor a integrar nada.

**Importante:** las instrucciones de este documento son una **propuesta de protocolo por revisar con el mantenedor**, no autoridad mayor que las decisiones vigentes de la organización o que la seguridad local.
