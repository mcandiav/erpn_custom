# Matriz de aceptación — Spec 017 §17

Fecha: 2026-10-09 · Versión: 16.0.112 · Evidencia: pruebas automáticas (decisión de Miguel 2026-10-09).

Suite completa: 436 pruebas; misma línea base de 9 fallas y 1 error ajenos a Spec 017 (`customer_contact_mirror`, `brand_supplier`, `encargo_brand_supplier`, `sales_order_encargo.TestValidateUnknown`, `sales_person_assignment`).

Estados:

- **OK**: cubierta por prueba automática.
- **OK (020)**: cubierta, con la regla de Spec 020 que prevalece (ver `plan.md`).
- **OK (código)**: comportamiento de UI verificado en código; el servidor que lo respalda tiene prueba.

Archivos: `be` = `encargo/test_barcode_exception.py`, `sup` = `test_supply.py`, `qa` = `test_quantity_adjust.py`, `dn` = `test_delivery.py`, `dem` = `test_demand.py`, `rec` = `test_reception.py`, `acc` = `test_spec020_acceptance.py`.

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
| 1 | KNOWN_ITEM + barcode coincidente → MATCH | OK | be `test_match_when_code_is_the_expected_items`, `test_matching_code_has_no_exception` |
| 2 | Barcode diferente → PURCHASED + PENDING_APPROVAL | OK | be `test_different_code_is_pending_approval`, `test_different_code_opens_the_exception` |
| 3 | Mensaje al Shopper sin datos comerciales | OK | be `test_shopper_message_has_no_commercial_data` |
| 4 | ToDo único al vendedor | OK | be `test_one_open_todo_per_user` |
| 5 | PENDING_APPROVAL no satisface recepción | OK | rec `test_known_item_with_other_barcode_needs_commercial`; dem `test_pending_barcode_still_occupies_quota` |
| 6 | Responsable aprueba → APPROVED | OK | be `test_responsible_approves_and_code_is_added` |
| 7 | Otro ComercialFRA no resuelve | OK | be `test_other_commercial_user_cannot_resolve`, `test_resolution_mode` |
| 8 | Override System Manager con motivo | OK | be `test_override_requires_comment` |
| 9 | Aprobación agrega Item Barcode si es único | OK | be `test_responsible_approves_and_code_is_added`, `test_code_already_on_expected_item_is_not_added_again` |
| 10 | Barcode de otro Item bloquea aprobación | OK | be `test_code_of_other_item_blocks_approval` |
| 11 | Corrección de maestro permite luego aprobar | OK | be `test_conflict_is_the_other_item` (sin conflicto, se aprueba; el conflicto se evalúa en cada intento) |
| 12 | Rechazo deja PURCHASED + REJECTED | OK | be `test_reject_frees_the_quota_and_notifies_seller` |
| 13 | Etiqueta "Compra rechazada - decide el vendedor" | OK | be `test_rejected_label`; sup `test_barcode_exception_and_rejection` |
| 14 | Rechazo no vuelve automáticamente a PENDING | OK (020) | La compra rechazada conserva su evento REJECTED; el cupo vuelve a la cola del Shopper de inmediato. be `test_reject_frees_the_quota_and_notifies_seller`; dem `test_rejected_purchase_frees_the_quota` |
| 15 | Nueva compra preserva evidencia | OK (020) | No hace falta "Solicitar nueva compra": el cupo vuelve solo y el evento rechazado queda como historia. acc `test_released_purchase_keeps_history_and_arrives_as_stock`, `test_each_purchase_keeps_its_own_evidence` |
| 16 | Sin decisión: caso detenido y ToDo abierto | OK | dem `test_pending_barcode_still_occupies_quota`; el ToDo solo se cierra al aprobar (be `test_responsible_approves_and_code_is_added`) |
| 17 | Unidad rechazada identificada → stock normal | OK | be `test_unit_leaves_the_encargo_and_goes_to_stock` |
| 18 | Unidad rechazada desconocida → PENDING_CLASSIFICATION | OK | be `test_rejection_sends_the_unit_to_stock_or_classification`; rec `test_unknown_code_without_encargo_needs_classification` |
| 19 | Aprobación reanuda Spec 018 sin nuevo scan | OK | be `test_approval_retries_the_same_unit_without_scan` |
| 20 | Rechazo de unidad en espera → stock/clasificación | OK | be `test_rejection_sends_the_unit_to_stock_or_classification` |
| 21 | Migración: históricos NOT_APPLICABLE, en espera PENDING_APPROVAL | OK | be `test_waiting_units_become_pending_approval`; dem `test_migration_counts_as_covered_not_in_transit` |
| 22 | Modal Validar con Continuar/Cancelar | OK (código) | `public/js/sales_order.js` `before_submit` + diálogo Continuar/Cancelar; sup `TestConfirmedShortfall` |
| 23 | Cancelar no valida la OV | OK (código) | `finish(false)` en Cancelar y al cerrar el diálogo; sup `test_without_modal_is_skipped` |
| 24 | Continuar genera Encargos y valida | OK | sup `test_same_figure_passes`, `test_split_is_shared_by_preview_and_submit` |
| 25 | Línea mixta con resumen cuantitativo | OK | sup `test_mixed_line_reconciles_with_qty`, `test_purchase_splits_covered_reception_transit` |
| 26 | Estado incluye "Compra rechazada - decide el vendedor" | OK | sup `test_barcode_exception_and_rejection` |
| 27 | OV con Encargo bloquea ajuste estándar | OK | qa `test_update_items_blocked_with_encargo` |
| 28 | Ajuste propio sin recrear reservas ajenas | OK | qa `test_reservations_of_received_units_are_not_released`, `test_then_releases_reserved_stock` |
| 29 | Aumento posterior a compra → Encargo para el delta | OK (020) | Decisión de Miguel: el delta sube el mismo Encargo. qa `test_increase_after_purchase_grows_same_encargo` |
| 30 | Línea → Encargo 1:N | OK | sup `test_two_encargos_on_one_line_merge`; qa `test_line_without_encargo_gets_a_new_one` |
| 31 | Disminución no baja de comprado/recibido/materializado | OK | qa `test_never_below_purchased_or_received`, `test_delivered_and_billed_lines`, `test_materialized_line_and_draft_order` |
| 32 | Ajuste aplica a KNOWN_ITEM | OK | qa `test_known_increase_splits_stock_and_encargo`, `test_known_decrease_cuts_pending_demand_first` |
| 33 | UNKNOWN_ITEM solo sobre pendiente | OK | qa `test_unknown_decrease_only_on_pending`, `test_unknown_increase_goes_to_its_encargo` |
| 34 | Nota de Entrega de línea mixta solo cantidad elegible | OK | dn `test_only_reserved_quantity_is_deliverable`, `test_rows_of_the_same_line_add_up`, `test_reservation_counts_per_warehouse` |
| 35 | PENDING_APPROVAL no entregable | OK | dn `test_unit_without_reservation_is_not_deliverable` |
| 36 | REJECTED no entregable | OK | dn `test_unit_without_reservation_is_not_deliverable`; be `test_unit_leaves_the_encargo_and_goes_to_stock` |
| 37 | UNKNOWN_ITEM sigue Spec 019 | OK | dn `test_encargo_pendiente_is_left_to_spec_019` |
| 38 | OV con Encargo bloquea "Actualizar artículos" | OK | qa `test_update_items_blocked_with_encargo` (servidor); botón oculto en `sales_order.js` |
| 39 | Sin línea nueva ni cambio de precio vía Update Items | OK | qa `test_update_items_blocked_with_encargo` (se bloquea el método completo) |
| 40 | Aumento vuelve a ejecutar gate de pago | OK | qa `test_increase_requires_applied_payment` |
| 41 | Delta con stock disponible → reserva + Encargo por faltante | OK | qa `test_increase_reserves_available_stock_first`, `test_known_increase_splits_stock_and_encargo` |
| 42 | Disminución: primero Encargo pendiente, luego reserva | OK | qa `test_decrease_cuts_unsourced_demand_then_reserved_stock`, `test_then_releases_reserved_stock` |
| 43 | Cambio de stock entre modal y submit bloquea | OK | sup `test_stock_changed_blocks`, `test_zero_confirmed_but_now_short_blocks` |
| 44 | Sales Person sin usuario → owner → System Manager | OK | be `test_responsible_falls_back_by_tier` |
| 45 | Vista Excepciones barcode con dos pestañas | OK (código) | Recepción Comercial, pestaña Excepciones barcode (`list_exceptions` view pending/rejected); be `test_matches_search`, `test_rejected_label` |
| 46 | Migración crea ToDo idempotente | OK | be `test_one_open_todo_per_user` (`v0_0_43` usa `open_exception` → `_open_todos`) |
| 47 | Rechazo exige comentario | OK | be `test_reject_requires_comment` |
| 48 | Override exige comentario | OK | be `test_override_requires_comment` |
| 49 | Aprobación normal con comentario opcional | OK | be `test_comment_rules`, `test_responsible_approves_and_code_is_added` |
| 50 | Stock disponible satisface la OV con Encargo abierto | OK (020) | Decisión A de Miguel: solo tras "Asignar stock a demanda" (STOCK_REALLOCATION). acc `test_stock_allocation_reduces_residual`; dn `test_blocks_stock_available_without_reservation` |

## Criterio de cierre (§19)

- [x] Diferencia de barcode con resolución comercial determinística (1–13, 44, 47–49)
- [x] Vendedor responsable controla el rechazo (7, 12–16)
- [x] Recepción reacciona a aprobar/rechazar (17–20)
- [x] OV informa cantidades por estado (25, 26)
- [x] Validación previa exige Continuar/Cancelar (22–24, 43)
- [x] Cambios de cantidad no destruyen reservas (27–33, 38–42)
- [x] Una línea maneja múltiples Encargos (30)
- [x] Nota de Entrega solo permite cantidad elegible (34–37, 50)
