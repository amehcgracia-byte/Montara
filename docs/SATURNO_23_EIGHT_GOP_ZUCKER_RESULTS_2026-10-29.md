# SATURNO-23 — resultado Zucker nativo con ocho GOP

Fecha 2026-10-29. Fuente: [GitHub Actions 40923839526](https://github.com/amehcgracia-byte/Montara/actions/runs/40923839526), job 123623943815; job `success`. Script `experiments/saturno_23/native_eight_gop.py`. Motor Zucker bloqueado en `60a7b7e9a39077b36f45057811abd6a833a168ef`.

Resultado experimental: `NATIVE_EIGHT_GOP_AB_EXACT`.

- Entrada original sintética H.264 90 segundos: **19756759 bytes**, 45 GOP, 2700 paquetes.
- Entrada selectiva: **3503672 bytes**, 8 GOP, 480 paquetes. Ahorro de contenedor: **16253087 bytes**, ~82.27%.
- Dos ventanas: [20,26) y [50,56). Salidas 180 + 180 fotogramas.
- A y A_repeat idénticas (framehashes y SHA-256 de MP4 por segmento), A/B también idénticas.
- Tres ejecuciones con dos intervenciones QA de decodificación cada una.
- Sin modificar el motor ni los submódulos.

## Incidencia anterior

La primera ejecución de SATURNO-23, run [40923295334](https://github.com/amehcgracia-byte/Montara/actions/runs/40923295334), falló por `AssertionError()` al comparar el paquete de ocho GOP con la lista de paquetes esperados aún calculada para diez GOP. Corregida en commit `875b2fd` mediante recálculo de índices con ocho GOP y workflow reactivado en `29bb363`. No fue evidencia de fallo de Zucker.

## Alcance

Se demuestra reproyección 360 nativa de dos segmentos con la selección reducida a ocho GOP y salida exacta frente al original. El material es sintético, sin audio; no existe aislamiento fuerte del original en B en este ensayo, ni concatenación Stage completa, análisis de color de proyecto, transferencia de red o costes. No considerar aprobado todavía el hito integral B+C+D sobre material real.

## Siguiente etapa

Unir el paquete de 8 GOP a un plan de exportación Stage real con audio y aislamiento físico A/B; realizar una prueba corta antes de repetir la integración larga. Documentar las dependencias y límites de GOP cerrados frente a fuentes reales.
