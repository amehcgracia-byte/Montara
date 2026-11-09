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

## Opciones antes de la primera prueba real

| Opción | Ventaja | Condición / inconveniente |
|---|---|---|
| A. Entorno beta aislado fuera de la VM compartida | Máxima separación de Chema; imagen Docker verificada sin tocar 8101–8103 | Infraestructura, coste y permisos propios por autorizar |
| B. Instalación paralela dentro de la VM actual | Aprovecha RAM y disco disponibles y acceso Gateway | Docker falta. Instalarlo, cambiar servicios o configurar un nuevo proxy son cambios **compartidos** y requieren autorización expresa del usuario y Chema; sin ello C7 está bloqueado |
| C. Adaptación explícita a LXD | El binario ya está presente | Exige nuevo modelo de seguridad y repetir aceptación de dos propietarios en LXD. No es equivalente a Docker ni es atajo validado |

**Recomendación:** preparar el despliegue A como objetivo preferido de
primera beta funcional, manteniendo B como alternativa sujeta a aprobación
y C únicamente si se decide invertir en validación específica. No se
ha creado ninguna instancia ni contratado recursos.

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
