# I6B · Preflight de una persona con portal C8 y Companion

**Fecha:** 2026-11-10. **Base:** `fernando/integracion@81eb003`. **Estado:** contratos offline aprobados; **no se ha hecho E2E híbrido real**.

## Por qué cambia U18

El histórico `tests/urano_remote_hybrid_preflight.py` comprueba `/api/v1/wizard/status`, ruta del editor clásico, que no está expuesta en C8. No modificarlo: es evidencia de un laboratorio anterior.

`tests/urano_owner_hybrid_preflight.py` es una herramienta nueva que comprueba únicamente tres GET opt-in: HTTPS `/healthz` con identidad `montara-owner-beta`, HTTPS `/urano/v1/dashboard` sin cookies que debe negar acceso (401/403), y `http://127.0.0.1:47820/health` en el **mismo ordenador** con identidad y FFmpeg de Companion. Mantiene validación DNS y TLS del U18 y no sigue redirecciones. No solicita sesiones, crea proyectos, lee archivos ni inicia renders. Salida local JSON nueva, sin URLs ni IP, con información desconocida como `null` y los gates de Google→Engine→MP4 marcados explícitamente **false**.

Ejemplo de uso futuro **solo en un cliente físico con Companion ya iniciado** y servidor aprobado:

```bash
python tests/urano_owner_hybrid_preflight.py \
  --server-origin https://montara-owner.memoriainvalida001.workers.dev \
  --execute --output mi-preflight-nuevo.json
```

Sin `--execute` no hay conexiones. No se despliega en la VM ni se ejecuta desde el navegador del usuario. `ready_for_manual_auth_trial=true` solo demuestra alcanzabilidad y rechazo del dashboard anónimo, **no** login Google, privacidad multiusuario ni benchmark.

## Incidencia real del 10-11-2026

La VM se ha reiniciado a las **11:32:32 UTC** (observado con `uptime -s`). Los servicios de Chema en 8101/8102 y una instancia en 8103 están activos; **nuestro puerto 8115 no escucha**, no hay cloudflared del usuario y la unidad `montara-owner-beta.service` no está registrada en el gestor `systemd --user` de `fgardel00`. URL externa `/healthz`: HTTP **503**. Esto es coherente con que la beta fuera lanzada mediante servicios transitorios que no sobreviven al reinicio, pero **no se ha demostrado el mecanismo exacto**. No reiniciar, activar, instalar ni registrar servicios sin auditar sus credenciales/túnel y garantizar ausencia de impacto en 8101–8103. No interpretar el 503 como regresión de login.

## Gate de benchmark real I6C

1. Restaurar el servicio privado con un lanzador reproducible y **arranque tras reinicio** controlado, configuración y secretos fuera de Git. Verificar Cloudflare y Google.
2. Ejecutar el preflight I6B en el ordenador del propietario con Companion real y versión registrada.
3. Conectar por separado Engine privado/proxy/receta, verificando que el backend rechaza subidas de originales no consentidas.
4. Fijar un fixture y repetir tres veces: latencias, CPU/RAM por host, proxy bytes, Stage, render local MP4 con ffprobe, estabilidad y fallos. Comparar Cloudflare vs Vercel con **el mismo backend y cliente** o etiquetar rutas distintas.
5. Medir una persona **antes** de afirmar capacidad de 2, 4, 8, 10 usuarios.

### Evidencia offline

En worktree independiente: `PYTHONPATH=tests python -m pytest -q tests/test_urano_owner_hybrid_preflight.py tests/test_urano_remote_hybrid_preflight.py tests/test_urano_browser_transfer.py tests/test_urano_hybrid_node_telemetry.py`: **20 passed, 2 skipped, 14 subtests passed**. Dos omitidas por `psutil` opcional ausente en la VM; CI instala `psutil` y las ejecutará. No implica acceso real a Google, red WAN ni Companion físico.

**Sin cambios de app.py, Companion, Engine/Mixer, main, Cloudflare, VM ni datos.**
