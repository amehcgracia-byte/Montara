# Paridad de Montara con Zucker Editor y Zucker Mixer

27 de octubre de 2026. Objetivo: conservar las posibilidades de las aplicaciones originales con una interfaz sencilla, sin convertir al usuario en quien descubre las omisiones.

## Referencias verificadas

- Aplicación instalada: `/Applications/Zucker Editor.app`, versión **2.6.20**, commit incluido en `build_info.json`: `c30a1d407e63be9b647726562a1b96fdd4cd8c77`.
- Motor incorporado por Montara: `60a7b7e9a39077b36f45057811abd6a833a168ef`. Contiene ese commit instalado: no es correcto concluir que Montara usa un motor antiguo solo por mirar otra rama.
- Mixer instalado: `/Applications/ZuckerMixer.app`, versión **2.8.12** según Info.plist. No se ha identificado un commit empaquetado para esa instalación.
- Mixer incorporado: `c7a46a6d8388c6e0703ef54983f2d627ea189f32`. Se compara también con el master público `c2bfd49667cd…`, versión declarada 2.8.13. No actualizar el submódulo sin revisar las diferencias.
- Montara base: `2be91af3da43916874b1066bdd55685f7bdfcbfd`, 0.38. El cambio de instalación del importador está en PR #4.

El inventario reproducible `capabilities.json`, generado por `tools/capability_inventory.py`, enumera módulos, funciones públicas, controles de HTML y rutas con archivo, línea y commit. La presencia de código no demuestra que la función esté accesible, que las dependencias estén instaladas o que exporte correctamente. Las rutas adicionales de Montara conviven con las del motor: **no se deben restar sus cantidades para calcular funciones faltantes**.

La comparación incluye el estudio original en `engine/tools/qa/`, porque el servidor lo utiliza para Show Studio. No todo archivo de esa carpeta es una función comercial acabada; los prototipos necesitan una comprobación de integración.

## Estados y criterio de diseño

**Conectada** = se localizaron acceso en interfaz y llamada correspondiente; no equivale a prueba completa de todos los casos. **Parcial** = existe una parte o un acceso reducido. **Pendiente** = no se localizó acceso equivalente en la interfaz de Montara revisada. **Adaptar** = depende del escritorio, sistema operativo o servicio externo y necesita una solución web. **Verificar** = hace falta probar el caso real antes de asegurar equivalencia.

Este inventario identifica posibilidades, no autoriza trasladarlas todas. La selección acordada con el usuario determina qué se incorpora. El diseño debe mostrar herramientas según el objeto seleccionado: clic derecho y panel contextual para vídeo/efecto, FX para pistas, y opciones avanzadas plegadas. Mantener las pantallas actuales y sus ejemplos con fuentes separadas.

## Stage y funciones comunes de vídeo

| Capacidad original | Estado en Montara | Acceso sencillo y comprobación requerida |
|---|---|---|
| Varias cámaras que empiezan en momentos distintos | Conectada | Box de vídeos; comprobar desfases reales y tomas sin audio útil. |
| Master externo y pistas separadas | Conectada | Box de audio; no sustituirlo por sonido de cámara. |
| Distinguir 360, fija y móvil | Conectada | Tipo de cámara al importar; conservar nombres genéricos. |
| Marcar y nombrar puntos de vista de 360 | Conectada | Preparación de cámaras y edición sobre imagen. |
| Cambiar tiro 360 por escena | Conectada / verificar | Arrastre y zoom; comparar preview y exportación. |
| Reencuadrar cámara plana por escena | Conectada / verificar | Recorte, posición y zoom dentro de Edit. |
| Movimiento de cámara 360 grabado y coreografía plana | Parcial | Motor `camera_moves.py` y `fixed_camera_moves.py`; distinguir tiro fijo de trayectoria con tiempo. |
| Distribución de cámaras y ritmo según música | Conectada / verificar | `music_direction.py`; pruebas con canciones distintas, no solo fixtures. |
| Sustituir una toma conservando duración | Conectada | Swap en selección de frames. |
| Mover límites entre tomas | Conectada / verificar | Cut editor; conservar límites válidos y sonido continuo. |
| Dividir y eliminar fragmentos en todos los modos | Parcial | Adaptador nuevo de split/ripple-delete centrado en Show de una fuente; falta demostrar equivalencia en Stage y Push. |
| Deshacer/rehacer sin render bloqueante | Parcial | Implementado en edición Show; no asumir misma cobertura en todas las pantallas. |
| Proxies y caché de preparación | Conectada / verificar | Evitar regenerar medios por cada ajuste; medir invalidación y exportación. |
| Procesamiento de sesión completa con varias canciones y vídeos | Pendiente | Nueva selección de canciones que mantenga asociación temporal con cámaras. |
| Abrir carpetas y salidas del sistema | Adaptar | En web: descargas y biblioteca, sin botones de escritorio que fallen. |

