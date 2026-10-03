# Spec 016 — Pagadores conocidos para atribución bancaria recurrente

**Estado:** ACTIVA — implementada en 16.0.90; permisos §18 corregidos en 16.0.91; pendiente validación en el sitio por rol (§18.12) y decisiones §18.11
**Fecha:** 2026-10-02
**Proyecto:** ERPn Custom / FRAgallardo
**Dependencias:** Spec 004 (Pagos de Clientes / mapeo de depósitos), asignación manual de pagos huérfanos, flujo vigente Bank Transaction → Payment Entry.
**Objetivo:** permitir que el sistema recuerde de forma explícita, reversible y auditable que un RUT de origen bancario distinto al RUT del cliente corresponde habitualmente a ese cliente, evitando resolver manualmente la misma excepción en cada depósito futuro.

---

## 1. Problema

Customer.tax_id sigue siendo la identidad tributaria principal del cliente. Sin embargo, existen clientes cuyos pagos llegan recurrentemente desde otro RUT: pareja, familiar, empresa relacionada, cuenta de un tercero u otro pagador habitual.

Hoy, cuando RUT del depositante != Customer.tax_id, el depósito queda huérfano y un usuario debe asignarlo manualmente. Si el mismo tercero deposita repetidamente para el mismo cliente, el sistema obliga a resolver una y otra vez una relación que ya fue conocida por la organización.

La solución NO debe transformar el RUT del depositante en un segundo RUT del Customer.

Principio:

~~~text
Cliente != Pagador bancario
~~~

---

## 2. Decisión arquitectónica

Se mantiene:

~~~text
Customer.tax_id = identidad tributaria principal del cliente
~~~

Se agrega una entidad explícita:

~~~text
Known Payer
RUT pagador -> Customer
~~~

Un Customer puede tener 0..N pagadores conocidos.

Un RUT de pagador activo puede pertenecer a máximo 1 Customer.

La asociación debe ser explícita, reversible, auditable, no destructiva e independiente de la aplicación del dinero a una Sales Order.

---

## 3. Separación conceptual obligatoria

El flujo se entiende en cuatro capas:

~~~text
Banco
  ↓
Pagador
  ↓
Cliente
  ↓
Aplicación del dinero
~~~

Esta Spec amplía solamente Pagador → Cliente.

Identificar automáticamente al Customer NO significa aplicar automáticamente el depósito a una OV.

---

## 4. Nuevo DocType — Known Payer

Crear un DocType versionado dentro de erpn_custom.

**Etiqueta visible:** Pagador conocido  
**Nombre técnico sugerido:** Known Payer

Campos mínimos:

| Campo técnico | Etiqueta UI | Tipo | Req. | Regla |
|---|---|---|---:|---|
| customer | Cliente | Link → Customer | Sí | Customer beneficiario habitual |
| payer_tax_id | RUT pagador | Data | Sí | RUT presentado |
| payer_tax_id_normalized | RUT normalizado | Data | Sí | Clave técnica canónica |
| payer_name | Nombre informado por banco | Data | No | Evidencia descriptiva |
| active | Activo | Check | Sí | 1 por defecto |
| source | Origen | Select | Sí | Bank Reconciliation / Manual / Migration |
| source_bank_transaction | Movimiento de origen | Link → Bank Transaction | No | Movimiento que originó la relación |
| confirmed_by | Confirmado por | Link → User | Sí | Usuario que confirmó |
| confirmed_on | Confirmado el | Datetime | Sí | Timestamp |
| disabled_by | Desactivado por | Link → User | No | Usuario que revocó |
| disabled_on | Desactivado el | Datetime | No | Timestamp |
| last_used_on | Último uso | Datetime | No | Último matching por esta relación |
| notes | Observaciones | Small Text | No | Administración |

Frappe conserva además owner, creation, modified y modified_by.

### 4.1 Revocación, no borrado

El flujo normal no debe borrar físicamente un Known Payer.

La revocación funcional se hace con active = 0.

El histórico permanece disponible.

---

## 5. Normalización del RUT

Debe reutilizarse una única función canónica compartida con el mapeo bancario existente.

Los formatos 12.345.678-9, 12345678-9 y 12 345 678-9 deben generar la misma clave.

El Programador debe inspeccionar la normalización vigente de Spec 004 y reutilizarla o refactorizarla. No crear una segunda lógica paralela.

---

## 6. Orden determinístico de resolución

Orden obligatorio:

~~~text
1. Customer.tax_id exacto normalizado
2. Known Payer activo
3. asignación manual
4. huérfano
~~~

El RUT principal de Customer siempre tiene prioridad.

---

## 7. Aprendizaje desde Pagos huérfanos

Se amplía el flujo actual:

~~~text
Pagos de Clientes
→ Pagos huérfanos
→ seleccionar Customer
→ Asignar
~~~

Después de una asignación manual exitosa, si el RUT origen bancario es distinto de Customer.tax_id y no existe una asociación activa idéntica, mostrar:

> ¿Recordar este RUT de origen para futuros depósitos de <Cliente>?

Opciones exactas:

- **Sí, recordar**
- **No**

### 7.1 Si responde No

- no crear Known Payer;
- conservar la asignación manual actual;
- no alterar ningún otro comportamiento.

### 7.2 Si responde Sí, recordar

Crear Known Payer con:

- customer = Customer asignado;
- payer_tax_id = RUT observado;
- payer_tax_id_normalized = RUT normalizado;
- payer_name = nombre informado por banco;
- active = 1;
- source = Bank Reconciliation;
- source_bank_transaction = movimiento actual;
- confirmed_by = usuario actual;
- confirmed_on = now().

La creación debe ocurrir en backend y volver a validar todos los candados.

---

## 8. Candado 1 — exclusividad entre clientes

No se permite:

