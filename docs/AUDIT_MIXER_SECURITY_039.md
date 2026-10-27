# Montara 0.39 — Auditoría inicial de aislamiento del Mixer

Fecha: 2026-10-27. Rama de trabajo: `fernando/continuacion-montara`.
Estado: **hallazgos de lectura de código, no explotación demostrada**. No se modificó `main`, el despliegue ni los submódulos.

## Alcance y evidencias

Inspección estática del bloque Mixer de `app.py` (aprox. líneas 227-377), del adaptador `mixer_adapter/single_song.py` y de la validación de la versión 0.39.

| Hallazgo | Evidencia | Impacto potencial si se publica multiusuario | Prioridad |
| --- | --- | --- | --- |
| Rutas arbitrarias de fuentes | `POST /montara/mix` admite `tracks` con rutas del cliente y comprueba `Path(p).is_file()`; crea symlinks o copia el contenido | Lectura/copia de archivos del servidor fuera del proyecto si el endpoint queda expuesto sin una autorización superior | Alta, bloqueo para producción |
| Identificadores de job como única llave visible | `GET /montara/mix/<job_id>`, `/track/<name>`, `/result`, `/fx/.../`, `/reference...` y `/render` consultan `mix_jobs[job_id]` sin comprobar propietario en este bloque | Acceso cruzado a mezclas o modificación de trabajos si se descubre/filtra un ID | Alta, bloqueo para producción |
| Estado y trabajos volátiles | `mix_jobs` es un diccionario en memoria; los trabajos se lanzan mediante `threading.Thread(..., daemon=True)` | Se pierde estado al reiniciar; operaciones interrumpidas y dificultad de reintento | Media |
| Sección crítica global | `mix_lock = threading.Lock()` porque Mixer usa variables a nivel de módulo | Los trabajos se serializan, aunque sean de proyectos distintos | Media, puede esperar a escala |
| Pistas de distinta duración | `SingleSongMix._register()` usa `duration = min(stem.duration for stem in stems)` | Podría recortar la canción si una pista acaba antes; averiguar si está compensado por offsets y diseño del mixer | Pendiente, preguntar y probar |
| Archivos grandes de referencia | `POST /reference` guarda `storage` en disco de trabajo sin límite propio visible en el handler | Consumo excesivo de espacio si no existen límites globales | Media |
| Nombres de pista | `target = tracks_dir / path.name` | Colisiones cuando dos fuentes diferentes comparten nombre | Media |

## Distinciones esenciales

- **Una carpeta elegida por el usuario en su ordenador no es una ruta que el backend remoto pueda leer**. El backend solo ve rutas en su propio sistema de archivos. Hay que resolver selección local y transferencia/autorización de manera explícita.
- En el uso local de desarrollo, recibir rutas del propio operador puede ser una decisión razonable. La preocupación surge al aceptar peticiones de clientes externos.
- Un identificador aleatorio de 12 caracteres hexadecimales ayuda a evitar enumeración casual, pero no sustituye una comprobación de permiso por proyecto/usuario.
- No se ha confirmado aquí si una capa superior de autenticación, proxy o contenedor ya limita el acceso en cada despliegue. Auditar el recorrido completo antes de concluir exposición pública.

## Diseño mínimo recomendado, sin microservicios

1. Introducir un **registro de fuentes por proyecto**. Las APIs públicas reciben `source_id` y nunca rutas arbitrarias. El servidor resuelve IDs contra archivos previamente importados y autorizados dentro del espacio aislado del proyecto.
2. Añadir `project_id`/propietario a los trabajos y una comprobación común de acceso en **todos** los endpoints, no únicamente en la creación.
3. Mantener el mixer como motor y el bloqueo global inicialmente. No tocar `mixer/` ni `engine/`.
4. Para cargas, verificar límites de tamaño, nombres, extensiones, colisiones, symlinks y cuotas. Los originales pueden permanecer fuera del repositorio Git.
5. Aislar cada trabajo en directorio propio y hacer persistente como mínimo el manifiesto de estados. Progresar posteriormente a procesos separados para concurrencia.

## Pruebas de regresión exigidas antes de integrar cambios

- Una petición con ruta válida **no registrada** debe rechazarse, aunque el archivo exista en el servidor.
- Un usuario A no puede ver, descargar, remezclar ni cambiar la referencia de un trabajo de B.
- La ruta `../`, symlinks a archivos externos y nombres duplicados no deben evadir el aislamiento.
- Proyectos con pistas legítimas siguen generando la misma mezcla que antes.
- Dos trabajos separados no comparten faders, referencias ni caché.
- Reiniciar el proceso no deja un trabajo aparentemente activo para siempre; se puede recuperar o marcar interrumpido.
- Prueba con fuentes de duraciones/offsets distintos para aclarar la regla de pista más corta.

## Próxima implementación sugerida

**Primer PR funcional, deliberadamente pequeño:** registro y resolución de fuentes autorizadas y pruebas negativas de acceso a rutas. Después autorización por job. No introducir autenticación improvisada ni basarse en confiar en un path recibido del cliente.

**Límite de la presente revisión:** no se han ejecutado pruebas ni realizado un pentest; esta nota es el resultado de inspección de código. Los tests previos documentados para main 0.39 son históricos y no sustituyen nuevas regresiones tras modificar la API.
