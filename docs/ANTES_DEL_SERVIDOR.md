# Preparación antes del servidor: estado y lista de cierre

28 de octubre de 2026. Esta es la lista operativa actual; el inventario completo de funciones sigue en [paridad Editor/Mixer](audit/PARIDAD_EDITOR_MIXER.md).

**Objetivo inmediato:** instalar una versión identificable en un servidor Linux limpio, abrir Montara de forma privada, cargar las fuentes de un ejemplo real, editar, exportar y medir; no descubrir allí dependencias ausentes. Eso no equivale a haber incorporado todas las herramientas de Zucker ni a estar listo para abrir suscripciones públicas.

## A. Preparación de la primera prueba de vídeo

| Trabajo | Estado y evidencia |
|---|---|
| Fuentes y versiones identificables | Engine y Mixer siguen fijados a sus commits, sin modificaciones. Contenedor con identidad de Montara y proveedores mediante argumentos de build. No cambiar los pins automáticamente. |
| Instalación Linux repetible | Dockerfile, dependencias resueltas en `deploy/requirements-linux.lock`, FFmpeg, fuentes de subtítulos y runtime de importación Deno 2.5.6 / yt-dlp 2026.10.21 / EJS 0.8.0. El nuevo contenedor debe pasar su CI, no solo instalar paquetes. |
| No copiar claves o datos de trabajo a la imagen | `.dockerignore` excluye archivos de entorno, entornos virtuales, estado del selector, logs y salidas. No añadir credenciales ni medios del usuario al checkout. |
| Espacio y escritura antes de trabajar | `python -m deploy.preflight --server --data /data --smoke`: comprueba volumen, margen de disco, dependencias, fuentes, exportación y decodificación sintética H.264 + AAC + texto. No es un benchmark del producto ni una garantía para archivos de 30 GB. |
| Evitar descarga sorpresa de Whisper | `python -m deploy.warmup --data /data`: descarga/verifica el modelo local en volumen persistente y ejecuta una decodificación CPU. Registra tiempos de descarga/caché, carga y prueba por separado. No conecta un LLM ni una API de pago. |
| Acceso de prueba privado | Usuario `montara`, contraseña mínima de 16 caracteres, puerto solo en localhost del servidor. Una instancia y un usuario de edición a la vez. No es autenticación pública multiusuario. |
| Datos persistentes y recuperación | Volumen dedicado; healthcheck autenticado; comprobación de que proyecto, fuentes y exportación sobreviven a reinicio. Montara no hereda por accidente las rutas del Editor local. |
| Ejemplos completos | Stage con cámaras y master o nueve stems; Show con narración/recursos separados y Podcast con cámaras/micros. No sustituir por un vídeo ya editado. Preflight comprueba fuentes base; pruebas específicas verifican su uso. |
| Recorrido real y tiempos | Stage, Push, Mix y Session tienen aceptación Linux previa en [40517716811](https://github.com/amehcgracia-byte/Montara/actions/runs/40517716811). Esta rama añade Stage contra el contenedor autenticado, descarga del resultado por HTTP y recuperación tras reinicio. El resumen distingue segundos medidos del motor, recorrido de navegador con esperas y duración de salida. |
| Soporte del primer día | Instrucciones y comprobaciones en [deploy/README.md](../deploy/README.md). No requiere un cambio de estética, un dominio nuevo, un LLM o GPU para probar Stage en CPU. |

**Instalación base y primer vídeo: comprobados.** La aceptación nativa y la del contenedor están enlazadas al final. Esto cierra la preparación A para una primera prueba privada; no cierra los desarrollos de B ni acredita recursos del futuro alojamiento.

## B. Desarrollo que puede hacerse sin Abacus y aún no está completo

Esta lista no debe desaparecer ni trasladarse a «necesita servidor» para poder declarar todo terminado.

| Pendiente | Qué falta / relación con el primer día |
|---|---|
| Vídeo de una canción de sesión completa | Audio por lotes ya existe. Falta asociar todas las cámaras a la línea temporal común, con desfase/deriva y cobertura por canción, y ofrecer crear el vídeo sin repetir todos los análisis. No bloquea exportar un vídeo Stage de canción única; sí bloquea prometer vídeo de una jam entera. |
| Edición de cortes equivalente en todos los modos | Split, delete y undo están más completos en Show. Falta verificar y cerrar su equivalencia en Stage y Push, no solo mover límites o cambiar zoom. |
| Sustitutos Linux de recorte de persona y cambio de fondo | Las funciones del motor basadas en Vision/Quartz siguen dependiendo de Mac. El chroma verde/negro portable no sustituye segmentación de persona en un fondo cualquiera. Elegir e integrar una alternativa portable para las funciones que conservemos; no instalar todos los modelos del Studio. |
| Selección de controles adicionales de Mixer | Revisar estéreo vinculado y elegir los controles realmente necesarios. No añadir todos los de la aplicación original ni convertir la selección pendiente en un supuesto bloqueo de Abacus. |
| Selección de Show avanzado | Pintura, seguimiento, audio avanzado y otras familias siguen pendientes de elección conjunta. La existencia del código original no prueba acceso o exportación en Montara. No se consideran integradas por tener una ruta del motor. |
| Biblioteca humana seleccionada | Promover recursos de forma explícita, manteniendo categorías, tipo de fondo y procedencia. Los candidatos guardados en el selector separado no son aprobaciones automáticas del catálogo comercial. |
| Proxies locales y render final en el ordenador del usuario | Hay prototipo. `main` incorporó en `a8b7226` una selección revisada de caché/proxies y benchmarks de Fernando; ver [integración de Fer](INTEGRACION_FER_2026-10-28.md). Los laboratorios de carpetas/proyectos y endpoints experimentales de `fernando/continuacion-montara` siguen separados: no hay asistente instalado ni recorrido completo. Es otra entrega, independiente de la primera prueba de render remoto. No confundir fragmentar la subida con evitarla. |
| Sesiones y originales grandes reales | La subida reanudable y detección por bloques están implementadas. Faltan material representativo, disco y pruebas de muchas horas/30 GB; se puede probar donde existan esos recursos, no exige el nombre de un proveedor concreto. |
| Autenticación, planes y cuotas públicas | Acceso privado y simulador de planes existentes no son suscripciones cobradas. Se puede desarrollar sin Abacus; requiere acordar identidad, pagos, cupos y conservación. No es requisito para la primera prueba privada de uno en uno. |

**Criterio de cierre:** cada función que se incluya en la versión de prueba debe tener acceso en Montara, receta guardada, comportamiento Linux definido y caso de preview/exportación verificado. Las funciones aún no seleccionadas o que dependan de Mac se mantienen visibles en esta lista; no se ocultan como «ya listas».

## C. Pruebas y conexión cuando exista el servidor/cuenta

1. Verificar la máquina real: CPU, RAM, límites efectivos, almacenamiento persistente y espacio temporal; permiso para Docker o un proceso Python persistente. Confirmar GPU, driver y CUDA si se contrata una; no suponerlos incluidos por tener acceso a modelos.
2. Ejecutar el preflight y la primera prueba con el mismo ejemplo de referencia. Registrar fase fría y repetición, duración/resolución de fuentes y salida, RAM/disco, errores y transferencias. Medir el vídeo real del usuario después.
3. Configurar la IA interna: credenciales, URL/modelo real, contratos de Story/Podcast/Gamer que se decidan, consumo y calidad. La capa común ya existe; una respuesta simulada no acredita el proveedor real. Ver [STANDARD_AI.md](STANDARD_AI.md).
4. Probar enlaces de YouTube nuevos desde esa infraestructura y verificar qué acceso admite la fuente. Runtime instalado no garantiza ausencia de verificación. No prometer una solución al CAPTCHA por cambiar de IP o iniciar sesión en Google.
5. Evaluar aceleración de Whisper/render y **CorridorKey**, con calidad, tiempo, VRAM y disco medidos. CorridorKey queda expresamente apartado hasta disponer de NVIDIA/CUDA compatible: candidato, no integrado, sin correo comercial enviado. Ver [nota de candidato](CORRIDORKEY_CANDIDATO.md).
6. Medir varios usuarios con aislamiento por instancia/volumen, cola y límites. La primera prueba usa un único editor por instancia; no aumentar workers sobre un proyecto global compartido para simular multiusuario.
7. Ajustar presupuestos y planes solo con costes medidos: cómputo, IA, almacenamiento, transferencia y conservación. No activar cobros ni gastos por uso automáticamente.
8. Configurar dominio/HTTPS, cuentas de pruebas externas y recuperación/copia de seguridad para el alojamiento elegido. Antes se puede probar privadamente mediante SSH, sin publicar el ordenador personal.

## Qué podremos afirmar al cerrar A

«La versión está preparada y comprobada para instalarla y hacer una primera prueba privada de vídeo en Linux. Nos faltan las comprobaciones de la máquina y los servicios reales.»

**Eso no equivale todavía a «todo lo que puede hacerse antes del servidor está terminado».** Para esa frase también hay que resolver el alcance y los pendientes de B. La cuenta de Abacus no debe ser una excusa para posponer desarrollo local que sigue abierto.

## Aceptación técnica de esta preparación

- Código de instalación y aislamiento: `ec08344`. [Ejecución 40674705733](https://github.com/amehcgracia-byte/Montara/actions/runs/40674705733): los cuatro recorridos nativos Stage, Push, Mix y Session pasaron en Linux. Suite: **122 pruebas Python**, 31,93 s; en Mac: 122 aprobadas en 50,55 s. Un primer pase frío de Mac tuvo un timeout no reproducido en el test de cola de Push; se comprobó aislado y luego se repitió la suite completa. No se cambió el producto para ocultarlo.
- El primer contenedor llegó a resultado y descarga por HTTP, pero su cliente de CI no tenía `ffprobe`. Su aceptación quedó fallida, sin completar inspección/reinicio. Se corrigió la instalación del cliente en `2a95271`; no se declara aprobado ese primer ensayo.
- La repetición solo del contenedor **pasó** en [40677610059](https://github.com/amehcgracia-byte/Montara/actions/runs/40677610059), código `2a95271`, con el mismo código de producto y el cliente corregido: acceso privado, Stage real, intercambio de toma, descarga por HTTP, inspección/decodificación completa del MP4 y recuperación de fuentes/proyecto/exportación tras reiniciar. Se inspeccionaron sus tres capturas finales.
- Se incorporó después `main` (`a8b7226`), que añade los proxies/cachés revisados de Fer sin conectar esos prototipos a la interfaz. La versión combinada pasó **147 pruebas locales en 60,77 s**. Esa integración de Fer tiene además sus cuatro recorridos Linux aprobados en [40677455132](https://github.com/amehcgracia-byte/Montara/actions/runs/40677455132). Se conservan los commits y resultados distintos: no se presenta el ensayo de contenedor `2a95271` como un nuevo render de cada commit documental o del prototipo posterior.
- Se inspeccionaron las capturas Linux de cámaras, selección de frames y pantalla final del primer contenedor. El reproductor headless puede verse negro por sus códecs; la aceptación exige además inspeccionar y decodificar el MP4. GitHub tiene cuota de artefactos agotada: se conservan capturas acotadas e informes en los logs del ensayo, sin depender de que la subida de artefactos funcione.

Medidas recuperadas del recorrido Stage nativo, fixture `much-to-me`: salida **100,233333 s / 1920×1080**, 19 cortes; ingestión **62,241 s**, sincronía **15,264 s**, edición **17,048 s**, exportación **429,549 s**. Recorrido de navegador **1054,458 s**, incluyendo esperas, preparación de vistas y descarga. Las fases no suman ese recorrido y no se presenta todo él como tiempo de render. Son una ejecución de CI, con recursos efectivos del runner no inventariados aquí; **no son rendimiento de Abacus ni del contenedor limitado a 2 CPU/8 GiB**.

La prueba de instalación del primer contenedor sí registró esos límites, runtime correcto, volumen escribible y exportación sintética correcta. Su preparación de Whisper CPU separó descarga/comprobación de caché **2,476 s**, carga **0,726 s** y prueba sintética de silencio **3,542 s**. No mide precisión de transcripción ni velocidad con una voz real.

El contenedor limitado a **2 CPU / 8 GiB**, ya con el cliente corregido, produjo una salida de **100,233991 s / 1920×1080**, 16 cortes y tres cámaras utilizadas. Tiempos de motor: ingestión **47,993 s**, sincronía **12,040 s**, corte **0,008 s**, edición **12,691 s**, exportación **329,192 s**. Recorrido de navegador con esperas y descarga: **811,000 s**. Pico del cgroup antes de reiniciar: **1.972.752.384 bytes, unos 1,84 GiB**, incluyendo procesos y caché del contenedor; no es RSS individual ni una previsión para 4K/30 GB. Los planes tienen distinto número de cortes respecto al recorrido nativo: no se calcula una mejora porcentual entre ambas pruebas.

La prueba CPU permite instalar y medir un primer vídeo; **no demuestra edición instantánea ni cumple por sí sola todos los objetivos de velocidad**. Conservar estas referencias para comparar con la máquina real.
