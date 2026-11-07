# URANO U13E2C — Integrar adaptador real con Stage #107

**Fecha:** 2026-11-07. **Estado:** adaptación de test y preflight ligera; NO hay aceptación E2E con vídeos reales ni se ha desplegado nada.

Base: main `5becd9e` (#107), con selección automática de fuentes Stage por evidencia de audio. En esta rama se incorpora de #104 el soporte `--real-camera` (dos veces) y `--real-master`, y validación de paths/sha256 por streaming sin copiar los originales. Se conserva el selector `[data-intent=video]` de main. Las pruebas de contrato no contienen vídeos reales.

**Riesgo de aceptación:** los clips originales tienen distintas duraciones (iPhone 986.8 s, Sony 89.76 s, 360 911.64 s; máster MP3 634.04 s). La coincidencia acústica NO se infiere de duraciones ni de que los archivos estén presentes. El nuevo Stage puede excluir cámaras sin prueba de sincronía y fallar si ninguna corresponde al máster, que sería el comportamiento correcto del producto. Antes de un render largo: probar de forma aislada la correspondencia de audio, o seleccionar un máster procedente de esa misma grabación con origen acreditado. No modificar el flujo de Chema para forzar cámaras ni marcar como filler una cámara sin criterio.

**Limitaciones:** la ejecución de este test nativo usa `app.py` y un Companion aislado en loopback; no prueba todavía la integración U13 en runtime multiusuario. El flujo realiza exportación y decodificación completas solo al ejecutarse con fuentes reales, no por pasar los unitarios.

**Operación segura:** la VM GCP estuvo al 100% de disco; Chema liberó espacio y el 07-11 se midieron ~72 GB disponibles. Los originales permanecen en `/home/fer/lab-clips/originales`. No usar `/home/jm`, no modificar el checkout FER con cambios locales, no subir media a Actions; scratch exclusivo por ensayo, límite de disco y limpiar SOLO scratch propio tras examinar resultados. No usar root como identidad habitual de ejecución del Companion. Se requiere verificar permisos y navegador H.264 antes de E2E. No publicar ninguna URL ni alterar servicios activos.

**Pendiente:** ejecutar unitarios+syntax CI, ensayo preflight de audio; compatibilidad navegador #107 (cámara emparejada/no emparejada/filler); una E2E real con salida decodificable, integridad de originales, recuperación; 360 por separado. 
