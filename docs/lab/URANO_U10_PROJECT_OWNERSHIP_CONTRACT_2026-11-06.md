# URANO U10 — Contrato mínimo de propietario y recuperación (P0)

**Fecha:** 2026-11-06 · **Estado:** implementación aislada en PR DRAFT; **NO desplegado**, **NO conectado a login, web ni motor**, **NO SaaS listo**.

## Alcance implementado

- `urano/project_catalog.py`: catálogo SQLite de metadatos, sin dependencias extra, usando identificador aleatorio UUID por proyecto.
- `create(owner_id,title)`, `list_for(owner_id)`, `get(owner_id,project_id)` y `save_recipe(owner_id,project_id,recipe,expected_revision=N)`.
- Consultas y escrituras restringidas por `owner_id` **también en SQL**; proyectos ajenos se ocultan bajo `ProjectNotFound` indistinguible de inexistentes.
- Receta JSON persistente, lectura tras reconstruir objeto de catálogo (simulación de reinicio) y versión optimista para impedir sobreescrituras de dos editores desincronizados.
- Límites mínimos a títulos, IDs y JSON (256 KiB); no se guardan originales de vídeo ni rutas locales, y el cliente no elige el UUID.
- Cinco tests aislados con dos identidades **ficticias**, sin acceder a usuario real, Companion, servicios de la VM o Vercel.

## Frontera de seguridad que NO resuelve

El `owner_id` es **un principal ya verificado por el backend**. No se debe tomar del cuerpo, querystring, cookie no verificada o cabecera suministrada por un cliente. Esta pieza no implementa registro, login, autenticación, sesiones, MFA, restablecimiento de contraseña, CSRF, autorización de media ni autorización del Engine. **Si una ruta expone este catálogo tomando un owner_id arbitrario, la seguridad quedaría rota.**

No alterar `app.py`, `deploy/entry.py`, `deployment/vercel`, el Engine, el Mixer, los pins de submódulos ni el Companion en este PR. No usar todavía este catálogo como fuente de verdad del proyecto del motor: el Engine mantiene un proyecto actual y requiere aislación por proceso/sandbox y contrato específico.

## Tests / criterio de aceptación

`python -m unittest discover -s tests -p 'test_urano_project_catalog.py' -v`

1. Dos propietarios listan solo sus proyectos; no pueden leer ni escribir en los ajenos.
2. Receta y propiedad sobreviven al cierre y reapertura de SQLite.
3. Revisión obsoleta no pisa una receta más reciente.
4. Datos mal formados no se persisten.
5. Un intento de escritura ajena no crea registros fantasma.

La CI específica ejecuta exactamente estos tests. **El test local no sustituye el resultado de GitHub Actions**; confirmar run verde antes de solicitar merge.

## Siguientes iteraciones, con gates separados

1. Elegir el mecanismo mínimo de identidad real y una interfaz server-side `principal_from_session`; probar que el cliente no puede suplantar el propietario.
2. Incorporar rutas HTTP para catálogo usando **exclusivamente el principal autenticado**, con prueba cruzada de dos clientes web.
3. Diseñar el aislamiento del runtime Engine: proceso/sandbox por proyecto o controlado por inquilino; no compartir `last_project_path` entre cuentas.
4. Vincular metadatos del catálogo con el proyecto del Engine, proxies/identidad del Companion y exportaciones, sin subir originales por defecto.
5. Validar recuperación de una sesión y proyecto con navegador real, pestaña cerrada y Companion reconectado.
6. Evaluar backups, migraciones de SQLite y lifecycle/storage/quotas antes de datos comerciales.

**Regla de integración:** no desplegar a la VM FER ni tocar a JM; no mezclar con el laboratorio Cloudflare o el despliegue estable Vercel. Este primer PR solo demuestra el contrato de almacenamiento y aislamiento basado en un principal suministrado correctamente.