~~~text
RUT X -> Customer A (ACTIVE)
RUT X -> Customer B (ACTIVE)
~~~

Al intentar registrar el mismo RUT activo para otro Customer, bloquear.

Mensaje:

> El RUT pagador <RUT> ya está asociado a <Cliente>. Debe desactivar primero esa asociación antes de asignarlo a otro cliente.

No sobrescribir ni trasladar automáticamente la relación.

---

## 9. Candado 2 — protección del RUT principal

Si existe:

~~~text
Customer A.tax_id = RUT X
~~~

no permitir:

~~~text
RUT X -> Customer B como Known Payer
~~~

Mensaje:

> El RUT <RUT> corresponde al RUT principal del cliente <Cliente> y no puede registrarse como pagador de otro cliente.

Este control aplica al crear, reactivar, modificar RUT, importar o migrar.

---

## 10. Candado 3 — duplicado exacto

Si ya existe RUT X → Customer A activo, repetir la misma creación no debe producir una segunda fila.

La operación debe ser idempotente.

---

## 11. Conflicto durante una asignación manual

Caso:

~~~text
Known Payer activo:
RUT X -> María Pérez

Movimiento actual:
RUT X

Usuario asigna manualmente el depósito a Carolina Soto
~~~

La asignación puntual del depósito puede seguir las reglas vigentes, pero al elegir Sí, recordar:

- no modificar el Known Payer existente;
- no crear una segunda asociación;
- mostrar:

> Este RUT de origen ya está registrado como pagador de María Pérez. El depósito actual fue asignado a Carolina Soto, pero la relación permanente no fue modificada.

Agregar acción **Revisar asociación**, link al Known Payer existente.

---

## 12. Desactivación, reasignación y reactivación

### 12.1 Desactivar

Acción: **Desactivar asociación**

Resultado:

- active = 0;
- disabled_by = current_user;
- disabled_on = now().

Los movimientos históricos ya procesados:

- no se modifican;
- no pierden Customer;
- no revierten Payment Entry;
- no se recalculan automáticamente.

### 12.2 Reasignar

Solo después de desactivar la relación anterior puede crearse una nueva relación activa para otro Customer.

El histórico anterior permanece.

### 12.3 Reactivar

Puede existir acción **Reactivar asociación**.

Antes de reactivar se deben ejecutar nuevamente los candados 1 y 2. Si hay conflicto, bloquear.

---

# 13. Gestión UI obligatoria

Esta sección es normativa. El Programador NO debe decidir libremente dónde ubicar la administración ni reemplazarla por otra navegación sin aprobación del Arquitecto.

## 13.1 Punto principal — ficha Customer

En la ficha estándar de Customer agregar una sección visible:

**Pagadores conocidos**

Debe existir aunque el cliente no tenga registros.

Si no hay registros, mostrar:

> No hay pagadores conocidos asociados.

Acción (solo `KNOWN_PAYER_ADMIN_ROLES`, §18):

**Agregar pagador conocido**

La sección es visible para los cuatro roles de §18; ComercialFRA y Accounts User la ven sin el botón.

Si existen registros, mostrar como mínimo:

- RUT pagador;
- Nombre informado por banco;
- Estado;
- Fecha de asociación;
- Último uso.

Cada fila debe abrir el documento Known Payer mediante un link real estándar de Frappe.

No desactivar directamente desde la tabla: la modificación de la regla permanente se confirma en el documento Known Payer.

## 13.2 Ficha Known Payer

Mostrar claramente:

- Cliente;
- RUT pagador;
- Nombre informado por banco;
- Estado Activo/Inactivo;
- Origen;
- Movimiento de origen;
- Confirmado por;
- Confirmado el;
- Último uso;
- Desactivado por;
- Desactivado el;
- Observaciones.

Links reales:

- Cliente → Customer;
- Movimiento de origen → Bank Transaction.

Acciones:

- si está activo: **Desactivar asociación** (solo `KNOWN_PAYER_ADMIN_ROLES`);
- si está inactivo y no existe conflicto: **Reactivar asociación** (solo `KNOWN_PAYER_ADMIN_ROLES`);
- **Ver cliente** (los cuatro roles);
- **Ver movimiento de origen**, cuando exista (los cuatro roles).

Para ComercialFRA y Accounts User la ficha es de solo lectura.

## 13.3 Diálogo de desactivación

Al pulsar **Desactivar asociación**, mostrar:

> ¿Desactivar este pagador conocido?
>
> Los futuros depósitos provenientes del RUT <RUT> dejarán de asociarse automáticamente a <Cliente>.
>
> Los movimientos ya procesados no serán modificados.

Botones:

- **Cancelar**
- **Desactivar**

No usar un cambio silencioso del checkbox Activo como flujo operativo principal.

## 13.4 Desde Pagos de Clientes / Pagos huérfanos

Después de asignar manualmente un depósito a un Customer con RUT distinto, mostrar el diálogo de aprendizaje de §7.

Si se crea la relación, mostrar confirmación breve con link:

**Ver pagador conocido**

## 13.5 Desde Bank Transaction

Cuando un movimiento haya sido identificado mediante Known Payer, mostrar trazabilidad visible:

~~~text
Cliente identificado: <Customer>
Método de identificación: Pagador conocido
Pagador conocido: <RUT / registro>
~~~

Pagador conocido debe ser Link → Known Payer.

Debe poder navegarse:

~~~text
Bank Transaction
→ Known Payer
→ Desactivar asociación (solo KNOWN_PAYER_ADMIN_ROLES)
~~~

No poner un botón directo de desactivación dentro de Bank Transaction.

## 13.6 ListView administrativa

Debe existir ListView estándar de Known Payer para Accounts Manager y System Manager (administración) y Accounts User (solo lectura). ComercialFRA no usa la ListView: al abrirla se le redirige a `pagos-huerfanos` con el aviso "La lista de pagadores conocidos es administrativa. Consúltelos desde la ficha del cliente."

