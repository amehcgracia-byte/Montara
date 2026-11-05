# URANO U3B — protección experimental de vídeo original local

**Fecha:** 2026-11-05. **Estado:** PASS de pruebas unitarias simuladas; **NO** validación completa de producto ni aprobación de merge.

## Objetivo

Aplicar la dirección indicada por Fernando: **Companion es obligatorio para importar vídeos originales locales**. Si Companion falta o no puede crear el proxy, la web debe detener esa importación con un error comprensible, en lugar de enviar un original grande a la nube.

## Cambios implementados en laboratorio

Rama **`fernando/companion-windows-w1`**, PR [#74](https://github.com/amehcgracia-byte/Montara/pull/74) draft:

- `web/montara.js`, commit `fd1b621`: en `upload(file,entry)`, un vídeo local sin proxy recibido de Companion no entra en las rutas de upload normal. Sin Companion, se muestra «Open Montara Companion to import a video from your computer.»
- `uploadSmall`: tanto `{missing:true}` como `null`, error del proceso o fallo de FFmpeg **bloquean** el envío de vídeo original, con mensajes de reintento. La protección no depende ya del umbral heredado de 200 MiB.
- En ruta válida, cuando `smallVersion()` devuelve un proxy, se asigna `entry.small` antes de invocar el upload existente de derivados. Los flujos **audio** sin modificar siguen usando el código previo, hasta evaluar su política.
- Test existente `tests/urano_u3a_upload_baseline.cjs` actualizado para verificar la política U3B (la línea base U3A permanece descrita en [informe anterior](URANO_U3A_ORIGINAL_UPLOAD_BASELINE_2026-11-05.md)). El workflow cambia nombre visible a «URANO U3B Companion-only video upload guard (FER)». Caso nuevo de vídeo 2 MiB y regresión de Stage audio WAV 10 MiB.

## Evidencia

- **PASS**, [GitHub Actions 41941489547](https://github.com/amehcgracia-byte/Montara/actions/runs/41941489547), commit `66ed9d5e5a8c4a64804f67005dd8a7f7eeadf613`: **9 escenarios en Node VM con las funciones JS reales** y red simulada.
- Los 8 escenarios de vídeo cubren Companion ausente, original pequeño y grande, `missing`, fallo de proxy, FFmpeg que lanza excepción y entrega correcta de un proxy. Resultado: **cero originales de vídeo enviados**; el proxy de 2 MiB sí pasa al uploader.
- El noveno escenario confirma que un WAV Stage de 10 MiB continúa en la ruta de carga reanudable; no significa que esa conducta esté validada como política comercial.
- Hubo una primera ejecución con fallo en el simulador de audio: la ficha de WAV tenía erróneamente MIME vídeo. Se corrigió el mock, **no el código funcional**, en commit `66ed9d5`; CI repetido quedó verde.

## Límites y condiciones para U3C

1. **Protección de frontend solamente:** el backend aún acepta uploads directos; un cliente manipulado o una ruta alternativa puede saltarse la regla. No afirmar «prohibido subir cualquier vídeo original» a nivel de servicio.
2. **Importaciones de Show** (`web/show-media.js`) siguen usando FormData para medios, voz e imágenes. Su política se debe tratar aparte y no romperlas con bloqueos globales.
3. **Push URL y Stage audio** siguen los flujos anteriores; no equiparar transferencia de derivados con subida de originales.
4. **No hay browser E2E completo** para el nuevo comportamiento ni pruebas reales de grandes archivos/HDR/GPU. La aprobación por JM y comprobaciones de regresión generales siguen pendientes.
5. **Uso de `entry.small` como señal interna:** no constituye prueba criptográfica de que el contenido es un proxy. Antes de imponer la política en backend, se necesita un diseño de origen/proveniencia verificable, sin confiar solo en nombre, tamaño o campos enviados por cliente.
6. La licencia de distribución FFmpeg permanece pospuesta, pero publicación comercial **NO GO** hasta resolverla.

## Siguiente

**U3C:** revisión de puntos de entrada del backend y rutas Show/Push para diseñar un contrato de tipos de medios y procedencia; probarlo con red y navegador simulados antes de modificar la validación del servidor. Conservar rama en draft y proteger Engine/Mixer/producción.
