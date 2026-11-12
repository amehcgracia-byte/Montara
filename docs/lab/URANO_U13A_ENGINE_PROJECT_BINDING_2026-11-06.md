# URANO U13A — Enlace interno entre catálogo y carpeta Engine

**Fecha:** 2026-11-06. **Estado:** implementación de contrato aislado, PR draft, **sin activar Engine ni conectar interfaz**.

## Contexto contrastado con `main`
- `recovery.py` permite `GET /montara/recovery/latest` y devuelve **solo** el trabajo más reciente.
- `web/full-session.js` llama a `/wizard/projects/open` con una ruta conocida; `app.py` recupera `last_project_path` al reiniciar.
- `urano/project_catalog.py` (U10) identifica proyectos por UUID y propietario, pero no conoce dónde está su proyecto real del Engine.
- Mensaje a IA Chema sobre proyectos anteriores enviado en [issue #34](https://github.com/amehcgracia-byte/Montara/issues/34#issuecomment-6682639303). **En la consulta de 06-11 no había respuesta aún**; Chema comunicó verbalmente al usuario que no habían desarrollado el selector histórico. Confirmar respuesta antes de integrar algo en la UI pública.

## Contrato implementado

`urano/engine_bindings.py` define `EngineProjectRegistry`. Almacena en SQLite una relación unívoca entre UUID de proyecto del catálogo, propietario y **nombre relativo** de carpeta del Engine bajo `<data_root>/Projects/<folder>/project.json`. Su lectura ocurre solo mediante código backend de confianza.

- `bind_trusted(owner_id, catalog_project_id, folder_name)` exige primero un catálogo que pertenezca al propietario, una carpeta válida con `project.json`, sin symlinks en carpeta ni fichero; niega rutas con separadores, traversal, carpeta fuera de Projects y duplicados. **No publicar endpoint HTTP que permita al navegador reclamar carpetas ajenas**.
- `resolve_internal(owner_id, catalog_project_id)` vuelve a comprobar propiedad de catálogo y que el fichero Engine sigue existiendo; devuelve ruta de backend, **nunca la expone al navegador**.
- No se modifica `project.json`, el valor `last_project_path` ni el proyecto actual activo del Engine. **No hay apertura de proyecto ni adopción de proyectos legados**.
- Cinco tests específicos de aislamiento, no duplicación, traversal/symlinks, desaparición de origen y no modificación de datos. CI también ejecuta pruebas U10–U12b y JS syntax check.

## Gate de seguridad antes de un editor funcional multiusuario

1. Definir autoridad real para vincular una carpeta Engine a un UUID: **solo crear el vínculo al crear un workspace nuevo dentro del runtime aislado del usuario**, con propiedad verificada, nunca adoptar un directorio existente por input del navegador.
2. Decidir unidad de aislamiento del Engine: hoy hay **un proyecto activo por proceso**; cambiarlo desde otro usuario puede contaminar el estado. Requerir proceso/container/sandbox aislado o equivalente antes de abrir proyectos de distintas cuentas.
3. Implementar operación de activación atómica y segura, rechazar trabajo renderizando, controlar jobs/proxies/originales/rutas y relink Companion, con tests reales de dos usuarios y varios proyectos.
4. Migración de proyectos anteriores solo mediante proceso explícito y auditado, no autodetección indiscriminada de carpetas.
5. Mantener vigentes las ramas apiladas: U10 #86 → U11 #88 → U12 #89 → U12b #90 → U13A. Nunca fusionar una pila entera de forma ciega.

**No declara** multiusuario, cuentas aptas para producción, editor funcional, nuevos ficheros originales, costes de nube ni API segura para abrir vídeos. Las credenciales/datos locales no se escriben en Git.