Filtros mínimos:

- Cliente;
- RUT pagador;
- Estado;
- Nombre bancario;
- Fecha de creación.

Columnas mínimas:

- RUT pagador;
- Cliente;
- Nombre bancario;
- Estado;
- Confirmado el;
- Último uso.

Esta es una vista secundaria. La navegación operativa principal es Customer → Pagadores conocidos.

## 13.7 Ubicación en navegación

No crear un Workspace separado exclusivamente para esta feature.

El acceso operativo continúa siendo Pagos de Clientes.

La administración de la relación vive en Customer → Pagadores conocidos.

Known Payer List queda disponible mediante Desk/búsqueda para Accounts User (lectura), Accounts Manager y System Manager.

---

## 14. Trazabilidad en Bank Transaction

El Programador debe inspeccionar primero los campos existentes de Spec 004 y reutilizarlos si son equivalentes.

Debe quedar persistida o reconstruible al menos:

- Customer atribuido;
- método de identificación;
- Known Payer utilizado, cuando aplique;
- timestamp;
- ejecución/intento de mapping.

Si no existe un campo equivalente, agregar de forma versionada un método de identificación con valores:

- Customer Tax ID;
- Known Payer;
- Manual;
- Unknown.

Y, si hace falta, un Link a Known Payer.

No duplicar campos existentes.

---

## 15. Integración con el motor de Spec 004

La resolución debe quedar encapsulada en una única función reutilizable equivalente a:

~~~python
resolve_customer_from_bank_payer(tax_id)
~~~

Debe devolver al menos:

- Customer resuelto o None;
- método de resolución;
- Known Payer usado, cuando corresponda.

Orden interno:

~~~text
Customer.tax_id
→ Known Payer activo
→ None
~~~

El botón manual, scheduler de 15 minutos y cualquier futura ingesta en tiempo real deben reutilizar la misma resolución.

---

## 16. Payment Entry

Known Payer solo cambia cómo se identifica el Customer.

Después de identificarlo, debe seguir utilizándose el flujo contable vigente de Spec 004.

No crear un realizador alternativo.

No crear un segundo Payment Entry por introducir esta feature.

Toda la idempotencia vigente debe conservarse.

---

## 17. No aplicar automáticamente a Sales Order

Esta Spec NO autoriza:

~~~text
Known Payer
→ Customer
→ Sales Order automática
~~~

Un Customer puede tener varias OVs, saldo disponible, pagos parciales o compras futuras.

La feature termina cuando el depósito queda correctamente atribuido al Customer.

La aplicación del saldo sigue gobernada por la lógica vigente.

---

## 18. Permisos

Principio: **UI operativa ≠ administración** y **backend operativo ≠ backend administrativo**. `ComercialFRA` opera Pagos de Clientes sin convertirse en usuario contable.

### 18.1 Grupos de roles (código: `erpn_custom/chile/payment_roles.py`)

| Grupo | Roles | Uso |
|---|---|---|
| `PAYMENT_OPERATION_ROLES` | ComercialFRA, Accounts User, Accounts Manager, System Manager | Operación de pagos: listar, asignar, recordar, consultar |
| `KNOWN_PAYER_ADMIN_ROLES` | Accounts Manager, System Manager | Administración de Known Payer: alta manual, desactivar, reactivar |

Cada método backend valida el grupo que corresponde a la operación; no existe una lista única de roles permitidos. Ningún archivo define listas propias de estos roles: todos importan de `payment_roles.py`.

`ComercialFRA` es un **rol operativo, no administrativo**: opera pagos y aprende Known Payer desde el flujo; no administra relaciones ni recibe permisos contables.

### 18.2 Matriz UI (normativa)

| Acción UI | ComercialFRA | Accounts User | Accounts Manager | System Manager |
|---|---|---|---|---|
| Ver Workspace `Pagos de Clientes` | Sí | Sí | Sí | Sí |
| Ver página `Pagos huérfanos` | Sí | Sí | Sí | Sí |
| Ver detalle de depósito huérfano | Sí | Sí | Sí | Sí |
| Asignar huérfano a Customer | Sí | Sí | Sí | Sí |
| Ver diálogo `¿Recordar este RUT...?` | Sí | Sí | Sí | Sí |
| Ejecutar `Sí, recordar` | Sí | Sí | Sí | Sí |
| Ver sección `Pagadores conocidos` en Customer | Sí | Sí | Sí | Sí |
| Abrir ficha `Known Payer` | Sí, lectura | Sí, lectura | Sí | Sí |
| Ver link desde Bank Transaction a Known Payer | Sí | Sí | Sí | Sí |
| Crear Known Payer manualmente desde administración | No | No | Sí | Sí |
| Ver ListView administrativa de Known Payer | No | Lectura opcional | Sí | Sí |
| Desactivar asociación | No | No | Sí | Sí |
| Reactivar asociación | No | No | Sí | Sí |
| Eliminar físicamente Known Payer | No | No | No operativo | Solo excepcional/admin técnico |

### 18.3 Matriz backend (normativa)

| Operación backend | ComercialFRA | Accounts User | Accounts Manager | System Manager |
|---|---|---|---|---|
| Listar pagos huérfanos | Sí | Sí | Sí | Sí |
| Consultar detalle para asignación | Sí | Sí | Sí | Sí |
| Asignar depósito huérfano a Customer | Sí | Sí | Sí | Sí |
| Crear Known Payer desde `Sí, recordar` | Sí | Sí | Sí | Sí |
| Consultar Known Payer | Sí | Sí | Sí | Sí |
| Resolver Customer mediante Known Payer | Sí, vía flujo | Sí | Sí | Sí |
| Ejecutar mapping operativo permitido | Sí, vía flujo | Sí | Sí | Sí |
| Crear Known Payer manualmente fuera del flujo | No | No | Sí | Sí |
| Desactivar Known Payer | No | No | Sí | Sí |
| Reactivar Known Payer | No | No | Sí | Sí |
| Modificar libremente campos administrativos | No | No | Sí | Sí |
| Borrar físicamente Known Payer | No | No | No operativo | Solo excepcional/admin técnico |

