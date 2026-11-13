# I5a — Companion: distribución por sistema y contrato de actualización seguro
Fecha 2026-11-13 · Rama I5a desde main · Gate de lanzamiento **NO SUPERADO**

> **ATENCIÓN A CHEMA Y SU IA:** el Companion de Chema en Mac y el Companion de Fernando en Windows **son AMBOS TEMPORALES**. No hay dos productos definitivos ni dos protocolos que deban mantenerse en paralelo. Su misión es converger hacia **un solo Companion Montara multiplataforma** que trabaje con originales locales, y el mismo contrato de protocolo/Engine en Windows y macOS. No declarar una versión comercial ni ofrecer una descarga final hasta validar firma, actualizador y pruebas humanas. No sobreescribir las instalaciones actuales.

## A. Novedades en este PR
- `companion/release_catalog.py` expone un **catálogo opt-in** de instaladores Windows (x64/arm64) y macOS (Intel/Apple Silicon), con selección explícita de OS/arquitectura, `version`, vínculo a SHA de Engine y SHA-256 exacto de cada archivo. No devuelve carpetas del servidor ni URLs arbitrarias.
- `GET /montara/companion/releases` devuelve únicamente versiones autorizadas. `GET /montara/companion/releases/download?os=windows|macos&arch=x64|arm64` sirve exclusivamente archivos registrados y con hash correcto, nunca ZIP o PowerShell no autorizados.
- Si no hay manifiesto de release aprobado, el catálogo devuelve una lista vacía y la descarga responde 503; NO publica paquetes de QA por defecto.
- La distribución exige `signed=true`, identidad de firmante declarada y `notarized=true` adicional en Mac. **Importante**: son aseveraciones de un proceso de publicación autorizado, NO verificación criptográfica del certificado por Python. El proceso de publicación **DEBE verificar** `Get-AuthenticodeSignature`/certificado y editor en Windows, y firma Developer ID Installer + notarización + staple + `spctl` en macOS ANTES de registrar la versión. No permitir que un navegador edite este manifiesto.
- No modifica la ruta histórica `/montara/companion/download` todavía usada por la UI Mac de Chema; es una vía QA LEGACY y **no** debe presentarse como release aprobada. La migración de UI será gradual, una vez disponibles paquetes realmente firmados.

## B. Duplicidades
- Reutilizar `companion/companion.py` como núcleo/protocolo localhost `127.0.0.1:47820`, adaptadores de `windows_support`, `companion/install.sh` y `macos-installer` de Chema. No crear otro servidor de vídeo.
- Windows: existe prototipo **nativo** de Fernando (.NET 8 bandeja; `companion/windows_native/` en `fernando/chema-native-owner`, versión desarrollo 0.6.12.0). El anterior ZIP/PowerShell H4 fue **retirado por seguridad** tras alerta Defender y NO debe revivirse. Ver `docs/integration/MONTARA_COMPANION_NATIVE_WINDOWS_SECURITY_AND_RELEASE_GATE_2026-11-13.md` en rama H4.
- Mac: Chema mantiene `.pkg` + LaunchAgent con verificación del runtime y rollback; no borrar ni sustituir esa implementación al integrar el catálogo.

