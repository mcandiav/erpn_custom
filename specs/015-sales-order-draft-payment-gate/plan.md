# Plan técnico — Spec 015

## Objetivo del corte

Permitir guardar una Sales Order Draft sin líneas, manteniendo un gate estricto de Submit:

- al menos una línea válida;
- pago efectivamente aplicado a la OV > 0;
- validaciones de Encargo/stock existentes intactas;
- Shopper activado solo después de Submit exitoso.

## Estrategia

### 1. Metadata de Sales Order.items

Verificar el meta efectivo de `Sales Order.items`.

Si la obligatoriedad proviene de `reqd = 1`, crear patch idempotente con Property Setter para dejar `reqd = 0` exclusivamente en Sales Order.

No modificar JSON/core de ERPNext.

### 2. Gate de Submit

Incorporar al inicio del `before_submit` existente de `erpn_custom.encargo.sales_order_encargo`:

1. `require_order_lines(doc)`;
2. `require_applied_payment(doc)`;
3. lógica actual de split/Encargo/reserva.

No crear un segundo `before_submit` concurrente si puede evitarse.

### 3. Pago aplicado

Extraer o exponer la consulta actualmente encapsulada en `sales_order_credit._applied_to_order()` para que sea reutilizable por el gate de Submit.

La función debe leer `Payment Entry Reference` submitted y retornar el total aplicado a la OV.

No confiar en `advance_paid` como fuente primaria.

### 4. Encargo y Shopper

No cambiar:

- `create_unknown_encargo`;
- relación obligatoria Encargo → Sales Order;
- `activate_draft_encargos`;
- estados Shopper;
- reserva parcial.

El único cambio de flujo es que la OV puede obtener su nombre estando vacía.

### 5. UI

No hace falta habilitar Agregar Encargo en una OV todavía no guardada.

Después de guardar la OV vacía, la lógica actual ya debe mostrar el botón porque `frm.is_new() == false`.

Verificarlo en sandbox.

## Riesgos a comprobar

- que ERPNext no tenga otra validación de tabla vacía posterior al meta;
- que calcular impuestos/totales con Draft vacío no falle;
- que Sales Team se asigne aunque no haya items;
- que guardar varias veces una OV vacía no genere efectos secundarios;
- que el Submit fallido por pago no cree Encargos de faltante ni reservas;
- que el patch sea reversible mediante restauración de `reqd = 1`.

## Rollback

Rollback funcional:

1. restaurar `Sales Order.items.reqd = 1`;
2. retirar guardas R1/R2 del código si el corte se revierte;
3. no requiere migración destructiva de datos.

Las OVs Draft vacías creadas durante pruebas deberán eliminarse/cancelarse según corresponda antes del rollback.