### 18.4 Separación UI / backend

- Una pantalla visible no implica permiso backend.
- Un permiso backend no implica que la acción se muestre en UI. Ejemplo: ComercialFRA crea un Known Payer mediante el flujo controlado `Sí, recordar`, pero no ve ni ejecuta Desactivar/Reactivar.
- Ocultar un botón es solo presentación. La autorización real se valida siempre en servidor, también ante llamadas directas a la API.

### 18.5 Rutas, páginas y workspaces afectados

| Elemento | Ruta | Roles con acceso | Dónde se define |
|---|---|---|---|
| Workspace `Pagos de Clientes` | `/app/pagos-de-clientes` | `PAYMENT_OPERATION_ROLES` | Roles del Workspace; ComercialFRA agregado por patch `v0_0_36` |
| Page `Pagos huérfanos` | `/app/pagos-huerfanos` | `PAYMENT_OPERATION_ROLES` | Roles de la Page; ComercialFRA por patch `v0_0_36` |
| Page `Pagos de Clientes / Vinculador` | `/app/vinculador-pagos` | `PAYMENT_OPERATION_ROLES` | Roles de la Page; ComercialFRA por patch `v0_0_36` |
| Workspace Sidebar y Desktop Icon `Pagos de Clientes` | — | Sin roles propios; la visibilidad la dan el Workspace y las Pages | `workspace_sidebar/`, `desktop_icon/` |
| Pantalla de aplicaciones | — | `PAYMENT_OPERATION_ROLES` | `hooks.add_to_apps_screen` → `deposit_mapping.has_vinculador_permission` |
| Ficha Known Payer | `/app/known-payer/<name>` | Los cuatro roles (ComercialFRA y Accounts User: lectura) | Permisos DocType §18.8 |
| ListView Known Payer | `/app/known-payer` | Accounts User (lectura), Accounts Manager, System Manager | Permisos DocType + `known_payer_list.js` redirige a ComercialFRA a `pagos-huerfanos` |
| Ficha Customer, sección `Pagadores conocidos` | `/app/customer/<name>` | Los cuatro roles | `public/js/customer.js` + `known_payer.customer_known_payers` |
| Ficha Bank Transaction | `/app/bank-transaction/<name>` | Los cuatro roles (ComercialFRA: lectura) | Permisos DocType §18.8 + `public/js/bank_transaction.js` |

Los accesos a `Deposit Mapping Settings`, `Deposit Mapping Run` y `Deposit Mapping Attempt` del sidebar no cambian: ComercialFRA no recibe permisos sobre esos DocTypes (ver §18.11).

### 18.6 Botones y elementos visibles por rol

| Elemento | Ubicación | ComercialFRA | Accounts User | Accounts Manager | System Manager |
|---|---|---|---|---|---|
| `Asignar` | Page Pagos huérfanos | Ve | Ve | Ve | Ve |
| `Asignar a Customer` | Bank Transaction huérfano | Ve | Ve | Ve | Ve |
| `Vincular pagos` | Page Vinculador | Ve | Ve | Ve | Ve |
| Diálogo `¿Recordar este RUT de origen…?` con `Sí, recordar` / `No` | Tras asignar | Ve | Ve | Ve | Ve |
| `Ver pagador conocido` / `Revisar asociación` | Tras `Sí, recordar` | Ve | Ve | Ve | Ve |
| Sección `Pagadores conocidos` con links | Customer | Ve | Ve | Ve | Ve |
| `Agregar pagador conocido` | Customer | No ve | No ve | Ve | Ve |
| `Ver cliente`, `Ver movimiento de origen` | Known Payer | Ve | Ve | Ve | Ve |
| `Desactivar asociación` | Known Payer activo | No ve | No ve | Ve | Ve |
| `Reactivar asociación` | Known Payer inactivo | No ve | No ve | Ve | Ve |
| Botón `Guardar` / edición de campos | Known Payer | No ve (solo lectura) | No ve (solo lectura) | Ve | Ve |
| Link `Pagador conocido` + método de identificación | Bank Transaction | Ve | Ve | Ve | Ve |
| Botón de desactivación | Bank Transaction | No existe para ningún rol | | | |

Condiciones en código: `Agregar pagador conocido` depende de `can_create` (permiso DocType create); Desactivar/Reactivar dependen de `Accounts Manager` o `System Manager` en `known_payer.js`.

### 18.7 Métodos backend afectados

