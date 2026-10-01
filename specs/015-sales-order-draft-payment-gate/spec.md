# Spec 015 — Orden de Venta Draft sin líneas y validación comercial segura

**Estado:** CERRADA — validada en el sitio el 2026-09-30 (producto desde `16.0.85`)  
**Fecha:** 2026-09-30  
**Proyecto:** ERPn Custom / FRAgallardo  
**Dependencias:** Spec 013 (Encargo), flujo de pagos de clientes existente  
**Objetivo:** eliminar el producto fantasma que hoy se usa únicamente para poder guardar una Orden de Venta antes de crear un Encargo, sin debilitar las condiciones de validación ni el disparo hacia Shopper.

---

## 1. Problema observado

El flujo de Encargo exige que el Encargo esté vinculado a una Sales Order existente.

Actualmente:

1. una Sales Order nueva no puede guardarse sin al menos una fila en `items`;
2. el botón **Agregar Encargo** solo se habilita cuando la Sales Order ya fue guardada y tiene `name`;
3. por ello el vendedor crea una fila temporal/fantasma para poder guardar;
4. luego usa **Agregar Encargo**, que crea la fila técnica real `ENCARGO-PENDIENTE`;
5. finalmente debe borrar manualmente la primera fila temporal.

Caso de evidencia: `OV-2026-00076`, donde quedaron dos filas `ENCARGO-PENDIENTE`: una fila técnica sin Encargo real y otra correspondiente al Encargo Crossbody.

Esto es un defecto de flujo: el vendedor no debe crear ni borrar productos artificiales para obtener el número de OV.

---

## 2. Decisión arquitectónica

Se mantiene la relación obligatoria:

```
Encargo -> Sales Order existente
```

No se permitirá crear un Encargo huérfano ni crear primero el Encargo y vincularlo después.

En cambio, se permitirá guardar una **Sales Order en Draft sin filas de producto**.

El estado Draft se interpreta como documento de trabajo incompleto y puede existir con:

- cliente;
- vendedor / Sales Team según reglas vigentes;
- cero filas en `items`;
- cero pago aplicado.

La flexibilización aplica **solo al guardado en Draft**.

---

## 3. Flujo objetivo

```
Nueva OV
  ↓
Seleccionar cliente
  ↓
Guardar OV vacía
  ↓
ERPNext asigna OV-YYYY-#####
  ↓
Agregar Encargo
  ↓
Crear ENC + única fila técnica ENCARGO-PENDIENTE
  ↓
Aplicar pago / saldo del cliente
  ↓
Validar (Submit) OV
  ↓
Encargo pasa a Open/PENDING
  ↓
Aparece en la lista del Shopper
```

El vendedor nunca debe agregar manualmente `ENCARGO-PENDIENTE`.

---

## 4. Regla de guardado Draft

### 4.1 Permitido

Una Sales Order con `docstatus = 0` puede guardarse con:

```
items = []
```

### 4.2 Implementación esperada

Quitar la obligatoriedad de la tabla `Sales Order.items` mediante personalización/versionado controlado de ERPn Custom, preferentemente un Property Setter idempotente aplicado por patch.

No modificar core de ERPNext.

No usar monkey patch genérico para saltarse validaciones obligatorias de otros documentos.

### 4.3 Alcance

La relajación afecta solamente a Sales Order.

Quotation, Sales Invoice, Delivery Note y demás documentos conservan su comportamiento estándar.

---

## 5. Reglas obligatorias antes de Submit

Una OV **NO puede validarse** si incumple cualquiera de estas reglas.

### R1 — Debe contener al menos una línea comercial

```
len(doc.items) > 0
```

Si no:

> La Orden de Venta debe contener al menos un producto o Encargo antes de validarse.

Esto impide que una OV vacía pase de Draft a Submitted.

### R2 — Debe existir pago real aplicado a la OV

Debe existir un monto aplicado a la orden mayor que cero:

```
applied_payment > 0
```

La fuente autoritativa no debe ser un valor editable de UI. Debe calcularse desde `Payment Entry Reference` submitted vinculado a:

- `reference_doctype = Sales Order`
- `reference_name = <OV>`
- `docstatus = 1`

Puede reutilizarse la lógica actual de `_applied_to_order()` de `erpn_custom.chile.sales_order_credit`, refactorizándola a función pública/interna reutilizable si corresponde.

No basta con:

- que el cliente tenga saldo disponible;
- que exista un depósito huérfano;
- que exista un Payment Entry sin asignar;
- que `advance_paid` tenga un valor stale o manipulado.

Debe existir **asignación efectiva a esa OV**.

Mensaje:

> La Orden de Venta requiere al menos un pago aplicado antes de validarse.

### R3 — Encargo desconocido debe conservar vínculo válido

Toda fila cuyo `item_code == ENCARGO-PENDIENTE` debe tener `custom_encargo` válido, como ya exige Spec 013.

No relajar esta regla.

### R4 — Mantener validaciones de stock/Encargo existentes

Debe seguir ejecutándose la lógica actual de Spec 013:

- `apply_stock_encargo_split(doc)`
- `validate_unknown_item_rows(doc)`
- `ensure_encargos_for_known_shortfalls(doc)`
- configuración de reserva parcial;
- reservas de stock en `on_submit`.

---

## 6. Orden de validación en before_submit

Las validaciones de seguridad comercial deben ocurrir **antes** de cualquier efecto que pueda activar demanda para Shopper.

Orden requerido:

```
before_submit
  1. validar que existan líneas
  2. validar que exista pago aplicado > 0
  3. ejecutar split stock / encargo
  4. validar ENCARGO-PENDIENTE
  5. generar Encargos de faltantes conocidos
  6. preparar reservas
```

Solo si `before_submit` termina correctamente ERPNext puede ejecutar `on_submit`.

---

## 7. Regla Shopper — comportamiento que NO debe cambiar

Actualmente Spec 013 activa los Encargos Draft durante el `on_submit` de Sales Order:

```
Sales Order Submit
  ↓
activate_draft_encargos(doc)
  ↓
Encargo.status = Open
purchase_status = PENDING
  ↓
Shopper puede verlo
```

Este comportamiento debe mantenerse.

Consecuencia:

- guardar OV vacía: **no envía nada al Shopper**;
- guardar OV con Encargo en Draft: **no envía nada al Shopper**;
- OV sin pago: **no puede validarse**, por lo tanto no envía nada al Shopper;
- OV con pago + producto/Encargo válido: puede validarse;
- solo después del Submit los Encargos correspondientes entran a la cola del Shopper.

Esto preserva la regla de negocio: FRA no compromete dinero de compra hasta que la venta fue validada con algún pago real del cliente.

---

## 8. ENCARGO-PENDIENTE

`ENCARGO-PENDIENTE` se mantiene como Item técnico no-stock porque ERPNext requiere una fila de Sales Order para representar económicamente el producto desconocido.

No debe:

- deshabilitarse;
- borrarse;
- ser creado manualmente por vendedores;
- usarse como producto real;
- servir como fila temporal para guardar una OV.

Debe ser insertado únicamente por el flujo **Agregar Encargo**.

La presente Spec no reemplaza el diseño técnico de `ENCARGO-PENDIENTE`; elimina la necesidad de crear una fila artificial previa.

---

## 9. UI esperada

### OV nueva no guardada

El vendedor completa al menos el cliente y presiona **Guardar**.

No se exige producto.

### OV guardada y vacía

La OV tiene número y permanece Draft.

Debe estar disponible **Agregar Encargo**.

### Intento de validar OV vacía

Bloquear con R1.

### Intento de validar OV con producto/Encargo pero sin pago

Bloquear con R2.

### OV lista

Si tiene:

- al menos una línea válida; y
- al menos un pago aplicado;

puede validarse normalmente.

---

## 10. Compatibilidad con ventas de stock

La regla de pago aplica también a ventas de productos conocidos.

Ejemplo:

