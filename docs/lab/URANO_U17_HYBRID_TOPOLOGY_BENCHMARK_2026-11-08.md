# URANO U17 — Benchmark híbrido de Montara (08-11-2026)

## Qué queremos medir realmente

**Arquitectura objetivo:**
- **Ordenador de cada usuario:** navegador, Companion, FFmpeg y exportación en CPU local con **archivos originales locales**. Los originales no se cargan como vídeos completos al servidor.
- **Servidor compartido:** autenticación, proyecto, planificación y datos/proxies necesarios para Stage, coordinación y entregas de receta; CPU/RAM/disco/tráfico se observan **por separado**.
- **Red entre ambos:** latencia, subida de proxies/metadata, descarga de recetas, bytes transferidos; si se usan variables sintéticas deben etiquetarse.

Escalera prevista de concurrencia: **2, 4, 8, 10, 25** usuarios. Los 25 son estrés, no capacidad prometida ni requisito previo de beta. Al escalar, lo importante es **cuánto trabajo permanece en cada CPU local** y dónde se satura el servidor; no asumir 25 MP4 renderizados en GCP.

## Implementado en este incremento

- `tests/urano_hybrid_benchmark.py`: wrapper para lanzar en paralelo **dos** ensayos completos de `tests/e2e_native_stage.py` (basado en PR #121); cada ensayo tiene navegador, app, Companion, media sintética, directorios y puertos independientes. Verifica MP4 local generado, render con originales, export antiguo del servidor evitado, tamaño final y persistencia. Observa CPU y RSS del árbol de procesos si `psutil` está presente. Genera `hybrid-report.json` sin nombres ni rutas de material original.
- `tests/test_urano_hybrid_benchmark.py`: contratos negativos para no inventar cifras, no aceptar topología distribuida si todos corren sobre una CPU, fallar si no existe MP4 aunque el resumen diga éxito y no pisar resultados anteriores.
- `.github/workflows/urano-u17-hybrid-benchmark.yml`: contratos rápidos y aceptación pesada en GitHub con 2 stacks completos; **sin desplegar ni tocar 8101/8102/8103**.

### No confundir esta primera ejecución con benchmarking distribuido

La prueba automatizada de GitHub es **shared-runner-integration-only**: navegador, servidor y Companion están en la **misma máquina física de CI**, aunque sean procesos y directorios aislados. Por tanto:
- Sirve para validar convivencia de dos stacks completos y medir contención **en ese runner**.
- **No** sirve para predecir rendimiento de 4, 8, 10 o 25 clientes con sus CPUs individuales, ni tráfico WAN, ni saturación de GCP, ni la eficiencia real del envío de proxies.
- El informe lleva obligatoriamente `distributed_result=false`, `server_remote=false`, `companion_runs_on_separate_client_machines=false`, y los contadores de red no medidos `null`. No se interpolan.
- La función `validate_distributed_nodes` exige **al menos dos hosts físicos cliente diferentes y un servidor físico distinto** antes de aceptar la etiqueta «distributed». No autoriza por sí sola un resultado: necesita telemetría real por host.

### Próxima medición de producto, con arquitectura correcta

La aceptación distribuida exigirá **2 clientes físicos (idealmente Mac y/o Windows con Companion)** y **1 servidor remoto de pruebas**, cada uno reportando CPU/RAM/proceso, tiempo de preparación/Stage/export local, bytes de proxy/metadata y MP4 y recuperación tras desconexión. Para 4→8→10→25 pueden emplearse agentes de carga que representen CPU cliente **solo si cada cliente está realmente aislado y hay hardware suficiente**; de lo contrario marcar como simulación/carga de servidor, nunca como 25 usuarios reales.

La prueba U16C #129 ya validó Ingest concurrente de dos Engine reales, pero en el **lado servidor** con vídeo sintético. El presente gate recorre la **exportación con CPU local Companion**, pero todavía NO utiliza la autenticación Google integrada en los workers ni dos hosts físicos separados.

## Estado y coordinación

Este cambio se basa directamente en PR #121 para poder reutilizar su E2E local. Es **una rama independiente** de #129 y no debe fusionarse a ciegas con la pila U15/U16. La integración se revisará selectivamente con Chema. No modifica Engine, Companion, cámaras, recetas ni servicios en ejecución. Ninguna subida de vídeo de usuario a GitHub.

**Criterio:** no declarar éxito de «Montara híbrido distribuido» hasta tener mediciones tomadas en hosts distintos con Companion renderizando localmente y un servidor remoto atendiendo proyectos. La CI de este commit documentará únicamente el gate compartido.
