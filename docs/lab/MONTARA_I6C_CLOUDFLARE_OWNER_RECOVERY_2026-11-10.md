# I6C — Diagnóstico y recuperación de la beta pública Cloudflare Owner

**Fecha:** 2026-11-10. **Alcance:** exclusivamente recursos de la beta FER, sin cambios de `main`, Engine, Companion, Vercel ni servicios 8101–8103 de Chema. **Evidencia comprobada en Cloudflare y VM real.**

## Arquitectura real de Cloudflare

- **Cloudflare Pages:** `montara-beta-preview.pages.dev`, conectado por integración GitHub al repositorio `amehcgracia-byte/Montara`, rama de producción `fernando/c8-public-beta-landing-pages-20261110`. HTTP 200, despliegue canónico con estado `success`. Existe además el laboratorio independiente `montara-cloudflare-lab.pages.dev`; se conserva intacto.
- **Cloudflare Worker público:** `https://montara-owner.memoriainvalida001.workers.dev`, script `montara-owner`. Existe y mantiene la binding `OWNER_PRIVATE_API` de tipo `vpc_service`.
- **Workers VPC Service:** `montara-owner-private-8115`, restringido a HTTP puerto 8115 y al túnel `montara-owner-fg`. **No utiliza IP pública de la VM.**
- **Cloudflare Tunnel:** `montara-owner-fg`, conexiones QUIC salientes desde la VM. En funcionamiento tras recuperación, estado `healthy`, cuatro conexiones reportadas por API.
- **Backend:** Gunicorn en `127.0.0.1:8115`, cuenta Linux separada `fgardel00`, aplicación Google Owner WSGI; solo loopback, ninguna entrada pública de GCP.

`127.0.0.1` es la dirección local del **servicio privado** detrás de la URL pública real. No es una web temporal ni una alternativa a la URL de Cloudflare. El origen del túnel no depende de la IP pública estática que se asignó para Gateway SSH. Identity Google tampoco exige que el backend esté alojado en GCP.

## Incidencia y hallazgo

Tras el apagado/reinicio automático de GCP se observó HTTP 503, ausencia de Gunicorn:8115 y `cloudflared`, pero los tres puertos de Chema 8101–8103 estaban operativos. Los ficheros privados existentes (script de arranque y secretos 0600) seguían presentes.

Se comprobaron con el conector conectado directamente a Cloudflare: proyectos Pages, conexión GitHub, Worker `montara-owner`, binding `OWNER_PRIVATE_API`, túnel y VPC Service. El Worker devuelve 503 cuando la binding no logra conectar a origen, no porque carezca de URL pública.

**Corrección funcional verificada:** el VPC Service apuntaba a la IP literal `127.0.0.1`. Tras reiniciar los servicios, seguía devolviendo 503. Se cambió únicamente el destino de este VPC Service a **hostname `localhost`**, con el **mismo** túnel y puerto 8115. HTTP público pasó inmediatamente a **200**. Este cambio está documentado como resultado observado: no demuestra la causa interna exacta del rechazo de la IP literal por Workers VPC beta. No se modificó el Worker ni se abrió un puerto público.

## Servicios persistentes en la VM

Se crearon dos servicios **systemd --user** de `fgardel00`, con `UMask=0077`, `NoNewPrivileges=true`, `Restart=on-failure`, `KillMode=control-group`, y habilitados para `default.target`:
- `montara-owner-beta.service`: invoca el script privado preexistente `~/.config/montara-owner-beta/start-owner-portal.sh`. Escucha únicamente loopback 8115.
- `montara-owner-tunnel.service`: ejecuta el binario privado existente `~/.local/bin/cloudflared tunnel run --token-file [ruta privada]` con QUIC. El token nunca aparece en la línea de comandos ni en GitHub.
- Se habilitó **`loginctl enable-linger fgardel00`** para permitir que el gestor systemd de esta cuenta funcione sin una sesión SSH iniciada.

**Comprobado:** ambas unidades `enabled` y `active`; `Linger=yes`. **Aún no se ha probado el comportamiento tras OTRO reinicio real**, que se hará en una ventana controlada sin interrumpir a Chema.

**Nota de portabilidad:** los archivos operativos activos son privados y se gestionan en el HOME del usuario de prueba; una futura instalación Oracle/Azure debe templar usuario, HOME, ruta de checkout, secretos, unidades de servicio y origen del túnel. No copiar credenciales ni rutas de proyecto como constantes de producto.

## Verificación de la URL pública

| Ruta | Resultado esperado y observado |
| --- | --- |
| `/healthz` | HTTP **200**, identifica `montara-owner-beta`; devuelve `authenticated=false`, `engine_provisioned=false`, `public_multiuser_ready=false` |
| `/` | HTTP **303** hacia el inicio del flujo Google (sin seguir redirecciones ni registrar el enlace de autorización) |
| `/urano/v1/dashboard` | HTTP **401** sin sesión |
| `/urano/v1/projects` | HTTP **401** sin sesión |
| `montara-beta-preview.pages.dev/` | HTTP **200** |
| `montara-cloudflare-lab.pages.dev/` | HTTP **200** |

**Esto no acredita que un usuario haya completado login Google**, que Engine esté aprovisionado ni que Companion haya producido MP4. Es salud de entrada y autorización anónima únicamente.

## Manual de diagnóstico sin secretos

1. Confirmar que la VM está encendida. Desde cuenta FER, `systemctl --user is-active montara-owner-beta.service montara-owner-tunnel.service` y `systemctl --user is-enabled ...`; `loginctl show-user fgardel00 -p Linger`.
2. Comprobar escucha `127.0.0.1:8115`. Si responde local pero falla la URL pública, comprobar Cloudflare: `montara-owner` → binding `OWNER_PRIVATE_API` → VPC Service → hostname `localhost` y puerto 8115 → túnel `montara-owner-fg` `healthy`.
3. Comprobar códigos HTTP de las cuatro rutas anteriores, sin seguir la redirección Google y sin imprimir credenciales.
4. Si el servicio falla, inspeccionar logs locales solo con redacción de tokens, URLs OAuth, cookies y cabeceras. No compartir archivos `*.token`, `owner-beta.env`, `google-*secret*`, ficheros de proyecto ni datos de usuarios.
5. No modificar ni reiniciar 8101–8103 ni el túnel/Pages/laboratorio de Chema. No exponer 8115 por firewall ni registrar un dominio comprado por necesidad técnica.

## Puertas pendientes

- Reinicio real controlado: VM autoapagado → arranque automático de unidades y túnel → 200 externo y login Google comprobado.
- Test Google auténtico con cuenta beta autorizada; dashboard, aislamiento de proyectos, tests negativos.
- I5B Engine aislado por propietario, I6B/benchmark híbrido de una persona, y posteriormente comparación Cloudflare/Vercel con mismo backend.
- No fusionar esta topología operativa directamente en `main` de Chema sin revisión de despliegue; es un entorno FER.

Documentación oficial: https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/ y https://developers.cloudflare.com/workers-vpc/api/ y https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