## C. Reutilización y fases
1. **I5a** (este PR): API común de distribución que no expone QA ni archivos sin hash/version/OS coherentes; diseño independiente del proveedor de hosting. Tests 6/6 PASS y once tests existentes de instalador Mac 11/11 PASS en VM.
2. **I5b Windows**: incorporar y probar `.NET Windows tray`, servicio bundled, MSIX/MSI y la corrección de WinError5 sin reemplazar el código de Chema en Mac; compilación Windows CI y prueba real en Windows 10. El MSIX de CI actual está autofirmado solo para laboratorio, **nunca release**.
3. **I5c Mac**: revisar propuestas de Chema (#164, #170–186); firma Apple Developer ID Installer, notarización y compatibilidad real de Mac. El `productbuild` actual puede generar paquete QA sin firma si no hay secretos.
4. **Auto-updater común**: búsqueda **manual** desde el icono de bandeja/menú de cada SO con notificación opcional futura; mostrar versión y cambios; instalación solo con consentimiento del usuario. Nunca sobrescribir en plena exportación, mix o proxy. El sistema operativo debe verificar la firma real, el desarrollador y la cadena de confianza antes de instalar. Verificar hash y pin del Engine. Si falla actualizar: restaurar ejecutable anterior, conservar todo dato, directorio de proyectos, Engine/venv, originales y caches.
5. **Canal estable**: subdominio de Montara o almacenamiento estático accesible aun con GCP apagada (por ejemplo Cloudflare), artefactos inmutables versionados y firmas verificadas en CI antes de publicación. Un HASH+TLS no reemplaza firma ni notarización. Evitar GitHub privado con tokens en cliente o mantener GCP encendida solo para instaladores.

## D. Riesgos y requisitos de aceptación
- **Certificados:** Windows firma confiable (CA/Store/Artifact Signing según elegibilidad; cert autofirmado de pruebas NO sirve al usuario), Mac Developer ID Installer + notarización Apple. No hay certificado comercial confirmado ni release distribuible en ambos OS hoy. La firma no garantiza ausencia de falsos positivos de SmartScreen/Defender ni de malware.
- **Aún NO hay auto-updater operativo multiplataforma**; el nuevo feed es una base de distribución, no un instalador que pueda actualizarse solo. El botón Windows `Buscar actualizaciones` es un prototipo sin canal firmado. Mantenerlo deshabilitado hasta cadena de confianza completa.
- El núcleo local de Companion y los adaptadores deben usar el mismo protocolo y puerto. No alterar sin revisar el contrato de Google/Owner, recetas Stage/Push/Show, proxies, render y reinicio tras trabajos.
- Evitar volver a introducir el ZIP/PowerShell retirado, `ExecutionPolicy Bypass`, exclusiones Defender o sugerir desactivar el antivirus.
- Los instaladores definitivos deben hacer rollback y migrar sin borrar proyectos, archivos originales, vídeos finales, exports ni el Engine.
- El catálogo actual comprueba hash de archivo en el servidor inmediatamente antes del envío; **la autenticidad del publicador** se establece fuera de él por los pasos de firma/notarización en el pipeline de publicación. Restringir escritura a `Installers/companion-releases.json` al operador de release, jamás a web/usuario.
- Los paquetes grandes deberían servirse desde almacenamiento estático firmado y con HTTP Range; no conectar el download final a la vida de la VM.
- Chema sigue operando `main`: no alterar su UI Mac ni activar rutas de usuarios hasta disponer de paquetes firmados y pruebas de compatibilidad. El catálogo es aditivo y está vacío por defecto.

## E. Validaciones y siguiente PR
- VM GCP, checkout aislado de esta rama: `python -m unittest discover -s tests -p test_companion_release_i5.py -v` → **6/6 PASS**; `node --test tests/companion-native-installer.test.cjs` → **11/11 PASS**; compilación de `app.py` y módulo PASS.
- Checks: rechazo de manifiesto ausente/roto, Engine equivocado, Windows sin firma, Mac sin notarización, hash alterado, symlinks, rutas/arquitectura ajenas y descarga positiva con datos de prueba.
- No hay binarios finales firmados ni instalados por este PR. No se ha editado `web/` ni Windows del usuario ni Mac de Chema.
- `engine/` y `mixer/` permanecen fijados sin modificar. La validación de dos usuarios, render y compatibilidad finales sigue en I7.

**Colaboración:** revisar `docs/COLLABORATION.md`, issue #216 y `STATUS-JM/STATUS-FER`. En revisiones usar A novedades, B duplicidades, C reutilización, D riesgos, E recomendaciones. Cambios en Companion deben respetar Owner y no subir originales sin consentimiento. El ticket #221 contiene la regresión E2E previa de luz/encuadre ajena al catálogo.
