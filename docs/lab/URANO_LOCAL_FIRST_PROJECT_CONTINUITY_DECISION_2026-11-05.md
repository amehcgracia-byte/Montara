# URANO — decisión de arquitectura: continuidad local de proyectos (05-11-2026)

**Estado:** propuesta de implementación, basada en lectura de código. No significa funcionalidad terminada ni despliegue. **Responsables:** laboratorio FER en coordinación con JM. **Objetivo inmediato:** recuperar trabajo tras cerrar y reabrir navegador/Companion en el **mismo ordenador**, sin almacenar originales en nube ni rehacer el Engine.

## 1. Decisiones de producto confirmadas por Fernando

1. **Montara es un producto online.** No crear modo offline comercial, sincronización diferida multi-dispositivo ni prometer edición desconectada. Un corte de red no debe corromper el estado local persistido, pero eso no implica garantizar operaciones remotas offline.
2. **Companion es la ruta normal para vídeo local.** Evitar subida completa silenciosa de originales. Conservar temporalmente el mecanismo **manual, consentido y experimental** de U3C; no declararlo política comercial.
3. **Originales y cachés audiovisuales viven preferentemente en el equipo del usuario.** Backend central: cuentas, permisos, catálogo mínimo, trabajos y resultados remotos necesarios; no réplica obligatoria de vídeos.
4. **Portabilidad entre ordenadores, colaboración multi-dispositivo y restauración cloud completa quedan fuera del primer alcance.** La recuperación en el mismo equipo sí es prioridad. Sin originales accesibles no hay render desde esos originales.
5. **No introducir por ahora un sistema complejo de migraciones entre versiones del motor.** Registrar identificadores de versión relevantes en proyectos para diagnóstico y evitar prometer compatibilidad futura automática. La política de actualizaciones se decidirá antes del lanzamiento.
6. **GOP remoto selectivo sigue como candidato Fase 2**, no como realidad productiva: SATURNO-20–25 logró 39,8 % menos bytes en un caso sintético/controlado sobre loopback; no demuestra ahorro general en Internet o para toda clase de fuentes.
7. Autorización JM comunicada por Fernando: se pueden integrar mejoras justificadas en main si superan las pruebas pertinentes y no causan regresiones; respetar la coordinación y submódulos. Preferir una PR pequeña por componente; no fusionar la rama experimental completa.

## 2. Capacidades existentes comprobadas (no duplicar)

- `companion/companion.py`: POST `/projects` elige una carpeta, crea `Montara/<name>/montara-project.json` con `app`, nombre, fecha y `sources`, registra ID de 16 hex en `HOME/projects.json`; `load_projects()` restaura el mapa ID→ruta después de iniciar Companion.
- `companion/companion.py`: POST `/projects/<id>/save?name=...` guarda un archivo binario mediante `.part` y reemplazo; es **guardado de archivo**, no un endpoint general de lectura/recuperación de la receta editable.
- `web/companion.js`: `projectFolder()`, `saveInProject()`, detección y localización con metadatos/fingerprint de bordes.
- `web/footage-memory.js`: IndexedDB `montara-footage`, referencias/handles con caducidad de 14 días, no fuente canónica permanente.
- `web/montara.js`: `sessionStorage['montara-open-edit']`; existe recuperación asociada a proyecto de backend, pero su durabilidad no sustituye por sí sola al estado del proyecto local.
- `web/full-session.js`: ID de sesión en localStorage; `full_session.py`: sesión y estado del lado servidor.
- JM 0.66 incluye `?resume=frames` desde móvil nuevo, vía proyecto del servidor. No confundir esta recuperación web concreta con persistencia local universal de Stage/Push/Show/Mixer.
- Engine tiene su propio esquema/recetas/cachés. **Antes de programar, leer la API real de guardar/reanudar proyectos del Engine y las llamadas `montara-open-edit` y `/projects` para no duplicarlas.**

Fuentes: `docs/lab/URANO_U2_DATA_FLOW_AND_PERSISTENCE_2026-11-05.md`, `docs/lab/INVENTORY-FER.md` (F1.4, F1.5, F8), `companion/companion.py`, `web/companion.js`, `docs/lab/STATUS-JM.md`.

## 3. Diseño candidato mínimo (SIN decidir crear SQLite)

**Fuente de verdad de edición:** mantener el formato/receta persistente existente del Engine y sus referencias de proyectos. **Índice local:** Companion puede registrar `project_id`, ruta elegida, referencia al proyecto del backend, medios identificados, revisión y sello de tiempo, preferiblemente ampliando `montara-project.json` y `projects.json` existentes. No inventar `.montara` ni migrar a SQLite sin identificar una limitación real.

