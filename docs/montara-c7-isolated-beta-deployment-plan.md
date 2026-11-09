# C7 — Plan de despliegue aislado para la beta de MONTARA

**Estado:** planificación e inventario, no instalación ni despliegue. Rama C7
apilada sobre C6; `main` y VM compartida intocadas.

## Diagnóstico de referencia (solo lectura, vía Gateway)

La sesión `fgardel00` conectó correctamente por SSH a
`montara-test`. Inventario observado: Linux x86_64, 31 GiB RAM,
~29 GiB disponibles, disco raíz 96 GB / ~58 GB libres, puertos
127.0.0.1:8101, :8102 y :8103 ocupados. En el PATH no hay `docker` ni
`podman`; sí `lxc` y `lxd`. No existe
`/var/run/docker.sock`. No se instalaron programas ni se cambiaron
servicios.

**Consecuencia:** la aceptación con Docker en GitHub Actions no demuestra
que nuestro C7 pueda arrancar en esta VM tal cual. No es aceptable
sustituir Docker por LXD de forma implícita ni usar permisos sudo para
simular que la separación por propietario ya funciona.

## Decisión de producto: usuarios reales, no usuarios Docker

**Docker no es un requisito funcional del editor.** El usuario final entra con
Google desde el navegador, abre su propio proyecto, genera proxies con
Companion y exporta localmente. No ve Docker ni tiene que instalarlo.
Los dos contenedores en CI son una forma de comprobar **aislamiento del Engine
y de sus ficheros** bajo dos identidades distintas, no una simulación de
interfaz de usuario.

**En la implementación actual**, el puente privado
`ContainerWorkerBridge` **sí invoca Docker literalmente** para ejecutar
cada worker. Prescindir de Docker es técnicamente posible, pero **no** se
consigue quitando ese ejecutable: habría que escribir un adaptador para
procesos separados por UID, LXD u otro aislamiento equivalente, demostrar
destrucción y revocación al cerrar sesión, controlar límites y ficheros, y
repetir todas las pruebas de propietarios cruzados. El supervisor de proceso
`private_worker_supervisor.py` lo advierte expresamente: no es una sandbox
multiusuario por sí solo.

### Escalonar pruebas con personas, sin sobredimensionar

1. **C8 personal**: un usuario autorizado, vídeos sintéticos o propios,
   Companion instalado, proyecto, cortes, audio y MP4 final. Aislamiento
   suficiente para esta prueba controlada y sin servicio público de invitación.
   Preferir un despliegue temporal con los permisos existentes, pero **no
   afirmar** que el backend multiusuario Docker funciona en una máquina que
   todavía no tiene Docker.
2. **Beta cerrada con amigos**: 2–4 personas reales, cada una con su propia
   cuenta Google, sesión, proyectos, fuentes y permisos; nunca compartir un
   Engine con estado mutable. Solo abrir las invitaciones cuando la plataforma
   de aislamiento elegida haya pasado la aceptación de usuarios cruzados.
3. **Después de las pruebas**: comparar coste, mantenimiento y seguridad de
   Docker frente a procesos aislados por usuario Linux o LXD. Si se sustituye
   Docker, eliminar la dependencia mediante PR y regresiones, **no por borrar
   imágenes sin haber reemplazado el código**.

**Regla:** no alquilar otra VM ni instalar Docker solo para marcar una fase en
un roadmap. Escoger la opción mínima capaz de ejecutar la prueba pendiente
con separación verificable.

## Inventario, caducidad y retirada de residuos de laboratorio

Registrar antes de activar cualquier prueba: recurso/imagen, ID de dueño,
proyecto, ruta de datos, fecha de creación, consumo máximo, responsable y
condición de retirada. Diferenciar:

- **Efímero**: contenedores de CI, temporales de pruebas, imágenes de build,
  registros sintéticos, recibos HMAC de laboratorio, runners y logs
  descartables. El comando Docker actual usa `--rm` para el contenedor,
  pero **eso no elimina imágenes, cachés, ficheros montados ni volúmenes**.
- **Persistente y necesario**: código, historia y pruebas de URANO/JÚPITER/
  SATURNO, proyectos legítimos de usuarios, consentimientos, snapshots
  necesarios para diagnosticar incidencias y claves activas; no limpiar
  automáticamente.
- **Retirada controlada**: al cerrar C8, generar un informe *dry-run* de
  imágenes, volúmenes, contenedores detenidos, almacenamiento de proxies,
  carpetas temporales, acciones y PR históricas. Revisarlo con propietario y
  Chema si afecta a la VM compartida; eliminar únicamente recursos
  identificados inequívocamente como propios y sin usuarios activos.

