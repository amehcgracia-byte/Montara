# Montara 0.62 — encuadre manual, iluminación automática

Decisión de Chema: retirar únicamente la herramienta manual de luz/contraste. Se conserva el ajuste automático entre cámaras y su preparación/medición. No se desactiva la corrección automática ni se borran los ajustes guardados de proyectos anteriores.

El diálogo Edit conserva la cámara, encuadre, zoom, orientación 360 y aplicar encuadre a la misma fuente. Ya no incluye Light, Shadows, Auto manual ni Show original. La petición de guardado usa `edit_component=framing` sin campos de iluminación. Aplicar a la fuente copia solo geometría y preserva la luz de cada toma y los tiempos de corte.

Un encuadre plano ampliado abre suavemente; un general se acerca. Es un movimiento relativo de 6% dentro del área elegida, sin alejarse más allá de esa selección ni añadir paneos al azar. Preview y export usan la misma receta. Estos recortes no se amplían a un intermedio 4K para hacer el pequeño movimiento. Se invalidan las previews/segmentos de la receta anterior.

Editor: `a13dc640ad9b6995b36b3a9f0c6011d20d4e6885`, descendiente de `3ff470ee`, mediante su rama activa. Mixer `f15ff91` sin cambios. No se copia una rama experimental de Fernando.

Validación local: 40 tests de luz/encuadre/previews aprobados; después 14 de encuadre, incluidos tres renders FFmpeg reales que comprueban el sentido del movimiento por el tamaño del objetivo en el primer/último frame. Regresión de revisión por grupos de tres en navegador aprobada. Aceptación Linux aprobada en [41918689424](https://github.com/amehcgracia-byte/Montara/actions/runs/41918689424): Stage, Push, Mix, sesión/Companion y contenedor privado. Capturas de Stage, Push, Mix, Companion, recuperación y contenedor revisadas. PR Montara #73 integrada en main `a6c49ce`; Editor #54 integrado en su rama activa. La repetición aislada del contenedor `41920087336` se canceló cuando se recuperó la comprobación original.

Editor Fast: 1321 aprobadas y los mismos 22 fallos preexistentes, contrastados por nombre; Slow aprobado (`41918503873`). No se afirma que toda la batería del Editor esté verde. Instaladas JM 0.62/main `a6c49ce` y Companion Mac 0.6.2 con engine `a13dc640` y mixer `f15ff91`. HTTP autenticado confirma versión, motor y JS sin `lightAuto`, con activación automática de Stage conservada. No había renders/mezclas activos; wizard estaba en waiting_review. Página abierta mediante el túnel privado estable http://127.0.0.1:8101/. No es un despliegue público de Vercel.

## Personas y solos: trabajo separado, todavía no activado

Chema usa tanto pistas separadas como máster solo. La propuesta es detectar personas de forma acotada sobre copias pequeñas, confirmar qué instrumento corresponde a cada posición, alternar general/individuos y favorecer la actividad de pistas separadas. Detectar una persona no identifica su instrumento. Una subida de nivel tampoco prueba por sí sola que sea un solo; sangrado de micros y panoramas requieren validar umbrales.

Hay un prototipo local sin publicar en la rama del Editor `codex/stage-performer-framing` (`42d89a3e`); no está fijado por Montara ni validado en Linux. No ofrece todavía el flujo completo de asociación de músicos y pistas. Con un máster mezclado no existe aún un analizador fiable de solos de saxo/piano/bajo configurado para Montara: ante esa ausencia debe usar generales/rotación visual, sin anunciar reconocimiento de solistas. No se instalan modelos grandes ni se hacen consultas a un proveedor sin configuración.