Fuentes: `engine/server/wizard.py`, `engine/server/edit_timeline.py`, `engine/core/music_direction.py`, `engine/core/camera_moves.py`, `engine/core/fixed_camera_moves.py`, `web/montara.js`, `web/cut-editor.js`, `web/flat-camera.js`.

## Mixer: audio solo, mezcla y master

| Capacidad original | Estado en Montara | Acceso sencillo y comprobación requerida |
|---|---|---|
| Mezclar una canción con sus instrumentos | Conectada | Faders y reproducción del resultado. |
| Ajuste automático de niveles y roles | Conectada / verificar | Mostrar y escuchar exactamente los niveles aplicados. |
| Fader por instrumento y mute | Conectada | Mantener los niveles entre preview, FX y master. |
| Panorámica manual por pista | Parcial | El plan y preview usan pan, pero no se localizó un control manual en las tiras. |
| Solo por pista | Pendiente | El Mixer original lo ofrece; Montara expone mute. |
| Ecualización por instrumento | Parcial | Procesado automático heredado; sin controles equivalentes para ajustes del usuario. |
| Gate/expansor y control de ruido por pista | Parcial | Diferenciar procesado automático de controles manuales ausentes. |
| Reverb y delay, activación e intensidad | Conectada | FX contextual por pista; hay pruebas de ganancia y suma. |
| Ajustes específicos de batería y pistas equivalentes | Parcial | Automatismo del pipeline; no toda su edición está expuesta. |
| Master con referencia local | Conectada / verificar | Medir niveles, dinámica y clipping con/sin FX. |
| Referencia desde enlace | Parcial / adaptar | Importador conectado; bloqueos de fuente externos. |
| Preview exacto frente a escucha rápida aproximada | Parcial | Comparar Web Audio con render Python, FX y pan. No presentarlos como idénticos sin medición. |
| Detectar canciones en una jam de varias horas | Parcial / verificar | Nuevo adaptador de sesión con detector acústico original, caché y revisión de cortes; recorrido de 6:30 probado. Falta medir una jam real de varias horas. Canción única conserva su adaptador. |
| Revisar, dividir, unir y renombrar canciones detectadas | Pendiente | Reutilizar Select Cuts mediante adaptador, no copiar toda su pantalla. |
| Reanalizar con revisión de candidato/segunda pasada | Pendiente | Conservar decisiones previas y permitir aprobar un nuevo análisis. |
| Mezcla común de sesión con ajustes por canción | Parcial | Mezcla común, mute y FX para canciones elegidas implementados; ajustes independientes por canción todavía no expuestos. |
| Renderizar varias canciones, cancelar y recuperar resultados | Conectada / verificar | Lote MP3, cancelación y recuperación explícita del manifiesto en disco. Probado con dos ventanas; pendiente carga prolongada real. |
| Historial de versiones de mezcla por canción | Parcial / verificar | No equivale al historial visual de Show. |

Fuentes: `mixer/jam_app.py`, `mixer/jam_mix_pipeline.py`, `mixer/static/app.js`, `mixer/static/tutorial.js`, `mixer_adapter/single_song.py`, `web/montara.js`, `web/mix-levels.js`.

## Push y subtítulos

