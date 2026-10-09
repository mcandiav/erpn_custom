# Spec 020 — Matriz de aceptación (§23 y §25)

Fecha: 2026-10-09 · Versión: 16.0.109 · Decisión de Miguel: basta con pruebas automáticas más los pilotos reales ya hechos.

Archivos de prueba en `erpn_custom/encargo/`. `acc` = `test_spec020_acceptance.py`.

| # | Caso §23 | Evidencia |
|---|---|---|
| 1 | Encargo x4 aparece al Shopper como 4 | `acc` TestFourShoppers.test_queue_goes_down_to_zero; `test_shopper` test_pending_encargo_exposes_only_reference |
| 2-5 | Compras 1+1+1+1 de Shoppers distintos: 3, 2, 1, desaparece | `acc` test_queue_goes_down_to_zero (rechaza la quinta compra) |
| 6 | Cada compra conserva su evidencia | `acc` test_each_purchase_keeps_its_own_evidence; `test_shopper` test_all_four_evidences_required, test_images_of_a_purchase_only_for_its_shopper |
| 7 | Dos Shoppers no sobrecompran la última unidad | `acc` test_last_unit_cannot_be_bought_twice; `confirm_purchase` decide bajo `demand.lock_encargo` |
| 8 | Compra parcial qty=2 consume solo 2 | `acc` test_partial_purchase_consumes_only_its_qty; `test_shopper` test_partial_purchases_until_demand_is_sourced |
| 9-10 | KNOWN_ITEM sin compra: asigna y muestra `APARTAR - ENC` | `test_reception` test_known_item_without_purchase_is_direct_reception; piloto real OV-2026-00330 / ENC-2026-00405 (2026-10-08) |
| 11 | Recepción directa reduce la cola Shopper | `acc` TestFourDirectReceptions; piloto OV-2026-00330 (salió de la cola) |
| 12-13 | ENC-403 sin necesidad Shopper; OV-328 a 5 cubierto | `test_demand` test_ov_328_acceptance; `test_supply` test_ov_328_direct_reception_and_stock_cover_the_line; producción OV-2026-00328 |
| 14 | Recepción directa KNOWN_ITEM no sustituye la línea | `test_reception` test_known_item_is_not_materialized |
| 15 | UNKNOWN_ITEM sigue Spec 019 | `test_reception` test_encargo_pendiente_unit_is_materialized_after_the_receipt; `test_materialization` |
| 16 | Sin demanda compatible: STOCK NORMAL | `test_reception` test_known_code_without_encargo_goes_to_stock_at_cost; `acc` (quinta unidad) |
| 17 | FIFO por Encargo más antiguo | `test_reception` test_oldest_demand_first; `test_demand` test_fifo_by_creation_then_name, test_older_demand_blocks_fifo |
| 18 | Una unidad no satisface dos Encargos | `acc` test_unit_is_counted_once; `test_reception` test_repeated_read_is_a_noop (scan_event_id único) |
| 19 | Stock libre asignado reduce la demanda | `acc` test_stock_allocation_reduces_residual |
| 20 | Compra liberada conserva historia y llega como stock | `acc` test_released_purchase_keeps_history_and_arrives_as_stock; `test_demand` test_released_commitment_leaves_only_arrived |
| 21 | Excepción de barcode de una compra no bloquea las otras | `acc` test_barcode_exception_holds_only_its_purchase; `test_barcode_exception` test_only_the_named_purchase_is_resolved |
| 22 | No encontrado no reduce demanda | `shopper.mark_not_found` crea solo un `Encargo Purchase Attempt`, nunca un Supply Event; `test_demand` test_no_supply_is_all_pending |
| 23 | Tres intentos disparan revisión | `test_shopper` test_review_from_third_not_found |
| 24 | Reconciliación idempotente | `test_demand` test_same_data_same_result; `acc` test_repeated_reconciliation_is_stable |
| 25 | Migración legacy PURCHASED sin inventar detalle | `test_demand` test_purchase_in_transit, test_pre_018_reception_without_units; patch v0_0_43 aplicado |
| 26 | Regularización OV-328 exige preview System Manager | `test_reception` test_regularize_is_admin_only; producción 2026-10-07 |
| 27 | Shopper nunca ve Cliente/OV/precio/vendedor | `test_shopper` test_list_fields_exclude_commercial_data, test_list_card_hides_commercial_data |
| 28 | Inventario no se duplica en la reconciliación | Revisión de código: `reconcile_encargo_supply` solo escribe cantidades; `allocate_stock` crea SRE sin Material Receipt |
| 29 | SRE no se recrean globalmente | `test_reservations` test_only_own_references_are_repairable; botón "Corregir reservas" toca solo SRE propias |
| 30 | Totales nunca exceden requested_qty | `test_demand` test_oversupply_never_goes_negative, test_requested_reduced_below_sourced |

## §25 Criterio de cierre

- 4 Shoppers 1+1+1+1, cola 4 a 0: `acc` TestFourShoppers.
- 4 recepciones directas sin compra, cola 4 a 0: `acc` TestFourDirectReceptions; en producción, ENC-403 y ENC-405.

## Delivery Note

- Verificado 2026-10-09: NE-2026-00003 (docstatus 1) entregó FRA-00001 desde `Recepcion Encargos - FRAG` contra OV-2026-00326 (línea neou35fdo0), la bodega donde estaba la unidad apartada.
