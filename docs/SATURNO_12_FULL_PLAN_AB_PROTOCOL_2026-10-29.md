# SATURNO-12 — A/A y A/B del plan Stage REAL completo

## Evidencia previa, no repetir decisiones
SAT-09: plano reducido 60/60, audio/tiempos exactos y B aislado.
SAT-10: Stage real completo, 19 planos/7 movimientos 360, plan y proyecto guardados.
SAT-11: GOP/paquetes/ventanas de los 19 planos y color exactos. Necesita TODOS
los GOP de vídeo en este fixture; ahorro de bytes proviene de descartar audio de cámaras.
Esta limitación NO se elimina ni se presenta como éxito de omisión de imágenes.

## Pregunta de este ensayo
¿Puede Zucker exportar el MISMO plan real completo desde el paquete preparado,
sin acceso a las rutas originales ni resultados/caches A, conservando píxeles,
audio y timeline, también con movimiento 360? Es un control de export/portabilidad
completo, no validación universal de recorte mínimo ni de vídeo 4K.

## Intervenciones QA predefinidas
- Procesos nuevos y runtimes/caches inicialmente vacíos para A, repetición A y B.
- Configuración de branding original restaurada; assets estándar del software
  instalados en ambos lados, con sus hashes declarados. No son grabaciones originales.
- force_rerender_segments=True en el proyecto QA; verify_motion sigue habilitado.
- threads:v=1 en libx264 mediante wrappers de export._run_ffmpeg_progress Y
  export.run_reprojected_command; ambas rutas quedan registradas por separado.
- No modificar ningún fichero de engine/mixer ni la lógica de planos/movimiento.
- B en namespace de montajes: ocultar tests/fixtures y carpetas completas A/A-repeat,
  incluidos exports y runtimes. Comprobar ausencia de las cuatro rutas originales.
- Namespace es aislamiento de rutas de ensayo, no sandbox contra un atacante root.

## Gate cerrado antes de observar resultados
1. Verificar hashes de las fuentes/receta SAT-11; regenerar paquete sin repetir
   los análisis ni decisiones ya aprobados.
2. Render A y repetición A completos (19 planos, misma configuración y plan).
3. Exigir mismos 3007 frames esperados, hashes SHA256 de cada frame, PCM íntegro
   no vacío y timeline completo de paquetes/streams exacto.
4. Si falla A/A, parar y NO gastar render B ni culpar al paquete.
5. Si A/A pasa, ejecutar B aislado y exigir los mismos criterios A/B.
6. Observar al menos siete llamadas nativas de movimiento 360 exitosas en cada render.
7. SHA256 de MP4 completo se registra pero no se añade como criterio obligatorio.

La evidencia decodificada se procesa en streaming/framehash: no almacenar en RAM
los aproximadamente 9 GB de vídeo raw de cada export. Se conserva cada hash de
frame; el timeline entero se guarda como JSON canónico comprimido con zlib/base64
y su SHA256, con primeros/últimos paquetes y metadatos legibles. No es una muestra.

## Medidas D que sí se pueden recoger ahora
Bytes reales del paquete de medios + JSON, ZIP de paquete y ZIP de originales
con mismo compresor/nivel, tiempo de preparación, tiempo por render en runner.
Assets comunes se identifican y hashean; transport manifest aún no implementado.
No hay servidor remoto de producción autorizado/conectado ni transferencia real
medida; no convertir estos tiempos en rentabilidad ni gastos RunPod.

## Interpretación limitada
PASS_FULL_PLAN_ISOLATED_AB demostraría portabilidad audiovisual del plan ensayado
con paquete que quita audio de cámaras, pero conserva todos sus GOP de vídeo.
No demostraría ahorro de transferencia de imágenes ni mínimo universal de dependencias.
Un resultado negativo se conserva con errores de worker/comandos y no se maquilla.
Una sola ejecución consolidada. Sin PR ni disparar cuatro E2E ni tocar ramas ajenas.