**Guardado:** cambios de edición → mecanismo existente de guardado de Engine/backend + checkpoint local ligero, cuando proceda, de estado suficiente para reabrir. Escritura atómica, límites de tamaño, validación de esquema y rutas, exclusión de secretos, y garantía de no sobrescribir una revisión reciente con otra antigua. Distinguir receta de edición, selección de fuentes y mero estado de UI.

**Reapertura:** navegador vuelve a autenticar en servidor → obtiene/recuerda identificador de proyecto autorizado → detecta Companion → Companion encuentra entrada persistente local y medios originales → servidor/Engine recupera su receta autorizada → interfaz se reconstruye. Falta definir concretamente cuál componente es autoritativo para cada campo antes de modificar endpoints. **No confiar en el `project_id` que mande el navegador como prueba de autorización.**

**Si Companion no está disponible:** informar que falta el componente local o los originales; conservar en el servidor solo lo ya permitido. No subir originales silenciosamente. La subida manual de U3C continúa únicamente como excepción de laboratorio.

**Si se pierde conexión de red:** no afirmar modo offline; las escrituras locales concluidas deben sobrevivir, y las acciones que dependan del servidor deben fallar con mensaje claro y no perder el último checkpoint válido. No introducir cola offline de acciones ni reconciliación remota en esta fase.

## 4. Requisitos de seguridad para la implementación

- `Origin` y localhost no sustituyen autorización de Companion. Antes de exponer una lectura local de proyecto a una web pública, vincular la sesión autorizada al proyecto (token corto o emparejamiento seguro); no crear `GET /projects/<id>` que devuelva rutas o recetas sensibles sin protección.
- Proyecto local y cuenta cloud: relación explícita y validada en servidor cuando haya cuentas. Nada de escanear discos ajenos ni publicar rutas locales en catálogo cloud.
- Metadatos de medios: fingerprints de bordes sirven para localizar candidatos, no son prueba criptográfica de contenido completo. Resolver colisiones/archivos cambiados con validación apropiada.
- Escrituras atómicas, rechazo de traversal/symlinks inesperados, permisos de archivos, límites de JSON y caducidad de tokens; tests de dos identidades ficticias en la capa de acceso cuando se implemente multiusuario.

## 5. Primera PR implementable — acotada y verificable

**Meta:** continuidad local de un proyecto Stage en mismo dispositivo, desde `main` actual. **No** crear base de datos, SaaS, hosting, SSO, colaboración ni GOP en esta PR.

1. Trazar **una** ruta Stage real: creación, guardado, cierre pestaña, reinicio de Companion y reanudación; documentar qué estado ya recupera hoy y cuál se pierde. Revisar código y tests existentes; repetir solo el tramo no validado.
2. Si falta checkpoint local, añadir **solo** el dato/endpoint seguro mínimo sobre los formatos actuales. Diseñar autorización antes de nueva lectura de archivos del Companion desde web.
3. Pruebas focalizadas: creación/reanudación tras reinicio, revisión antigua no pisa la nueva, falta de original/USB, ruta manipulada rechazada, Companion ausente no provoca upload automático, y errores de red no destruyen checkpoint.
4. E2E Stage Linux + inspección de capturas según `CLAUDE.md`; CI Windows del Companion si se toca su código. No declarar soporte de otros modos sin probar.
5. PR pequeña contra `main` con pines de submódulos inalterados, resultados verificables y rollback. Merge solo tras gates.

**Cierre de diseño:** esta nota fija alcance y reutilización, **no asegura que la recuperación sea ya completa**. La siguiente acción es inspección focalizada de Stage y de la receta existente; el desarrollo vendrá guiado por el hueco comprobado.

## 6. Fuera de alcance y prioridades posteriores

- Cuentas multiusuario y autorización backend: trabajo separado, necesario antes de SaaS público; incorporar pruebas de propiedad como parte de su implementación, sin campaña independiente de experimentos.
- Render GOP remoto: integración separada desde resultados SATURNO, medición con originales y red real, no garantía de reconstructibilidad a partir de metadatos.
- Comparación de proveedores y costes: después de medir flujo real; priorizar salida de red, almacenamiento transitorio, colas y concurrencia.
- Licencias de FFmpeg en paquete Windows: revisión previa a distribución comercial; investigación y desarrollo continúan.