| Capacidad | Estado | Comprobación / adaptación |
|---|---|---|
| Reel desde varias cámaras y master | Conectada / verificar | Comprobar audio master en todos los ejemplos. |
| Cuatro reels desde un archivo | Conectada / verificar | Selección, duración, exportación independiente y captions. |
| Cuatro reels desde enlace nuevo | Parcial / adaptar | No usar cache-hit como prueba de descarga. |
| Vertical, horizontal dentro de lienzo vertical, Mix y Mix Alternate | Conectada / verificar | Comparar preview/export de los cuatro formatos. |
| Porcentaje horizontal/vertical dentro de Mix | Conectada / verificar | Conservarlo al modificar intervalo y encuadre. |
| Elegir encuadre y zoom por reel | Conectada / verificar | No confundir recorte de fuente con orientación de salida. |
| Seleccionar frases musicales y evitar títulos/logos de entrada | Parcial | Análisis audiovisual conservador; no se afirma comprensión semántica general. |
| Transcribir otra vez tras mover el intervalo | Conectada / verificar | Casos de ampliación a ambos lados y cambio total del fragmento. |
| Letras introducidas por el usuario y alineación por palabra | Conectada / verificar | La temporización debe derivarse del audio, no del número de caracteres. |
| Estilos, color, glow y palabra a palabra | Conectada / verificar | Comparar fuente, preview y subtítulos quemados. |
| Separación de captions, puntuación, ajustes de tiempo | Conectada / verificar | No confundir silencios con cortes visuales. |
| Subtítulos traducidos | Pendiente / adaptar | Existe `show_translate.py` en el motor; no se localizó acceso equivalente general en Montara. |
| Agenda y publicación social | Pendiente, nueva función | Referencia Ssemble; no asumir que ya existe por reutilizar Editor/Mixer. |

Fuentes: `push_pack.py`, `reel_selection.py`, `source_cache.py`, `web/push-pack.js`, `engine/captions/`, `engine/core/show_translate.py`.

## Show: cuatro modos y edición general

| Capacidad original | Estado | Acceso / prueba requerida |
|---|---|---|
| Gamer rápido e Influencer más pausado | Conectada / verificar | Comparar planes, duraciones y resultado con fuente idéntica. |
| Zoom por lo que se dice | Parcial | `show_direction.py` es una heurística de texto; no un director LLM completo. |
| Story con narración, imágenes y clips separados | Conectada / verificar | Asignación semántica requiere proveedor o plan revisado; no prometer equivalencia por fixture. |
| Podcast con micros separados y varias cámaras | Conectada / verificar | Pruebas con voces solapadas, desfase y micros compartidos. |
| Podcast 360, asignación de asiento y corrección de cámara | Conectada / verificar | Persistir corrección por tramo y comprobar render. |
| Revisar y guardar decisiones de montaje | Conectada | Planes e historial; mantener trazabilidad. |
| Navegar atrás por fuentes y estilo sin saltar pasos | Conectada / verificar | Comprobar estado restaurado después de recarga. |
| Añadir efecto desde selección de texto | Conectada | Tiempo ligado al fragmento seleccionado. |
| Clic derecho en vídeo y en efecto | Conectada / verificar | Menús según objeto; deselección al reproducir y clic fuera. |
| Posición, escala y recorte sobre el vídeo | Conectada / verificar | No usar la selección como visibilidad forzada del efecto. |
| Timeline Video Cuts + FX y música | Conectada / verificar | Comprobar actualización inmediata, cursor y arrastre. |
| Texto, zoom y efectos sencillos | Conectada | Subconjunto accesible; no equivale a todo Show Studio. |
| Edición completa de Studio por capas | Parcial / adaptar | Studio tiene modelo/controles propios; la puerta `/api/v1/show-studio/` no está autorizada en la preview actual. No abrirla sin límites de sesión y archivos. |

Fuentes: `web/show-modes.js`, `web/show-editor.js`, `web/show-live.js`, `web/compact-editor.js`, `show_editor_state.py`, `show_direction.py`, `engine/core/show_edit.py`, `engine/core/show_story.py`, `engine/core/show_podcast.py`, `engine/server/show_studio_api.py`, `deploy/sandbox_entry.py`.

## Show: medios, dibujos, personajes y audio avanzado

