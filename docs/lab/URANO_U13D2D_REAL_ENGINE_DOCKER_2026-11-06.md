# URANO U13D2D — Engine real en contenedores privados

Fecha: 2026-11-06. **Estado: PR draft. CI inicial pendiente. No desplegado.**

## Hipótesis y novedad

U13C comprobó que el Engine verdadero puede cargar dos proyectos sintéticos en un subprocess. U13D2B demostró aislamiento de archivos entre dos contenedores Docker usando Python sintético; U13D2C comprobó el puente supervisor ↔ Docker con un worker sintético. **Este gate combina las dos piezas:** dos contenedores reales construidos con el `Dockerfile` oficial de Montara y su Engine fijado como submódulo, con el worker `urano.engine_worker_process` y el puente `ContainerWorkerBridge`.

## Diseño de la prueba

- CI `.github/workflows/urano-u13d2d-real-engine.yml` hace checkout con submódulos recursivos, construye el Dockerfile existente **sin desplegarlo**, extrae el ID inmutable local `sha256:...` (sin registrar ni publicar imagen) y arranca una prueba de apertura de proyectos.
- `tests/test_urano_real_engine_docker.py` crea únicamente dos carpetas ficticias de propietario en el runner. Los `project.json` se generan usando `core.project.new_project_document()` **del Engine real dentro de esa imagen**, no documentación falsa.
- Se crean dos catálogos/bindings válidos por propietario (la API y el proceso de autenticación real siguen fuera). El supervisor arranca dos contenedores Linux simultáneos, sin red, sin root/capabilities, con filesystem principal de solo lectura, límites CPU/memoria y un único volumen de proyecto cada uno.
- Alice abre `Earlier`, Bob abre `BobProject`; Alice cambia a `Recent` mientras Bob permanece en su propio runtime. La respuesta del Engine se valida contra `ZUCKER_STATE.project.folder`; tras terminar y verificar retirada de contenedor se invalidan los slots del supervisor.
- Intentar usar el ID de un proyecto de Bob desde el runtime de Alice debe fallar antes de enviar su carpeta al Engine. **Sin vídeos** en esta prueba.
- La policy de Docker ahora permite tanto `repo@sha256:...` como `sha256:...` de imagen local inmutable, sin permitir tags mutables. Se añade `PYTHONPATH=/app` para importar la implementación privada de URANO mientras el workdir/data root de cada worker permanece en `/workspace`.

## Condiciones y seguridad

**No es todavía una beta para Chema ni el producto final.** Este test demuestra que el protocolo combinado puede abrir proyectos sintéticos con Engine real en Docker. **No** hace edición o export de vídeo, no valida Companion ni Stage/Push/Show, no mide rendimiento, no habilita autenticación web ni lectura de medios privados.

Los workspaces sintéticos en la máquina efímera CI tienen permisos permisivos sólo para que el UID 10001 del contenedor escriba el proyecto; **prohibido reutilizar este aprovisionamiento en una VM multiusuario o producción**. Antes del uso real se exige aprovisionar carpetas privadas con permisos correctos (UID o mapeo seguro), límites de datos, secretos, sockets y carga de FFmpeg. El Engine podría requerir accesos de red específicos para funcionalidades futuras; conservar modo sin red en esta prueba de lectura.

La pila de PR U10 → U11 → U12 → U12b → U13A → U13B → U13C → U13D → U13D2A → U13D2B → U13D2C → U13D2D sigue **draft**, sin fusionar y sin modificar `main`, despliegues Vercel/Cloudflare, hosts FER/JM, ni DNS. Nunca confundir suites verdes aisladas con beta final.

## Próxima etapa real

- Confirmar y documentar estado exacto del job Docker U13D2D y corregir fallos reproducibles del gate.
- U13E: añadir material sintético y ejecutar **edición/export real**, primero local en contenedor y después workflow distribuido Companion/servidor, incluyendo recuperación de medios/proxies. El objetivo de concurrencia es 1,2,4,8,10,25 usuarios con trabajo dividido según el Companion, **NO todo render en servidor**. Sin cola global obligatoria.
- Antes de beta externa: host endurecido, identidad real, autorización de rutas, lifecycle del worker muerto, relink de originales, revocación y prueba E2E navegador/edición/export con dos cuentas. Solicitud de acceso de Chema pendiente; sin contraseña predecible ni usuario vacío.
