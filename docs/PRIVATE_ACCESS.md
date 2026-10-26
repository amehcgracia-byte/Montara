# Acceso interno: propietario, desarrolladores y testers

## Estado real

Motor de permisos e invitaciones implementado y probado en `private_access.py`. No se publica como un plan ni se añade al simulador de precios. **Todavía no está activado en la demo pública**: ésta no tiene cuentas verificadas ni cobros/cuotas reales. No se han creado usuarios, enviado invitaciones ni contratado servicios.

La demo de Vercel crea una instancia independiente por visitante. Sus cookies son accesos a una prueba, no identidades de usuario. No usar esas cookies ni un selector de plan del navegador como prueba de una suscripción. Una SQLite por instancia no puede servir como registro común de cuentas. Para la beta real, usar un servicio de cuentas y permisos central, con almacenamiento persistente compartido. Esta implementación SQLite sirve para ese servicio único; con varios servidores escritores, migrar las mismas operaciones atómicas a Postgres.

## Comportamiento

- Plan `internal`, 0 €, todas las funciones permitidas por el plan superior que existan en ese servidor; sin cuota comercial. No equivale a GPU disponible, IA conectada ni recursos infinitos.
- Roles owner/developer/tester de uso del producto; ninguno concede administración del sistema, acceso a otros proyectos, claves de proveedores o datos de otros usuarios.
- Invitación individual de un solo uso, aleatoria de 256 bits, almacenada solo como hash. Válida 7 días por defecto; al aceptarla se vincula a la identidad verificada del proveedor y concede 30 días de acceso. Duraciones administrables.
- Solo el administrador del servidor emite, revisa o revoca mediante la herramienta local. No hay endpoint público para autoasignar planes.
- Revocar una invitación revoca también el permiso que concedió. Caducidad y revocación se comprueban desde el servidor en cada consulta; no se guardan permisos permanentes en el navegador.
- Los registros de consumo no se desactivan por ser una cuenta gratuita. Los eventos duplicados no suman otra vez; los importes contradictorios se rechazan. No se registran tokens de invitación ni material de los proyectos.

## Activación cuando haya cuentas

1. Elegir y conectar un proveedor de identidad con sesiones verificadas, CSRF, aislamiento de proyectos y límite de intentos. No implementar una contraseña compartida ni aceptar `account_id` aportado por el cliente.
2. Registrar `register_private_access(app, store, verified_account)` únicamente en el servicio central: `verified_account()` debe devolver el identificador estable del proveedor obtenido al verificar su sesión.
3. La página de invitación lleva el token en el fragmento del enlace (`/invitacion#…`, sin token en la consulta ni analítica). La página guarda temporalmente el token durante el inicio de sesión, lo borra del historial y hace POST al aceptar. No se ha publicado esa página hasta conectar la identidad real; un enlace actual de demo no es una cuenta.
4. GET `/montara/account/access` responde solo por la cuenta verificada. POST `/montara/account/invitation` exige sesión y mismo origen, consume atómicamente el token y vincula el permiso a esa cuenta.
5. Antes de cada trabajo, el servicio de trabajos consulta el permiso central. Ignora saldo comercial para `internal`, pero aplica presupuesto técnico, límite de concurrencia y capacidad real del servidor. La cola nunca crea GPUs ni instancias de pago por el simple hecho de tener este permiso.
6. Conectar eventos reales del trabajador a `record_usage`: CPU/GPU, tokens facturables, almacenamiento/transferencia y coste. El registro está implementado; **el motor de render y los proveedores aún no envían eventos a este registro**. No presentar sus datos como gasto medido hasta hacer esa conexión.
7. Fijar un presupuesto global y por tester, horas de prueba y concurrencia antes de la carga intensiva. Al alcanzar el límite técnico, conservar proyectos y poner trabajos en espera; el tester no recibe un cobro. El propietario ve el aviso y decide si amplía el ensayo.

## Administración local del servicio central

Desde la carpeta de la aplicación, usando su Python:

```
python private_access.py --database /ruta/privada/access.sqlite invite --label "Tester 01" --role tester --days 30
python private_access.py --database /ruta/privada/access.sqlite report
python private_access.py --database /ruta/privada/access.sqlite revoke ID_DE_INVITACION
```

La primera orden muestra el token una sola vez. Es una credencial: compartir solo con el destinatario por un canal privado, sin guardarlo en el repositorio, logs o anuncios. La salida de report no contiene tokens.

## Prueba de carga pendiente del servidor

No confundir funciones desbloqueadas con una prioridad física o velocidad garantizada. Medir una tarea base y luego 2, 5 y 10 usuarios concurrentes con los mismos archivos. Separar cola, carga, análisis, transcripción, mezcla, render y descarga; registrar p50/p95, fallos, RAM máxima y coste por trabajo. Empezar con concurrencia baja y un límite de gasto explícito; no ejecutar carga intensiva contra el Vercel de demostración.

Validación actual: invitaciones de un solo uso, carrera concurrente, expiración de invitación/acceso, revocación, identidad no falsificable desde el cuerpo, mismo origen, no caché, registro idempotente de consumo. Los tests usan cuentas y almacenamiento desechables, sin proveedores ni recursos pagados.