| Capacidad original | Estado | Adaptación sencilla |
|---|---|---|
| Importar imágenes, vídeo y audio locales | Conectada | Biblioteca y botón + por pista. |
| Importar fragmento de vídeo/voz por enlace | Parcial / adaptar | Fallo real de acceso a YouTube desde Vercel tras corregir JS; ver informe del runtime. |
| Reutilizar originales y fragmentos guardados | Conectada | Caché por vídeo y biblioteca por proyecto; comprobar aislamiento. |
| Ocultar/retirar recursos de biblioteca | Conectada | Mantener efectos existentes al retirar una fuente del catálogo. |
| Catálogo seleccionado de dibujos animados | Pendiente | Las decisiones viven en selector separado, no están promovidas al catálogo de la app. |
| Distinguir vídeo con fondo y green screen | Parcial | Colecciones separadas en selector; conservar tipo al promover. |
| Quitar fondo verde/negro, lluvia/humo de borde suave | Conectada / verificar | Comprobar alpha en preview y export, no solo miniatura. |
| Recortar sujeto de foto | Conectada / adaptar | Función original usa capacidades que pueden depender del SO; validar en Linux. |
| Recortar sujeto móvil del vídeo | Parcial / adaptar | Opción presente; demostrar segmentación en servidor y paridad con Mac. |
| Imagen con boca y ojos, voz del narrador | Conectada / verificar | Rectángulo durante arrastre, sincronía, tiempo de entrada/salida. |
| Voz propia desde archivo, enlace o micrófono | Conectada / verificar | Enlace sujeto a bloqueo; micrófono requiere permiso del navegador. |
| Herramientas de pintura y pinceles sobre imagen | Pendiente | `show_paint_tools.js`, `show_bridge_draw.py`; panel contextual de dibujo. |
| Dibujos que siguen mano/dedo | Pendiente / adaptar | Trayectorias y análisis compartidos; no equivalen a overlay estático. |
| Fórmulas, texto y animaciones geométricas de Studio | Parcial | Clips de biblioteca no son equivalentes a editar esos objetos. |
| Espirales, vapor y otros efectos geométricos | Pendiente | Recuperar parámetros desde el mismo objeto visual. |
| Seguimiento de objeto y texturas sobre él | Pendiente / adaptar | `show_follow.py`, `show_textures.py`; medición de análisis y caché. |
| Movimiento de partes de imagen y capas de píxeles | Parcial | Boca/ojos conectados; Studio permite más regiones y transformaciones. |
| Siluetas, pintar dentro del sujeto, duplicados | Pendiente / adaptar | Studio dispone de ejemplos; verificar cuáles compila el render real. |
| Sustituir fondo del narrador | Parcial / adaptar | La UI tiene intención de background, pero `show_backgrounds.available()` exige macOS y Vision. La misma implementación no funciona en Linux: necesita segmentador alternativo y pruebas de paridad. |
| Entradas/salidas y coreografía de personajes | Parcial | Montara guarda entradas simples; no expone todas las posibilidades originales. |
| Fototeca y extraer foto desde vídeo | Parcial | El motor ofrece endpoints específicos; no se localizó acceso completo en el flujo nuevo. |
| Face swap | Pendiente / adaptar | El motor lo describe como ejecución en Mac; confirmar proveedor/modelos portables antes de ofrecerlo. |
| Clay/storyboards y dibujos revisados generados por IA | Pendiente / adaptar | Servicios y aprobación de borradores; no cambiar por efectos simulados. |
| Brief/idea del show y dictado | Pendiente | Reducir a solicitud opcional; no añadir formulario obligatorio. |
| Biblioteca de música y preview por canción | Conectada | Procedencia, licencia y estado seleccionado visibles. |
| Música por enlace, volumen y colocación | Conectada / verificar | Verificar importación externa y mezcla/export; el catálogo no garantiza permisos de un enlace. |
| Limpiar ruido y equilibrar narración | Pendiente de acceso equivalente | `show_audio.py` y `web/show_audio.js` originales; comprobar controles disponibles en Montara. |
| Censura por palabras con efecto sonoro | Pendiente de acceso equivalente | Preservar edición temporal y sonido original fuera del tramo. |
| Conectores propios de IA y estado de cuenta | Adaptar | No hay interfaz de conectores equivalente en Montara; no copiar credenciales ni accesos de escritorio. |

Fuentes: módulos `engine/core/show_*.py`, `engine/web/show_*.js`, `engine/tools/qa/show_studio_tools.js`, `show_paint_tools.js`, `show_scene_workshop.js`, `show_timeline_model.js`; integración actual `web/show-media.js`, `web/show-music.js`, `web/show-chroma.js`, `show_library.py`, `green_library.py`, `music_shelf.py`.

## Rendimiento, instalación y servicio

