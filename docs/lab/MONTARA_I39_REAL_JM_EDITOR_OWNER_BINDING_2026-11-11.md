# MONTARA I38–I39 — Primer enlace REAL entre Owner UUID y editor original de Chema

**Fecha:** 2026-11-11. **Rama:** `fernando/integracion`. **Estado:** laboratorio PASS; sin despliegue ni fusionar `main`.

## Lo nuevo (frente a las pruebas históricas I19–I27)

No se ha creado otro registro de proyectos: `urano/owner_jm_editor_handoff.py` **reutiliza U13A** (`EngineProjectRegistry`) y el catálogo del Owner para asociar el **UUID canónico** de Montara a la carpeta de proyecto que el Engine auténtico tiene efectivamente abierta (`ZUCKER_STATE.project.folder`). La operación solo se ejecuta en backend confiable; no admite rutas, IDs de JM ni directorios elegidos por un navegador. Comprueba modalidad Stage/Push/Show, propietario real, ruta física no enlazada, estado activo del Engine y GET de proyecto. Reabrir el mismo proyecto es idempotente. Intentar vincular un proyecto de otro usuario o el de otra modalidad se rechaza.

**Pruebas offline** contra los contratos existentes: 5 nuevas pruebas de handoff + 5 U13A + 6 de selección por modalidad = **16 PASS**. Workflow `.github/workflows/fer-i38-owner-jm-handoff.yml` preparado, sin ejecución Actions confirmada.

## Evidencia física con código original de Chema

Se creó un checkout **temporal aislado** de `fix/jm-native-video-save-project-recovery-20261110`, sin modificar JM/`main`, y se enlazó su submódulo Engine únicamente hacia el bundle inmutable ya instalado `engine-b5e48317ef85225f901adc69af8cc17aa8146880`. Se ejecutó con Python y dependencias `site` del bundle, con datos propios en `TemporaryDirectory`:

1. `create_montara_app(..., samples=False)` de **app.py ORIGINAL** arrancó, no un fake ni nuestro estudio I28. `GET /` entregó el HTML completo original (**41.905 bytes, HTTP 200**), incluyendo las modalidades Stage (youtube), Push (reel) y Show. `GET /montara/version` y `GET /api/v1/wizard/status` devolvieron HTTP 200.
2. `tests/urano_i39_complete_jm_editor_owner_lab.py` creó dos propietarios privados en el catálogo, inició un proyecto UUID de Owner con la app ORIGINAL, obtuvo HTTP 200 de `/api/v1/wizard/projects/open` y `/api/v1/project`, y lo vinculó a `EngineProjectRegistry` U13A **sin una segunda base de datos de mapeos**. Propietario extranjero denegado.
3. I38 `tests/urano_i38_owner_jm_real_engine_handoff_lab.py` también pasó de forma independiente con la app Engine real y catálogo U13A.

**Ninguna de estas pruebas:** hace una sesión Google del navegador real en el editor, transporta uploads al Engine privado en un proceso systemd de otro UID, conecta Companion Windows, ni genera MP4. NO confundir pruebas de Flask `test_client` con beta HTTP pública operativa.

## Consecuencia arquitectónica

El editor JM original puede vivir en un **runtime propio por usuario** y usar sus rutas actuales `/api/v1/*`, `/montara/*` internamente; no requiere reinventar 3 editores ni duplicar procesamiento/recetas. La UI original debe reutilizarse, igual que `tests/e2e_native_stage.py`, con el broker Owner como autorizador y aislamiento por proceso. La arquitectura del núcleo es independiente de GCP, Cloudflare o una vCPU concreta; systemd queda como ejecutor Linux sustituible.

No hay que mantener un Flask JM global con diferentes owners y proxies desprotegidos. Tampoco exponer físicamente `app.py` sin autenticación; los ensayos de hoy fueron sobre datos y HTTP test client internos.

## Siguiente trabajo de PRODUCTO, sin rehacer I19–I27

1. Empaquetar el editor JM completo (`app.py`, módulos de `web/`, Python, Engine pinneado) como **bundle inmutable único**, a partir del `main` de Chema cuando esté listo. Los laboratorios han probado una copia temporal de su rama candidata, no constituyen un merge.
2. Ejecutar **app.py original por cuenta/proyecto** bajo el runtime aislado controlado por el broker, con las rutas protegidas mediante el Owner y el Engine sin acceso global. Los recursos CPU/RAM/IO dependen de política configurable, no de 4/8 vCPU fijos.
3. Enlazar operaciones originales (/wizard, /montara, uploads, preview, range, exports) con el transporte privado por proyecto. Nunca un proxy indiscriminado a 8101–8103.
4. Hacer pasar el E2E original `tests/e2e_native_stage.py` con esa variante privada y con una segunda cuenta aislada, sin subir originales (Companion obligatorio); después requerir la prueba humana de Fernando en Windows.

**No solicitar la participación del usuario hasta poder probar el flujo de producto en navegador y Companion; sí escalar a Fernando bloqueos reales de UX o decisiones sobre compatibilidad.**
