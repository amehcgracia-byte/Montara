# SATURNO — limpieza de reproducibilidad y paquete portátil V2 (2026-10-29)

**Estado:** cuatro reconstrucciones sintéticas reproducidas en paquete portátil y un ensayo chroot adicional superado en entorno QA Linux x86_64. Ningún motor modificado, ninguna prueba E2E de Zucker declarada.

## Artefacto
El paquete **`SATURNO_02_03_PORTABLE_V2_2026-10-29.zip`** está adjunto a la conversación del proyecto; **no está subido como binario a GitHub**. SHA-256 exacto: `33801ce48f0ff3ab278252b863ea8286b8c14cbb5d323f0bec9a2c9bff72af46` (tamaño 1.287.958 bytes).

Este paquete preserva scripts históricos de SATURNO-02/03, con **corrección exclusivamente de rutas absolutas** del productor (`battery.py`, `experiment.py`, `isolated_trial.py`), informes, recetas y JSON. Tiene `SHA256_MANIFEST.json` con los hashes de 20 archivos incluidos (más el propio manifiesto). No contiene las fuentes sintéticas de vídeo grandes: se regeneran al ejecutar `battery.py`.

**Precaución:** los resultados JSON dentro del ZIP son de una nueva repetición de QA, no idénticos bit a bit a los registros del primer ensayo, y sobrescriben ficheros de resultados si se vuelve a ejecutar. El ZIP de conservación histórica (SHA256 `7de2e1b27117aab61f9304b528e354209c1bb8b6ab4bbe95f1f20ca9d8eab5e7`) se conserva aparte.

## Repetición ejecutada desde la copia portátil
- `python saturno02/battery.py`: código 0.
- `python saturno02/audit_v3.py`: código 0.
- `python saturno03/isolated_trial.py`: código 0.
- `python saturno03/isolated_final_v2.py`: código 0.
- `python saturno03/av_chroot_v3.py` con root en entorno de laboratorio desechable: código 0 y `pass: true` (60/60 frames, PCM 96.000 muestras, denegación del acceso al original bajo la ruta ensayada).

Equipo del reensayo: Python 3, FFmpeg 7.1.5 y Linux x86_64. Consultar `PORTABLE_REPLAY.json` y `CHROOT_REPLAY.log`. El valor `0` del proceso no demuestra automáticamente un E2E de aplicación; se conservaron verificaciones y límites en JSON.

## Reproducción en VM de QA
```bash
sha256sum SATURNO_02_03_PORTABLE_V2_2026-10-29.zip
unzip SATURNO_02_03_PORTABLE_V2_2026-10-29.zip -d saturno-qa
cd saturno-qa
python saturno02/battery.py
python saturno02/audit_v3.py
python saturno03/isolated_trial.py
python saturno03/isolated_final_v2.py
# Únicamente en VM Linux x86_64 de QA desechable:
sudo python saturno03/av_chroot_v3.py
```

**Restricciones:** el último paso requiere privilegios y crea una jaula `chroot`; nunca ejecutarlo en producción. `chroot` es aislamiento de rutas limitado, no una sandbox contra adversarios. No se prueba sincronía A/V sobre timecode compartido, estructura de dependencias mínima, contenidos reales 360 ni export auténtico de Zucker.

## Puerta de integración siguiente
El documento `docs/SATURNO_03D_ZUCKER_REAL_E2E_GATE_2026-10-29.md` establece criterios para el **exportador real**: fuente y paquete A/B, aislamiento de originales y cachés, mismo plan y comparación audiovisual. Su estado sigue **NO PROBADO / BLOQUEADO SIN ADAPTADOR QA APROBADO**. El código `_spherical_uses_original_motion` en el motor confirma que el movimiento 360 de calidad final puede leer el original completo. No alterarlo sin permiso de José Manuel.

## Deuda restante de publicación
Los scripts completos aún viajan en el ZIP y **no están cada uno versionados en GitHub**. No describir esto como completado, ni fusionar a main hasta que ambos barcos revisen el protocolo. El siguiente paso de higiene es subir individualmente los scripts cuando haya un mecanismo fiable de transferencia de bytes, con una prueba CI no privilegiada; la prueba chroot debe quedar en un runner QA manual y explícito.
