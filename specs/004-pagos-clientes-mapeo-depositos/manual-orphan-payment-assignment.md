# Requerimiento — Asignación manual de pagos huérfanos

## Contexto

El flujo automático de `Pagos de Clientes` vincula depósitos bancarios (`Bank Transaction`) con un `Customer` cuando existe coincidencia exacta por RUT. El caso no resuelto es cuando el depósito fue realizado por un tercero distinto del cliente comercial: hermano, pareja, familiar, empresa relacionada u otra persona.

Caso de prueba actual:

- Bank Transaction: `ACC-BTN-2026-01705`
- Pagador bancario: `At-Once Ltda`
- RUT pagador: `77421420-8`
- Monto: `$119.990`
- Estado actual: `Unreconciled`
- `party`: vacío
- `custom_mapping_status`: `No Match`
- `custom_realization_status`: `Skipped`
- `custom_realization_error`: `no_customer`
- Cliente comercial al que debe atribuirse manualmente: `Cynthia Contreras Soto`

Se comprobó que editar manualmente `Deposit Mapping Attempt` y seleccionar un Customer NO realiza la atribución real. Ese DocType es historial/auditoría y no debe utilizarse como interfaz operativa.

## Objetivo

Permitir que un usuario autorizado asigne manualmente un depósito huérfano a un Customer, preservando intacta la evidencia bancaria original y reutilizando el flujo contable existente de realización hacia `Payment Entry`.

## Definición de pago huérfano

Un pago huérfano es un `Bank Transaction` que cumple:

- `deposit > 0`
- `party` vacío o sin `Customer` asignado
- no cancelado
- aún disponible para atribución

Importante: `Unreconciled` por sí solo NO define un pago huérfano. Un depósito puede estar correctamente atribuido a un Customer y todavía no estar conciliado contablemente.

## UX requerida

Agregar dentro del workspace/página `Pagos de Clientes` una vista operativa llamada **Pagos huérfanos**.

Cada fila debe mostrar como mínimo:

- Fecha
- Bank Transaction
- Nombre del pagador bancario (`bank_party_name`)
- RUT pagador (`custom_rut_del_pagador`)
- Banco origen
- Cuenta origen, si existe
- Monto depósito
- ID de transacción
- Estado de mapping
- Customer a asignar
- Acción `Asignar`

El campo Customer debe ser un Link real a `Customer`, con búsqueda estándar de ERPNext.

## Flujo de asignación manual

El usuario debe poder ejecutar:

`Pagos de Clientes -> Pagos huérfanos -> seleccionar Customer -> Asignar`

Ejemplo esperado:

`ACC-BTN-2026-01705 / At-Once Ltda / 77421420-8 / $119.990 -> Cynthia Contreras Soto`

Al confirmar `Asignar`, el backend debe ejecutar una operación única e idempotente que:

1. Valide permisos.
2. Recargue el `Bank Transaction` y verifique que siga siendo elegible y no haya sido atribuido por otro proceso.
3. Preserve sin modificación la evidencia bancaria original:
   - `bank_party_name`
   - `custom_rut_del_pagador`
   - `transaction_id`
   - `deposit`
   - `withdrawal`
   - `description`
   - cuenta/banco de origen cuando corresponda.
4. Asigne:
   - `party_type = "Customer"`
   - `party = <Customer seleccionado>`
5. Marque la atribución como manual, sin fingir que hubo coincidencia automática por RUT.
6. Registre un nuevo `Deposit Mapping Attempt` de auditoría con:
   - Trigger = `Manual`
   - Resultado = `Mapped`
   - Customer = seleccionado
   - Bank Transaction = correspondiente
   - Reason = indicación explícita de asignación manual de tercero, por ejemplo `Asignación manual a Customer`
   - Regla diferenciada de la regla automática `exact-tax-id-v1`; no registrar una coincidencia exacta de RUT cuando no existió.
7. Ejecute el realizador existente `realize_attributed_deposit(bank_transaction_name)`.
8. Cree o reutilice de forma idempotente el `Payment Entry` correspondiente.
9. Deje el `Payment Entry` presentado/submitted y asociado al Customer seleccionado.
10. Vincule el `Payment Entry` al `Bank Transaction` mediante el mecanismo existente.
11. Actualice `custom_realization_status` y campos de trazabilidad existentes.
12. Devuelva a UI un resultado claro con Bank Transaction, Customer, Payment Entry y monto.
13. Refresque la lista: el depósito debe desaparecer de `Pagos huérfanos` inmediatamente después de una asignación exitosa.

## Regla contable

La identidad bancaria y la identidad comercial son conceptos distintos:

- **Pagador real:** se conserva desde el banco.
- **Cliente beneficiario:** se registra en `party = Customer`.

No modificar el RUT ni el nombre del pagador para hacerlos coincidir con el Customer.

Ejemplo:

- Pagador real: `At-Once Ltda`, RUT `77421420-8`
- Cliente beneficiario: `Cynthia Contreras Soto`

El saldo a favor debe incrementarse en la cuenta operativa de Cynthia, pero la trazabilidad debe seguir indicando que el dinero fue depositado por At-Once Ltda.

## Reutilización obligatoria

No crear un circuito contable alternativo.

La implementación debe reutilizar:

- `Bank Transaction`
- `Payment Entry`
- `realize_attributed_deposit()` de `chile/realize.py`
- las relaciones nativas de conciliación/vinculación ya utilizadas por el flujo automático
- el cálculo existente de saldo a favor del Customer basado en `Payment Entry.unallocated_amount`

## Método backend sugerido

Agregar una función equivalente a:

```python
assign_orphan_deposit(bank_transaction, customer)
```

Ubicación sugerida:

`erpn_custom/chile/deposit_mapping.py`

Debe ser whitelisted solamente a los mismos roles autorizados para `Pagos de Clientes` y nunca confiar en valores de estado enviados por el frontend.

La función debe releer el documento desde servidor, validar elegibilidad, aplicar party, registrar auditoría y llamar al realizador.

## Idempotencia y concurrencia

La asignación manual debe ser segura ante doble clic, recarga o ejecución concurrente.

Casos esperados:

- Si el Bank Transaction ya está asignado al mismo Customer y ya tiene Payment Entry: retornar éxito idempotente, sin crear otro pago.
- Si ya está asignado a otro Customer: rechazar y mostrar conflicto; no sobrescribir silenciosamente.
- Si ya no tiene monto disponible o está cancelado: rechazar.
- Nunca crear dos Payment Entry para el mismo Bank Transaction.

## Historial de Intentos

`Deposit Mapping Attempt` debe tratarse como registro de auditoría, no como interfaz de asignación.

Requerimiento UX:

- Los campos que representan resultado del motor deben ser de solo lectura para usuarios operativos.
- En particular, editar manualmente `customer`, `trigger`, `resultado`, `candidate_customers` o `reason` no debe aparentar que ejecuta una acción real.
- Si se mantiene edición por System Manager por razones administrativas, debe quedar claro que no ejecuta atribución ni realización.

`candidate_customers` debe continuar siendo evidencia del motor automático y no una lista editable para asignación manual.

## Vista Pagos huérfanos

La página `Pagos de Clientes` debe tener una sección o entrada directa llamada `Pagos huérfanos`.

Filtro funcional:

```text
deposit > 0
AND docstatus < 2
AND party vacío
```

Podrán añadirse verificaciones adicionales de elegibilidad coherentes con el realizador, pero no usar solamente `status = Unreconciled` como definición de huérfano.

## Criterios de aceptación

### AC1 — Visualización
Dado `ACC-BTN-2026-01705` sin party, debe aparecer en `Pagos huérfanos` mostrando At-Once Ltda, RUT `77421420-8` y `$119.990`.

### AC2 — Asignación manual
Al seleccionar `Cynthia Contreras Soto` y pulsar `Asignar`, el Bank Transaction debe quedar con:

- `party_type = Customer`
- `party = Cynthia Contreras Soto`

sin alterar el pagador bancario ni su RUT.

### AC3 — Realización
Debe existir exactamente un `Payment Entry` submitted por `$119.990` vinculado al Bank Transaction y a Cynthia.

### AC4 — Saldo a favor
El saldo disponible de Cynthia debe aumentar en `$119.990` respecto de su saldo anterior, siempre que el Payment Entry quede sin aplicar a una OV.

### AC5 — Auditoría
Debe existir un `Deposit Mapping Attempt` nuevo con Trigger `Manual`, Resultado `Mapped`, Customer Cynthia y una razón explícita de asignación manual.

### AC6 — Salida de huérfanos
Después del éxito, `ACC-BTN-2026-01705` ya no debe aparecer en `Pagos huérfanos`.

### AC7 — Idempotencia
Repetir la acción no debe crear un segundo Payment Entry ni duplicar saldo.

### AC8 — Conflicto
Si otro usuario/proceso asigna previamente el depósito a otro Customer, la operación debe detenerse con mensaje de conflicto y conservar la atribución existente.

## No alcance

Este requerimiento NO modifica:

- matching automático por RUT exacto;
- ingestión Banco de Chile;
- lógica de aplicación de saldo a Orden de Venta;
- reglas de ranking de Customer;
- creación automática de Customers;
- evidencia original del banco.

## Decisión de arquitectura

La asignación manual es una excepción controlada al matching automático, pero utiliza el mismo modelo contable y el mismo realizador. La atribución comercial se expresa mediante `Bank Transaction.party_type/party`; la identidad del pagador se conserva en los campos bancarios de origen. `Deposit Mapping Attempt` queda como auditoría del proceso y no como comando operativo.
