# URANO U13D2A — concurrencia por usuario, sin cola global

**Decisión del propietario (06-11-2026):** no implementar como política de producto una cola global FIFO entre usuarios. Cada propietario puede tener su runtime independiente y trabajar/renderizar simultáneamente, sujeto a capacidad física. El bloqueo de U13B/U13D es **por runtime individual**, para evitar cambios incompatibles dentro de los trabajos del mismo usuario. El Companion y el Engine repartidos entre equipo local/servidor deben medirse sin presuponer su carga.

## Verificación entregada

- `tests/test_urano_parallel_owners.py` utiliza dos procesos hijos verdaderos y dos cuentas ficticias, con protocolos de apertura coordinados de modo que **cada proceso necesita comprobar que el otro también ha entrado en su apertura antes de terminar**. La prueba fallaría si se impusiera una cola global que solo permitiera abrir uno tras acabar el otro.
- Comprueba además que un trabajo marcado busy en el runtime de Alice **no impide** que Bob reserve y prepare su propio proyecto y que los IDs/slots no coinciden.
- CI ejecuta todas las pruebas U10–U13D2A. Este gate comprueba concurrencia del coordinador, **NO capacidad de CPU ni renders reales**.

## Capacidad que queremos medir, NO capacidad confirmada

Escenarios sucesivos con **1, 2, 4, 8, 10 y 25 usuarios concurrentes** y diferentes mezclas Stage, Push, Show, proxy/companion, visualización y exportación. Cada escenario debe medir: RAM/RSS/PSS, CPU, tareas bloqueadas, latencias P50/P95, tiempo a primer fotograma, tiempos E2E y de export, errores, consumo de disco, tráfico/red, trabajo descargado a Companion, procesos externos de FFmpeg y salidas verificadas. Definir umbrales y costes antes de decidir límites de admisión/escalado. No confundir una protección per-owner con una cola global; tampoco iniciar 25 renders reales sin cuotas y aislamiento verificados.

## Puerta de seguridad pendiente (U13D2 real)

Este incremento **no da aislamiento fuerte de sistema operativo**: los dos procesos de prueba se ejecutan bajo el mismo usuario Linux y comparten datos sintéticos. Antes de usuarios externos, implementar un executor que arranque por UID separado o contenedores sin privilegios, con directorios y secrets separados, red y filesystem restringidos, límites CPU/RAM/PIDs, comprobación de fuga entre propietarios, cancelación de subprocess y reconciliación tras caída del supervisor. Hacer una prueba negativa de lectura cruzada y de escape con proceso controlado antes de invitar a Chema. Conservar rutas no públicas y contraseñas de prueba temporales individuales.

**No se modifica el Engine, main, Vercel, Cloudflare ni la VM compartida.** PR draft apilada tras U13D #94; no confundir con despliegue de beta.
