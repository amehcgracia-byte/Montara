# URANO U13E2C — Integrar adaptador real con Stage #107

**Fecha:** 2026-11-07. **Estado:** adaptación de test y preflight ligera; NO hay aceptación E2E con vídeos reales ni se ha desplegado nada.

Base: main `5becd9e` (#107), con selección automática de fuentes Stage por evidencia de audio. En esta rama se incorpora de #104 el soporte `--real-camera` (dos veces) y `--real-master`, y validación de paths/sha256 por streaming sin copiar los originales. Se conserva el selector `[data-intent=video]` de main. Las pruebas de contrato no contienen vídeos reales.

**Riesgo de aceptación:** los clips originales tienen distintas duraciones (iPhone 986.8 s, Sony 89.76 s, 360 911.64 s; máster MP3 634.04 s). La coincidencia acústica NO se infiere de duraciones ni de que los archivos estén presentes. El nuevo Stage puede excluir cámaras sin prueba de sincronía y fallar si ninguna corresponde al máster, que sería el comportamiento correcto del producto. Antes de un render largo: probar de forma aislada la correspondencia de audio, o seleccionar un máster procedente de esa misma grabación con origen acreditado. No modificar el flujo de Chema para forzar cámaras ni marcar como filler una cámara sin criterio.

**Limitaciones:** la ejecución de este test nativo usa `app.py` y un Companion aislado en loopback; no prueba todavía la integración U13 en runtime multiusuario. El flujo realiza exportación y decodificación completas solo al ejecutarse con fuentes reales, no por pasar los unitarios.

**Operación segura:** la VM GCP estuvo al 100% de disco; Chema liberó espacio y el 07-11 se midieron ~72 GB disponibles. Los originales permanecen en `/home/fer/lab-clips/originales`. No usar `/home/jm`, no modificar el checkout FER con cambios locales, no subir media a Actions; scratch exclusivo por ensayo, límite de disco y limpiar SOLO scratch propio tras examinar resultados. No usar root como identidad habitual de ejecución del Companion. Se requiere verificar permisos y navegador H.264 antes de E2E. No publicar ninguna URL ni alterar servicios activos.

**Pendiente:** ejecutar unitarios+syntax CI, ensayo preflight de audio; compatibilidad navegador #107 (cámara emparejada/no emparejada/filler); una E2E real con salida decodificable, integridad de originales, recuperación; 360 por separado. 

## Evidencia adicional — análisis de audio estrictamente en memoria (07-11)

Se verificó con Gateway en VM FER, **solo lectura**, mediante FFmpeg → PCM mono 800 Hz y correlación cruzada normalizada (filtro banda 80–330 Hz) de muestras de 16 s en cuatro posiciones de cada cámara contra el máster MP3 completo. Sin archivos escritos, sin renders, sin modificar originals ni los servicios. Mejor correlación absoluta encontrada: iPhone **0.359** (signo negativo, cámara t=493 s / máster t=295.44 s), Sony **0.389** (negativo, t=67 s / máster t=573.15 s), 360 **0.4206** (positivo, t=455 s / máster t=238.4 s). Este método exploratorio submuestreado **NO reproduce el algoritmo de sincronía del Engine** y los coeficientes NO prueban correspondencia definitiva ni calidad de sincronización; tampoco deben convertirse en un gate artificial de inclusión. La aceptación exige evidencia y resultados del Engine Stage #107. Hardware FER dispone de NumPy/SciPy y Playwright existentes; las cuatro fuentes son legibles por el usuario FER. Espacio libre comprobado ~72 GB.

CI de contratos [run 42418119407](https://github.com/amehcgracia-byte/Montara/actions/runs/42418119407): **SUCCESS**. E2E general Linux [run 42418119411](https://github.com/amehcgracia-byte/Montara/actions/runs/42418119411): pendiente al redactar este apunte. Ninguno de los dos implica que se haya ejecutado una exportación con fuentes reales.
