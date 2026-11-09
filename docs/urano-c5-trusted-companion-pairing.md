# C5 — Emparejamiento de confianza Companion → Stage (beta privada)

> **Estado:** contrato técnico verificado en GitHub Actions. **Sin despliegue, sin usuarios reales y sin autorización de integración a main.** Este documento no autoriza activar la beta pública.

## Objetivo y frontera de confianza

Companion conserva el vídeo original en el equipo local. Después de generar un proxy, calcula una **huella de extremos del original** (primeros y últimos 64 KiB + tamaño + nombre) y el **SHA-256 completo de los bytes del proxy**, y puede emitir un recibo con firma HMAC-SHA256. **Limitación explícita:** la huella de extremos NO prueba criptográficamente que los bytes interiores de un original enorme no hayan cambiado sin alterar extremos ni tamaño. En una fase posterior se puede reforzar con hash integral o manifiesto de fragmentos cuando la eficiencia del procesado lo permita. El navegador transporta el recibo, pero **no dispone de la clave**.

El servidor verifica una firma asociada **al propietario exacto**, a un proyecto UUID, un slot de cámara, nombre/tamaño/huella del original y SHA-256 completo del proxy. Solo entonces escribe en el inbox privado `receipt_authenticated: true` y **`attested: false`**. No existe inscripción de claves por HTTP.

Tras Stage Ingest `done`, `attest_authenticated_inbox()` es una operación **interna del operador**: comprueba que cada vídeo del Engine está en su proyecto privado, que el inbox guarda recibos autenticados, que los bytes coinciden, y que hay una salida Stage finalizada. Solo entonces llama a `StageSourceProvenance.register_trusted()`.

No se debe conectar `original_claim` sin firma a `register_trusted`, aunque coincida su SHA-256: el navegador podría fabricarlo. Una re-subida válida o nuevo Ingest invalida las certificaciones previas.

## Aprovisionamiento fuera del navegador

1. El operador habilita **una clave aleatoria de 32 bytes por propietario / instalación de Companion** y un destino seguro para transferirla a ambos extremos. No se genera en JavaScript ni se envía por chat, correo o API HTTP. No se reutiliza una clave entre propietarios.
2. El archivo del equipo local se guarda fuera del directorio público de Montara y se referencia con `MONTARA_COMPANION_RECEIPT_KEY_FILE`. En POSIX debe ser regular, no symlink, y con permisos **0600**. En Windows usar ACL exclusiva del usuario; las políticas de ACL necesitan comprobación específica en una instalación real.
3. El operador instala una copia protegida en el servidor, también con acceso exclusivo a su usuario de servicio. Configura `CompanionReceiptVerifier({owner_id: Path(...)} )` desde configuración **de confianza**, junto con `create_owner_api(receipt_verifier=...,proxy_staging_root=...,stage_provenance=...)`. No añadir ruta de inscripción de secretos.
4. El navegador consulta al Companion en loopback el recibo `/proxies/{id}/signed-receipt?project_id=...&slot=...` y lo transmite con `X-Urano-Signed-Receipt`. El endpoint privado coteja HMAC en tiempo constante, ámbito, identidad y SHA de los bytes efectivamente subidos.
5. Un servicio interno, no una petición del navegador, prepara entradas y ejecuta Ingest en el Engine aislado. Tras `done`, puede invocar `attest_authenticated_inbox(..., container_workspace=Path('/workspace'))` usando el binding y raíz de montaje **establecidos por el operador**. Para normalización fuera de ese montaje, la operación debe permanecer bloqueada hasta que exista una ruta confinada y comprobable.

**Precaución:** el modo `receipt_verifier=None` existe únicamente por compatibilidad de pruebas/inbox no acreditado. Guarda `receipt_authenticated:false`; **nunca** certifica originales. El cliente beta nuevo exige recibos firmados y no puede continuar sin emparejamiento.

## Condiciones para C5 beta funcional

- Dos propietarios distintos: sus cookies, sesiones, claves, carpetas, recipientes de Ingest y certificados son distintos.
- Un recibo reutilizado en otro proyecto, cámara, proxy o propietario se rechaza, incluso cuando el hash del archivo sea igual.
- Alterar original o proxy después de firmarlo invalida el recibo o el hash. Reemplazar un proxy o reiniciar Ingest revoca el certificado anterior.
- Stage acepta formatos válidos y puede transcodificar el proxy; se comprueba SHA de **entrada** y la salida normalizada por separado.
- La exportación local con WAV y originales funciona en Windows/macOS, con Companion real, navegador HTTPS y origen CORS explícitamente configurado. Un MP4 sintético en CI no sustituye esta prueba.
- El runtime de contenedores y sus permisos de volumen deben validarse en entorno propio. **No instalar software ni cambiar UID/GID en la VM compartida sin aprobación expresa de usuario y Chema.**

## Evidencia y limitaciones

- [PR C5 #145](https://github.com/amehcgracia-byte/Montara/pull/145): histórico, pruebas de aislamiento y aceptación Docker real.
- Pruebas `tests/test_c5_signed_companion_receipt.py`, `tests/test_c5_companion_proxy_receipt.py` y `tests/test_c5_authenticated_ingest_attestation.py`.
- **Pendiente de integración final:** wiring del servicio que llama a la certificación tras Ingest DONE, aprovisionamiento real por propietario, pruebas en navegador/Companion reales y despliegue HTTPS. No declarar `render_ready` simplemente porque un archivo esté staged o `receipt_authenticated:true`.

`main` y los servicios de la VM permanecen sin cambios. La fusión requiere autorización explícita del usuario y aprobación final de Chema.
