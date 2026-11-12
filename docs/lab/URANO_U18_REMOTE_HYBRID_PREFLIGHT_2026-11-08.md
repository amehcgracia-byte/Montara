# URANO U18 — Comprobación de conexión híbrida real sin despliegue (08-11-2026)

**Estado: herramienta opcional de preparación y tests offline. NO se ha comprobado todavía el servidor GCP ni dos equipos físicos.**

## Objetivo

Preparar una prueba **real** con dos ordenadores cliente, cada uno con su navegador y Companion local, y un **servidor Montara remoto por HTTPS**. La herramienta solo verifica si la conexión de prueba está lista para pasar a un ensayo manual autorizado; **no mide rendimiento distribuido ni inicia sesiones, renders o uploads**.

### Código

`tests/urano_remote_hybrid_preflight.py`:
- Se ejecuta **en cada equipo cliente**, de forma opt-in con `--execute` y un URL de servidor suministrado por un operador autorizado. Solo acepta un origen HTTPS sin puerto especial, rutas, usuario/contraseña, query ni fragmento. Rechaza IP literales, localhost y DNS que resuelva a IP privadas o reservadas.
- Hace únicamente **GET /api/v1/wizard/status** en el servidor de prueba, con TLS verificado y sin seguir redirecciones. HTTP 200, 401 o 403 acreditan que ese endpoint concreto responde; **401/403 no significa login válido**. Si el servicio tiene otra ruta o protocolo, el resultado puede ser *no preparado* aunque el servidor esté funcionando.
- Hace **GET http://127.0.0.1:47820/health** en el mismo equipo donde se ejecuta y exige la identidad `montara-companion` con FFmpeg activo. Jamás consulta un Companion remoto ni lo abre a la red.
- Emite un JSON local de preparación, con éxito/fallo, estado HTTP y tiempos observados. No imprime ni guarda hostnames, IP, cuerpos, cookies, headers, rutas de proyectos ni vídeos.
- No se conecta automáticamente: **sin `--execute` no hace comprobaciones**. No existe un servidor predeterminado ni se ejecuta remotamente desde GitHub.

### Uso futuro con autorización

Una vez elegido un **servidor de laboratorio HTTPS** y con Companion arrancado en el ordenador del participante:

```bash
python tests/urano_remote_hybrid_preflight.py \
  --server-origin https://servidor-laboratorio.example \
  --execute \
  --output u18-preflight-cliente-a.json
```

Repetir desde el segundo equipo (archivo de resultados distinto). Este ejemplo es ilustrativo: el dominio `example` **no es un host real ni sustituye un despliegue**. `--output` exige archivo nuevo en un directorio existente para no pisar datos.

**Antes de ejecutar en equipos o redes reales**: confirmar el dominio y el permiso de quien administre la infraestructura. La utilidad no configura firewall, Google OAuth, Cloudflare, ni mueve archivos. La validación del nombre IP en DNS reduce el riesgo de usar direcciones privadas, pero una comprobación DNS previa no garantiza por sí misma ausencia de DNS rebinding; utilizar únicamente un dominio bajo control confiable.

### Evidencia

`tests/test_urano_remote_hybrid_preflight.py` y `.github/workflows/urano-u18-remote-preflight.yml`: simulaciones offline de respuestas 200/401/302, Companion sano/insano, rechazos de URL inseguros y hosts internos, y comprobación de que no se imprimen direcciones ni datos privados. **CI no debe contarse como acceso al GCP real**.

## Requisitos que aún faltan para declarar beta o carga 2→4→8→10→25

1. Un entorno HTTPS de pruebas realmente publicado, con autenticación Google y owner→worker autorizado. Las PR U15/U16 aún están aisladas; no equiparar `/api/v1/wizard/status` público o protegido con autorización completa de proyectos.
2. Dos equipos físicos con Companion instalado y funcionando de forma segura; no exponer su puerto localhost en Internet. Confirmar que ambos tienen originales sintéticos o expresamente autorizados, y que el original no cruza la red por fallback.
3. Ejecutar Stage→receta→Companion→MP4, con red real y métricas U17B/U17C en las máquinas correspondientes; recoger tiempos CPU/RAM por host y bytes de proxy/recetas por HTTP. El preflight **no** ejecuta este flujo ni garantiza compatibilidad de versiones.
4. Solo después comparar 2, 4, 8, 10 y, según margen, 25. No asignar 25 procesos FFmpeg a GCP para estimar la capacidad de clientes híbridos.

**Sin acceso ni cambios en** `main`, puertos 8101/8102/8103, Engine, Mixer, Companion productivo, datos de Chema, servidores Cloudflare o GCP. PR U18 apilada sobre U17C **#132**, que depende de U17B **#131**, U17A **#130** y U13E2D **#121**. No fusionar pilas de ramas automáticamente.
