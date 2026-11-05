# PUENTE JÚPITER → URANO · Libro de integraciones pequeñas

Actualizado el **05-11-2026** por laboratorio FER. Estado **registrado en el momento de escribir**, puede variar: leer GitHub Actions y PR antes de fusionar. **Ninguna de estas PR ha sido fusionada por FER**, ni se ha desplegado en JM/FER VM. FUENTES: [matriz de triaje](PUENTE_JUPITER_URANO_INTEGRATION_TRIAGE_2026-11-05.md), [issue de coordinación #34](https://github.com/amehcgracia-byte/Montara/issues/34), [issue #56](https://github.com/amehcgracia-byte/Montara/issues/56), [colaboración](../../docs/COLLABORATION.md).

## 1. [Montara PR #79](https://github.com/amehcgracia-byte/Montara/pull/79) · Windows discovery desde 0.66

- Rama `fernando/integrate-windows-discovery-066`, base `bec8f85b`, HEAD `e2dacec`. **Draft**, mergeable técnicamente, sin merge.
- Diferencial único: `companion/companion.py` (despacho solo Windows y rechazo de symlinks/junctions), `companion/windows_support.py`, `tests/test_companion_windows_support.py` y workflow dedicado.
- CI de revisión: Windows discovery **5/5 PASS** + compilación; [run 42089713726](https://github.com/amehcgracia-byte/Montara/actions/runs/42089713726); E2E Linux [run 42089713664](https://github.com/amehcgracia-byte/Montara/actions/runs/42089713664) **SUCCESS** (Stage, Push, Mix, Session, contenedor).
- **No confundir** CI y contrato con prueba física completa: quedan aceptación del código integrado con selector nativo/USB/OneDrive en Windows real, revisión de capturas CI E2E y revisión JM de producto, según alcance y gate de PR. No exige rescatar la rama FER completa.

## 2. [Montara PR #80](https://github.com/amehcgracia-byte/Montara/pull/80) · U3C originales

- Rama `fernando/integrate-u3c-video-consent-066`, basada en `main` 0.66 `bec8f85b`, HEAD `08a3f40` al registrar.
- Web no sube originales de vídeo sin decisión explícita cuando Companion falta/falla; conserva opción **manual solo experimental** y rutas de audio.
- CI focal [run 42095383014](https://github.com/amehcgracia-byte/Montara/actions/runs/42095383014) PASS 12 casos simulados.
- Primera ejecución E2E [42092808118](https://github.com/amehcgracia-byte/Montara/actions/runs/42092808118): Stage, Mix, Session, contenedor OK; **Push falló** por timeout de 120 s tras evitar subida original sin Companion. Hipótesis causal: test de Push usa deliberadamente importación sin Companion y no aceptaba el nuevo `window.confirm`.
- Corrección `08a3f40`: **solo el test** `tests/e2e_journey.py` acepta la subida experimental con verificación del contenido de la confirmación; el código de producto sigue requiriendo consentimiento. Segunda ejecución [42095382907](https://github.com/amehcgracia-byte/Montara/actions/runs/42095382907) **en progreso al registrar**, no declarar PASS E2E hasta resultado.
- Protección U3C es **frontend**, no control de backend / tenencia SaaS. No fusionar si falla revalidación ni interpretar esto como cierre URANO multiusuario.

## 3. [zucker_videos PR #59](https://github.com/amehcgracia-byte/zucker_videos/pull/59) · Calidad y duración FFmpeg

- Rama `fernando/fix-shot-quality-duration-066`, desde `claude/recover-montara-engine` (descendiente del pin efectivo Montara 0.66 `bfb964c3`). **Draft**, no cambia pins.
- Solicitud no resuelta según respuesta de Chema en issue #56: la puntuación de escenas usa proxy cuando existe, pero `_extract_quality_frames` no tenía `-t`. Corregido añadiendo duración de salida solo si finita y positiva.
- **Hallazgo adicional durante el review:** caché de calidad anterior identificaba archivo, no duración. Una extracción acotada no debe heredar scores anteriores de otra ventana; ahora `sampling_window_sec` forma parte del fingerprint de cache. Produce una nueva clave y puede recalcular una vez las puntuaciones; conserva caché para llamadas idénticas posteriores.
- Dos pruebas focales: contrato de `-t` y fallback sin duración; dos duraciones del mismo medio no comparten cache y la segunda visita a la misma ventana sí la reutiliza. **No afirmar PASS** hasta CI del editor.
- Gates: tests de motor, regresión con vídeo real/ventanas VFR o B-frames, comprobar que no cambia selección de planos por error y coordinación JM. No fusionar automáticamente.

## 4. Decisión de secuencia

1. Cerrar gates #79 (especialmente aceptación real Windows y revisión de artefactos) y #80 (E2E completo). Cada PR independiente.
2. Cuando estén aprobadas: merge controlado a `main` actual, verificar pin y rollback por PR; **no** mezclar Windows y política upload.
3. Editor #59 está separado y solo se considera para el motor tras sus pruebas y revisión de fotogramas/puntuaciones.
4. Próxima mejora a revisar, pero sin desarrollarla aún: identidad original/proxy/receta `FOCUS_A_C`; comprobar diferencial respecto de Stage local export del motor 0.66.
5. Posteriormente URANO local-first con continuidad real mismo ordenador, sin inventar esquema de proyecto o SQLite por inercia.

**Regla transversal:** si un gate no está verde, se investiga el error y no se da el paso por aprobado. No confundir tests simulados con E2E real, ni un CI verde con aceptación física/visual.
