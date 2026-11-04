# JÚPITER · Companion Windows nativo W3B–W3E: hallazgo y corrección del bloqueo de proxies

**Fecha:** 2026-11-04 · **Laboratorio:** FER · **Estado:** fix validado en Windows para proxy sintético corto; **PR #74 draft**, sin merge ni despliegue. Evidencia: consola proporcionada por Fernando, Windows 10 (10.0.19045 AMD64), Python 3.11.9; FFmpeg y FFprobe en PATH.

## Alcance y entorno

Equipo Windows con 7,9 GB RAM y 25,4 GB libres. Python registrados 3.11, 3.13 y 3.14; Tkinter 8.6. Las pruebas descargaron cuatro módulos de Companion en carpetas temporales y usaron contenido sintético 640×360 de dos segundos; sin instalar paquetes o renderizador Stage. No se probaron unidades externas, GPU ni navegador remoto. La versión de Companion reportada por /health: 0.6.2.

## W3B · Selector

Se abrió el diálogo gráfico de carpetas en Windows; el usuario pulsó **Cancelar**. Falta registro completo de consola para acreditar explícitamente valores de retorno/raíces encontradas y ensayo con **Aceptar**. No se declara terminada la validación de disco extraíble.

## W3C · API Windows real (pre-fix)

- Sintético H.264 generado con FFmpeg: **475.402 bytes**.
- Companion 0.6.2 arrancó en loopback con puerto temporal (49405 en esta ejecución).
- `GET /health` → **HTTP 200**; FFmpeg disponible.
- `POST /locate` por nombre, tamaño y SHA-256 de primeros y últimos 64 KiB → **HTTP 200**.
- `POST /proxies` aceptó solicitud, pero el job no llegó a estado terminal en **100 s**. Script detuvo el proceso y limpió el directorio, sin preservar log. **W3C falla específicamente en generación del proxy.**

## W3D · Diagnóstico diferencial

El experimento W3D conservó evidencias y aisló rutas:

- `probe` de FFprobe: **0,06 s**; plan: H.264, 640×360, 30 fps, SDR y duración 2 s.
- **Comando exacto construido por `companion.proxy_command()`** ejecutado mediante `subprocess.run(..., capture_output=True)`: **FFmpeg exit 0**, 60 frames, fichero de salida creado, `progress=end`.
- Mismo flujo mediante `companion.make_proxy()` en proceso independiente: **timeout a 20 s**.
- Conclusión causal apoyada por código y diferenciación: el `Popen(stdout=PIPE, stderr=PIPE)` anterior consumía `stdout` hasta EOF **antes** de leer `stderr`; el buffer de errores de FFmpeg puede llenarse e impedir la salida del hijo, bloqueando también la lectura del padre. No es fallo demostrado de FFmpeg, codec o hardware.

## Fix de la PR #74

- Commit `7964645`: `stderr=subprocess.STDOUT` y lectura de un único stream, manteniendo interpretación de `out_time_us` para progreso, diagnóstico limitado en memoria y fallback a error en procesos no exitosos.
- Commit `d92c5e8`: prueba automática `tests/test_companion_proxy_pipe.py` que simula un proceso que llena stderr antes de emitir progreso.

## W3E · Evidencia POSITIVA Windows nativo

Ejecutada con código exacto del commit `d92c5e88f1cffdd58fd7af0c2904b1e7ab702cc1`, Python 3.11.9:

| Comprobación | Resultado |
|---|---|
| Test regresión, canal de FFmpeg saturado | **PASS**, 1 test, **0,707 s** |
| `companion.make_proxy()` con FFmpeg real y sintético 640×360 | **PASS**, estado `ready` |
| Tiempo total de rutina | **0,31 s** |
| Tiempo FFmpeg informado por Companion | **0,30 s** |
| Bytes proxy | **169.608** |
| Tamaño del proxy frente al original sintético | **36 %** |
| Limpieza del laboratorio | `LABORATORIO_LIMPIADO` |

**Importante:** este resultado W3E prueba directamente `make_proxy()`, no reejecutó el recorrido completo HTTP `/proxies` después del fix. Ese E2E nativo y la elección de carpeta con «Aceptar» quedan pendientes antes del cierre W3. La reducción observada de tiempo de bloqueo a 0,31 s no es una mejora de velocidad generalizable del codificador; se ha eliminado un bloqueo en una muestra.

## Estado y próximos gates

1. [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74) permanece **draft sin merge**; esperar el CI para `d92c5e8` y cualquier revisión de JM. La ejecución previa de `fe3e70e` finalizó en éxito.
2. Validar en Windows con el fix el recorrido **HTTP completo** y el diálogo «Aceptar», manteniendo logs de fallo y puerto loopback.
3. Comprobar instalación ligera y fallback de FFmpeg (NVENC/QSV/AMF según capacidad); no confundir con render original Stage.
4. No editar `engine/`, `mixer/` ni servicios existentes de JM.

**Documentación de laboratorio: no solicitud de merge automático.**