| Área | Situación y requisito |
|---|---|
| Dependencias completas de importación | Faltaban EJS y motor JS utilizable en plantilla; se han corregido y probado en Linux. La negativa de YouTube persiste con dos enlaces. |
| Mac frente a Linux | Vision/Quartz, recorte de persona y face swap necesitan evaluación explícita. No es un problema que se resuelva copiando HTML. |
| Preview frente a export | Cada herramienta debe producir la misma receta y resultado en ambos. Cambios de geometría no deben recalcular transcripción o sincronía. |
| Proyectos aislados | Mantener autorización por usuario y límites de archivos antes de exponer más API del motor. |
| Cancelación y reintentos | Existen en fuentes; comprobar qué trabajos expone Montara y que no deja recursos huérfanos. |
| Almacenamiento | Mantener espacio de trabajo y persistencia; el arreglo anterior preserva proyectos. No usar catálogo prerenderizado como sustituto de procesamiento. |
| GPU | La preview verificada es CPU, 2 vCPU. No afirmar aceleración GPU instalada. Se necesita perfilado por tarea, compatibilidad de modelos y codificador. |
| IA | `app.py:_prepare_environment()` fija `MONTARA_LOCAL_DIRECTOR=1`; `engine/core/gag_director.py:claude_cli()` devuelve None con ese valor. Montara desactiva expresamente esa vía del director Claude de escritorio. Distinguir heurísticas, planes guardados y llamadas reales; hace falta un proveedor web configurado para recuperar esa capacidad. |
| Acceso testers y suscripciones | Preparación parcial; no equivalen a autenticación, facturación y cuotas públicas completas. |
| Biblioteca y permisos | Promoción explícita de recursos, conservar colecciones/procedencia; no inferir licencia por encontrar un clip online. |

## Alcance acordado con el usuario — 27 de octubre de 2026

- **Sesiones largas de Mixer: incorporar.** Detectar canciones dentro de una jam de varias horas, permitir revisar sus límites y aplicar una mezcla común a las canciones elegidas. Conservar la asociación temporal de vídeos y pistas para poder solicitar después el vídeo de una canción. Usar el detector original mediante un adaptador de sesión; no sustituirlo por el adaptador actual de canción única.
- **Muchos archivos y vídeos de hasta 30 GB: objetivo de diseño, todavía no capacidad verificada.** La preview pública limita actualmente las subidas a 256 MiB. Este objetivo requiere copias pequeñas para editar, transferencia reanudable de originales cuando el render sea remoto, almacenamiento persistente suficiente y trabajos que procesen por bloques. Medir espacio temporal, memoria y tiempos con material representativo antes de ofrecerlo. No basta con aumentar el límite de una petición.
- **Mixer: conservar la sencillez actual.** Revisar juntos los controles manuales antes de implementar cambios. Investigar el enlace de dos pistas como pareja estéreo, con asignación izquierda/derecha y controles vinculados; confirmar el comportamiento del original. No añadir por defecto pan, solo, EQ o gate por aparecer en el inventario.
- **Show avanzado: selección conjunta pendiente.** Revisar las herramientas originales por familias con ejemplos y elegir cuáles aportan valor. No dar por aprobada la incorporación de pintura, seguimiento, face swap ni del resto del Studio completo.
- **IA: Abacus como destino previsto.** No recuperar los conectores de escritorio de Claude/ChatGPT como requisito de Montara. La aplicación necesitará una integración interna con el servicio de IA elegido; eso no obliga a mostrar conectores al usuario. La cuenta aún no existe y no hay integración ni GPU verificadas. Preparar el prompt de traspaso cuando el usuario se registre, no antes.
- **Linux: solo dependencias de herramientas elegidas.** Para cada herramienta seleccionada, comprobar si usa Vision/Quartz u otra tecnología de Mac y decidir su alternativa portable. No instalar modelos o componentes de funciones descartadas.

### Planes y consumo de IA — aclaración del usuario

Precios orientativos, todavía sin facturación ni límites comerciales definitivos:

| Plan previsto | Acceso previsto |
|---|---|
| Entrada, 15 €/mes | Edición y procesamiento base. Sin acceso general al LLM; las posibles tareas simples de IA, como un cartel, deben definirse expresamente y tener presupuesto acotado. Sin storyboards. |
| Intermedio, 30 €/mes | IA limitada a herramientas de Montara, con cupo medido y visible antes de ejecutar trabajos adicionales. |
| Editor profesional, 50–55 €/mes | Todas las herramientas aprobadas y mayor capacidad. La intención comercial es acceso amplio sin un contador restrictivo de peticiones; aún no se ha demostrado viable ofrecer consumo de IA ilimitado por una tarifa fija. |

El LLM estará limitado a tareas de vídeo, audio y recursos de la aplicación; no se ofrecerá como agente general para crear otras aplicaciones ni ejecutar instrucciones arbitrarias. Esta restricción de alcance no garantiza por sí sola un coste bajo: duración, reintentos, modelos de imagen/vídeo y concurrencia siguen afectando al consumo.