**Prohibido** ejecutar `docker system prune -a --volumes`,
`rm -rf` sobre rutas compartidas, limpiar carpetas de Chema, o borrar
ramas/PR de otra persona. Tampoco borrar imágenes mientras algún worker
activo las utilice. La limpieza de ramas se hace por cambios funcionales
únicos y dependencias, no por antigüedad ni número de commits.

## Opciones antes de la primera prueba real

| Opción | Ventaja | Condición / inconveniente |
|---|---|---|
| A. Entorno beta aislado fuera de la VM compartida | Máxima separación de Chema; imagen Docker verificada sin tocar 8101–8103 | Infraestructura, coste y permisos propios por autorizar |
| B. Instalación paralela dentro de la VM actual | Aprovecha RAM y disco disponibles y acceso Gateway | Docker falta. Instalarlo, cambiar servicios o configurar un nuevo proxy son cambios **compartidos** y requieren autorización expresa del usuario y Chema; sin ello C7 está bloqueado |
| C. Adaptación explícita a LXD | El binario ya está presente | Exige nuevo modelo de seguridad y repetir aceptación de dos propietarios en LXD. No es equivalente a Docker ni es atajo validado |

**Recomendación revisada:** evitar contratar recursos o instalar Docker hasta determinar qué hace falta para **C8 personal**. Para una beta pública de amigos sin vigilancia se exige aislamiento real por propietario: A es la opción menos invasiva con el bridge Docker actual; B necesita autorización de cambios compartidos; C exige adaptador y pruebas nuevas. No se ha creado ninguna instancia ni contratado recursos.

## Arquitectura objetivo

```text
Navegador HTTPS (dominio fijo, Google OAuth)
       |
       v
Proxy HTTPS de confianza [Host/scheme validados]
       |
       v
Flask owner API en loopback [sesiones + owner + CSRF + catálogo]
       |
       +--- inbox por propietario [proxy MP4 y HMAC autenticado]
       |
       +--- controlador confiable
                |
                +--- Docker owner A [UID, disco, Engine Stage aislados]
                +--- Docker owner B [UID, disco, Engine Stage aislados]
                         |
                         +-- ingest_proof: slots + hashes, nunca rutas
       |
       v
Receta exportable sin originales -> Companion 127.0.0.1:47820
                                      -> MP4 en PC del usuario
```

No debemos dirigir los MP4 originales a la VM. La web transporta proxies
y recetas; los originales y el render final quedan en Companion.

## Controles previos obligatorios

- `urano/c7_deployment_readiness.py` proporciona una puerta de revisión
  **todo o nada**; no despliega ni eleva privilegios.
- El controlador de propietarios solo utiliza workers Docker con imagen
  fijada a digest y volúmenes privados. La sesión de login nunca provisiona
  contenedores por sí sola.
- Reverse proxy HTTPS y conectividad a la app únicamente por loopback;
  no confiar en `X-Forwarded-Host` de clientes externos.
- Dominio beta canónico idéntico al configurado para Google y Companion.
- Credenciales Google y HMAC almacenadas en ficheros privados, fuera de
  GitHub y nunca en JavaScript.
- Ningún servicio/puerto existente de Chema se reconfigura; para cualquier
  cambio sobre la VM compartida se exige **doble aprobación explícita**.
- Presupuesto/costes, reglas de red, backups, retención de proxies,
  límite de disco, caducidad de sesiones y recuperación de proyecto
  pendientes de validación operativa.
- Reproducir dos propietarios reales (dos sesiones, dos workers privados,
  dos proyectos), Stage DONE, recibos autenticados y certificación.
- C8 necesita Chrome/Edge en el PC, Companion emparejado, medios de prueba,
  prueba de cortes/audio y MP4 final local.

## Entregables de C7

**Ahora:** selección razonada de arquitectura, inventario read-only,
contrato de preflight y tests. **No hemos alcanzado** "C7 deployed".

**Al autorizar una instalación:** activar recursos separados, configurar
DNS/TLS/Google, secrets y worker de cada propietario y repetir E2E
aislado. Si la beta usa VM existente, revisar y acordar con Chema
los cambios antes de emitir comandos de instalación.

**Después:** C8 en navegador y Companion reales. Consolidación grande de
ramas y PR solo tras analizar diferencias funcionales de
Saturno/Júpiter/Urano, no por número de commits.
