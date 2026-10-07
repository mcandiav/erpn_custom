# Plan - Spec 019 Materialización progresiva de Encargo en OV

Estado: APROBADO PARA PROGRAMACION
Fecha: 2026-10-06

## Etapa 1 - Investigación técnica ERPNext

- Verificar comportamiento soportado de Update Items sobre Sales Order submitted.
- Verificar inserción/reducción de Sales Order Items en submitted.
- Verificar interacción con delivered_qty, billed_qty y Stock Reservation Entry.
- Documentar mecanismo elegido antes de implementar mutaciones.

### Resultado Etapa 1 (ERPNext 16.29.0, commit a5de60c, Frappe 16.28.0)

- `update_child_qty_rate` (botón Update Items) **no se usa**:
  - al final cancela y recrea **todas** las Stock Reservation Entry de la OV, lo que deshace las reservas parciales de Specs 013/018;
  - en filas nuevas impone la bodega por defecto del Item y no la de recepción.
- Estrategia elegida, "lo más default posible": acción backend `erpn_custom.encargo.materialization` que usa las mismas piezas de ERPNext que Update Items:
  - `set_order_defaults` para la fila nueva;
  - `validate_child_on_delete` antes de eliminar;
  - la misma secuencia post-guardado: totales, packing list, payment schedule, `check_credit_limit`, `update_reserved_qty`, `update_delivery_status`, billing y `set_status`.
  - Solo se omite la cancelación/recreación masiva de reservas.
- Línea real:
  - bodega `Recepcion Encargos - FRAG`;
  - hereda rate, price_list_rate, descuentos, margen, delivery_date, cost_center y project de la línea técnica;
  - se reserva 1 SRE por unidad con `inventory.reserve_unit`.
- Línea técnica: qty − 1; al llegar a 0 se elimina con `validate_child_on_delete` (ERPNext lo permite si no hay entregas ni facturas).
- Atomicidad:
  - la materialización corre dentro de un savepoint después del Material Receipt;
  - si falla, se revierte solo la materialización, la unidad queda `POSTED` + `ERROR`, el receptor ve `APARTAR - ENC-… - PENDIENTE DE VINCULAR A OV` y ComercialFRA reintenta.
- Entrega: hook `Delivery Note.before_validate` quita líneas ENCARGO-PENDIENTE de entregas nuevas mixtas y bloquea las demás.
- Reversión: "Devolver a stock" de una unidad materializada devuelve 1 a ENCARGO-PENDIENTE (recrea la línea si se eliminó) y resta 1 a la línea real.
- Riesgos a observar en el piloto:
  - `check_credit_limit` y `validate_for_duplicate_items` (si `allow_multiple_items` está apagado) pueden rechazar; en ese caso la unidad queda en ERROR, el motivo es visible y se puede reintentar.

## Etapa 2 - Modelo de trazabilidad

- Campos de origen Encargo en Sales Order Item.
- Referencia a línea técnica original.
- Estado de materialización en Recepción Unidad.
- Cantidades materializada/pendiente en Encargo.
- Auditoría por unidad.

## Etapa 3 - Servicio de materialización

Implementar operación idempotente por Recepción Unidad:

1. validar recepción e inventario;
2. validar Encargo/OV;
3. calcular pendiente;
4. crear/incrementar línea real compatible;
5. reducir línea técnica;
6. cerrar línea técnica al llegar a cero;
7. adaptar reserva;
8. registrar auditoría.

## Etapa 4 - UI

- Indicadores y links en Sales Order.
- Sección Materialización en Encargo.
- Lista Pendientes de vincular a OV.
- Acción controlada Reintentar materialización.

## Etapa 5 - Entrega y reversión

- Validar Delivery Note con Item real.
- Bloquear entrega de ENCARGO-PENDIENTE.
- Probar liberación/devolución estándar.
- Restaurar demanda pendiente cuando corresponda.

## Etapa 6 - Piloto

- ENC-2026-00401 / OV-2026-00326.
- Confirmar Item real en inventario.
- Confirmar split/materialización en OV.
- Confirmar reserva/apartado.
- Crear Delivery Note de prueba.
