# I14 — Primera apertura real de Engine en VM sobre datos sintéticos

**Fecha:** 2026-11-10. **Objetivo:** comprobar el Engine real y el protocolo U13 de proyectos sin tocar `main`, ni Owner C8, ni la instancia de Chema, ni datos de usuario. **No es una prueba de aislamiento OS multiusuario ni un E2E de Companion.**

## Qué se ejecutó realmente

- Google Cloud, VM compartida del entorno FER, Linux 8 vCPU, 31 GiB RAM, disco 96 GB (~48 GB libres al arrancar). Estas son **características del banco de pruebas**, no requisitos del producto.
- Se validó el submódulo Engine real en el commit pinneado **`b5e48317ef85225f901adc69af8cc17aa8146880`** y se utilizó su función real `core.project.new_project_document` para generar un proyecto sintético en `tempfile.TemporaryDirectory`.
- En un directorio efímero distinto de las DB reales se construyeron `ProjectCatalog`, `EngineProjectRegistry`, `RuntimeActivationGuard` y `PrivateWorkerSupervisor`, sin acceder a ninguna cuenta Google real.
- El supervisor inició el proceso `urano.engine_worker_process`, dentro del cual se creó **la aplicación real del Engine**; la apertura se ejecutó por `/api/v1/wizard/projects/open`, con comprobación posterior de que el estado interno del Engine apuntaba al proyecto correcto.
- Intentar abrir el UUID de un proyecto que pertenece a otro `owner_id` produjo `ProjectNotFound` antes de enviar comandos al Engine.
- Finalizado el test, se cerró el proceso y la guardia pasó de `ready` a `idle`, se borró el directorio efímero, sin medios reales ni persistencia de proyecto.

## Resultado VM del primer ensayo

| Métrica | Valor observado | Limitación |
| --- | --- | --- |
| Arranque del worker y handshake real Engine | **6,086 s** | Con CPU/cache del entorno en ese momento; no representa p95 |
| Apertura y verificación de proyecto | **0,037 s** | Proyecto sintético sin vídeo |
| Duración total | **6,152 s** | Solo apertura y cierre |
| RSS observado del proceso padre | **142,34 MiB** máximo de las dos muestras | No es **pico total** de worker/hijos/cgroup ni reserva obligatoria de RAM |
| Proyecto ajeno denegado | **PASS** | Autorización lógica, no aislamiento del filesystem Linux |
| Cierre + estado idle | **PASS** | No prueba cancelación de árbol FFmpeg en ejecución |
| OS sandbox / Docker / UID separado | **NO** | Mismo usuario de laboratorio; prohibido exponerlo como tenant real |
| Companion/Stage/MP4 | **NO** | Aún pendiente de recorrido híbrido |

## Segunda ejecución, dependencias/cachés parcialmente calientes

Segundo ensayo reproducible después de preparar los tests I14, sobre el **mismo commit Engine**:

- **1,970 s** para levantar Engine y completar el handshake.
- **0,046 s** para abrir y verificar el proyecto sintético.
- **2,060 s** para toda la ejecución, incluida limpieza.
- **131,36 MiB** de RSS observado en el proceso principal (muestreo puntual, no pico real).
- De nuevo **PASS** proyecto ajeno denegado, Engine abierto, cierre e inactividad.

Las diferencias de 6,086 s a 1,970 s probablemente incluyen variaciones de importación/cachés/carga; **no atribuir esa diferencia exclusivamente a un runtime ni usarla como SLA sin más repeticiones**.

**Ejecución reproducible en la VM:** activar el checkout de `fernando/integracion` con el código I14, verificar Engine submódulo, e invocar el programa con `PYTHONPATH=tests python tests/urano_i14_real_engine_lab.py --engine-dir /ruta/al/engine-pinneado --repo-root /ruta/a/montara`. El script no contiene nombres de proveedor ni rutas persistentes; el operador facilita un checkout de Engine ya instalado y su interpreter con dependencias.

El artefacto emite JSON sin rutas privadas de usuarios. La huella SHA Engine permite detectar cuando la fuente no coincide con el repo de la prueba. El script **no configura** Docker, systemd, VPC, usuarios, firewall, login, puertos HTTP, Google OAuth, ni instalación de paquetes.

## Seguridad y siguiente paso inmediato

Aunque I13 ya impone propiedad y CSRF, este I14 usa un subprocess con **el mismo UID del operador**: no constituye aislamiento para datos ajenos. No instalar esta versión detrás de la web ni interpretar `real_engine_open=true` como `isolation_verified=true`.

La siguiente puerta es ejecutar **este mismo escenario real** detrás de un ejecutor OS aislado que limite visibilidad de directorios y recursos, con pruebas adversariales de acceso cruzado, memoria/cgroup y cancelación. Comparar OCI ligero y systemd+UID real sin que el puerto 8115 ni 8101–8103 cambien. El Engine pinneado y los originales conservan el contrato portable de I5C/I11. No se crea un contenedor persistente por usuario.

**No fusionar a `main` antes de completar la unión Proyecto→Engine aislado→Companion físico→MP4.**
