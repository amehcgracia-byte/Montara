# SATURNO-09 — Paquete reducido aislado y diagnóstico Stage

Base: `21b2acf56af8372abe0ba5eff2fc5dad69c94441`. Única rama modificable:
`fernando/continuacion-montara`. No repetir los doce controles SAT-08.
Sin modificar main, motores ni ramas ajenas. Una ejecución consolidada, sin PR/artifacts.

## Ensayo 1: vídeo Y audio reducidos con aislamiento de B
Reutilizar el método SAT-05 run 40860115536: fuente 3–7 s, H264 qp=0,
Matroska yuv420p. Ventana A 4–6 s == B 1–3 s. No es stream-copy ni GOP mínimo.
Empaquetar también los primeros 2.25 s de master a WAV float32 sin cuantización.
Exigir igualdad SHA256 de las ventanas previas decodificadas de vídeo y audio.

Cada export usa proceso nuevo, ZUCKER_DATA_ROOT exclusivo, cache inicialmente
vacía y rerender forzado. B corre en namespace Linux sudo unshare: tmpfs vacío
sobre todo tests/fixtures, outputs A/A-repeat y sus runtimes/caches.
Comprobar rutas originales inexistentes y carpetas enmascaradas vacías dentro de B.
Un fallo del namespace es fallo de infraestructura. No renombrar originales.

Gate predefinido: paquete total menor; ventanas previas iguales; A/A y A/B
60/60; audio PCM íntegro exacto tras export AAC; PTS/DTS/duraciones de streams
y paquetes iguales. Hash de MP4 registrado, no exigido como requisito adicional.
Todos los caches iniciales vacíos. Encoder threads:v=1 solo en memoria QA.
Medir preparación y render. Caso plano de 2 s, no Stage/360 ni economía remota.

## Ensayo 2: Stage y selector de cámaras
Lectura de web/montara.js: bloque localhost usa `$('#cameraList .cam').forEach`,
pero `$` devuelve un elemento y `$$` una lista. Hipótesis: TypeError tras draft,
antes de mostrar cámaras. Confirmar con flujo real ANTES de corregir.

Reutilizar tests/e2e_journey.py.journey sin reescribir su selección/montaje.
Observar consola, errores HTTP, estado wizard, JSONs de proyecto y comandos FFmpeg.
El primer wait del adaptador QA observará también failed (máximo 60 s), para
capturar el error en vez de volver a esperar 300 s sin evidencia.
Si el original falla con forEach, probar segundo contexto de navegador con
un reemplazo `$ -> $$` en la RESPUESTA montara.js: no se edita fuente ni motor.
Si falla por otro motivo no se aplica esa corrección. Si original pasa, no se modifica.

Servidor con control de encoder SAT-08 en memoria; comandos efectivos registrados.
Guardar edit_plan REAL cuando exista. Recoger texto de errores y server log.
Diagnóstico recogido no equivale a Stage aprobado: gate_full_stage separado.
Solo journey completo puede ponerlo true, explicitando ambos controles QA.

## Interpretación predefinida
Paquete reducido aprobado solo cierra este caso plano con audio propio bajo QA.
Stage aprobado proporciona referencia y plan para el A/B completo posterior.
Si falla, registrar causa observable y no atribuirla a Zucker por defecto.
Tiempos del runner no equivalen a transferencia/nube ni coste real de producción.
Los cuatro hitos siguen abiertos hasta completar toda la evidencia acordada.
