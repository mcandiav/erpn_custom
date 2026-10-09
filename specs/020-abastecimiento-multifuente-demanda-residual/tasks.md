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

## Recepción — E4
- [x] Quitar PURCHASED como requisito de candidato.
- [x] Buscar Encargo compatible con necesidad abierta.
- [x] FIFO por `Encargo.creation`; desempate por `name`.
- [x] Mostrar APARTAR - ENC para KNOWN_ITEM PENDING.
- [x] Completar SHOPPER_PURCHASE compatible o crear RECEPTION_DIRECT cuando no existe fuente.
- [x] Reducir demanda residual.
- [x] No materializar línea KNOWN_ITEM.
- [x] Mantener Spec 019 para UNKNOWN_ITEM.
- [x] STOCK NORMAL solo si no existe demanda compatible.
- [x] CIERRE E4: piloto real nuevo sin compra Shopper previa confirma APARTAR, evento directo, vínculo y reducción de cola. (2026-10-08: OV-2026-00330 / ENC-2026-00405 / RCU-2026-00253, evento RECEPTION_DIRECT, SRE MAT-SRE-2026-00245, fuera de la cola Shopper.)

## Reconciliación — E5
- [x] PENDING_APPROVAL ocupa cupo de demanda; REJECTED lo libera.
- [x] Implementar `reconcile_encargo_supply`.
- [x] Implementar reconciliación efectiva por Sales Order Item / SRE (`reconcile_sales_order_item_supply` o equivalente). (16.0.109: `encargo/reservations.py`, botón "Revisar reservas".)
- [x] Ejecutar recálculo de demanda después de compra/recepción/barcode/devolución/stock reallocation/materialización donde aplica.
- [x] Recalcular resumen visual OV desde Supply Events + Recepcion Unidad.
- [x] Corregir `covered_qty`: no considerar una unidad realmente cubierta si la reserva ERPNext quedó inválida/desalineada. (16.0.109: bucket "Reserva inválida".)
- [x] Al mover/apartar una unidad en `Recepcion Encargos - FRAG`, cancelar/reubicar la SRE anterior de `Matriz - FRAG` cuando corresponda y crear/validar la reserva correcta sin duplicarla. (16.0.109: detectado como "reserva en otra bodega"; lo repara "Corregir reservas", System Manager.)
- [x] Validar invariantes por línea: stock físico por bodega, SRE vigente y `covered_qty` deben reconciliar; nunca reserva > stock elegible de esa bodega por efecto de este flujo.
- [x] No duplicar ni recrear SRE globalmente. (La corrección toca solo las SRE propias del flujo.)

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
