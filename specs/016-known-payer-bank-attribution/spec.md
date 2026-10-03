# Spec 016 — Pagadores conocidos para atribución bancaria recurrente

**Estado:** ACTIVA — lista para revisión e implementación por Programador
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

Acción:

**Agregar pagador conocido**

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

- si está activo: **Desactivar asociación**;
- si está inactivo y no existe conflicto: **Reactivar asociación**;
- **Ver cliente**;
- **Ver movimiento de origen**, cuando exista.

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
→ Desactivar asociación
~~~

No poner un botón directo de desactivación dentro de Bank Transaction.

## 13.6 ListView administrativa

Debe existir ListView estándar de Known Payer para roles autorizados.

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

Known Payer List puede quedar disponible mediante Desk/búsqueda para perfiles administrativos.

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

El Programador debe verificar los roles reales ya utilizados por Pagos de Clientes. No inventar roles nuevos sin necesidad.

### ComercialFRA / rol operativo equivalente

Debe poder:

- ver pagadores conocidos;
- crear una relación desde **Sí, recordar**;
- abrir el Known Payer;
- agregar manualmente un pagador si corresponde a sus permisos funcionales.

### Rol financiero/administrativo equivalente

Debe poder:

- crear;
- desactivar;
- reactivar;
- consultar ListView e histórico.

### System Manager

Control completo.

La eliminación física no debe ser una acción operativa normal para ComercialFRA.

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
7. revisar permisos reales de ComercialFRA y roles financieros;
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

La aceptación debe incluir pruebas automáticas, prueba UI con usuario operativo y evidencia de que no se duplicaron Payment Entries ni se modificó la evidencia bancaria original.