| Método | Clase | Grupo / control | Validación en servidor |
|---|---|---|---|
| `chile.page.vinculador_pagos.vinculador_pagos.dashboard` | Operativo | `PAYMENT_OPERATION_ROLES` | `frappe.only_for` |
| `chile.page.vinculador_pagos.vinculador_pagos.assign_orphan` | Operativo | `PAYMENT_OPERATION_ROLES` | `frappe.only_for` + `has_vinculador_permission` en `assign_orphan_deposit` |
| `chile.page.vinculador_pagos.vinculador_pagos.enqueue_mapping` | Operativo | `PAYMENT_OPERATION_ROLES` | `frappe.only_for` |
| `chile.deposit_mapping.assign_orphan_deposit` (interno) | Operativo | `PAYMENT_OPERATION_ROLES` | `has_vinculador_permission`; asignación y Payment Entry dentro de `accounting_context` |
| `chile.deposit_mapping.run_deposit_mapping` (job) | Operativo | Corre como el usuario que lo encoló; el scheduler corre como Administrator | Mapeo y realización dentro de `accounting_context`; no depende del rol interactivo cuando lo lanza el scheduler |
| `chile.deposit_mapping.apply_party_for_bank_transaction` (ingesta Banco de Chile) | Sistema | No whitelisted | Sin cambios |
| `chile.known_payer.remember_payer` | Operativo | `PAYMENT_OPERATION_ROLES` | `frappe.only_for` + depósito asignado a ese Customer + candados + inserción controlada (`flags.learning_flow`) |
| `chile.known_payer.customer_known_payers` | Consulta | Permiso DocType read | `frappe.has_permission`; devuelve `can_create` para la UI |
| `chile.known_payer.deactivate` | Administrativo | `KNOWN_PAYER_ADMIN_ROLES` | `frappe.only_for` + bloqueo de fila |
| `chile.known_payer.reactivate` | Administrativo | `KNOWN_PAYER_ADMIN_ROLES` | `frappe.only_for` + bloqueo de fila + candados |
| Alta manual (formulario, `frappe.client.insert`, importación) | Administrativo | `KNOWN_PAYER_ADMIN_ROLES` | Permiso DocType create + `validate_known_payer` rechaza altas sin `learning_flow` de roles no administrativos |
| Edición de Known Payer | Administrativo | Permiso DocType write (Accounts Manager, System Manager) | `customer`, `payer_tax_id`, `source` son set_only_once; `active` solo cambia vía `deactivate`/`reactivate` |
| Borrado físico | Admin técnico | System Manager | Permiso DocType delete solo System Manager |

### 18.8 Permisos de DocType

| DocType | ComercialFRA | Accounts User | Accounts Manager | System Manager |
|---|---|---|---|---|
| Known Payer | read | read, report | create, write, read, report, export, print (sin delete) | completo |
| Bank Transaction | read (nuevo, patch `v0_0_36`) | sin cambios | sin cambios | sin cambios |
| Payment Entry, GL Entry, Journal Entry, configuración contable | **ninguno nuevo** | sin cambios | sin cambios | sin cambios |

Sin permiso write, ComercialFRA y Accounts User no pueden modificar `active`, `disabled_by`, `disabled_on`, `customer` ni `payer_tax_id`.

### 18.9 Backend controlado (sin permisos contables para ComercialFRA)

La asignación y la realización de la Spec 004 (`update_bank_transaction` + `create_payment_entry_bts` de ERPNext) validan permisos del usuario de sesión. Cuando el usuario no tiene `Accounts User`, `Accounts Manager` ni `System Manager`, el backend ejecuta solo ese tramo dentro de `chile.elevation.accounting_context`, siempre después de validar `PAYMENT_OPERATION_ROLES`, y restaura la sesión al terminar. El usuario real queda en `Deposit Mapping Run.requested_by` y como owner del `Deposit Mapping Attempt` de la asignación manual; el Bank Transaction actualizado y el Payment Entry generado en ese tramo quedan con modified_by/owner Administrator.

Lo único que recibe ComercialFRA es: roles del Workspace y de las dos Pages, read en Bank Transaction y read en Known Payer.

### 18.10 Comportamiento ante acceso no autorizado

| Intento | Resultado |
|---|---|
| Rol fuera de `PAYMENT_OPERATION_ROLES` abre Workspace o Page | Frappe no muestra el Workspace; la ruta de la Page devuelve "No permitido" |
| Llamada a método operativo sin `PAYMENT_OPERATION_ROLES` | `frappe.PermissionError` (HTTP 403) desde `frappe.only_for`; sin efectos |
| ComercialFRA o Accounts User llaman `deactivate` / `reactivate` | `frappe.PermissionError` (HTTP 403); la relación no cambia |
| ComercialFRA o Accounts User crean Known Payer fuera de `Sí, recordar` | Rechazo por permiso DocType create; si existiera ese permiso, `validate_known_payer` lanza `PermissionError`: "Solo Accounts Manager o System Manager crean pagadores conocidos fuera de \"Sí, recordar\"." |
| Cambio directo del check `active` | Error "Use Desactivar asociación o Reactivar asociación." |
| ComercialFRA o Accounts User editan la ficha Known Payer | Ficha de solo lectura; una escritura vía API se rechaza por permiso write |
| ComercialFRA abre `/app/known-payer` | Redirección a `pagos-huerfanos` con el aviso de §13.6 |

### 18.11 Decisiones abiertas (bloqueos documentados)

1. **Alcance de la lectura de Bank Transaction.** El read de ComercialFRA es necesario para abrir el detalle y el link a Known Payer, pero alcanza a todos los movimientos bancarios (también retiros). Limitarlo a depósitos de clientes requiere una regla adicional (por ejemplo, condición de consulta por permiso) que esta Spec no define. Decide: Arquitecto / Miguel.
2. **Owner del Payment Entry.** Con ComercialFRA el Payment Entry queda con owner Administrator; el usuario real queda en el Run y en el intento. Decide si es aceptable: Miguel.
3. **Links de Deposit Mapping en el sidebar.** Para ComercialFRA siguen visibles o no según cómo Frappe v16 filtre el sidebar por permisos; si son visibles, al abrirlos Frappe muestra "No permitido". PENDIENTE DE VERIFICACIÓN en el sitio; ocultarlos requiere decisión.

La eliminación física no es una acción operativa: solo System Manager, de forma excepcional.

### 18.12 Checklist de implementación

Marcado `[x]` = implementado en código en `16.0.91`. `[ ]` = pendiente de validación en el sitio o de decisión.

**A. Documentación**

- [x] Actualizar `specs/016-known-payer-bank-attribution/spec.md`.
- [x] Incorporar ambas matrices de permisos.
- [x] Eliminar referencias que dejen ComercialFRA fuera del flujo.
- [x] Actualizar `README.md` y eliminar la frase "ComercialFRA fuera".
- [x] Documentar que ComercialFRA es rol operativo, no administrativo.

