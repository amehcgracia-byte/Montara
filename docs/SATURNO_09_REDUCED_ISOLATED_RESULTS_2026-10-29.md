# SATURNO-09 — Paquete reducido aislado: resultado real

Run [40881393749](https://github.com/amehcgracia-byte/Montara/actions/runs/40881393749),
job 123473535571, commit `55171c00ceafdeb9815c58d1e7b0b6300d501fd9`.

## Gate plano de 2 s: APROBADO bajo controles QA
- Ventana de vídeo previa A (4–6 s) y B (1–3 s): píxeles exactos.
- Ventana previa de audio: PCM float32 exacto.
- A/A con procesos y caches independientes: 60/60, audio exacto y timeline exacto.
- A/B reducido: **60/60**, audio PCM completo exacto, PTS/DTS/duraciones iguales.
- También coincidieron los SHA256 de archivos finales completos (criterio observado,
  no añadido a posteriori como requisito).
- B se ejecutó en namespace de montajes aislado: tmpfs vacío sobre tests/fixtures
  (incluye TODAS las cámaras y el máster originales), exports A y caches A.
  Las rutas originales no existían dentro de B. El host no fue modificado.
- Cada proceso con ZUCKER_DATA_ROOT distinto y cache inicialmente vacía.
- Control de codificación `libx264 -threads:v 1` solo en memoria QA; fundidos activos.
- No se ha modificado Zucker, mixer, main ni código de producto Montara.

## Bytes y tiempos reales
| Medición | Resultado |
|---|---:|
| Vídeo original + audio original | 3,018,077 bytes |
| Vídeo fragmento + audio fragmento | 1,371,820 bytes |
| Fracción de medios trasladados | 45.4534 % |
| Reducción de medios | **54.5466 %** |
| Fracción de vídeo solamente | 40.7886 % |
| Preparación de ambos fragmentos | 0.3264 s |

Son MEDIOS únicamente: falta manifest, empaquetado de transporte y overhead de red.
El método recodifica vídeo sin pérdida (qp=0); no es recorte GOP mínimo.
El audio es WAV float32 de 2.25 s; no usa el máster MP3 completo.
Caso pequeño y plano, no extrapolar ahorro ni velocidad a proyectos grandes.
Tiempos de exports exactos, comandos, hashes y timeline en el JSON de evidencia.
No hay medidas de red ni nube ni gasto RunPod.

## Stage: causa del bloqueo observada
El flujo original falló en 4 s con:
`OBSERVED_UI_FAILURE: $(...).forEach is not a function`.
Las llamadas /wizard/projects/new y /wizard/draft devolvieron 200.
Por tanto no era una espera de render ni un fallo de creación de draft:
la UI había entrado en failed antes de cámaras.

El control que corrigió solo `$('#cameraList .cam').forEach` siguió fallando
con el mismo mensaje. La revisión de TODA la función localizó otro selector
singular usado como lista: `$('[data-camera-type]').forEach` (línea 492).
Hay dos, no uno. En la base `$ = document.querySelector` y
`$$ = [...document.querySelectorAll]`; ambos usos son incompatibles con forEach.

**Stage sigue BLOQUEADO.** Que el job de diagnóstico termine en verde solo
indica colección correcta; `stage.gate_full_stage=false` lo deja explícito.

## Continuación predefinida, sin repetir ensayos concluidos
El siguiente run recogerá SOLO Stage, sustituyendo ambos selectores en la
respuesta JavaScript del navegador QA, sin tocar la fuente del producto.
Reutilizará como evidencia el fallo original de este run en lugar de repetirlo.
Se registran hashes del JS original/corregido/servido y stack de fallos capturados.
Guardar plan REAL y referencia si completa el journey. No modificar motores.

## Evidencia versionada
`experiments/saturno_09/results_40881393749.json` contiene resultados completos
de ambos ensayos, comandos efectivos y de motor, hashes de fotogramas,
PCM, timelines y evidencias del namespace y de la UI.
La continuación no depende de artefactos de GitHub sujetos a cuota.

## Estado global
Primer bloque (paquete reducido plano con audio propio) superado bajo QA.
A Stage completo pendiente; B/C multicámara/360 pendientes; D remoto pendiente.
No hay aprobación de arquitectura ni parche de producción autorizado.
