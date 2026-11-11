# MONTARA SMART — Hito 1 completado: portal Google + editor privado + worker real

**Fecha:** 11 noviembre 2026 · **Rama:** `fernando/integracion` · **NO integrado en main**.

## Resultado verificado

Se ha conectado en **beta privada activa GCP/Cloudflare** el portal Google existente con el editor auténtico de Chema mediante una opción de despliegue reversible. `MONTARA_JM_EDITOR_PILOT=private` activa el editor original solo si hay Engine privado, bundle JM pinneado y manifiesto de versiones comprobado. Ningún origen local, vídeo ni secreto de usuario se cambió.

- HTTPS público: `/healthz` **200**, `/urano/v1/google/start` **302** hacia OAuth y `/urano/v1/dashboard` sin sesión **401**. Tunnel, portal y broker `active`.
- Con sesión autenticada **de prueba en SQLite aislada, sin usar el Google personal**: dashboard HTTP **200**, crear Stage HTTP **201**, editor original con HTML `montara.js` HTTP **200**, adaptador JS HTTP **200**, proyecto de otro Owner **404**.
- Broker root nuevo activo con **Engine `b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b`**, JM `14cce126137a0ef30a987351ff35b750f54473bd`, Mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`; configuración actual 4096 MB, 250 % CPU, 256 tasks, max proxy Companion 2048 MiB, fallback original 256 MiB.
- Worker **systemd DynamicUser verdadero**, no simulado, creado para un proyecto UUID de prueba sin datos reales. Listo en segundos, `ready.json` correcto, Unix HTTP del editor HTTP **200**, `/api/v1/project` HTTP **200** y UUID correcto, `/montara/uploads` HTTP **200** con límites 2048/256 MiB; proceso finalizado voluntariamente. **0 jobs de prueba activos** al concluir.
- No se han cambiado `main`, editor JS/CSS de Chema, originales en Windows, proyectos privados existentes ni Companion instalado.
- 18 regresiones HTTP/JS PASS al preparar el despliegue.

**Alcance:** esto cierra la **activación técnica del hito 1**. Todavía NO se ha realizado login Google humano ni el recorrido completo Google→subida real→render con Companion Windows. Esos últimos pasos son parte del ensayo integral y validación humana, no motivo para repetir más auditorías de infraestructura.

## Cambios concretos para SMART

- `urano/owner_beta_wsgi.py`: piloto editor por opción, validación inmutable del bundle y sin permitir Engine compartido.
- `urano/owner_dashboard.py`: crear Stage con modalidad antes de abrir editor de Chema; no botón «Abrir Engine» en el piloto; proyectos viejos conservados.
- `urano/minimal_owner_api.py`: monta assets y gateway de Chema detrás de Google/SQLite.
- `urano/editor_mode.py`: función pura; el broker root ya no importa Flask accidentalmente.
- `urano/private_broker_service.py`: runner de worker root pinneado y con rollback.
- `urano/private_broker_worker.py`: imports de Engine antiguo únicamente en modo legacy; priorizar paquete `urano` actualizado sobre `app/urano` antiguo.
- Liberado acceso multimedia HTTP mayor de 300 KB exclusivamente en rutas autenticadas de subida.
- Los nuevos bundles completos estaban previamente preparados bajo `/opt/montara/bundles`.

## Configuración de despliegue reversible

Activada con dos drop-ins creados **sin sobrescribir las unidades originales**:

- Usuario: `~/.config/systemd/user/montara-owner-beta.service.d/30-smart-chema-stage.conf`, apuntando a `~/.config/montara-owner-beta/start-owner-portal-smart.sh` y `/home/fgardel00/montara-owner-portal-smart-candidate`.
- Root: `/etc/systemd/system/montara-i26-broker.service.d/30-smart-chema-stage.conf`, apuntando a `/opt/montara/broker-smart-candidate/private_broker_service.py`, con worker pinneado `/opt/montara/broker-smart-candidate/private_broker_worker.py`.

Un primer despliegue se revirtió automáticamente al comprobar el puerto **antes de que Gunicorn escuchara**. El segundo esperó la respuesta de salud y fue exitoso. La reversión automática demostró que las unidades originales podían volver a arrancar. Para una reversión deliberada, retirar **solo** ambos drop-ins `30-smart-chema-stage.conf`, `systemctl daemon-reload` (root y user) y reiniciar respectivamente `montara-i26-broker.service` y `montara-owner-beta.service`. Conservar bases SQLite y archivos; revisar trabajos activos antes de reiniciar.

**Revisiones en ejecución:** bundle editor/Engine/Mixer exactos arriba; candidato de portal copiado de `326e3c1e`, worker final ajustado en `47eb3b46`; ambos cambios están versionados en `fernando/integracion`. No se ha hecho restart del broker después del último ajuste del archivo worker; se ejecuta al lanzar el próximo worker.

## Siguiente hito (2 de 5)

**Stage navegador real hasta «Solicitar render».** Reducir a lo imprescindible: adaptar `GET /montara/version`, `GET /montara/branding`, previews y revisión/cortes dentro del Owner; revisión de media y Range, sin abrir un proxy general ni tocar otras modalidades. No crear otro editor, uploader ni renderizador. Después Companion Windows, E2E y validación humana; `main` solo tras validación.

**Regla SMART:** un hito por entrega, con prueba funcional de cierre y sin añadir nuevas fases de laboratorio.
