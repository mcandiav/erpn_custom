# Plan — Spec 021 Edición de compras del Shopper
**Estado:** PROGRAMADO en 16.0.113. Piloto en sandbox pendiente. No cerrado.
**Fecha:** 2026-10-09
**Fuente normativa:** `spec.md` y decisión vigente sobre moneda Shopper (configuración del usuario; fallback USD).

## E1 — Verificación de contratos actuales
- Identificar vínculo de `Encargo Supply Event` y `Recepcion Unidad` por unidad, y verificar punto de confirmación física en Chile.
- Inventariar campos efectivamente capturados por Shopper, permisos, fotos, barcode, casos de `qty > 1`.
- Preservar valor por defecto USD cuando no hay moneda de usuario.

## E2 — Backend seguro de edición
- Endpoint POST con allowlist de campos Shopper, propietario autenticado y condición de no recepción.
- Proteger concurrencia, evidencias, datos históricos y referencias barcode/caja.
- No modificar cantidades, moneda, eventos, inventario o SRE.

## E3 — UI móvil
- *Mis compras* → *Editar compra*, solo cuando la compra es editable.
- Precio y moneda ISO visible de solo lectura; captura de cambio de precio, tienda, barcode/QR, imágenes.
- Guardar/Cancelar; mensajes de conflicto/recepción; refresco de tarjeta y totales.

## E4 — Pruebas y aceptación
- Ejecutar los 15 criterios de aceptación de `spec.md` §8, incluyendo unidad parcialmente recibida y comprador con moneda no configurada (USD).
- Evidencia para aprobar piloto de edición real antes de recepción y rechazo después.
- Documentar resultado y versión desplegada; cierre solo tras aceptación.

## Fuera de alcance
- No modificar moneda por usuario ni fallback USD.
- No reabrir Spec 020.
- No activar Spec 021 en README técnico antes de autorización/handoff.