```
OV con producto de bodega
+ pago aplicado > 0
→ Submit permitido
```

```
OV con producto de bodega
+ pago aplicado = 0
→ Submit bloqueado
```

La Spec no exige pago total. Exige **algún pago efectivo (> 0)**.

Una futura regla de porcentaje mínimo, ranking de cliente o excepción de crédito queda fuera de este corte.

---

## 11. Compatibilidad con OV mixta

Una OV puede contener simultáneamente:

- producto conocido con stock;
- producto conocido con faltante;
- `ENCARGO-PENDIENTE` vinculado a Encargo desconocido.

Con pago aplicado > 0 y todas las líneas válidas, el Submit debe conservar el comportamiento actual:

- stock disponible → reserva estándar;
- faltante conocido → Encargo correspondiente;
- desconocido → Encargo ya vinculado;
- Encargos → Open/PENDING al completar Submit.

---

## 12. Casos de aceptación

### AC-01 — Guardar OV vacía

**Dado** cliente válido  
**Cuando** vendedor guarda una OV sin items  
**Entonces** se crea `OV-YYYY-#####` en Draft  
**Y** no se crea Item  
**Y** no se crea Encargo  
**Y** no aparece nada para Shopper.

### AC-02 — Crear Encargo después de guardar OV vacía

**Dado** una OV Draft vacía guardada  
**Cuando** vendedor usa Agregar Encargo  
**Entonces** se crea un Encargo Draft  
**Y** se crea exactamente una fila `ENCARGO-PENDIENTE` vinculada al ENC  
**Y** no existe fila fantasma adicional.

### AC-03 — No validar OV vacía

**Dado** una OV Draft sin items  
**Cuando** se intenta Submit  
**Entonces** se bloquea con R1.

### AC-04 — No validar OV sin pago

**Dado** una OV con una línea válida  
**Y** cero Payment Entry Reference aplicado a esa OV  
**Cuando** se intenta Submit  
**Entonces** se bloquea con R2  
**Y** ningún Encargo pasa a Open  
**Y** nada nuevo aparece para Shopper.

### AC-05 — Pago disponible pero no aplicado no sirve

**Dado** cliente con saldo a favor  
**Pero** sin asignación a la OV  
**Cuando** se intenta Submit  
**Entonces** se bloquea con R2.

### AC-06 — Pago parcial permite Submit

**Dado** OV total CLP 100.000  
**Y** Payment Entry Reference aplicado por CLP 10.000  
**Y** al menos una línea válida  
**Cuando** se intenta Submit  
**Entonces** el control de esta Spec permite continuar.

Las demás validaciones estándar de ERPNext pueden igualmente bloquear el documento.

### AC-07 — Encargo entra al Shopper solo después de Submit válido

**Dado** Encargo Draft vinculado a la OV  
**Y** pago aplicado > 0  
**Cuando** la OV se valida correctamente  
**Entonces** `activate_draft_encargos` lo pasa a Open/PENDING  
**Y** queda visible en la lista Shopper.

### AC-08 — Regresión OV-2026-00076

Repetir conceptualmente el caso que produjo OV-2026-00076:

- crear OV;
- guardar sin producto;
- Agregar Encargo Crossbody;
- aplicar pago;
- validar.

Resultado esperado: **una sola fila comercial**, correspondiente al Encargo. No se crea ni se borra manualmente una fila artificial.

---

## 13. Pruebas automáticas mínimas

Agregar pruebas para:

1. Draft Sales Order sin `items` puede insertarse/guardarse.
2. Submit sin `items` falla.
3. Submit con items y pago 0 falla.
4. Submit con saldo del cliente pero no aplicado falla.
5. Submit con Payment Entry Reference > 0 pasa esta validación.
6. `ENCARGO-PENDIENTE` sin `custom_encargo` sigue fallando.
7. Encargo Draft no se activa durante Save.
8. Encargo se activa únicamente después de Submit exitoso.
9. Fallo de validación de pago no produce efectos parciales de reserva ni apertura para Shopper.
10. Flujo Agregar Encargo desde OV vacía guardada deja exactamente una fila.

