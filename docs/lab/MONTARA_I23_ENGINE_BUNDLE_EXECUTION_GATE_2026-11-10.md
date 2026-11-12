# I23 — Engine COMPLETO probado con DynamicUser (10/11/2026)

**Resultado físico: PASS, dos ejecuciones.** Este gate de laboratorio valida la ejecución del `urano.engine_worker_process` auténtico con Python 3.11 y dependencias reales bajo un UID Linux de host dinámico, sin exponer el HOME del operador. **NO** constituye aún un broker multiusuario seguro para la beta pública.

## Evidencia exacta

- VM GCP `montara-test` recuperada por el usuario después del autoapagado programado. Owner/túnel activos; Chema 8101–8103 activos. `main` intacta.
- Engine SHA pinneado comprobado: `b5e48317ef85225f901adc69af8cc17aa8146880`.
- El script opt-in archiva código **rastreado en Git** de Engine y URANO y copia runtime Python + `site-packages` a un bundle temporal de laboratorio. No cambia permisos del HOME ni del checkout original.
- La unidad transitoria de systemd del sistema utiliza `DynamicUser=yes`, `ProtectHome=yes`, `ProtectSystem=strict`, `PrivateNetwork=yes`, `PrivateDevices=yes`, `PrivateTmp=yes`, `NoNewPrivileges=yes`, `RestrictSUIDSGID=yes`, `MemoryMax=768M`, `TasksMax=64`, `CPUQuota=100%`, `RuntimeDirectoryMode=0700` y un `BindReadOnlyPaths` del bundle.
- El worker Engine verdadero recibe `open` y `stop`, abre un documento `new_project_document` sintético dentro de su directorio de ejecución y confirma JSON `ready`, `opened`, `stopped`.
- Primera ejecución física completa: **PASS**, UID host **63717**, HOME inaccesible; worker cerrado. Segunda ejecución: **PASS**, UID host **63240**, HOME inaccesible; worker cerrado. Distintos del UID 1006 del operador.
- Segunda ejecución, tiempo total **16,26 s** incluyendo la copia del paquete de aproximadamente 1,3 GB de dependencias de laboratorio, montaje y cierre. Este NO es el tiempo puro de apertura del Engine ni un valor p95. Se deberá usar bundle compartido, versionado y read-only para evitar copiarlo por cada trabajo.
- Después de la repetición: **0 unidades `montara-i23-*`**, cero directorios temporales del bundle, Owner/túnel activos, Chema en 8101–8103, disco 47 GB libres.

## Fallo de integración diagnosticado y resuelto

El primer intento produjo salida no cero sin mensaje útil; se corrigió la captura acotada de stderr. El mensaje reveló `Failed to find executable /opt/montara-i23/python/bin/python3.11` porque systemd intenta resolver el ejecutable **antes** de montar la ruta `BindReadOnlyPaths`. La corrección usa **`/usr/bin/env` del host como ejecutable inicial** y pasa el Python del bundle como argumento. **No se relajaron permisos ni se instaló software.** Después pasaron dos pruebas completas.

## Lo que falta, sin añadir más laboratorios de identidad

1. Incorporar la ejecución `DynamicUser` al **broker confiable** con un canal IPC limitado y una identidad de unidad/cgroup **persistida y ligada al job/generación** de I18/I21. El servicio HTTP no debe disponer de `sudo`, D-Bus de systemd root o rutas arbitrarias. Verificar solo el objetivo exacto al cancelar.
2. Probar con dos proyectos reales sintéticos simultáneos bajo este worker completo, más FFmpeg limitado y cancelación; utilizar las pruebas adversariales I17/I22 como base, no repetir lo ya demostrado.
3. Tras completar la seguridad de broker/recovery, habilitar **solo beta privada y feature flag** el botón `Abrir proyecto` con la cuenta Google real del usuario. Luego Companion Windows → Stage → MP4 local.

El mecanismo de empaquetado del laboratorio todavía copia dependencias de una instalación existente. Para producto será necesaria una distribución controlada, reproducible y segura: fijación de versiones/hashes, enlaces simbólicos validados, permisos de solo lectura, control de integridad, manejo de recursos temporales y límites efectivos, sin depender de rutas privadas `/home`. La presencia de root para lanzar servicios transitorios exige un broker mínimo con privilegios muy restringidos: **este script no se conecta a la web**.

La CI I23 comprueba contratos de forma **offline**, no sustituye estos dos ensayos físicos ni certifica producción. El fallo histórico de E2E Linux/Companion C6 sigue siendo una incidencia separada y preexistente. `main` y PR #189 siguen DRAFT/no fusionadas.
