# URANO U12b — interfaz de laboratorio aislada (sin tocar la web comercial)

Fecha: 2026-11-06. Estado: PR en borrador; pruebas CI como gate, **NO desplegada**.

## Alcance

Esta entrega continúa la pila de PRs **U10 #86 → U11 #88 → U12 #89 → U12b**. No se ha reescrito ni enlazado el frontend `web/` de Chema. El navegador de proyectos vive en `urano/lab_ui/` y el servidor opt-in en `urano/lab_app.py`.

- Interfaz con tokens visuales Montara: registro ficticio o login, panel «Mis proyectos», crear proyecto, seleccionar cualquiera (antiguo o reciente), guardar notas de receta, cierre de sesión y recuperación de sesión tras recargar.
- `lab.js` llama exclusivamente a las APIs U11/U12 previamente probadas; no persiste passwords, cookies ni CSRF en localStorage. El navegador envía automáticamente cookies Secure/HttpOnly.
- El renderizado de nombres se hace con `textContent` para evitar interpretar títulos de proyecto como HTML.
- Servidor Flask aparte con CSP estricta, rutas limitadas a `/urano-lab/`, `lab.js`, `lab.css`, límites de payload y cache `no-store` en HTML.
- Tests `tests/test_urano_lab_dashboard.py` prueban la presencia de assets, que no se monta ninguna API de Engine, dos navegadores con cuentas distintas, múltiples proyectos antiguos, restricción de acceso a los ajenos y recuperación tras cerrar/iniciar sesión. CI ejecuta todos los contratos U10–U12b y `node --check`.

## Lo que NO está hecho

- **No existe aún registro/login comercial**: no hay confirmación email, recuperación de contraseña, rate limit perimetral, verificación host/proxy/TLS completa, revisión de endurecimiento ni autorización de media/trabajos.
- **No hay integración con Engine, edición, apertura física de proyecto, recuperación de originales, Companion ni exportación**: pulsar un proyecto en la demo recupera su **receta y metadatos**, no abre aún el proyecto de vídeo real.
- **No despliegue**: para probarlo se requiere un entorno HTTPS privado de laboratorio y un directorio de datos exclusivo, que debe mantenerse fuera de servicios existentes. No exponer el factory como aplicación pública.
- No usar emails o contraseñas personales, archivos originales ni medios reales.
- No tocar `main`, la VM FER/JM, producción Vercel, DNS, ni el laboratorio estático Cloudflare. Su benchmark no dispone de API.

## Coordinación pendiente

El comentario de coordinación en [issue #34](https://github.com/amehcgracia-byte/Montara/issues/34#issuecomment-6682639303) pregunta si el equipo de Chema ha avanzado **selector de proyectos históricos**. Antes de conectar este panel a la UI principal o a la API del Engine, comprobar su respuesta, el HEAD de `main`, las rutas existentes `/montara/recovery/latest` y `/wizard/projects/open`, y evitar duplicar trabajo.

## Gate siguiente: U13 (proyecto real)

1. Resolver fuente de verdad y propiedad de **media/proxies/recetas** entre catálogo SQLite, proyectos del Engine y Companion.
2. Diseño seguro de aislamiento de Engine por propietario/trabajo (el Engine actual se mantiene en un estado activo global).
3. E2E en entorno privado, con dos identidades y varios proyectos; abrir un proyecto antiguo, relink de originales, editar, exportar, cerrar/reabrir.
4. Tras pruebas y acuerdo Chema, integrar por PR pequeña. No presentar U12b como SaaS desplegable.

Validación específica: `python -m unittest discover -s tests -p 'test_urano_*.py' -v` y `node --check urano/lab_ui/lab.js`, con Flask 3.x de pruebas. Para declararlo funcional en producción faltan E2E real y revisión de capturas según `CLAUDE.md`.
