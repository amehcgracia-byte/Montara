# STATUS — laboratorio Fernando
Actualizado: 2026-11-13 · Responsable: equipo Fernando · rama I2: `fernando/integracion-i2-google-owner-20261113`
## Fuentes de verdad y coordinación
- Acuerdo: `docs/COLLABORATION.md` y `AGENTS.md`. Issue compartido #216 reactiva ambos STATUS (JM actualiza SOLO STATUS-JM).
- La autorización posterior de Chema permite a Fernando preparar integración a main; revisión y PR pequeños siguen siendo obligatorias.
- Referencia histórica (NO merge masivo): PR #189 `fernando/integracion`. Entrega técnica Owner: `docs/integration/MONTARA_MAIN_INTEGRATION_HANDOFF_OWNER_COMPANION_2026-11-13.md` en `fernando/chema-native-owner`.
## Estado y pruebas
- **VALIDADO POR USUARIO / beta H4 (13-11):** Google real → proyectos privados → editor Stage original de Chema → Companion Windows 0.6.10 con Engine b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b → MP4 local de 635117659 B, imagen y audio correctos.
- **NO INTEGRADO EN MAIN:** el recorrido Owner H4 completo; la validación H4 no equivale a main ni a producción.
- H4 privado: Google OAuth, catálogo SQLite, sesiones revocables (3 días por defecto y como máximo) y Engine/worker privado por dueño. No subir originales por defecto.
- Windows: MSIX 0.6.11.1 tray parcial; el servicio real del PASS fue lanzado con Python desde SMART Beta; versión empaquetada 0.6.12.0 construida en CI, aún sin validación humana de instalador/firma persistente.
- Pendientes: doble espera de miniaturas al guardar tomas, handling localhost WinError 10053, instalador Companion por SO, multiusuario E2E real de dos cuentas y rollback.
- VM: watchdog 120 min, timer 20 min, SSH/web + trabajos FFmpeg; worker vacío no bloquea el apagado (PR #202). Cierre cooperativo avanzado pendiente.
## Integración a main por piezas
- **I1 integrado en main:** PR #217, política de sesión Montara uniforme de 3 días y pruebas. El portal H4 aislado también emite 3 días.\n- **I2 preparado para main:** OAuth Google RS256+PKCE + asociación por sub verificado + catálogo SQLite original, aplicación independiente, sin montar editor/Engine; 15/15 pruebas aisladas PASS. PR de I2 pendiente de confirmación CI/fusión.
- Orden: login/catálogo Owner → runtime autorizado/worker → editor Chema y media → Companion Windows/Mac → aceptación y despliegue por fases.
- Mantener rutas incompletas inactivas: no presentar la incorporación de un módulo como beta completa ni cambiar `engine/` o `mixer/` sin sus repos.
- PR: informar A novedades, B duplicidades, C reutilización, D riesgos, E recomendaciones; declarar SHAs de Engine/Mixer y comandos de prueba.
- Acciones en main únicamente mediante PR revisada, sin fusión de rama experimental ni force-push.
