# Tasks - Spec 020 Abastecimiento multifuente y demanda residual

Estado: LISTA PARA EJECUCION
Fecha: 2026-10-07

## Modelo
- [ ] Crear Encargo Supply Event.
- [ ] Agregar/derivar sourced_qty.
- [ ] Agregar/derivar pending_supply_qty.
- [ ] Definir covered_qty.
- [ ] Mantener received_qty físico separado.
- [ ] Agregar constraints de no sobreasignación.

## Migración
- [ ] Migrar Encargos PENDING.
- [ ] Migrar PURCHASED a evento legacy.
- [ ] Relacionar Recepcion Unidad determinística.
- [ ] Patch idempotente.
- [ ] Regularizador con preview para OV-328/ENC-403.

## Shopper
- [ ] list_pending filtra pending_supply_qty > 0.
- [ ] Tarjeta muestra cantidad residual.
- [ ] Permitir compra parcial.
- [ ] Registrar un evento por compra.
- [ ] Preservar evidencia por Shopper/tienda.
- [ ] Evitar carreras entre Shoppers.
- [ ] Refrescar 4->3->2->1->0.
- [ ] Ocultar Encargo al llegar a 0.

## Recepción
- [ ] Quitar PURCHASED como requisito de candidato.
- [ ] Buscar Encargo compatible con necesidad abierta.
- [ ] FIFO por `Encargo.creation`; desempate por `name`.
- [ ] Mostrar APARTAR - ENC para KNOWN_ITEM PENDING.
- [ ] Crear RECEPTION_DIRECT.
- [ ] Reducir demanda residual.
- [ ] No materializar línea KNOWN_ITEM.
- [ ] Mantener Spec 019 para UNKNOWN_ITEM.
- [ ] STOCK NORMAL solo si no existe demanda compatible.

## Reconciliación
- [ ] PENDING_APPROVAL ocupa cupo de demanda; REJECTED lo libera.
- [ ] Implementar reconcile_encargo_supply.
- [ ] Implementar reconcile_sales_order_item_supply.
- [ ] Ejecutar después de compra.
- [ ] Ejecutar después de recepción.
- [ ] Ejecutar después de barcode decision.
- [ ] Ejecutar después de devolución.
- [ ] Ejecutar después de stock reallocation.
- [ ] Ejecutar después de materialización.
- [ ] Recalcular resumen OV desde realidad.
- [ ] No duplicar ni recrear SRE globalmente.

## UI ComercialFRA
- [ ] Sección Abastecimiento en Encargo.
- [ ] Acción `Asignar stock a demanda` para demanda sin fuente; FIFO automático/propuesto.
- [ ] Acción `Liberar compromiso` sobre Supply Event Shopper ya comprometido; motivo obligatorio.
- [ ] Mostrar solicitado/abastecido/pendiente/recibido/cubierto.
- [ ] Tabla cronológica de eventos y fuentes.
- [ ] Links a Recepcion Unidad y evidencia Shopper.

## Integración
- [ ] Adaptar Spec 017 a excepción por evento.
- [ ] Adaptar Spec 018 a demanda sin compra previa.
- [ ] Confirmar Spec 019 solo materializa UNKNOWN_ITEM.
- [ ] Revisar Delivery Note.

## Pruebas
- [ ] Ejecutar los 30 casos de spec.md §23.
