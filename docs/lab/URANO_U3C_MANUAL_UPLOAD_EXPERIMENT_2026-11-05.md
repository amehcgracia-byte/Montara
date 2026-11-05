# URANO U3C — conservar subida manual de originales para pruebas

**Fecha:** 2026-11-05 · **Decisión expresa del usuario:** mantener por ahora la capacidad de subir un original sin Companion, porque podría ser útil para experimentos. No se pretende que sea la ruta comercial normal.

## Política experimental adoptada

- **Camino normal:** Companion prepara el proxy y se sube el derivado.
- **Companion ausente o error de proxy:** no se envía automáticamente el original.
- **Capacidad de laboratorio conservada:** antes de subir el vídeo original, el navegador muestra una confirmación **por intento**, con el tamaño en MiB y aviso sobre tráfico y espacio servidor. Cancelar detiene la subida; aceptar la permite **solo para ese intento**.
- **Audio Stage y medios auxiliares Show:** no se han modificado en esta intervención. La carga resumible de derivados continúa operativa.

## Código y validación

- Rama experimental: `fernando/companion-windows-w1`, PR #74 en draft.
- `web/montara.js`, commit `dcc6096`: `confirmOriginalVideoUpload(file,entry,reason)`; la opción manual se recuerda solo en `entry.manualOriginalUpload` durante el intento, evitando confirmación recursiva. No depende de tamaño.
- `tests/urano_u3a_upload_baseline.cjs`, commits `c791413` y `78518ef`: prueban **12 escenarios simulados**, incluyendo rechazo implícito por defecto, consentimiento explícito de originales de 2 y 300 MiB, error FFmpeg consentido, proxy correcto y audio Stage. Se captura cada petición mediante mocks; no hay red ni vídeos reales.
- CI [41941997924](https://github.com/amehcgracia-byte/Montara/actions/runs/41941997924): job de pruebas U3C **completed/success**. `Companion Windows packaged smoke` y `Montara end-to-end (Linux)` asociados al último commit todavía tenían estado pendiente/en progreso al registrar este informe.
- Primera ejecución [41941900406](https://github.com/amehcgracia-byte/Montara/actions/runs/41941900406) falló **por una aserción regex del test mal escapada**; corregida, no indicaba un error de producto.

## Límites relevantes

1. **Interfaz solamente:** el backend sigue aceptando originales por rutas existentes, sin una puerta equivalente de consentimiento, autenticación de múltiples usuarios ni cuotas por cuenta. Un usuario puede enviar datos por API directa.
2. **`window.confirm` es provisional:** mensaje funcional para laboratorio, no diseño UX comercial; no incluye medición real de tráfico ni confirmación persistente.
3. **No es garantía global de control de medios:** `Show` contiene FormData directo para biblioteca/voz y `Stage` envía fragmentos/mezclas a servidor. La política definitiva requiere inventario de endpoints y clases de medios, no un bloqueo a todo upload.
4. **Los 12 tests son mocks con las funciones JavaScript reales**, no pruebas E2E de navegador abierto, vídeos pesados, usuarios simultáneos ni límites económicos.
5. **Licencias FFmpeg y publicación:** siguen pendientes. No distribuir ejecutable de prueba con FFmpeg ni fusionar PR #74 hasta revisión correspondiente.

## Próximo salto hacia URANO U4

Priorizar el diseño del **contrato frontend–Companion–servidor**, identidad de proyecto/trabajo/usuario y clasificación de medios; cuantificar qué metadatos de origen deben persistir y cómo mantener el consentimiento explícito de cargas manuales cuando haya autenticación y cuotas. Inspeccionar rutas actuales antes de realizar cambios en servidores, base de datos o motor.

**Resultado U3C:** capacidad manual de pruebas conservada y cubierta por CI, sin convertirla en fallback automático comercial.
