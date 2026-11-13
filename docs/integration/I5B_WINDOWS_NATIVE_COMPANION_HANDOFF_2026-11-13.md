# I5b — Windows Companion nativo (QA, no distribución)

**13-11-2026 | IMPORTANTE PARA CHEMA Y SU IA**

**El Companion Windows de Fernando y el Companion macOS de Chema siguen siendo provisionales.** Son prototipos a converger hacia UN protocolo Montara local compatible con un instalador por sistema y actualizaciones con firma real. No hay dos productos permanentes; no reemplazar sin probar la instalación existente de ninguno de los dos.

## A. Novedades

- Controlador nativo .NET 8 WinForms y bandeja en `companion/windows_native/`, icono Montara, consultas localhost 47820 y servicio Python empaquetado para pruebas.
- CI Windows 2022 con build de desarrollo MSIX, PyInstaller selftest y test del render. La firma del QA es **autofirmada efímera**, sin reputación ni confianza para distribución.
- `companion/local_video.py` incorpora el fix WinError5: reintentos acotados únicamente para escritura del indicador `progress.json`; receta, proyectos y MP4 mantienen sus escrituras estrictas. Tests de regresión incluidos.
- El botón `Buscar actualizaciones` en Windows sigue siendo un prototipo NO funcional: no baja ni ejecuta scripts de actualización.

## B. Duplicidades

Mantener el núcleo `companion/companion.py` y Engine/Mixer fijados. NO sustituir el `.pkg` Mac, LaunchAgent, rollback o mejoras de Chema. No crear otro servidor de vídeo.

## C. Reutilización

Origen: `fernando/chema-native-owner`, candidato Windows 0.6.12.0 no validado como instalador real en Windows 10. La exportación Stage local ya fue validada con el servicio Python en el equipo del usuario, pero eso NO valida el nuevo MSIX.

## D. Riesgos y puertas obligatorias

1. **Certificado Windows:** certificado confiable de identidad del editor (Microsoft Store, Artifact Signing si elegibles o CA), firma con timestamp, verificación por sistema de cadena + editor real. MSIX autofirmado de CI nunca como descarga final. No indicar a usuarios que desactiven Defender/SmartScreen ni recuperen el ZIP/Powershell anterior retirado tras alerta.
2. **Auto-updater:** comprobación bajo demanda desde la bandeja; mostrar versión y cambios, pedir consentimiento y usar el instalador del sistema, **verificar firma real y hash** antes de aplicar. No actualizar con proxy, mix o render ocupado. No detener procesos de otra instalación. Recuperar versión anterior ante error.
3. **Persistencia:** preservar las carpetas y referencias locales, originales, Engine, entorno, proyectos, exports y cachés. El parche de progreso jamás toca Engine.
4. **Origen HTTPS:** la fuente Windows contiene aún patrones concretos para beta H4; un canal final requiere configuración revisada de origen estable y alcance por usuario. Nunca admitir un Origin arbitrario.
5. **Mac:** su PKG también depende de firma Apple Developer ID Installer, notarización y comprobación de lanzamiento. La compilación QA no sustituye esos certificados.
6. **Distribución:** el catálogo de I5a solo admite versiones aprobadas por operador y SHA Engine coincidente. El campo signed del manifiesto no certifica por sí solo la firma: el pipeline debe comprobarla **antes de publicar**.
7. **Estado real:** ni el updater Windows ni el Mac final firmados/certificados están desplegados desde main. Sin nueva instalación en PCs, sin cambio de producción.

## E. Pruebas y siguientes pasos

- `tests/test_companion_windows_render_progress.py`: regresión WinError5 Windows y no-Windows.
- Workflow de Windows: dotnet build y MSIX dev, servicio PyInstaller, selftest, control de contenido y prueba de origen; no publica release y mantiene artefactos QA cortos.
- Cerrar puerta solo tras Windows CI verde y prueba humana Win10 de instalador, versiones compatibles y caso actualización activa/inactiva; Mac después firma/notarización/test real. I6 apagado seguro, I7 E2E completo multiusuario.

Documentación obligatoria entre IA: `docs/COLLABORATION.md`, issue #216 y STATUS-JM/STATUS-FER. Referencia de seguridad: `docs/integration/MONTARA_COMPANION_NATIVE_WINDOWS_SECURITY_AND_RELEASE_GATE_2026-11-13.md` en rama `fernando/chema-native-owner`.
