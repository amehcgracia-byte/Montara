# Integración de Fernando — rama estable

**Inicio:** 2026-11-10 · **Rama:** `fernando/integracion` · **Base inicial:** `main@765a34ceec33311cd520856d46fec15adfc6c0a1`.

## Función
Esta rama será la **referencia estable de integración revisada de Fernando**, no el laboratorio de experimentos ni el desplegable automático. Se creó exactamente desde `main`. No se han importado todavía cambios funcionales. `main` sigue bajo el control de Chema.

**Fuentes históricas que NO se borrarán ni reescribirán:**
- `fernando/continuacion-montara`: investigación/experimentos SATURNO, JÚPITER, URANO.
- `fernando/c8-public-beta-landing-pages-20261110`: beta pública limitada con Google OAuth real, catálogo SQLite y Cloudflare (aplicación privada en la VM). Se conserva como despliegue operativo independiente hasta migración expresamente aprobada.
- Otras ramas/PR de investigación y PR de Chema siguen intactas.

## Reglas de trabajo
1. Antes de cada bloque, consultar el SHA actual de `main`, PR abiertas de Chema, los submódulos Engine/Mixer y el árbol de dependencias. Actualizar con merge/rebase **no destructivo y validado** en una rama temporal; nunca push --force.
2. Preparar una **rama corta desde esta base actualizada** por cambio funcional, enlazada a PR original, informe/benchmark, tests y decisión. La rama estable recibe la pieza solo tras revisión y tests. No fusionar en cascada pilas enteras ni toda la rama histórica.
3. Separar `integrado en main`, `integrado en fernando/integracion`, `validado en laboratorio`, `candidato`, `documentado`, `superado/duplicado` y `descartado`.
4. Priorizar contratos de autenticación/catálogo, arquitectura de proyecto/archivos, Companion Windows, proxies y motor/Stage por dueño. Preservar la UX reciente de Chema, versiones instaladas y el último `main`.
5. Resolver en revisión humana, **antes de tocar código**, divergencias de funcionamiento o decisiones de diseño: cambios de `companion/companion.py` (#74/#79/#81 frente a #136 y versión actual); cambios de Stage/360; alternativa subprocess/UID frente a Docker; diferencias de schema/owner/proxy; pines Engine/Mixer.
6. Para cada bloque, pruebas focales + regresiones y E2E Linux con capturas examinadas donde aplique. Declarar con exactitud pruebas no ejecutadas. Dos identidades reales y archivos distintos deben comprobar separación antes de abrir Stage multiusuario público.
7. Cambios en `engine/` y `mixer/` se proponen y prueban en sus repos, y sus nuevos SHAs se actualizan por separado en Montara. No editar submódulos desde Montara.
8. No tocar `main`, servicios 8101–8103, secretos, despliegues compartidos, recursos de pago o datos de usuarios sin autorización/coordinación; la beta 8115 y sus datos se conservan.
9. Mantener un manifiesto de trazabilidad de PR originales, commits, archivos, pruebas, estado y decisión; la información histórica no se elimina por volumen. Para limpiar ramas/PR, primero demostrar que están representadas y archivadas, y solicitar aprobación.

## Orden propuesto
- **I0:** inventario de ramas/PR, bases, cambios únicos, documentación y pruebas. Confirmar con el usuario ante divergencias.
- **I1:** trasladar funcionalidades de identidad y proyectos de C1/C4/C8 sin duplicar catálogo.
- **I2:** diseño mínimo y probado de ejecución por propietario (revisar subprocess #93–#95, Docker #96–#98, LXD).
- **I3:** Companion y contratos proxy/original/receta con pruebas Windows/Mac; sin subir originales silenciosamente.
- **I4:** mejoras de media y rendimiento con resultados reproducibles y compatibilidad con el Engine actual.
- **I5:** PR pequeñas y revisadas hacia `main`, coordinadas con Chema.

**Referencias:** docs/COLLABORATION.md, docs/lab/INVENTORY-FER.md, PR #138 y auditoría de consolidación issue #163. El plan de PR #138 es histórico y debe refrescarse contra cambios recientes de Chema antes de integraciones.
