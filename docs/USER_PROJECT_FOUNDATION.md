# Usuarios e historial: integración selectiva de Fernando

Base: main `515b44c` (Montara 0.67). Fuente revisada: `3683ee238fdb9c17773e27ae78f76b9a3596a423`,
PR #86 → #88 → #89 → #90. No es una fusión de la rama experimental.

## Incluido

- Catálogo SQLite por propietario, UUID, historial de proyectos y receta versionada.
- Sesiones opacas revocables, cookie Secure/HttpOnly y protección CSRF.
- Registro/login ficticio y panel de historial en una aplicación Flask opt-in independiente.
- Se conserva la interfaz principal, el Companion y los pines Engine `4f481002` / Mixer `f15ff91`.
  `app.py` no monta estas rutas. No se asocian proyectos privados existentes a cuentas nuevas.
- Corrección de integración: conservar la referencia a ambos formularios antes del `await`.
  El código original registraba la cuenta, pero no avanzaba el navegador; tampoco terminaba
  de crear proyectos desde el formulario. Se bloquean envíos durante la recuperación inicial.

## Pruebas

23 contratos U10–U12b aprobados localmente. La prueba nueva
`python tests/e2e_urano_dashboard.py --output <directorio>` usa HTTPS local,
dos contextos Chromium y cuentas inventadas. Comprueba registro/login, crear dos
proyectos, guardar notas, recuperar el antiguo tras recarga, cerrar/iniciar sesión
y separación entre cuentas. Con el script original falla tras el registro;
con la corrección pasa. Capturas locales revisadas. La CI de Linux ejecuta
esta prueba junto a los recorridos existentes; su resultado final se publica en la PR.

## Aún pendiente

Esto no es login comercial ni un historial conectado al editor. Faltan autorización
de medios/trabajos, vinculación con proyectos reales, recuperación de originales y
aceptación conjunta de edición/exportación con dos usuarios. Registro de laboratorio
sin verificación de correo, recuperación de contraseña ni controles perimetrales.
No habilitarlo en Internet con cuentas reales.

Las PR #91–#99 de Fernando desarrollan binding, procesos y contenedores separados;
se mantienen fuera de esta integración. #99 acredita ingest sintético real, pero
expresamente no acredita sync/edit/export ni el editor web combinado.

## Reutilización y coordinación (issue #34)

`recovery.py` y PR #87 recuperan sólo el último trabajo gestionado, no un catálogo
por usuario. El Engine dispone de GET `/api/v1/wizard/projects` y POST
`/api/v1/wizard/projects/open` (ruta conocida); el estado activo y `last_project_path`
son del runtime, no de una cuenta. Son interfaces del despliegue privado actual,
no autorización multiusuario. Reutilizar la apertura sólo tras validar propietario
y asignar un runtime aislado. No duplicar detección de sesiones, retención ni relink
Companion; el catálogo no garantiza que los medios sigan presentes en el dispositivo.
