# Montara 0.67 — panoramas ligeros y mezcla antes del rango

Base: main `4f1dceb` (incluye PR #79–83 de Fernando). Engine `bfb964c3`,
Mixer `f15ff91`: sin cambios de submódulos ni copia de ramas experimentales.

## Correcciones

- Companion 0.6.6 ya no omite las panorámicas monoscópicas cosidas 2:1.
  Crea hasta 2048×1024, mantiene toda la esfera, audio y duración, y restaura
  metadatos esféricos reales V1/V2 usando el injector Apache-2.0 ya empleado
  por el Editor. Verifica con ffprobe antes de publicar el proxy. Sin otra
  codificación al inyectar metadatos. El render local conserva el original.
- Los formatos esféricos no compatibles (estéreo, proyección distinta o
  panorámica rotada) fallan explícitamente: no se reinterpretan como mono.
- La protección de consentimiento de Fernando permanece. Un error de proxy
  no autoriza una subida original. Installer incorpora también windows_support.
- Stage con pistas separadas: mezcla y masteriza antes de mostrar el rango;
  allí aparece un solo máster, no una lista de instrumentos como canciones.
- Jam larga con varias pistas y vídeos: usa las copias ligeras para detectar
  canciones y la suma de escucha existente como guía. Reutiliza la sincronía
  del motor por HTTP para identificar la canción de las cámaras. Mezcla solo
  esa canción mediante el flujo existente (Companion o rangos en servidor).
  Después abre las cámaras y el rango con el máster terminado.
- Vídeos de canciones distintas, sincronía dudosa o límites ambiguos requieren
  revisión; no se adivina ni se mezcla toda la jam por defecto. Una cámara sin
  sonido no permite identificación automática por esta vía.

## Validación

Pruebas nuevas: proxy 4K real con audio, identidad del original, metadatos,
encuadres distintos con v360; rechazo de metadatos inválidos; selección de
canción con sincronía dudosa/ambigua y límites de acceso al máster terminado.
`tests/e2e_session_video.py` añade recorrido real navegador → Companion →
proxy panorámico → detección → sincronía → máster de una canción → rango.
La aceptación completa y la instalación se registran al terminar CI.

No actualizar/reiniciar servidor o Companion durante renders del usuario.
