# C8 · Beta personal del editor completo — instalación privada de un usuario

**Estado:** launcher probado en CI, **no desplegado**. Este procedimiento usa el
editor completo y Companion; no es la plataforma multiusuario C1–C7. El
backend existente mantiene **un único proyecto activo por proceso**.

## Requisitos y límites

- Linux x86_64 con Python 3.11, FFmpeg/ffprobe, paquetes de
  `deploy/requirements-linux.lock` y submódulos `engine` / `mixer`
  fijados. Este documento no instala ni actualiza software.
- Un usuario Linux **no root**, checkout y carpeta privada para la beta,
  un solo proceso Gunicorn y puerto local **8114**. No usar los puertos de
  Chema/JM/servicios existentes: 8090, 8101, 8102, 8103.
- El editor está protegido por usuario/contraseña **Basic Auth**, con datos
  y credenciales aislados bajo el HOME del usuario. El puerto escucha
  exclusivamente `127.0.0.1` y **no debe abrirse al público**.
- HTTPS Google, cuentas independientes y certificaciones HMAC de C1–C7
  **no están integradas en esta versión**. No invitar amigos ni publicar una
  URL pública de esta instalación.
- Para comprobar Companion en un navegador hay que verificar los orígenes
  de loopback; la recepción de originales al servidor es un fallback del
  editor existente y no representa la arquitectura definitiva.

## Preparación sobre una cuenta aislada y un checkout aprobado

Solo después de escoger el host de prueba y obtener la autorización
correspondiente, clonar/subir un checkout de la rama
`fernando/c8-personal-private-beta-20261109`, con los submódulos fijados
y dependencias disponibles. **No reutilizar `~/montara` de Chema/JM ni
cambiar procesos 8101–8103.**

Desde el checkout (en un usuario distinto, con Python 3.11 y entorno ya
preparado):

```bash
python3.11 -m deploy.personal_beta --init
python3.11 -m deploy.personal_beta --check
python3.11 -m deploy.personal_beta --serve
```

`--init` solicita la contraseña sin mostrarla por pantalla y la guarda
con permisos 0600. La carpeta de datos utiliza 0700. El proceso se
detiene con Ctrl-C y no instala ningún servicio persistente.

Desde el ordenador del propietario, mediante túnel SSH autentificado:

```bash
ssh -N -L 8114:127.0.0.1:8114 USUARIO@HOST_APROBADO
```

Abrir **http://127.0.0.1:8114** y autenticarse como `montara` con la
contraseña de `--init`. El túnel no da una URL pública y no sirve para
una beta abierta con amigos. No insertar contraseñas en comandos, URLs,
issues o registros de CI.

## Aceptación personal

1. Abrir la interfaz real de Montara, verificar versión y proyecto.
2. Probar Stage con clips sintéticos y luego material propio, viendo
   tiempos y diferencias entre los archivos originales y proxies.
3. Comprobar Companion en Windows, selección de carpeta, permisos de
   navegador y localización de los originales.
4. Editar cortes, audio y exportar MP4; **reproducirlo y escucharlo**
   para verificar imagen, sincronía y sonido, no solo la respuesta HTTP.
5. Reiniciar únicamente cuando no haya trabajo activo; reabrir proyecto,
   revisar persistencia, logs y espacio consumido.
6. Registrar incidencias (paso, navegador, versión, resultado esperado /
   real) en la PR C8 sin subir vídeos o información privada.
7. Si el recorrido es convincente, presentar a Chema resultados y dudas.
   **No convertir esta instalación single-user en multiusuario por compartir
   la contraseña**: los amigos precisan espacios realmente independientes.

## Retirada y limpieza

Al finalizar la sesión: apagar el proceso con Ctrl-C, cerrar túnel SSH,
comprobar que 8114 dejó de escuchar, inventariar tamaño de carpeta de datos
y ficheros temporales. Borrar únicamente las pruebas **identificadas** como
desechables, conservando proyecto/manifest si se necesita diagnóstico.
Nunca ejecutar limpieza genérica de Docker, eliminación recursiva de
carpetas ajenas o borrado indiscriminado de ramas.

## Estado conocido (9 de noviembre de 2026)

- Gateway confirmó el arranque de la VM y que 8101–8103 escuchan.
- Hay un issue independiente [#155](https://github.com/amehcgracia-byte/Montara/issues/155)
  sobre el apagado automático al utilizar SSH no interactivo.
- El nuevo `deploy.personal_beta` tiene una batería CI de contratos
  privados; **no se ha instalado ni arrancado en la VM**.
- Preparar servicio/SSH tunnel en un puerto 8114 requiere acordar el
  emplazamiento; las instalaciones se harán en la cuenta propia y con
  aprobación de las partes responsables del servidor.
