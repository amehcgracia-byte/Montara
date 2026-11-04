# Material compartido del laboratorio y futuros proyectos colaborativos

## Disponible en el laboratorio

Directorio común `/srv/montara-lab/media`, grupo `montara-media`, permisos 2770. JM y FER tienen lectura/escritura en sesiones nuevas; comprobado con los dos usuarios. No se han movido sus originales. Las sesiones SSH/servicios ya abiertos pueden conservar sus grupos anteriores hasta reconectarse o el siguiente arranque de la VM; no reiniciar el laboratorio de FER por este motivo.

Una fuente canónica por archivo, en subcarpetas con nombre descriptivo; conservar procedencia y un manifiesto pequeño con hash SHA256, tamaño, duración y resolución. No publicar vídeos grandes en Git. El propietario del archivo decide cuándo retirarlo. La retención de Montara no recorre este directorio. Es infraestructura de pruebas: todavía no hay un navegador de esta carpeta en la interfaz ni una biblioteca pública compartida.

## Diseño futuro, sin cuentas públicas implementadas aquí

Un proyecto/canción tiene propietario, miembros y presupuesto de almacenamiento. Un enlace de invitación autoriza subir material únicamente a ese proyecto: token revocable, limitado y con vencimiento; no concede acceso al ordenador ni a otros proyectos. Los archivos pertenecen al proyecto y se contabilizan una vez, aunque participen varias personas. Los límites de GB, minutos de render y retención se configurarán con costes medidos; no confundirlos con tokens de un LLM.

Cada móvil selecciona su propio vídeo y lo envía con subida reanudable. Proxies para editar; los originales o los rangos necesarios deben estar accesibles al renderizador. Para material de varios móviles, la vía práctica es almacenamiento común y render en servidor. Un Companion de escritorio también puede hacerlo si descarga o ya tiene todas las fuentes requeridas. No puede renderizar vídeos que solo están en otros teléfonos sin transferir esos datos.

Un render pequeño dentro de un navegador móvil puede estudiarse después; no sustituye hoy al Companion de escritorio para sesiones largas, multicámara y 4K, ni garantiza continuar en segundo plano al bloquear el teléfono. Esta entrega no compra almacenamiento, no crea cuentas comerciales ni cambia los precios.