**B. Constantes de autorización**

- [x] `PAYMENT_OPERATION_ROLES` = ComercialFRA, Accounts User, Accounts Manager, System Manager (`chile/payment_roles.py`).
- [x] `KNOWN_PAYER_ADMIN_ROLES` = Accounts Manager, System Manager.
- [x] Sin listas divergentes: `deposit_mapping.py`, `vinculador_pagos.py` y `known_payer.py` importan de `payment_roles.py`.

**C. Workspace `Pagos de Clientes`**

- [x] ComercialFRA en roles del Workspace (patch `v0_0_36`).
- [x] Accounts User, Accounts Manager y System Manager continúan.
- [x] Sin permisos adicionales sobre módulos contables.

**D. Page `Pagos huérfanos`**

- [x] ComercialFRA en roles de la Page (patch `v0_0_36`).
- [ ] Confirmar en el sitio que ComercialFRA abre la página directamente.
- [x] `dashboard` acepta ComercialFRA.
- [ ] Confirmar en el sitio que `Asignar` funciona con ComercialFRA.

**E. Vinculador / Pagos de Clientes**

- [x] `vinculador_pagos.py` usa `PAYMENT_OPERATION_ROLES`.
- [x] Todos los `frappe.only_for()` revisados y clasificados (§18.7).

**F. `deposit_mapping.py`**

- [x] `ALLOWED_ROLES` eliminado; `has_vinculador_permission` usa `PAYMENT_OPERATION_ROLES`.
- [x] Solo operaciones del flujo operativo; sin funciones administrativas abiertas.
- [x] El scheduler corre como Administrator y no depende del rol interactivo.
- [x] Idempotencia y concurrencia sin cambios (mismos bloqueos y savepoints).

**G. DocType `Known Payer`**

- [x] ComercialFRA: read. Accounts User: read, report. Accounts Manager: administra. System Manager: completo.
- [x] Sin write para ComercialFRA.
- [x] `Sí, recordar` crea mediante método backend controlado.
- [x] ComercialFRA no puede modificar `active`, `disabled_by`, `disabled_on`, `customer`, `payer_tax_id`.

**H. `known_payer.py`**

- [x] `remember_payer` → `PAYMENT_OPERATION_ROLES`.
- [x] `deactivate` y `reactivate` → `KNOWN_PAYER_ADMIN_ROLES`.
- [x] Alta manual → `KNOWN_PAYER_ADMIN_ROLES` (permiso DocType + validación en servidor).
- [x] Permisos validados en backend aunque el botón esté oculto.
- [x] Candado de RUT activo único y candado de RUT principal sin cambios.

**I. UI de `Known Payer`**

- [x] Ficha de solo lectura para ComercialFRA y Accounts User.
- [x] Desactivar/Reactivar según estado para Accounts Manager y System Manager; ocultos para los demás.
- [x] Backend rechaza llamadas directas no autorizadas.

**J. Customer**

- [x] Sección `Pagadores conocidos` visible para los cuatro roles, con links a Known Payer.
- [x] `Agregar pagador conocido` solo con permiso create (Accounts Manager, System Manager).
- [x] Sin edición inline; desactivar solo desde la ficha Known Payer.

**K. Bank Transaction**

- [x] Método de identificación y link `Pagador conocido` visibles.
- [x] Sin botón Desactivar en Bank Transaction.
- [ ] Alcance de la lectura para ComercialFRA (§18.11, decisión 1).

**L. Seguridad negativa** (en el sitio)

- [ ] ComercialFRA → `deactivate` por API: rechazado.
- [ ] ComercialFRA → `reactivate` por API: rechazado.
- [ ] Accounts User → `deactivate` por API: rechazado.
- [ ] Accounts User → `reactivate` por API: rechazado.
- [ ] ComercialFRA crea Known Payer fuera de `Sí, recordar`: rechazado.
- [ ] Accounts User crea Known Payer fuera de flujo: rechazado.
- [ ] Accounts Manager administra: permitido.
- [ ] System Manager administra: permitido.

**M. Pruebas con ComercialFRA** (en el sitio)

- [ ] Entra a `Pagos de Clientes`.
- [ ] Abre `Pagos huérfanos` y lista huérfanos.
- [ ] Selecciona Customer y ejecuta `Asignar`.
- [ ] Responde `Sí, recordar`; se crea exactamente un Known Payer.
- [ ] Lo abre, lo ve desde Customer y sigue el link desde Bank Transaction.
- [ ] No ve `Desactivar` ni `Reactivar`, y no puede ejecutarlos por API.
- [ ] No obtiene permisos generales de contabilidad (Payment Entry, GL Entry, Journal Entry).

**N. Pruebas con Accounts User** (en el sitio)

- [ ] Opera pagos y aprende Known Payer desde el flujo.
- [ ] Consulta Known Payer.
- [ ] No desactiva, no reactiva, no crea manualmente.

**O. Pruebas con Accounts Manager** (en el sitio)

- [ ] Opera pagos y crea Known Payer desde aprendizaje.
- [ ] Crea Known Payer manualmente.
- [ ] Desactiva y reactiva.
- [ ] Revisa la ListView.
- [ ] Los candados continúan funcionando.

**P. Pruebas con System Manager** (en el sitio)

- [ ] Ejecuta todos los flujos y administra Known Payer sin romper validaciones de integridad.

**Q. No regresión funcional** (en el sitio)

- [ ] RUT principal sigue teniendo prioridad.
- [ ] Segundo depósito de Known Payer se atribuye automáticamente.
- [ ] Al desactivar, el siguiente depósito vuelve a huérfano si no hay otra regla.
- [ ] No se duplica Payment Entry.
- [ ] No se aplica dinero automáticamente a OV.
- [ ] No se altera la evidencia bancaria original.
- [ ] El scheduler de mapping sigue funcionando.
- [ ] La asignación manual existente sigue funcionando.

