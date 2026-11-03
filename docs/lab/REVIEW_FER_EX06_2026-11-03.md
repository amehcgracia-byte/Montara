# Revisión de las novedades de Fernando · 2026-11-03

## A · Novedades accesibles
PR Montara #68, draft, `f340461`: adaptador temporal bicúbica → bilineal en la referencia OpenCV de `core.spherical_motion`, runner A/B y cuatro pruebas. No modifica el motor ni su pin. Sus cinco recorridos CI figuran aprobados; eso valida que el experimento no rompe el producto por estar en el repositorio, no que acelere el producto.

## B · Duplicidades
La 0.59 trabaja en iluminación, miniaturas y render local desde originales. No introduce las optimizaciones CPU de reproyección de EX-06/07/13; no hay dos implementaciones de esos cambios en producto.

## C · Reutilización y comprobaciones
Se revisaron los tres archivos de #68 en un checkout separado. Se ejecutaron las cuatro pruebas contra el motor base `ff9baf45`: 4 aprobadas; el self-test informa `EX06_OPTIN_SELFTEST_OK`. No se repitieron los benchmarks ni se midió ahorro nuevo. El adaptador restaura la referencia al salir, incluida una excepción; no cambia la interpolación nearest.

## D · Riesgos y evidencia que falta
El adaptador cambia una referencia compartida del módulo: no es seguro en concurrencia y debe quedarse en laboratorio. La interpolación bilineal altera píxeles; falta validación perceptual a resolución completa y aceptación representativa. Las mejoras nativas EX-06/07/13 y sus cifras más recientes se comunican en el issue #34, pero ese aviso declara expresamente que el código aún no está publicado. No se han revisado esos commits ni confirmado sus mediciones de forma independiente. No se ha accedido al HOME ni a servicios del laboratorio de Fernando.

## E · Recomendación
Mantener #68 como draft de transferencia, sin fusionarlo como arreglo de producción. Pedir la rama nativa publicada en el Editor —un fork y PR sirven sin otorgar Write— y revisar primero EX-07/13, que reportan conservación exacta de salida. Evaluar EX-06 por separado porque cambia la calidad. Flags explícitos, valores por defecto intactos, pruebas de concurrencia y A/B con mismo motor, hardware y proyecto antes de mover el pin de Montara. No multiplicar porcentajes de ensayos diferentes ni prometer la misma mejora E2E o en Metal.
