# Tasks — Spec 017

Estado: CERRADA 2026-10-09. E1–E4 en 16.0.102 (revalidadas por Spec 020), E5 en 16.0.110, E6 en 16.0.111, E7 en 16.0.112.

## E1–E4 (16.0.102)

- [x] T01 Campos de excepción en Encargo, intento `BARCODE_REJECTED`, `rejected_encargo` en Recepcion Unidad, acción de evento `BARCODE_REJECTED`
- [x] T02 `encargo/barcode_exception.py`: resultado de compra, responsable, ToDo idempotente, aprobar / rechazar / solicitar nueva compra, listado
- [x] T03 Shopper: `confirm_purchase` registra la excepción y muestra el mensaje de la Spec sin datos comerciales
- [x] T04 Recepción: PENDING_APPROVAL no satisface; REJECTED fuera de candidatos FIFO; `resume_after_barcode_decision` (aprobar reanuda, rechazar desvincula a stock/clasificación)
- [x] T05 OV: anular permitido si la única compra está rechazada; cierra el ToDo
- [x] T06 Recepción Comercial: pestaña Excepciones barcode (Pendiente aprobación / Rechazada - decide el vendedor); botones en Encargo (`public/js/barcode_exception.js`)
- [x] T07 `encargo/supply.py`: estado por línea y vista previa al Shopper; `require_confirmed_shortfall` en `before_submit`; modal Continuar/Cancelar en `sales_order.js`
- [x] T08 Patch `v0_0_42`: campo `custom_shopper_qty_confirmed`; unidades en PENDING_BARCODE_APPROVAL → Encargo PENDING_APPROVAL + ToDo
- [x] T09 Tests: `test_barcode_exception.py`, `test_supply.py`
- [x] T10 Piloto 16.0.102: reemplazado por pruebas automáticas (decisión de Miguel 2026-10-09); excepción por evento cubierta en `test_spec020_acceptance.py`

## E5 — Cambios de cantidad (16.0.110)

- [x] T11 Revisión de solo lectura de `update_child_qty_rate` (ERPNext 16): anula y recrea todas las reservas de la OV
- [x] T12 Bloquear Actualizar artículos en OV con Encargo (servidor + botón oculto)
- [x] T13 Acción "Ajustar cantidad" (`encargo/quantity_adjust.py`): aumento con gate de pago, reserva del stock disponible y faltante al mismo Encargo; disminución sobre faltante y luego reserva de stock al validar; tests `test_quantity_adjust.py`

## E6 — Entrega (16.0.111)

- [x] T14 Nota de Entrega (`encargo/delivery.py`, hook `validate`): en OV con Encargos cada fila entrega como máximo lo reservado de su línea en esa bodega; unidades de compras PENDING_APPROVAL / REJECTED no tienen reserva de la línea, por lo tanto no son entregables; ENCARGO-PENDIENTE sigue bloqueado por Spec 019; devoluciones y OV sin Encargos siguen el estándar
- [x] T15 Stock disponible no se entrega sin reservar antes con "Asignar stock a demanda" (decisión A de Miguel; reemplaza el "resuelto por stock" al validar la NE); tests `test_delivery.py`

## E7 — Cierre

- [x] T16 Matriz de las 50 pruebas de §17 con evidencia (`checklists/acceptance.md`, 7 tests nuevos para los huecos), README (bitácora y Spec vigente), cierre de tasks
