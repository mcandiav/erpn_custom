# Tasks — Spec 017

Estado: EN CURSO (E1–E4 entregadas en 16.0.102, en piloto).

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
- [ ] T10 Piloto 16.0.102: compra con barcode distinto, aprobar, rechazar, nueva compra, modal Validar (confirmar que Frappe 16 espera el `before_submit` del formulario), estado por línea

## E5 — Cambios de cantidad

- [ ] T11 Revisión de solo lectura de `update_child_qty_rate` (ERPNext 16)
- [ ] T12 Bloquear Actualizar artículos en OV con Encargo
- [ ] T13 Acción "Ajustar cantidad de Encargo" (aumento con gate de pago y SRE del delta; disminución sobre pendiente y luego reserva)

## E6 — Entrega

- [ ] T14 Cantidad entregable por línea; PENDING_APPROVAL / REJECTED no entregables
- [ ] T15 Stock libre del mismo KNOWN_ITEM resuelve el Encargo al validar la NE; propuesta para anulación de NE

## E7 — Cierre

- [ ] T16 Piloto completo, README (bitácora y Spec vigente), cierre de tasks
