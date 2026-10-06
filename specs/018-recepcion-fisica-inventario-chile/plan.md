# Plan - Spec 018 Recepción física e inventario Chile

Estado: APROBADO PARA PROGRAMACION
Fecha: 2026-10-06
Dependencia: Spec 013/015 vigentes
Orden: implementar antes de Spec 017

## Etapa 1 - Modelo y configuración

- Crear DocType `Recepción Unidad`, un registro por unidad física escaneada.
- Índice/constraint único sobre `scan_event_id`.
- Estados mínimos: ingresada, pendiente de clasificación, pendiente de valorización, pendiente de aprobación de código, devuelta a stock.
- Vincular Encargo, Sales Order, Sales Order Item, Item, Stock Entry, bodega, moneda, precio, tasa y costo.
- Agregar `received_qty` y `purchase_currency` en Encargo.
- Backfill de `purchase_currency = USD` para Encargos existentes cuando corresponda.
- Crear `Configuración Recepción FRA` con:
  - cuenta transitoria obligatoria;
  - tasa USD->CLP de respaldo.
- Patch para crear `Recepcion Encargos - FRAG`.
- No crear la cuenta contable por patch.
- No crear `Recepcion Stock - FRAG`.

## Etapa 2 - Servicio de escaneo

Implementar servicio transaccional `receive_scan(code, scan_event_id)`.

Orden de resolución:

1. idempotencia por scan_event_id;
2. buscar Encargo comprado compatible con recepción pendiente usando FIFO;
3. resolver Item;
4. crear Item automático para UNKNOWN_ITEM cuando existan datos suficientes;
5. dejar PENDING_CLASSIFICATION cuando falten datos o barcode desconocido sin Encargo;
6. resolver costo/tipo de cambio;
7. generar Material Receipt;
8. destino:
   - Encargo -> Recepcion Encargos - FRAG;
   - stock normal identificado -> Matriz - FRAG;
9. incrementar received_qty en una unidad;
10. completar Encargo solo al llegar a requested_qty;
11. para KNOWN_ITEM intentar reserva estándar sin duplicación.

Reglas especiales:

- barcode URL/QR nunca debe convertirse automáticamente en item_code;
- barcode limpio alfanumérico/guion de hasta 40 caracteres sí puede usarse como item_code;
- los demás Items automáticos usan serie FRA-#####;
- tipo de cambio Shopper: fecha `purchased_on`;
- sin cuenta transitoria configurada no hay Stock Entry.

## Etapa 3 - UI FRAreceptor

- Mobile-first.
- Cada lectura genera scan_event_id.
- Sin controles de decisión.
- Mostrar:
  - APARTAR - ENC-...
  - STOCK NORMAL
  - STOCK NORMAL - REQUIERE CLASIFICACION
  - APARTAR - REQUIERE COMERCIAL
  - APARTAR - REQUIERE CLASIFICACION - ENC-...
  - RECIBIDO - PENDIENTE DE VALORIZACION
- Mantener Cliente y OV como información de solo lectura en la tarjeta vigente.
- Historial inmediato de lecturas.

## Etapa 4 - UI ComercialFRA

Workspace MCV Chile > Recepción:

- Apartados.
- Pendientes de clasificación.
- Excepciones barcode.
- Pendientes de valorización.

Acciones:

- Resolver clasificación.
- Reintentar valorización.
- Devolver a stock.
- Abrir Encargo/Item y trazabilidad.

Sin permisos generales de Stock Entry.

## Etapa 5 - Regularización y cierre

- Acción `Regularizar recepciones previas` solo para System Manager.
- Reutilizar el mismo servicio de recepción.
- Generar scan_event_id de migración por unidad.
- Regularizar ENC-2026-00401 como piloto obligatorio.
- Ejecutar solo después de configurar la cuenta transitoria.
- No ejecutar regularización vía patch/migrate.
- Piloto final en celular.
