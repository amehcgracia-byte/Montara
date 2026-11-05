# URANO U7 — Web actual, acceso seguro y objetivo funcional v1

**Fecha:** 2026-11-05 · **Tipo:** plan de integración, no despliegue, migración ni arquitectura comercial aprobada.  
**Decisión de rumbo del propietario:** terminar **primero** un flujo web usable completo (usuario, proyecto, fuentes, Companion, procesamiento, edición, exportación y recuperación), y **después** optimizar repartos de tareas, GPU, costes y colas. La división inicial navegador–Companion–servidor fue un boceto, no restricción definitiva.

## 1. Qué existe de verdad en GitHub `main`

- **Web:** el README declara URL estable `https://montara-tau.vercel.app/`, con fuente en `deployment/vercel`. La aplicación montada en Vercel ya ejecuta una **demo** usando Sandbox, no un hosting meramente estático. El README advierte **no sustituir el alias estable ni desplegar en la cuenta del propietario sin acuerdo**.
- **Despliegue Vercel:** `deployment/vercel/package.json` usa `@vercel/sandbox`; `deployment/vercel/runtime.js` crea/recupera Sandbox identificado por secreto de sesión hexadecimal (32), limita cuatro entornos activos, maneja discos/snapshots y arranca Gunicorn con un worker dentro de cada Sandbox. Los snapshots tienen políticas temporales (siete días en el código inspeccionado), no equivalen a retención comercial indefinida.
- **Acceso demo:** `deploy/sandbox_entry.py` exige token de sesión, da cookie HttpOnly+Secure+SameSite=Lax tras validación y restringe rutas del Engine y rutas relativas a los datos de la sesión. **No es un sistema de cuentas permanentes**: no se ha verificado login, email, plan, billing o propiedad de recursos por usuario dentro de un backend compartido.
- **Backend privado alternativo:** `deploy/entry.py` protege una instancia con HTTP Basic y usuario/editor único; no hay motivo para migrar allí la web existente solo por estar disponible.
- **Cliente y Companion:** `web/montara.js` y `web/companion.js` proporcionan importación de proxies y render local en los caminos que lo soportan. La URL de loopback `127.0.0.1:47820` es fija en JS y la autenticación local del Companion depende principalmente de `Origin`, pendiente de fortalecer antes de conectar cuentas reales.
- **Pruebas recientes:** PR #81 corrige bloqueo Windows de FFmpeg; PR #82 añade contrato real de funciones JS con HTTP simulado; PR #83 protege contra subida silenciosa del original desde handle reabierto. **No equivalen a ensayo completo browser real ↔ Companion real ↔ backend Vercel**.

## 2. Base funcional propuesta (sin reescritura)

```
Navegador (web actual, servida desde Vercel)
  |
  | sesión de cuenta autenticada / proyecto seleccionado [PENDIENTE]
  |
  +-----> API y proyecto existente / Engine / Mixer
  |          (Sandbox privado por sesión en demo; evaluar continuidad v1)
  |
  +-----> Companion localhost (cuando hay fuentes locales)
               |
               +--> originales permanecen locales
               +--> proxy/segmentos a procesamiento cuando corresponda
```

Esta es una **ruta mínima de integración**, no la topología final ni un coordinador inteligente.

## 3. Funciones P0 para definir «flujo v1 usable»

1. **Cuenta:** registrarse/acceder/salir, sesión segura, acceso al propio espacio. No usar login de demostración como identidad. El producto podrá cobrar desde el lanzamiento, pero **no crear ahora tarifas inventadas**.
2. **Proyectos:** crear/listar/abrir un proyecto por cuenta, identificadores durables y ownership verificado en backend. No interpretar `latest` global ni `sessionStorage` como catálogo de cuentas.
3. **Fuentes:** arrastrar local, Companion encuentra original y genera proxy. Las fuentes remotas/YouTube usan camino ya existente, sin declarar que Companion procesa todos los modos. Fallback original únicamente con consentimiento explícito de laboratorio.
4. **Procesar y editar:** reutilizar flujos Stage, Push, Show y Mixer ya implementados. Una web que llama a Sandbox/Engine existente vale antes de introducir scheduler GPU.
5. **Guardar y recuperar:** receta editable, relación de proxies y originales, exportaciones, trabajo y estados al cerrar pestaña y volver otro día, con archivos temporales/borrado controlados y advertencia si original local no está disponible.
6. **Seguridad y pruebas:** separación entre dos cuentas, cuota/límites de pruebas, permisos por proyecto y medio, autorización entre navegador y Companion, sin acceso al proyecto de terceros. En entorno sandbox por cuenta/sesión los límites actuales aportan aislamiento, pero **no sustituye propiedad de cuenta**.

## 4. No hacer ahora

- No elegir RunPod/GCP GPU ni planificador inteligente; experimentar y medir tras contar con recorrido funcional.
- No migrar la web de Vercel a VM por preferencia sin medir; conservar la opción de migrar cuando haya datos.
- No convertir Vercel Sandbox demo en contrato permanente: estudiar coste, persistencia, latencia, caducidad, límites de concurrencia y necesidades de cuentas.
- No desplegar a URL estable, crear usuarios reales, activar cobros ni almacenar datos personales de clientes antes de seguridad y validación.
- No sustituir el motor de Chema, ni mezclar ramas experimentales completas.

## 5. Siguiente trabajo implementable

1. **Auditar la interfaz pública de la demo y sus puntos de sesión:** identificar la API real de creación/reanudación de Sandbox y dónde se conserva el token, sin introducir cambios de cuentas todavía. Confirmar qué hay que conservar al transformar sesión anónima en proyecto de usuario.
2. **Construir una prueba de contrato de propiedad de proyecto para dos usuarios ficticios** en entorno aislado. Elegir primero el límite apropiado: Sandbox por cuenta/proyecto o proceso compartido; no diseñar tabla universal antes de esa decisión.
3. **Definir estado persistente mínimo** de cuenta/proyecto: referencia a Sandbox o backend, ID durable de proyecto, estado de edición, identidad de fuentes, timestamps y versión de receta; sin almacenar rutas locales en cloud ni originales enteros.
4. Probar recuperación con cuenta y proyecto ficticios, pestaña nueva y compañero desconectado/reconectado; exportación bajo flujo ya existente.
5. UI comercial, branding, selección de plan y pagos después de disponer de identidad, contabilidad de uso y criterios económicos básicos, sin exigir orquestación GPU.

**Criterio de producto:** v1 de punta a punta con identidad y recuperación, aunque sea limitado a pocos usuarios de prueba; después optimizar máquina, precios y escalado. **Sin acciones sobre la instalación Windows ni producción Vercel en este hito.**
