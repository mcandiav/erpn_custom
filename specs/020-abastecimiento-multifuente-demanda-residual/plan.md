# Plan - Spec 020 Abastecimiento multifuente y demanda residual

Estado: APROBADO PARA PROGRAMACION
Fecha: 2026-10-07
Prioridad: inmediata

## Etapa 1 - Investigación y modelo
- Inventariar uso actual de purchase_status, requested_qty, received_qty y custom_encargo_qty.
- Confirmar todos los puntos que asumen una sola compra por Encargo.
- Crear Encargo Supply Event.
- Definir cálculos sourced_qty, pending_supply_qty, received_qty y covered_qty.

## Etapa 2 - Migración
- Migrar legacy PENDING/PURCHASED sin inventar datos.
- Relacionar Recepcion Unidad cuando sea determinístico.
- Dejar patch idempotente.
- Preparar regularizador especial con preview para OV-328/ENC-403.

## Etapa 3 - Shopper multiusuario
- Cambiar cola a pending_supply_qty.
- Permitir compra parcial.
- Crear evento por compra.
- Evitar sobrescritura de evidencia.
- Proteger concurrencia.
- Refrescar cantidad residual después de cada compra.

## Etapa 4 - Recepción multifuente
- Quitar PURCHASED como requisito para asignar demanda.
- Buscar demanda compatible FIFO.
- Mostrar APARTAR por compromiso, no por origen de compra.
- Crear evento RECEPTION_DIRECT.
- Mantener STOCK NORMAL solo sin demanda compatible.

## Etapa 5 - Reconciliación
- Servicio único reconcile_encargo_supply.
- Servicio por Sales Order Item.
- Recalcular OV/Encargo/Shopper después de cada evento.
- Preservar SRE existentes y evitar reconstrucción global.

## Etapa 6 - Stock libre posterior
- Detectar/asignar stock elegible solo mediante acción/regla determinística.
- Crear STOCK_REALLOCATION.
- Resolver demanda residual sin duplicar compra.

## Etapa 7 - Integraciones
- Spec 017: barcode por evento/cantidad.
- Spec 018: recepción y warning.
- Spec 019: materialización solo UNKNOWN_ITEM.
- Delivery Note y reservas.

## Etapa 8 - Piloto
- Regularizar OV-2026-00328 / ENC-2026-00403.
- Confirmar 5 cubierto, pendiente 0, Shopper sin ENC-403.
- Probar demanda x4 con cuatro Shoppers distintos.
