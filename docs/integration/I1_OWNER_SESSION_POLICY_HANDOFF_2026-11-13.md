# I1 — Integración inicial Owner: política de sesiones (propuesta para main)
Fecha: 2026-11-13 · Issue #216 · fuente: beta funcional `fernando/chema-native-owner` · PR desde `main`.

> **ATENCIÓN A CHEMA Y SU IA:** Esta PR NO habilita Google OAuth, no crea portal de inicio, no conecta el editor al catálogo SQLite y NO hace que `main` funcione en modo multiusuario. Solo incorpora un pequeño contrato de expiración que necesitará el futuro portal Owner. Dejar los endpoints de producto existentes como están y nunca emitir sesiones sin identidad previamente autenticada en servidor.

## Contrato de esta pieza
- `urano/session_auth.py`: el valor predeterminado de `SessionStore.issue` **continúa siendo 3600 segundos**. El emisor solo puede pedir una duración mayor **explícitamente**, hasta 10 días (864000 s), para la beta privada acordada con Fernando. No se crean rutas públicas ni se relaja CSRF, Secure/HttpOnly/SameSite, revocación o separación de identidades.
- `tests/test_h4_google_session_ttl.py`: frontera exacta a los tres días, rechazo de un segundo fuera del máximo y mismo valor por defecto. No contienen secretos ni credenciales reales.
- `docs/lab/STATUS-FER.md`: recupera el estado del laboratorio propio, 40 líneas o menos, sin modificar `STATUS-JM.md` de Chema.

## A–E según `docs/COLLABORATION.md`
**A. Novedades:** política uniforme de 3 días para sesiones propias de Montara.

**B. Duplicidades:** se reutiliza `SessionStore` ya incluido en `main`; no se trae una segunda tabla de sesiones ni se cambia `ProjectCatalog`.

**C. Reutilización:** el servicio H4 aislado ya usa el contrato de 10 días. La futura integración Google lo invocará **después de verificar** callback/OIDC y perfil. No debe copiarse indiscriminadamente a login público.

**D. Riesgos:** los 10 días implican exposición más prolongada de una cookie robada; solo beta privada en este momento. Las sesiones antiguas mantienen expiración original; no hay migración de datos. Si se cambia el login, comprobar CSRF/cookies/revocación. No incorporar H4/Cloudflare/Companion por accidente en esta PR.

**E. Recomendaciones:** ejecutar los 3 tests nuevos y regresión existente `tests/test_urano_session_http.py` + `tests/test_urano_project_catalog.py`; comparar commits de `main` al abrir y antes de fusionar, y avanzar después con OAuth/Owner catálogo bajo feature flag. No marcar el conjunto como listo hasta pruebas E2E de dos usuarios y MP4.

## Dependencias que NO están incluidas
1. Google OAuth con código+PKCE, identidad de cuenta verificada, allowlist, logout.
2. Portal y catálogo privado autenticados sin seleccionar `owner_id` en navegador.
3. Worker/Engine autorizado por proyecto, aislado y con recuperación tras cierre.
4. Editor original Stage/Push/Show y proxy/receta/media ligados a propietario.
5. Companion autónomo Windows/Mac, instaladores por SO y firma/compatibilidad.
6. Pruebas E2E Linux con capturas revisadas, dos cuentas reales, ausencia de acceso cruzado, rollback y despliegue.
La interfaz puede verse igual pero sus controles internos son diferentes; **nunca sustituir autorización Owner por IDs suministrados por el navegador**.

## Pines y despliegue
Este cambio no modifica `engine/`, `mixer/`, rutas web, servicios ni paquetes de Companion. El PR mostrará los SHAs de submódulos heredados de `main`. No hay despliegue en VM ni fusión automática.
