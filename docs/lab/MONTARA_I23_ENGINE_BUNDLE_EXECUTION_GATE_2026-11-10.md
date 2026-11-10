# I23 — Siguiente gate único: Engine completo con DynamicUser

**Fecha:** 10/11/2026. **Estado:** preparado y revisado sin ejecución física. **NO apto para producción.**

I22 probó con éxito dos UIDs de host separados (65075 y 62267), proyectos privados, prohibición de lectura cruzada y sin acceso al HOME del operador, usando systemd del sistema y una copia del *núcleo* Engine. I21 ya probó que HTTP firmado -> I13/I18/I19 -> Engine real, ledger y cierre funciona en la VM, pero su Engine corría con UID host compartido.

**El único gate físico pendiente antes de unir ambas pruebas** es ejecutar el worker Engine completo bajo \`DynamicUser\`, con su Python 3.11 y dependencias. Para ello se ha preparado \`tests/urano_i23_dynamicuser_engine_lab.py\`, exclusivamente opt-in.

El script verifica el SHA del Engine pinneado, empaqueta en un directorio temporal de \`/tmp\` **solo código rastreado por Git** y copia la distribución Python/paquetes de laboratorio; comprueba enlaces simbólicos dirigidos al HOME, no modifica permisos originales y monta el bundle de solo lectura. Ejecuta un servicio **transitorio** \`systemd-run --system --pipe --wait --collect\`, con \`DynamicUser\`, \`ProtectHome\`, \`ProtectSystem=strict\`, \`PrivateNetwork\`, \`PrivateTmp\`, \`PrivateDevices\`, \`NoNewPrivileges\`, límite de 768MiB RAM/64 tareas/CPU equivalente a 1 núcleo y workspace \`RuntimeDirectoryMode=0700\`. Dentro del servicio crea un documento Engine sintético, ejecuta el worker real con comandos JSON \`open\` y \`stop\` y exige respuesta positiva, UID no root y distinto del operador, HOME bloqueado y cierre. Al salir se elimina el paquete temporal.

**No se ha ejecutado físicamente I23 en este turno:** Gateway vuelve a fallar al establecer SSH con la VM tras una sesión anterior en que el usuario aclaró que existe un autoapagado programado. No asumir que la causa del nuevo timeout esté demostrada. Sin acceso al servidor no afirmar PASS del worker, ni abrir rutas Owner, ni instalar paquetes, ni cambiar configuración global.

### Ejecución autorizada cuando vuelva SSH

\`\`\`bash
python3 tests/urano_i23_dynamicuser_engine_lab.py \
  --repo "$HOME/montara-integration-i23" \
  --engine "$HOME/montara-owner-beta/engine" \
  --venv "$HOME/montara-owner-beta/.venv" \
  --python-root "$HOME/.local/share/uv/python/cpython-3.11.18-linux-x86_64-gnu" \
  --operator-opt-in
\`\`\`

El operador debe crear un worktree desde la PR antes de lanzarlo. El script puede necesitar una adaptación mínima de importaciones o empaquetado antes de pasar; mantener el sandbox estricto, no chmod el HOME. La CI comprueba sintaxis/contratos offline, **no da por aprobado el Engine**.

Si pasa, el siguiente paso será incorporar el mismo servicio al broker de privilegios limitados con mapeo duradero de unidad, cgroup y generación I18/I21 y botón \`Abrir proyecto\` solo detrás de *feature flag* de beta privada. Después Companion -> Stage -> MP4 local. Evitar rondas de laboratorio adicionales sin un fallo concreto.

**No tocar:** \`main\`, PR #189 DRAFT, servicios de Chema 8101–8103, Owner 8115, Cloudflare o los originales locales.
