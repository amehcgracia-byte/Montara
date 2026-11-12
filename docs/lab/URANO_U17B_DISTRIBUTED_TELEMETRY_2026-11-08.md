# URANO U17B — Medición distribuida conservadora (08-11-2026)

**Estado: instrumentación opt-in + contratos CI; NO se ha ejecutado aún una prueba con dos ordenadores físicos y GCP.**

## Para qué sirve

Montara tiene un flujo híbrido; no debemos medir el render final del usuario como si consumiera CPU del servidor. U17A, PR #130, ya validó dos recorridos Stage → Companion → MP4 en **un único runner compartido**. Esta etapa añade medidores **pasivos**, portables entre macOS, Windows y Linux, que permiten obtener una lectura comparable por proceso en cada máquina cuando tengamos los hosts autorizados.

### Ficheros

- `tests/urano_hybrid_node_meter.py`: apunta a un **PID ya existente**, con un rol fijo (`client_companion`, `client_browser` o `server`); cada 0,5 s, por defecto, observa el proceso y sus descendientes con `psutil` y acumula segundos de CPU **observados** y máximo RSS **muestreado**. Nunca arranca Montara, fuerza un render, lee medios, inspecciona líneas de comandos en el informe, ejecuta SSH ni contacta por red. Solo guarda JSON local en una ruta nueva.
- `tests/urano_hybrid_merge_reports.py`: combina informes JSON **del mismo ensayo**, exige un servidor y tantos clientes Companion como el escalón (2,4,8,10,25), etiquetas distintas por host y muestras reales. Rechaza falta de muestras, valores inventados/negativos, duplicados, discrepancias de ensayo o ausencia de servidor. Un resultado válido de metadatos **no significa** rendimiento distribuido validado.
- `tests/test_urano_hybrid_node_telemetry.py`: casos positivos y fallos deliberados, incluso muestra real de su propio PID; CI `.github/workflows/urano-u17b-node-telemetry.yml`.

### Ejemplo seguro — solo en un entorno de pruebas autorizado

Instalar la única dependencia adicional **en el entorno privado de ensayo**: `python -m pip install psutil`.

En el Mac/PC con Companion **ya arrancado**, usando su PID local real:

```bash
python tests/urano_hybrid_node_meter.py \
  --pid 12345 --role client_companion \
  --host-label cliente-a --run-id prueba-hibrida-001 \
  --scenario-clients 2 --duration 120 \
  --output cliente-a-metricas.json
```

En otro ordenador cliente, su propio PID Companion: mismo `run-id`, `--host-label cliente-b`, JSON de salida distinto.

En el servidor de laboratorio — **solo lectura del PID de Montara**, sin reinicios ni despliegues —:

```bash
python tests/urano_hybrid_node_meter.py \
  --pid 67890 --role server \
  --host-label servidor-pruebas --run-id prueba-hibrida-001 \
  --scenario-clients 2 --duration 120 \
  --output servidor-metricas.json
```

Cuando el operador haya trasladado **solo los JSON de métricas** a un directorio privado de análisis (sin originales, nombres de usuarios ni identificadores reales):

```bash
python tests/urano_hybrid_merge_reports.py \
  --input cliente-a-metricas.json \
  --input cliente-b-metricas.json \
  --input servidor-metricas.json \
  --output resumen-metricas.json
```

Estos ejemplos son ilustrativos: los PID no se conocen hasta que se ejecutan las aplicaciones. **No ejecutar en JM/FER o en el GCP compartido sin autorización operativa.** El comando no altera el proceso que observa, pero consume un pequeño número de muestras.

## Semántica estricta

- `host-label` es una etiqueta declarada por el operador, **no demuestra** que dos procesos estén en dos máquinas físicas. `operator_physically_confirmed_distinct_hosts` solo registra una confirmación manual, no autenticación criptográfica.
- `distributed_performance_verified=false` hasta que una aceptación independiente demuestre dos clientes físicos distintos, servidor remoto, sincronización de inicio, render MP4, duración/material comparable y telemetría válida. **El agregador actual no emite PASS de rendimiento distribuido.**
- `transport.proxy_upload_bytes`, `recipe_download_bytes`, latencia y subida de originales aparecen como **null**. No es correcto sumar los bytes del adaptador de red completo (incluye programas ajenos) ni afirmar "originales no enviados" sin trazar las peticiones concretas.
- La CPU del proceso y sus descendientes es **muestra observada y cota inferior**; procesos efímeros pueden desaparecer entre muestras. El RSS es muestreo de memoria de procesos, no memoria cgroup/sistema ni memoria real del servidor compartida.
- El medidor registra únicamente plataforma, CPU lógicas, números de CPU/RSS y etiquetas controladas. No guarda comando, ruta del vídeo, IP, email, contenido de proyectos, contraseña, token ni hostname automático. **No recopilar originales para estas pruebas**.
- No conocemos la eficiencia por subida/sesión de proxies entre dos hosts. Falta instrumentación específica de peticiones web, además de completar autorización Google real→worker y Companion multiusuario productivo.
- El escalón **25** no debe lanzarse hasta que 2→4→8→10 demuestre margen razonable, y solo con carga distribuida o con una etiqueta explícita de simulación servidor.

## Qué demuestra este incremento y qué no

**DEMUESTRA (CI):** podemos medir y combinar CPU/RSS por proceso con límites, rechazar informes incongruentes y prevenir falsos PASS de concurrencia distribuida.

**NO DEMUESTRA:** un Mac real conectado a la VM, rendimiento de GCP con 2+ usuarios, redes WAN, export simultánea entre equipos, capacidad 25, cuotas o recuperación completa después de desconexión.

**Siguiente comprobación operativa, cuando corresponda:** seleccionar dos clientes físicos con Companion y un servidor de prueba aprobado; preparar una sesión de extremo a extremo comparando Stage, proxy de subida/descarga, export local, red y tasa de fallo, sin tocar producción. No convertir esto en requisitos de 25 usuarios para una beta pequeña.

**Integración:** rama de laboratorio apilada sobre **#130**; no modificar `main`, Engine/Mixer, Companion, port 8101/8102/8103, proxy ni AWS/Azure/Google/Oracle. Chema conserva el control de merges y despliegues.
