# H4 — corrección de Google y Companion autónomo (2026-11-13)

## Incidencia de Google OAuth H4

- El endpoint de callback devolvía `{"error":"Google authentication unavailable or denied"}` después de elegir cuenta.
- Causa reproducida en el código desplegado: `google_flow.py` emitía sesiones por `ttl_seconds=3*86400`, pero `SessionStore.issue()` rechazaba TTL superiores a `86400`. El `ValueError` se recogía como error genérico del proveedor Google.
- **Corregido y desplegado H4 únicamente:** `urano/session_auth.py` admite un máximo acotado de `259200` segundos (3 días), conservando el valor predeterminado de una hora. No se alteran Google OAuth, reglas de emails, sesiones antiguas, proyecto ni worker.
- Pruebas en VM: emisión 3 días PASS; caducidad exacta PASS; rechazo TTL excesivo PASS; valor por defecto PASS. Test añadido: `tests/test_h4_google_session_ttl.py`.
- Backup: `~/.config/montara-h4-native/rollback-google-ttl-20261113/session_auth.py`. Servicio `montara-owner-h4-native.service` reiniciado y activo.
- Se requiere validación humana del login Google desde la página inicial. No reutilizar el callback OAuth anterior (el código es de un solo uso y puede caducar). No compartir URLs de callback con códigos.
- No asumir que todos los problemas Google estaban cubiertos; cuenta fuera de allowlist o errores de red producen el mismo error genérico, pero la incompatibilidad TTL era una causa determinista.

## Incidencia de Companion MSIX 0.6.11.1

La versión instalada fue **solamente controlador de bandeja nativo**. La opción `Iniciar Companion` pedía `python.exe` y `companion.py` porque el paquete no contenía el servicio Python. Esto era una limitación del producto, **no una mala configuración del tester**. El Engine local y `local_video.py` recibieron una corrección independiente de `WinError 5` previamente validada.

## Nueva arquitectura beta 0.6.12.0 — trabajo en rama, sin despliegue

- `companion/windows_native/BundledService.cs`: inicia el ejecutable local propio `service/Montara.Companion.Service.exe` del MSIX; no busca Python del usuario, no descarga scripts y conserva datos en `%LOCALAPPDATA%/MontaraSMARTBeta`.
- Con consentimiento del usuario, puede copiar `projects.json` y `places.json` desde `%USERPROFILE%/.montara-companion` solo si no existen en el nuevo perfil. Nunca mueve ni borra vídeos.
- `companion/windows_native/Program.cs`: panel propio WinForms de Montara, fondo oscuro `#101014`, marfil `#F5F3EF`, coral `#FF4F2E`, estado, iniciar, corrección render y actualizaciones (esta última permanece inhabilitada hasta contar con canal fiable). La bandeja nativa permanece, pero no es toda la interfaz.
- `companion/video_jobs.py`: localiza el runtime Engine en `venv/Scripts/python.exe` en Windows; conserva `venv/bin/python` en POSIX, cubierto por `tests/test_companion_native_renderer_path.py`.
- `companion/companion.py`: selftest empaquetado sin puerto ni datos de usuario.
- `.github/workflows/companion-native-windows-ci.yml`: instala Python 3.11 en runner Windows, empaqueta Companion mediante PyInstaller `--onedir`, ejecuta selftest del exe, compila la bandeja .NET, incluye ambos en MSIX, verifica el parche `WinError 5` y excluye los scripts PowerShell retirados.
- Nuevas compilaciones en GitHub Actions pueden emitir MSIX, pero **no distribuir a testers** todavía: cada ejecución generaba un certificado autofirmado efímero distinto. Para una actualización estable se requiere identidad de firma de desarrollo persistente, clave privada protegida y proceso de publicación confiable. Nunca poner PFX/clave privada en Git ni en el servidor web público; no eliminar restricciones Defender ni confiar automáticamente en nuevas autoridades raíz.
- El sistema App Installer no permite modificar toda su ventana azul: la nueva interfaz Montara es la aplicación instalada; un setup visual propio requeriría otra capa de instalación, identidad de firma y validación. No confundirlo con MSIX ya confiable.

## Siguiente prueba humana

1. Acceder a H4 desde `/`, elegir cuenta admitida y comprobar sesión.
2. Mientras no se entregue una nueva versión firmada, arrancar el antiguo servicio Companion que ya funcionaba por su propio acceso directo; evitar `Iniciar Companion` del MSIX 0.6.11.1 si pide localizar Python.
3. Comprobar `http://127.0.0.1:47820/health` y modo Stage; no repetir render con sesiones fallidas o estados de Companion inciertos.
4. Dar de alta firma persistente y validar MSIX 0.6.12.0 con Defender en Windows antes de instalarlo.
