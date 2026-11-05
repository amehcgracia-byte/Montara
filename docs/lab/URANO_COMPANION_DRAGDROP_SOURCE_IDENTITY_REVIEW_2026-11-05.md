# URANO — recorrido drag & drop y Companion Mac/Windows

**Fecha:** 2026-11-05. **Base:** Montara main 0db9f753a3c57c534f7578f12efac0ea310158c7 (PR #79 + #80). **Método:** revisión estática, no E2E completo Windows. El diseño futuro comercial sigue siendo Companion-first; la subida del original queda temporalmente solo para pruebas con consentimiento.

## Lo que ya existe

1. **Drop:** web/montara.js recibe DataTransfer.files y llama a addFiles/upload. No recibe una ruta nativa absoluta del navegador.
2. **Permisos de navegador:** web/footage-memory.js captura FileSystemFileHandle en Chrome/Edge cuando está disponible, lo guarda en IndexedDB durante hasta 14 días y lo reabre tras comprobar permiso, tamaño y fecha. Ese handle no es una ruta física entregable al Companion y no equivale a persistencia total de edición.
3. **Identificación:** web/companion.js::smallVersion obtiene SHA-256 de los primeros y últimos 64 KiB del File y llama a POST http://127.0.0.1:47820/locate con nombre, tamaño y fingerprint. No transfiere el original completo.
4. **Búsqueda:** companion.py::locate compara nombre, tamaño y fingerprint con archivos candidatos. Prioriza carpetas de fuentes anteriores y places.json; macOS utiliza además mdfind/Spotlight y raíces comunes; Windows, tras #79, usa carpetas del perfil, OneDrive, discos secundarios/removibles y raíces configuradas, con limitación del recorrido y exclusión de junctions.
5. **Proxies:** POST /proxies convierte en el ordenador con FFmpeg; navegador descarga /proxies/{id}/file y después sube el **proxy** al backend. Original permanece local en el recorrido normal, pero el proxy sí se sube.
6. **Render nativo Stage:** web/montara.js solicita /edit/native-recipe; companion/video_jobs.py resuelve el original local mediante find_original, valida de nuevo nombre/tamaño/fingerprint y usa la ruta local en el trabajo de exportación.
7. **Carpeta de proyecto:** POST /projects abre selector nativo (AppleScript Mac, Tk Windows) para DESTINO de proyecto/resultados. No sirve para descubrir el archivo original desde drag/drop.

## Fallback actual tras #80

Si Companion no está presente o no puede preparar el vídeo, web/montara.js exige window.confirm para subir un original por el flujo heredado, incluyendo tamaño y aviso de red/almacenamiento; al cancelar se bloquea. Conservamos esta vía **solo para ensayos**, no como alternativa comercial final. Esta salvaguarda es de UI, no autorización de backend. web/companion.js conserva un comentario introductorio antiguo que decía que se sube el original sin Companion: comentario ya desactualizado después de #80.

## Consecuencias y huecos reales

- La prueba física de Fernando en Windows para #79 cubrió selector de carpeta y cancelación; **no** demuestra drop→locate→proxy→backend en Windows con original real. La ruta Mac tiene ayuda de Spotlight; no hay equivalente idéntico en Windows.
- La identidad nombre+tamaño+hash de bordes es un cotejo parcial, no hash criptográfico de todo el vídeo; conservar el alcance declarado.
- La búsqueda puede no encontrar originales fuera de raíces indexadas/recordadas; explorar todo C: por defecto no es una buena solución.
- En web/montara.js aún aparece el texto «Choose on your Mac...» aunque exista Companion Windows: ajuste UX pendiente.
- URANO debe reutilizar proxies, montara-project.json, projects.json y la receta del motor; falta continuidad coherente en mismo ordenador tras reinicio/reubicación, no inventar un sistema paralelo.
- No ampliar API de lectura local sin pairing/permisos: el filtro Origin del Companion no equivale a autenticación de cuenta.

## Recomendación

**Preservar la solución de Chema.** El siguiente gate útil es ensayo de drop→locate→proxy en Windows con clip sintético inocuo y sin upload de original; después atender persistencia/recuperación de proyecto y permisos. Ningún merge ni cambio de código se ha realizado en esta revisión.