---

## 19. Integridad permanente

Deben cumplirse siempre:

~~~text
RUT principal Customer
    → máximo 1 Customer según regla de identidad vigente

RUT Known Payer activo
    → máximo 1 Customer

RUT principal de Customer A
    != Known Payer activo de Customer B
~~~

No confiar en frontend.

El Programador debe proponer en su plan el mecanismo soportado por Frappe/MariaDB para garantizar concurrencia e integridad.

---

## 20. Idempotencia y concurrencia

Casos mínimos:

1. doble clic en Sí, recordar → un solo Known Payer;
2. dos usuarios crean el mismo RUT para el mismo Customer → un solo registro activo;
3. dos usuarios crean el mismo RUT para Customers distintos → uno falla controladamente;
4. scheduler usa una relación mientras otro usuario la desactiva → resultado consistente;
5. reejecutar mapping sobre Bank Transaction correctamente atribuido → no duplicar Payment Entry.

---

## 21. Históricos

No realizar migración masiva de depósitos anteriores en esta primera entrega.

No inferir relaciones por nombre parecido, monto, texto libre, cuenta o frecuencia.

La base de Known Payer crecerá inicialmente mediante:

- aprendizaje explícito al resolver huérfanos;
- alta manual autorizada.

Una futura herramienta podría proponer relaciones históricas. Queda fuera de esta Spec.

---

## 22. Casos de aceptación funcional

### AC-01 — primer depósito de tercero

Customer María Pérez tiene RUT A. Llega depósito con RUT B sin relación previa. Debe quedar huérfano.

### AC-02 — aprendizaje

Usuario asigna el huérfano a María Pérez y RUT B != RUT A. Debe aparecer la pregunta de recordar.

### AC-03 — responder No

El depósito actual queda asignado; no se crea Known Payer.

### AC-04 — responder Sí

Se crea exactamente un Known Payer activo RUT B → María Pérez, con usuario, fecha y movimiento origen.

### AC-05 — segundo depósito

Con Known Payer activo RUT B → María, un nuevo depósito RUT B identifica automáticamente a María y no queda huérfano.

### AC-06 — no asignación a OV

Aunque María tenga varias OVs, esta Spec no elige ninguna.

### AC-07 — desactivación

Desactivar deja active = 0, registra usuario/fecha y no modifica movimientos históricos.

### AC-08 — depósito posterior

Tras desactivar, el siguiente depósito RUT B ya no se resuelve mediante esa relación y vuelve a huérfano si no existe otra regla.

### AC-09 — reasignación

Con la relación anterior inactiva, se permite RUT B → Carolina ACTIVE conservando histórico.

### AC-10 — conflicto entre Customers

Con RUT B → María ACTIVE, intentar RUT B → Carolina ACTIVE debe bloquear.

### AC-11 — conflicto con RUT principal

Si Juan tiene Customer.tax_id = RUT B, no se permite RUT B → María como Known Payer.

### AC-12 — duplicado exacto

Repetir creación RUT B → María ACTIVE no duplica.

### AC-13 — link desde Customer

Customer muestra Pagadores conocidos y cada fila abre Known Payer.

### AC-14 — link desde Bank Transaction

Movimiento identificado por Known Payer muestra el método y link a la relación.

### AC-15 — confirmación de desactivación

Pulsar Desactivar asociación muestra el diálogo de §13.3 y no cambia estado hasta confirmar.

---

## 23. Pruebas automáticas mínimas

1. Customer.tax_id tiene prioridad;
2. resolución por Known Payer;
3. Known Payer inactivo no resuelve;
4. no duplicar relación exacta;
5. impedir mismo RUT activo en dos Customers;
6. impedir usar como Known Payer el tax_id principal de otro Customer;
7. permitir nueva asociación después de desactivar;
8. reactivación bloqueada si surgió conflicto;
9. aprendizaje idempotente;
10. Known Payer no aplica a Sales Order;
11. no duplicar Payment Entry;
12. conservar evidencia bancaria original;
13. método de identificación auditable;
14. actualizar last_used_on;
15. permisos de roles;
16. concurrencia no permite relaciones activas incompatibles.

---

## 24. Pruebas UI obligatorias en sandbox

### Flujo A — aprender

~~~text
Pagos de Clientes
→ Pagos huérfanos
→ seleccionar Customer
→ Asignar
→ Sí, recordar
→ abrir Pagador conocido
~~~

### Flujo B — reutilizar

~~~text
nuevo depósito mismo RUT
→ mapping
→ Customer automático
→ Bank Transaction muestra Pagador conocido
→ link abre relación
~~~

### Flujo C — desactivar

~~~text
Customer
→ Pagadores conocidos
→ abrir RUT
→ Desactivar asociación
→ confirmar
→ nuevo depósito deja de autoasignarse
~~~

### Flujo D — conflicto

Intentar registrar el mismo RUT activo para otro Customer y verificar bloqueo.

### Flujo E — RUT principal

Intentar registrar como pagador de B un RUT que ya es tax_id de A y verificar bloqueo.

### Flujo F — permisos por rol (§18)

Usuario solo `ComercialFRA`:

1. entra a Pagos de Clientes;
2. ve Pagos huérfanos;
3. asigna un huérfano;
4. responde Sí, recordar;
5. puede abrir el Known Payer creado;
6. no puede desactivarlo;
7. no puede reactivarlo;
8. no accede a administración contable general.

Usuario `Accounts User`: mismo flujo operativo, sin desactivar/reactivar.
Usuario `Accounts Manager`: flujo completo; crea manualmente, desactiva, reactiva y administra relaciones.
Usuario `System Manager`: control completo.