Preparar medición interna por cuenta y trabajo: proveedor/modelo, consumo que facture el proveedor, coste, duración, reintentos y resultado. Antes de gastar, aplicar autorización por plan y reserva de presupuesto; conciliar el consumo real al terminar, evitar cobros repetidos por reintentos y devolver reservas no usadas. Mantener un techo de gasto del servicio y límites técnicos de concurrencia. Los extras de pago por uso deben tener precio y aceptación explícitos; no facturar sobrecostes automáticamente por haber elegido el plan profesional.

Almacenamiento: separar espacio temporal de procesamiento de originales y proyectos persistentes en almacenamiento externo. Definir capacidad incluida, conservación, limpieza y coste de transferencia antes de publicar ofertas. No se ha comprado almacenamiento ni decidido un proveedor.

### Condiciones previas al traspaso a Abacus

El registro en Abacus no debe convertirse en el momento de descubrir herramientas incompletas. Antes del traspaso, preparar una versión reproducible y probar en Linux las funciones seleccionadas, con archivos reales, preview, exportación y persistencia. Incluir detección de canciones en sesiones largas y la ruta de archivos grandes dentro del alcance acordado. Adaptar las dependencias de Mac solo para herramientas elegidas.

La importación por enlace debe probarse con vídeos nuevos, sin depender de ejemplos previamente descargados. Actualmente YouTube sigue rechazando las dos pruebas frescas aun con EJS y Deno instalados. Registrar ese bloqueo como pendiente: no prometer ausencia de CAPTCHA ni considerar resuelta la importación por cambiar de alojamiento. La instalación del runtime y la autorización del proveedor son problemas distintos.

Se puede preparar y validar el contrato interno de IA y los controles de consumo antes de la cuenta; esas pruebas no acreditan llamadas reales a Abacus. La autenticación, facturación, recursos y rendimiento específicos de Abacus solo se validarán cuando exista acceso. El prompt de traspaso queda aplazado por petición del usuario.

### Abacus: comprobación documental, sin contratación

La [documentación oficial de SuperComputer](https://abacus.ai/help/chatllm-ai-super-assistant/supercomputer), consultada el 27 de octubre de 2026, describe una máquina Ubuntu persistente, alojamiento de aplicaciones, acceso a RouteLLM por API y GPU opcional. Indica acceso desde Pro, consumo del alojamiento de 1 crédito por 5 minutos y consumo de las llamadas al LLM separado del alojamiento. Esto permite estudiar Abacus como destino; no demuestra qué GPU, almacenamiento, concurrencia o rendimiento tendrá la futura cuenta de Montara. No asumir GPU de render incluida ni inferencia ilimitada. No se ha contratado nada.

El estado detallado de la implementación previa a Abacus está en [`../PRE_ABACUS_2026-10-27.md`](../PRE_ABACUS_2026-10-27.md).

## Orden de trabajo ajustado

1. **Sesiones largas:** estudiar el detector original y definir el flujo de revisión de canciones, mezcla común y selección de vídeo por canción. Mantener operativo el flujo sencillo de una canción.
2. **Archivos grandes:** diseñar y medir el recorrido de originales, copias pequeñas y almacenamiento para sesiones con muchos archivos; validar el objetivo de 30 GB fuera del límite actual de la preview.
3. **Revisión conjunta de Mixer y Show:** presentar comportamientos concretos del original y acordar cuáles trasladar. Las tablas anteriores siguen siendo inventario, no una lista de implementación aprobada.
4. **Adaptación de las funciones elegidas:** conservar la interfaz sencilla y resolver únicamente sus dependencias Linux; comprobar preview, persistencia y exportación.
5. **Abacus, cuando haya cuenta:** comprobar recursos, costes y acceso real a modelos; entonces preparar el traspaso e integrar y medir el motor de IA. Separar análisis por LLM de render y aceleración GPU.

Los fallos existentes de importación, edición y exportación siguen registrados; esta selección no los da por resueltos ni elimina su seguimiento.

## Lista de aceptación permanente por capacidad

Registrar: fuente/commit original, modo aplicable, acceso en Montara, llamada al motor, dependencias del servidor, resultado esperado, preview, persistencia y exportación, más un caso real representativo y su medición. Una función pasa a **verificada** solo al completar ese recorrido. Toda nueva versión de Editor/Mixer debe compararse contra este inventario antes de mover el submódulo.

Este documento entrega un inventario y una comparación de código. **No certifica paridad funcional completa ni que las capacidades marcadas pendientes se hayan implementado.** Las 79 pruebas Python y 6 de ciclo de preview validan el arreglo de instalación y regresiones existentes; no sustituyen pruebas específicas para todas estas herramientas.
