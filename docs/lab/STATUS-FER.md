# STATUS — laboratorio Fernando
Actualizado: 2026-11-14 · Responsable: equipo Fernando · integración I1–I5b en main (I5 release público pendiente)
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
- **I1 integrado en main:** PR #217, política de sesión Montara uniforme de 3 días y pruebas. El portal H4 aislado también emite 3 días.\n- **I2 integrado en main:** PR #218 Google RS256+PKCE, Owner por sub y catálogo privado opt-in; 15/15 pruebas aisladas PASS.\n- **I3a integrado en main:** PR #219, admisión privada y ledger de recuperación, 19/19 pruebas aisladas PASS.\n- **I3b integrado en main:** PR #220, broker opt-in + entrada systemd, 15/15 pruebas aisladas PASS.\n- **I4 integrada en main:** PR #222, código del puente Chema por gateway privado; 90/90 Python + 1/1 JS PASS. E2E real de main pendiente.\n- **I5a integrado en main:** PR #223, catálogo opt-in de releases Win/Mac por Engine y hash, sin paquete certificado publicado; 6/6 Python + 11/11 JS PASS.\n- **I5b integrado en main:** PR #224 Windows .NET tray provisional + MSIX QA y WinError5; CI Windows dotnet/PyInstaller/build-dev-package PASS y 6/6 Python PASS. Firma comercial/autoupdater NO listos.\n- **I4 candidato (histórico):** editor original Chema por gateway privado Owner, Stage/Push/Show, bridge JS y workspace; 90/90 pruebas Python + 1/1 JS PASS en checkout temporal. E2E real de main pendiente.\n- **CI:** issue #221 documenta seis fallos heredados de E2E sesión (luz/framing/performers), anteriores a I3.
- Orden: login/catálogo Owner → runtime autorizado/worker → editor Chema y media → Companion Windows/Mac → aceptación y despliegue por fases.
- Mantener rutas incompletas inactivas: no presentar la incorporación de un módulo como beta completa ni cambiar `engine/` o `mixer/` sin sus repos.
- PR: informar A novedades, B duplicidades, C reutilización, D riesgos, E recomendaciones; declarar SHAs de Engine/Mixer y comandos de prueba.
- Acciones en main únicamente mediante PR revisada, sin fusión de rama experimental ni force-push.

- **I6 candidato 14-11:** cierre cooperativo SIGTERM de Owner nativo, WSGI espera hilos, TimeoutStopSec=90s; pruebas 94 Owner + 7 ledger PASS en checkout aislado. Sin deploy.
- **Gate I6:** falta prueba de render prolongado/apagado VM y recuperación real. Un timeout no garantiza escritura durable ni cgroup vacío; preservar fencing. Ver docs/integration/I6_SAFE_SHUTDOWN_HANDOFF_2026-11-14.md.

- **I7 candidato 14-11:** aceptación SQLite dos Owner + aislamiento mutuo, CSRF, ledger, stop y crash recovery; 6/6 PASS (sin Google real ni Companion E2E). I6b y aceptación humana pendientes.

- **I6b candidato 14-11:** preflight SQLite Owner solo lectura: 7/7 tests; no se conecta al watchdog: falta bloqueo de nuevas admisiones + quiescencia y prueba OS. No está desplegado.
