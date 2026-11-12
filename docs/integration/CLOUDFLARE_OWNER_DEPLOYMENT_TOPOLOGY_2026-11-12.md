# Montara — Topología real de Cloudflare y política de publicación nativa

**Fecha:** 12-11-2026. **Objetivo:** conservar la beta privada mientras se prepara el editor nativo de Chema con Owner multiusuario. **Sin modificaciones de infraestructura ni despliegues.**

## Consultas de solo lectura verificadas
- Cloudflare Pages `montara-beta-preview`: proveedor GitHub, repositorio `Montara`, rama de producción **`fernando/integracion`**. Este dato confirma la conexión automática de Pages, no la del portal.
- Worker `montara-owner`: binding **`OWNER_PRIVATE_API`** de tipo `vpc_service`. Es una pasarela que envía tráfico privado a un origen, no un sistema que despliegue la rama GitHub automáticamente.
- Cloudflare Tunnel `montara-owner-fg`: `healthy`.
- VM: `montara-owner-beta.service`, `montara-i26-broker.service` y `montara-owner-tunnel.service` activos; endpoint `https://montara-owner.memoriainvalida001.workers.dev/healthz` responde HTTP 200.
- Portal Owner ejecutado por el unit de usuario con `WorkingDirectory=/home/fgardel00/montara-owner-portal-smart-candidate`, `ExecStart=~/.config/montara-owner-beta/start-owner-portal-smart.sh`.
- Tunnel de usuario: `~/.local/bin/cloudflared tunnel run --token-file ...` (no incorporar tokens o credenciales a documentos, procesos de test ni repositorios).

## Consecuencias precisas
1. La URL de aceptación `montara-owner.memoriainvalida001.workers.dev` **no está conectada directamente** a la rama `fernando/integracion`: el Worker publica la aplicación instalada en la VM.
2. Pages `montara-beta-preview` sí utiliza `fernando/integracion`; **no** debe cambiarse su rama de producción para activar el piloto. No confundir el sitio Pages con el portal Owner.
3. La nueva rama `fernando/chema-native-owner` parte de `main`, con adaptaciones mínimas. No está publicada.
4. Para la futura validación humana real se necesita publicar una versión coherente del portal detrás de un origen de Cloudflare y comprobar que el navegador puede conectarse a Companion. **No basta con cambiar la rama Pages.**

## Estrategia mínima y segura de aceptación
- Mantener exactamente como está `montara-owner` y el túnel actual mientras existan proyectos activos.
- Verificar primero en GitHub, una copia aislada y con pruebas, el contrato entre la interfaz **original** de Chema y Owner. No usar el CSS multiproyecto ni duplicar la portada.
- Para pruebas reales, crear una **instancia de validación aislada**, reutilizando el acceso de Cloudflare sin exponer nuevos servicios de GCP ni instalar un segundo broker sin justificación. Debe disponer de sesión Google y datos/worker estrictamente separados; si no se puede garantizar aislamiento, hacer una publicación reversible en ventana acordada tras guardar estados.
- Solo cuando el flujo real sea válido: preparar PR pequeño y revisable hacia `main` de Chema. No fusionar `fernando/integracion` entera.

## Protección de infraestructura
No alterar ahora ramas de Pages, Worker, rutas VPC, túneles, DNS, Cloudflare OAuth ni tokens. No reiniciar broker ni workers en ejecución; no borrar ni migrar datos históricos. Cada despliegue posterior requiere inventario explícito de servicios, aislamiento, rollback y confirmación del recorrido real.