Detalle obligatorio de pruebas positivas y negativas: checklist §18.12, bloques L a Q. Cada prueba se ejecuta con un usuario que tenga **solo** el rol bajo prueba.

---

## 25. No alcance

Esta Spec NO incluye:

- cambiar el RUT principal del Customer;
- múltiples identidades tributarias del Customer;
- fuzzy matching por nombre;
- aprendizaje automático sin confirmación humana;
- inferencia histórica masiva;
- asignación automática a OV;
- creación de Customer desde el banco;
- nuevo circuito contable;
- reemplazo de Bank Transaction;
- modificación de evidencia original;
- rediseño completo de Pagos de Clientes;
- cambio del scheduler salvo para reutilizar la nueva resolución;
- nueva integración Banco de Chile en tiempo real.

---

## 26. Componentes candidatos

El Programador debe inspeccionar el código actual antes de fijar rutas definitivas.

Cambios probables dentro de erpn_custom:

- nuevo DocType Known Payer;
- módulo de dominio en erpn_custom/chile/ para resolución/validación;
- integración con deposit_mapping.py o servicio equivalente de Spec 004;
- JS/UI de Pagos de Clientes;
- personalización de Customer para Pagadores conocidos;
- personalización de Bank Transaction para trazabilidad/link;
- permisos, fixtures o patches reproducibles;
- pruebas unitarias e integración.

No modificar core ERPNext/Frappe.

---

## 27. Invariantes

1. El RUT principal del Customer no cambia por un pagador alternativo.
2. Pagador y Customer son identidades distintas.
3. Un RUT pagador activo pertenece como máximo a un Customer.
4. Un RUT principal de Customer no puede ser pagador activo de otro Customer.
5. Toda relación puede desactivarse.
6. Desactivar no reescribe movimientos históricos.
7. Identificar Customer no significa aplicar dinero a una OV.
8. La evidencia bancaria original nunca se altera.
9. Toda resolución automática debe poder explicarse.
10. Toda UI necesaria para operar y administrar esta feature queda definida por esta Spec.

---

## 28. Regla de diseño UI para esta y futuras Specs

A partir de esta Spec, toda especificación funcional del proyecto que introduzca o modifique una capacidad operativa debe definir explícitamente su gestión UI.

Como mínimo, cuando aplique, debe cerrar:

- dónde vive la función;
- cómo llega el usuario;
- pantalla, formulario o listado;
- botones y acciones;
- links entre documentos;
- estados visibles;
- mensajes de confirmación y error;
- permisos de interacción;
- alta;
- edición;
- desactivación o cancelación;
- revisión y auditoría.

No se debe dejar la experiencia operativa abierta a criterio del Programador.

Si una feature no requiere UI, la Spec debe decirlo explícitamente.

---

## 29. Handoff obligatorio al Programador

Antes de programar, el Programador debe:

1. trabajar exclusivamente desde ERPnext-custom/erpn_custom/;
2. leer README.md, esta Spec 016, Spec 004 y manual-orphan-payment-assignment.md;
3. inspeccionar el código actualmente desplegado de Pagos de Clientes;
4. identificar la función canónica actual de normalización de RUT;
5. identificar el servicio real que resuelve Customer y realiza Payment Entry;
6. verificar campos de trazabilidad existentes antes de crear otros;
7. aplicar los grupos `PAYMENT_OPERATION_ROLES` y `KNOWN_PAYER_ADMIN_ROLES` según §18 (matrices, métodos y checklist); toda decisión de permisos no cubierta por §18 se documenta como bloqueo en §18.11;
8. proponer mecanismo de integridad y concurrencia para los candados;
9. presentar plan de archivos, patch/migración, UI y pruebas antes de escribir código;
10. no ampliar alcance hacia aplicación automática a OV ni aprendizaje heurístico.

El cambio debe ser incremental sobre Spec 004, no una reescritura del subsistema bancario.

---

## 30. Criterio de cierre

La Spec 016 se considera cerrada únicamente cuando en sandbox se demuestre:

~~~text
primer depósito de RUT alternativo
→ huérfano
→ asignación manual a Customer
→ ¿Recordar este RUT?
→ Sí
→ Known Payer activo

segundo depósito del mismo RUT
→ Customer identificado automáticamente
→ trazabilidad Known Payer
→ no huérfano

Customer
→ Pagadores conocidos
→ abrir relación
→ Desactivar asociación

tercer depósito del mismo RUT
→ ya no se atribuye por esa relación
→ vuelve a revisión si no existe otra regla
~~~

Y además se comprueban ambos candados:

~~~text
mismo RUT pagador activo en otro Customer → BLOQUEADO
RUT principal de otro Customer como Known Payer → BLOQUEADO
~~~

Permisos (§18). No basta con que ComercialFRA vuelva a ver el Workspace; debe comprobarse la cadena completa:

~~~text
ComercialFRA
→ Pagos de Clientes
→ Pagos huérfanos
→ Asignar
→ Sí, recordar
→ Known Payer creado
→ consulta permitida
→ administración bloqueada
~~~

y simultáneamente:

~~~text
Accounts Manager
→ Known Payer
→ Desactivar
→ Reactivar
→ permitido
~~~

La Spec 016 no se considera lista para cierre hasta que:

1. la matriz esté reflejada en código;
2. la UI respete esa matriz;
3. el backend valide esa matriz independientemente de la UI;
4. los cuatro perfiles hayan sido probados (checklist §18.12, bloques L a Q), con permisos positivos y negativos;
5. no se hayan entregado permisos contables innecesarios a ComercialFRA;
6. las decisiones abiertas de §18.11 estén resueltas por Miguel o el Arquitecto.

La aceptación debe incluir pruebas automáticas, prueba UI con usuario operativo y evidencia de que no se duplicaron Payment Entries ni se modificó la evidencia bancaria original.