---

## 14. Archivos candidatos

El Programador debe confirmar el plan antes de modificar código.

Probables cambios:

- `erpn_custom/patches/<nuevo_patch>.py`
  - Property Setter idempotente para `Sales Order.items.reqd = 0`.
- `erpn_custom/encargo/sales_order_encargo.py`
  - guardas R1/R2 al inicio de `before_submit`.
- `erpn_custom/chile/sales_order_credit.py`
  - exponer/reutilizar cálculo autoritativo del monto aplicado sin duplicar SQL.
- pruebas existentes de Encargo / Sales Order.
- README / bitácora al implementar.

No modificar core ERPNext.

---

## 15. Fuera de alcance

- crear Encargo sin Sales Order;
- eliminar `ENCARGO-PENDIENTE`;
- cambiar la cola del Shopper;
- financiar compras sin pago del cliente;
- exigir pago total;
- reglas de porcentaje mínimo por ranking;
- crédito comercial;
- excepciones manuales de gerencia;
- alterar el flujo de recepción Chile.

---

## 16. Invariantes

1. **Draft puede estar incompleto. Submitted no.**
2. **Ninguna OV sin líneas puede validarse.**
3. **Ninguna OV sin pago aplicado puede validarse.**
4. **Saldo disponible no equivale a pago aplicado.**
5. **Ningún Encargo llega al Shopper por guardar una OV.**
6. **El Shopper recibe demanda solo después de Submit exitoso.**
7. **Agregar Encargo crea la única fila técnica necesaria.**
8. **El vendedor no crea productos fantasma para obtener un número de OV.**
9. **No se rompe la reserva estándar de ERPNext ni el split stock/Encargo de Spec 013.**
10. **Toda modificación debe ser idempotente y versionada dentro de `erpn_custom`.**


---

## 17. Handoff obligatorio al Programador

Antes de escribir código, el Programador debe:

1. trabajar exclusivamente desde la raíz técnica `ERPnext-custom/erpn_custom/`;
2. leer `README.md`, esta Spec 015 y las secciones de Spec 013 que gobiernan Sales Order → Encargo → Shopper;
3. inspeccionar el meta efectivo de `Sales Order.items` en Frappe/ERPNext v16 y confirmar que la obligatoriedad proviene de metadata/Property Setter y no de una validación adicional del core;
4. inspeccionar la secuencia real de eventos `before_validate → validate → before_submit → on_submit`;
5. confirmar qué función será la única fuente para calcular pago aplicado;
6. presentar el plan de archivos, migración/patch, pruebas y rollback antes de modificar código.

La implementación debe priorizar el cambio mínimo. No se debe rediseñar Spec 013 ni la arquitectura del DocType Encargo.

## 18. Condiciones de no regresión

El Programador debe demostrar que este corte no altera:

- creación automática de Sales Team / comisión;
- aplicación y liberación de saldo de cliente;
- reserva parcial de stock;
- generación de Encargo por faltante de Item conocido;
- creación de Encargo UNKNOWN_ITEM mediante Agregar Encargo;
- cancelación de Encargo Draft huérfano al borrar su línea;
- activación `Draft → Open/PENDING` solamente al Submit;
- lista y compra del Shopper;
- nombres/series de documentos;
- permisos ComercialFRA vigentes.

## 19. Criterio de cierre

La Spec 015 se considera cerrada solo cuando se valide en sandbox, con usuario ComercialFRA, el flujo completo:

```
OV nueva
→ seleccionar cliente
→ guardar sin items
→ número OV asignado
→ Agregar Encargo
→ una sola línea ENCARGO-PENDIENTE vinculada
→ intento Submit sin pago bloqueado
→ aplicar pago real
→ Submit exitoso
→ Encargo Open/PENDING
→ visible para Shopper
```

Debe documentarse además una prueba de OV de stock conocida para comprobar que el nuevo gate de pago también la bloquea con pago 0 y la permite con pago aplicado > 0.
