# Feature Specification: ENC — Encargos, compra Miami y conciliación en recepción Chile

**Feature Branch**: `[013-encargo-preventa-recepcion]`

**Created**: 2026-09-23

**Status**: **ACTIVE — PLANIFICACIÓN TÉCNICA AUTORIZADA**. Spec vigente después del cierre aceptado de `012-sales-person-auto-commission`. El Programador debe inspeccionar ERPNext/Frappe v16, presentar plan técnico y pruebas contra esta Spec y esperar OK explícito de Miguel antes de escribir código.

**Parent context**: arquitectura FRAgallardo, flujo Encargo/Preventa, Sales Order, compras Miami, recepción de cajas Chile, Item/Barcode de ERPNext/Frappe v16.

## 0. Propósito de este documento

Definir de forma implementable el proceso de **Encargos (ENC)**: generación desde Sales Order, separación entre stock disponible y cantidad por abastecer, lista mínima para shopper Miami y conciliación posterior en recepción Chile.

La necesidad nace de ventas en las que el cliente encarga un producto que:

- puede haber sido comprado/vendido anteriormente y ya existir como Item maestro;
- puede no haber sido comprado nunca y todavía no tener Item maestro;
- puede conocerse inicialmente sólo por una foto de WhatsApp, descripción, marca, tienda, talla/color y precio;
- será comprado por un shopper externo en Miami;
- será recibido físicamente en Chile, donde FRA sí puede identificar objetivamente el producto.

La arquitectura debe evitar:

- crear Items duplicados por descripciones parecidas;
- exigir al shopper conocimientos o tareas propias del ERP;
- convertir una foto o descripción en una identidad de producto;
- vincular erróneamente una compra al cliente;
- perder la solicitud original del cliente;
- mezclar stock libre con unidades comprometidas a encargos.

---

## 1. Principio rector

Cada actor registra únicamente aquello que realmente conoce y controla:

```text
VENDEDOR
"sé qué pidió el cliente"
        ↓
ENC

SHOPPER MIAMI
"sé si logré comprarlo"
        ↓
estado de compra

RECEPCIÓN CHILE
"sé qué producto físico llegó"
        ↓
identidad real / Item

ERP
"sé a qué ENC corresponde o si queda como stock"
```

Regla principal:

> **ENC representa la obligación comercial. Item representa la identidad objetiva del producto. No son el mismo concepto.**

---

## 2. Entidad ENC

Crear un DocType custom de negocio, nombre funcional **Encargo** y numeración:

```text
ENC-YYYY-#####
```

Ejemplo:

```text
ENC-2026-00127
```

El ENC debe conservar la solicitud original del cliente aunque la identidad del Item sea desconocida al momento de vender.

### 2.1 Datos mínimos/sugeridos del ENC

El diseño definitivo de campos se confirmará antes de implementar, pero conceptualmente debe soportar:

- Sales Order vinculada;
- línea/origen de la Sales Order cuando corresponda;
- Customer;
- vendedor;
- descripción libre del producto solicitado;
- imagen principal de referencia;
- imágenes/adjuntos adicionales opcionales;
- marca;
- tienda sugerida;
- modelo, si se conoce;
- talla, si aplica;
- color, si aplica;
- cantidad;
- URL de referencia opcional;
- precio de venta acordado;
- precio/tope de compra u observación de precio, si corresponde;
- observaciones de compra;
- Item esperado/conocido, opcional;
- Item resuelto definitivo, cuando corresponda;
- estados de compra y recepción;
- trazabilidad de fechas/usuarios.

No todos los atributos de producto deben ser obligatorios. Una captura de WhatsApp más una descripción suficiente puede iniciar un ENC.

### 2.2 ENC no es una bodega ni una tabla paralela de productos

**Decisión arquitectónica:** ENC no se implementará como `Warehouse` de ERPNext y tampoco como un segundo maestro de productos.

Un Warehouse representa existencia física o logística de Items identificados. Un ENC puede existir cuando:

- todavía no existe producto físico bajo control de FRA;
- todavía no existe Item maestro;
- sólo existe una obligación comercial de conseguir algo para un cliente.

Por tanto crear una “Bodega Encargos” produciría una semántica incorrecta: parecería que FRA posee stock cuando en realidad sólo posee una demanda pendiente.

El ENC debe entenderse como una **bandeja/cola de abastecimiento comprometido**:

```text
ALMACÉN / STOCK
= lo que FRA tiene

ENC
= lo que FRA debe conseguir para un cliente
```

Puede existir una vista operacional llamada, por ejemplo, **Encargos pendientes**, que visualmente se comporte como una bandeja de productos por comprar, pero técnicamente sigue siendo una lista de documentos `Encargo`, no un Warehouse ni un Stock Ledger paralelo.

### 2.3 Disparador desde la venta

El vendedor comienza desde el almacén de venta/default.

Regla conceptual:

```text
Cliente solicita cantidad Q
        ↓
consultar disponibilidad real del almacén de venta
        ↓
¿stock disponible >= Q?
   ├─ Sí → venta normal desde stock
   └─ No → cantidad faltante genera ENC
```

Ejemplo:

```text
Cliente compra: 3
Stock Matriz:   1

Atención desde stock: 1
Cantidad ENC:         2
```

El ENC corresponde únicamente a la **cantidad no abastecida por stock disponible**, evitando considerar como encargo aquello que ya puede entregarse normalmente.

### 2.4 Dos tipos de origen, una sola entidad ENC

No crear dos clases diferentes de ENC. El mismo DocType cubre ambos casos:

**A. Item conocido, sin stock suficiente**

```text
ITEM-004381 existe
Stock disponible: 0
Cliente pide: 1

ENC-2026-00127
Item esperado: ITEM-004381
Cantidad: 1
```

Aquí no se crea ningún producto nuevo. Miami debe conseguir ese Item/variante.

**B. Producto todavía no identificado**

```text
Item: desconocido
Foto: sí
Descripción: sí
Marca/Tienda/Talla/Color: según disponibilidad

ENC-2026-00128
Item esperado: vacío
Cantidad: 1
```

La identidad del Item se resolverá posteriormente en recepción.

### 2.5 ENC como compromiso de cantidad, no existencia

Mientras un ENC está:

- pendiente de compra;
- marcado comprado por el shopper;
- viajando;
- pendiente de recepción;

su cantidad **no debe incrementar stock disponible** ni presentarse como existencia utilizable para otra venta.

Sólo después de la recepción física y del ingreso correspondiente al inventario existe stock ERPNext.

Una unidad recibida que satisface un ENC queda comprometida con ese ENC; una unidad recibida sin ENC compatible queda disponible como stock normal.

---

## 3. Imagen de referencia como dato operacional

La imagen no es decorativa. Es evidencia de **qué pidió el cliente** y ayuda al shopper a encontrar el producto.

Requisito de UX futuro:

```text
Imagen de referencia
[ pegar desde portapapeles ] [ arrastrar ] [ seleccionar archivo ]
```

La implementación debe permitir al vendedor:

1. copiar una imagen/captura, por ejemplo desde WhatsApp;
2. pegarla directamente con Ctrl+V o equivalente;
3. guardarla como `File` de Frappe vinculada al ENC;
4. verla como miniatura en las vistas operativas.

El comportamiento de pegado desde portapapeles debe ser **explícitamente implementado/probado**. No asumir que el control estándar `Attach Image` cubre por sí solo esta experiencia.

La imagen original del ENC debe preservarse como referencia histórica aunque posteriormente el ENC se vincule a un Item maestro con otra imagen de catálogo.

---

## 4. Item conocido vs Item todavía desconocido

Al crear un ENC existen dos situaciones válidas.

### 4.1 Producto ya conocido

Si el vendedor encuentra de manera inequívoca un Item existente, el ENC puede guardar:

```text
Item esperado = ITEM-xxxxx
```

Esto no elimina el ENC. El ENC sigue siendo necesario para representar la obligación de compra/abastecimiento para ese cliente.

### 4.2 Producto todavía desconocido

Si sólo existe descripción/foto/referencia:

```text
Item esperado = vacío
Item definitivo = pendiente
```

Esto es un estado válido y no debe obligar a crear un Item ficticio.

### 4.3 Regla anti-duplicación

No crear un Item maestro únicamente desde:

- descripción libre;
- foto;
- parecido visual;
- nombre escrito por vendedor;
- nombre de tienda;
- búsqueda aproximada.

La identidad del Item se resolverá cuando exista evidencia suficiente, principalmente durante recepción Chile.

---

## 5. Rol del shopper Miami

El shopper **no es empleado FRA** y su interfaz no debe exponerle complejidad de ERPNext.

No debe tener responsabilidad sobre:

- crear Item;
- editar Item;
- resolver duplicados;
- asignar UPC/EAN;
- crear Purchase Receipt;
- manejar Warehouse;
- decidir contabilidad;
- conciliar ENC contra Item;
- decidir si una compra errónea satisface el ENC.

Su función es únicamente **comprar**.

---

## 6. Lista operativa del shopper

Debe existir una vista/página ligera de ENC pendientes de compra.

Objetivo visual:

```text
MIAMI — COMPRAS PENDIENTES

NIKE OUTLET
----------------------------------
☐ ENC-2026-00127  [foto]
  Pegasus 41 / Negro / US 9
  Cantidad 1

☐ ENC-2026-00134  [foto]
  Air Max / Blanco / US 8
  Cantidad 1

ROSS
----------------------------------
☐ ENC-2026-00141  [foto]
  Samsonite Carry-on negra
  Cantidad 1
```

La vista debe permitir al menos:

- ordenar/agrupar por tienda;
- ordenar/filtrar por marca;
- ver foto;
- ver descripción relevante;
- ver talla/color/cantidad cuando existan;
- marcar estado simple.

Estados/acciones mínimas para shopper:

```text
PENDIENTE
COMPRADO
NO ENCONTRADO
```

El shopper no debe cerrar el ENC comercial.

---

## 7. Significado de “COMPRADO”

Cuando el shopper marca:

```text
COMPRADO
```

significa exclusivamente:

> “El shopper declara que realizó una compra intentando satisfacer este ENC.”

No significa:

- Item identificado definitivamente;
- producto recibido por FRA;
- ENC satisfecho;
- producto correcto;
- ingreso a inventario;
- entrega al cliente.

Registrar como mínimo:

- ENC;
- estado de compra;
- fecha/hora;
- identidad del shopper o mecanismo equivalente de auditoría.

---

## 8. Acceso del shopper

El mecanismo técnico se decidirá en fase de diseño, pero debe cumplir privilegio mínimo.

La solución futura puede ser una vista web específica, Portal u otro mecanismo ligero. No debe requerir acceso general al Desk de ERPNext.

No exponer al shopper información innecesaria como:

- saldos de cliente;
- datos bancarios;
- contabilidad;
- márgenes completos;
- otros módulos;
- datos personales del cliente que no sean necesarios para comprar.

No crear una página Guest pública sin control de acceso.

---

## 9. Punto de control definitivo: recepción Chile

La conciliación definitiva debe ocurrir cuando FRA recibe físicamente la mercadería.

La recepción no debe comenzar preguntando “¿Encargo o Stock?”.

Primero debe responder:

> **¿Qué producto físico tengo delante?**

Flujo conceptual:

```text
Caja recibida
    ↓
Sacar producto
    ↓
Escanear / identificar producto
    ↓
Resolver Item maestro
    ↓
Buscar ENC compatibles pendientes
    ↓
Humano confirma asignación
    ↓
ENC o STOCK
```

---

## 10. Resolución del Item maestro

Prioridad conceptual de identificación:

1. UPC/EAN/GTIN o barcode objetivo;
2. Item existente ya vinculado/esperado;
3. fabricante + MPN/modelo + variante, cuando sea suficientemente inequívoco;
4. atributos objetivos adicionales;
5. resolución manual controlada si no existe identificador universal.

Si el barcode ya pertenece a un Item:

```text
barcode
  -> Item existente
  -> reutilizar Item
```

Si no existe un Item suficientemente identificado:

```text
producto físico real
  -> crear Item una sola vez
  -> registrar barcode/identificadores
```

La implementación debe impedir o detectar que el mismo identificador objetivo termine creando Items duplicados.

---

## 11. Variantes

La identidad debe llegar hasta la variante real cuando sea relevante.

Ejemplo:

```text
Nike Pegasus 41
  ├─ Negro / US 8
  ├─ Negro / US 9   <- producto solicitado
  └─ Blanco / US 9
```

Modelo, color y talla pueden representar productos transaccionables distintos.

No considerar suficiente la coincidencia sólo a nivel de plantilla/modelo cuando la solicitud del ENC exige una variante específica.

---

## 12. Conciliación Producto recibido -> ENC

Una vez resuelto el Item físico, la recepción debe buscar ENC comprados/pendientes compatibles.

Ejemplo:

```text
ITEM-006721
Nike Pegasus 41 / Negro / US9

ENC compatibles:
- ENC-2026-00127
  Cliente ...
  [imagen original]
  Negro / US9
```

La interfaz puede **sugerir candidatos**, pero la vinculación definitiva debe ser confirmada por una persona de FRA.

No permitir que:

- IA;
- similitud de imagen;
- fuzzy matching;
- descripción aproximada

cierren automáticamente la asignación.

Pueden ayudar a ordenar candidatos, nunca reemplazar la confirmación determinística.

---

## 13. Resultado de recepción: sólo ENC o STOCK

Cada unidad recibida debe terminar operacionalmente en uno de estos destinos:

```text
PRODUCTO RECIBIDO
       ↓
¿satisface un ENC pendiente?
       |
   +---+---+
   |       |
  Sí       No
   |       |
 ENC     STOCK
```

No crear una categoría permanente de inventario llamada “error de compra”.

---

## 14. Compra equivocada

Si el shopper compra el producto equivocado:

### Caso A — se devuelve en Miami

- el producto no ingresa al inventario FRA;
- el ENC sigue pendiente hasta que se compre correctamente.

### Caso B — no se devuelve y llega a Chile

- se identifica el Item real;
- se ingresa como stock normal;
- **no** se fuerza su vínculo al ENC;
- el ENC original vuelve/permanece pendiente de compra.

Ejemplo:

```text
ENC pide: Pegasus Negro US9
llega:    Pegasus Negro US10

US10 -> STOCK
ENC US9 -> PENDIENTE DE COMPRA
```

La compra errónea no modifica la solicitud original del ENC.

---

## 15. Solicitud original inmutable

Los campos que representan **qué pidió el cliente** deben conservar evidencia histórica.

Una sustitución, error o nueva compra no debe reescribir silenciosamente la solicitud original para hacerla coincidir con lo comprado.

Si en el futuro existe una sustitución aceptada por el cliente, debe registrarse como evento/decisión explícita y auditable, no como edición destructiva de la evidencia original.

---

## 16. Múltiples unidades idénticas

El mismo Item puede satisfacer varios ENC y además dejar saldo de stock.

Ejemplo:

```text
5 unidades recibidas de ITEM-006721

ENC-0127 -> 1
ENC-0151 -> 1
ENC-0168 -> 1
STOCK    -> 2
```

Por tanto:

> **“Encargo” y “Stock” no son tipos de producto. Son destinos/compromisos de unidades del mismo Item.**

---

## 17. Estados conceptuales del ENC

El modelo definitivo se validará antes de programar. Como base:

```text
CREADO
  ↓
PENDIENTE DE COMPRA
  ↓
COMPRADO / PENDIENTE RECEPCIÓN
  ↓
RECIBIDO / PENDIENTE CONCILIACIÓN
  ↓
SATISFECHO
  ↓
DISPONIBLE PARA EMPAQUE
  ↓
ENTREGADO
```

Rutas alternativas:

```text
PENDIENTE DE COMPRA
  -> NO ENCONTRADO
  -> PENDIENTE DE COMPRA

COMPRADO
  -> RECEPCIÓN INCORRECTA
  -> producto recibido pasa a STOCK
  -> ENC vuelve a PENDIENTE DE COMPRA
```

Evitar utilizar un único campo de estado para mezclar conceptos distintos si durante diseño resulta más limpio separar:

- estado comercial;
- estado de compra Miami;
- estado de recepción/conciliación.

---

## 18. Relación con Sales Order — decisión implementable

El ENC debe quedar trazablemente vinculado a la Sales Order y a la fila concreta que originó la obligación.

### 18.1 Item conocido

Si el Item ya existe, la Sales Order conserva el **Item real** y la cantidad total solicitada por el cliente.

Ejemplo:

```text
SO Item: ITEM-004381
Cantidad vendida: 3
Disponible para comprometer: 1

stock_committed_qty = 1
encargo_qty         = 2
ENC-2026-xxxxx      = 2 x ITEM-004381
```

No dividir la venta en dos Items distintos y no crear un Item duplicado.

Agregar en `Sales Order Item` campos custom de trazabilidad, nombres técnicos finales a confirmar por el Programador:

- `encargo` — Link a Encargo;
- `encargo_qty` — cantidad que debe abastecerse;
- `stock_committed_qty` — cantidad cubierta por stock al confirmar la OV.

Los campos serán read-only para usuario normal y calculados server-side.

### 18.2 Cálculo del faltante

Para un Item de stock, antes de Submit:

```text
available_to_sell = max(actual_qty - reserved_qty_previa, 0)
stock_committed   = min(qty_solicitada, available_to_sell)
encargo_qty       = qty_solicitada - stock_committed
```

El cálculo debe:

- usar el Warehouse de la fila; si la organización tiene un almacén de venta/default configurado, la fila debe llegar con ese Warehouse;
- considerar de forma agregada filas repetidas del mismo Item + Warehouse dentro de la misma OV;
- excluir del cálculo la reserva generada por la propia OV que todavía se está confirmando;
- ser idempotente;
- ser seguro frente a concurrencia, reutilizando mecanismos estándar de reserva/bloqueo de ERPNext en vez de crear un ledger paralelo.

ERPNext v16 dispone de Stock Reservation. La implementación debe **reutilizar Stock Reservation Entry / API estándar** para reservar la porción `stock_committed_qty` cuando la función esté habilitada. No implementar un sistema custom de reservas.

### 18.3 Producto desconocido al vender

ERPNext Sales Order trabaja con Items. Para representar una venta cuyo producto real todavía no está identificado se utilizará **un único Item técnico reutilizable y no-stock**, por ejemplo:

```text
ENCARGO-PENDIENTE
Maintain Stock = 0
```

Este Item:

- no representa un producto físico;
- no se duplica por cada encargo;
- no lleva stock;
- no crea Warehouse ni Stock Ledger;
- existe sólo como soporte comercial para que la OV conserve cantidad, precio, impuestos y trazabilidad.

Para una fila `ENCARGO-PENDIENTE`:

```text
stock_committed_qty = 0
encargo_qty         = qty de la fila
encargo             = obligatorio
```

La descripción de la fila debe reflejar de forma legible el pedido del cliente, pero la fuente de verdad detallada es el documento ENC.

### 18.4 Creación del ENC desconocido desde la OV

En Sales Order Draft debe existir una acción clara:

```text
[ Agregar Encargo ]
```

La acción abre un diálogo/formulario para capturar:

- descripción;
- cantidad;
- precio de venta;
- imagen de referencia;
- marca;
- tienda sugerida;
- modelo;
- talla;
- color;
- URL;
- observaciones.

Al confirmar:

1. la OV debe estar guardada para tener nombre estable;
2. se crea un ENC en estado `BORRADOR`;
3. se agrega/actualiza la fila `ENCARGO-PENDIENTE`;
4. la fila queda vinculada al ENC;
5. al Submit de la OV el ENC pasa a `PENDIENTE DE COMPRA`.

No permitir Submit de una fila `ENCARGO-PENDIENTE` sin ENC vinculado.

### 18.5 Creación automática para Item conocido sin stock suficiente

Para filas de Item real:

1. en `before_submit` calcular `stock_committed_qty` y `encargo_qty`;
2. si `encargo_qty = 0`, no crear ENC;
3. si `encargo_qty > 0`, crear exactamente un ENC para esa fila y faltante;
4. copiar Item, descripción, marca e imagen del Item cuando existan;
5. dejar tienda sugerida y otros datos de compra editables por ComercialFRA;
6. enlazar ENC ↔ Sales Order ↔ Sales Order Item;
7. evitar duplicación si el hook se reintenta.

### 18.6 No reescribir la OV al resolver el Item real

Cuando un ENC originalmente desconocido se resuelve en recepción:

- no reemplazar `ENCARGO-PENDIENTE` dentro de una Sales Order ya submitted;
- guardar el Item real en `Encargo.resolved_item`;
- usar el Item real para inventario, recepción y Empaque;
- conservar la fila comercial original como evidencia de lo vendido.

La trazabilidad queda:

```text
Sales Order
  -> Sales Order Item (ENCARGO-PENDIENTE)
      -> ENC
          -> resolved_item = ITEM real
```

Esto evita cancelar/amendar la OV sólo para resolver una identidad que era desconocida al vender.

---

## 19. Recepción de cajas

Esta Spec debe integrarse posteriormente con la futura página/aplicativo de **Recepción de cajas**.

La recepción debe permitir separar operacionalmente:

- mercadería destinada a ENC;
- mercadería destinada a stock;
- compras equivocadas que terminan como stock.

El flujo de caja/packing unit exacto se diseñará cuando se trabaje el módulo de almacén/recepción.

No inventar ahora una estructura definitiva de cajas, seriales o unidades físicas que todavía no ha sido validada operacionalmente.

---

## 20. Auditoría mínima

Registrar de manera auditable:

- creación del ENC;
- Sales Order origen;
- solicitud original;
- imagen original;
- vendedor;
- cambios de estado;
- shopper que marca compra;
- fecha de compra declarada;
- recepción;
- Item resuelto;
- usuario FRA que confirma la conciliación;
- destino ENC o stock;
- reapertura por compra equivocada;
- fecha de satisfacción.

Evitar borrar evidencia histórica para “corregir” errores operacionales.

---

## 21. Fuera de alcance de esta primera Spec

Hasta nueva decisión, esta Spec no define:

- pago al shopper;
- cuentas por pagar del shopper;
- liquidación de gastos;
- compra contable completa;
- Purchase Order automática;
- Purchase Receipt definitivo;
- importación aduanera;
- cálculo de costo landed;
- cajas Miami definitivas;
- courier Miami -> Chile;
- etiquetado físico;
- serialización por unidad;
- devoluciones contables;
- sustituciones aceptadas por cliente;
- reserva de stock final;
- Shopify;
- interfaz completa de almacén;
- IA de reconocimiento visual como fuente de verdad.

---

## 22. User stories

### US1 — Encargo de producto desconocido (P1)

**Given** el cliente envía una foto de WhatsApp y descripción,  
**When** el vendedor crea la venta,  
**Then** puede crear un ENC sin Item maestro definitivo,  
**And** conserva imagen, descripción y datos útiles de compra.

### US2 — Producto ya conocido (P1)

**Given** el producto ya existe inequívocamente como Item,  
**When** el vendedor crea el ENC,  
**Then** puede registrar ese Item como esperado,  
**And** el ENC sigue existiendo como obligación de abastecimiento.

### US3 — Shopper compra (P1)

**Given** un ENC está pendiente,  
**When** el shopper marca COMPRADO,  
**Then** se registra la compra declarada,  
**But** el ENC todavía no se considera satisfecho.

### US4 — Recepción encuentra Item existente (P1)

**Given** llega un producto con barcode ya conocido,  
**When** recepción lo escanea,  
**Then** se reutiliza el Item existente,  
**And** no se crea un duplicado.

### US5 — Recepción de producto nuevo (P1)

**Given** llega un producto que no existe en catálogo,  
**When** recepción dispone de identidad suficiente,  
**Then** se crea un único Item maestro,  
**And** queda registrado su identificador objetivo.

### US6 — Asignación a ENC (P1)

**Given** el Item recibido coincide con un ENC comprado pendiente,  
**When** un usuario FRA confirma la asignación,  
**Then** la unidad satisface ese ENC.

### US7 — Producto recibido sin ENC compatible (P1)

**Given** un producto recibido no corresponde a ningún ENC pendiente,  
**When** recepción termina la identificación,  
**Then** se ingresa como stock.

### US8 — Compra equivocada (P1)

**Given** ENC pide talla US9,  
**And** llega talla US10,  
**When** recepción detecta la diferencia,  
**Then** US10 pasa a stock,  
**And** el ENC US9 continúa pendiente.

### US9 — Varias unidades iguales (P1)

**Given** llegan cinco unidades del mismo Item,  
**And** existen tres ENC compatibles,  
**When** recepción concilia las unidades,  
**Then** tres pueden asignarse a ENC,  
**And** dos quedan como stock.

### US10 — Pegado de imagen (P1)

**Given** el vendedor tiene una captura en el portapapeles,  
**When** pega la imagen en el ENC,  
**Then** se guarda como File vinculado,  
**And** queda visible como referencia/miniatura.

### US11 — Venta parcialmente cubierta por stock (P1)

**Given** el cliente compra 3 unidades,  
**And** el almacén de venta tiene sólo 1 disponible,  
**When** el vendedor confirma el abastecimiento,  
**Then** 1 unidad se atiende desde stock,  
**And** se generan ENC por las 2 unidades faltantes,  
**And** esas 2 unidades no aparecen como stock disponible.

### US12 — Item conocido agotado (P1)

**Given** el Item ya existe en ERPNext,  
**And** no existe stock disponible suficiente,  
**When** el vendedor crea el encargo,  
**Then** el ENC referencia el Item existente,  
**And** no se crea un Item duplicado.

---

## 23. Criterios de aceptación

La implementación se acepta cuando se demuestre en sandbox que:

1. ENC y Item son entidades conceptualmente distintas.
2. Un ENC puede existir sin Item.
3. Un ENC puede opcionalmente apuntar a un Item conocido.
4. La imagen original pertenece al ENC.
5. El shopper sólo compra y marca estados simples.
6. El shopper puede trabajar agrupando/ordenando por tienda y marca.
7. Marcar COMPRADO no cierra el ENC.
8. La identidad definitiva del producto se resuelve bajo control FRA.
9. Recepción identifica primero el producto físico y después decide ENC/stock.
10. Un Item existente se reutiliza.
11. Una compra equivocada no satisface el ENC.
12. Una compra equivocada no devuelta puede ingresar como stock.
13. La vinculación automática por IA/fuzzy no es fuente de verdad.
14. La solicitud original permanece auditable.
15. Una OV puede representar producto desconocido mediante el único Item técnico no-stock `ENCARGO-PENDIENTE`, siempre vinculado a un ENC.
16. Un Item conocido mantiene su Item real en la OV y el ENC representa sólo la cantidad faltante.
17. ENC no se implementa como Warehouse ni como stock virtual.
18. Una falta parcial de stock genera ENC únicamente por la cantidad faltante.
19. Un Item existente sin stock genera ENC referenciado al mismo Item, no un producto nuevo.
20. Cantidades ENC pendientes/compradas/en tránsito no incrementan stock disponible.
21. Reintentar Save/Submit no duplica ENC.
22. Dos OVs concurrentes no pueden comprometer dos veces la misma existencia disponible.
23. El shopper no obtiene acceso al Desk ni a datos comerciales/contables innecesarios.
24. Una fila `ENCARGO-PENDIENTE` sin ENC asociado no puede confirmarse.
25. Resolver un producto desconocido no reescribe destructivamente una OV submitted.

---

## 24. Decisiones congeladas

- nombre conceptual: **Encargo / ENC**;
- ENC es una **cola de demanda/abastecimiento comprometido**, no una bodega;
- no crear un Warehouse virtual “Encargos”;
- no crear un segundo maestro o tabla paralela de productos;
- la venta consulta primero stock real del almacén de venta/default;
- si el stock es parcial, crear ENC sólo por la cantidad faltante;
- si el Item existe pero está agotado, el ENC referencia el Item existente;
- si el Item no existe, el ENC puede nacer sin Item y con descripción/imagen;
- cantidades ENC no son stock disponible hasta recepción física e ingreso de inventario;
- numeración visible `ENC-YYYY-#####` o equivalente compatible;
- ENC representa lo solicitado por el cliente;
- Item representa la identidad real del producto;
- no crear Items ficticios para resolver incertidumbre;
- shopper externo con interfaz mínima;
- tienda y marca forman parte de la información operacional del ENC;
- shopper puede marcar Pendiente / Comprado / No encontrado;
- Comprado no equivale a satisfecho;
- recepción Chile es el punto de conciliación definitivo;
- producto se identifica antes de decidir ENC vs stock;
- reutilizar Item existente cuando la identidad coincide;
- compra equivocada no devuelta -> stock;
- ENC equivocado/no satisfecho -> vuelve o permanece pendiente;
- confirmación humana FRA para el vínculo final;
- imagen original del ENC se conserva;
- requerimiento de pegar imagen desde portapapeles;
- Item conocido: conservar Item real en Sales Order y generar ENC sólo por el faltante;
- Item desconocido: utilizar un único Item técnico no-stock `ENCARGO-PENDIENTE`;
- `ENCARGO-PENDIENTE` nunca representa existencia física;
- Sales Order Item mantiene cantidades calculadas de stock comprometido y ENC;
- reutilizar Stock Reservation estándar de ERPNext para la porción disponible, sin reserva custom;
- una OV submitted no se reescribe para sustituir `ENCARGO-PENDIENTE`; el Item real se resuelve en ENC.

---

## 25. Decisiones técnicas que el Programador debe confirmar en su plan

No son decisiones de negocio abiertas; son verificaciones técnicas contra la versión instalada antes de escribir código:

1. API/controlador estándar de Stock Reservation que permita reservar sólo `stock_committed_qty`.
2. Evento exacto de Sales Order (`before_submit` / `on_submit`) para calcular split, crear ENC y reservar sin doble ejecución.
3. Estrategia de locking/transacción para evitar doble compromiso concurrente del mismo Bin.
4. Nombre técnico definitivo de Custom Fields y módulos Python/JS.
5. Mecanismo de creación idempotente del Item técnico `ENCARGO-PENDIENTE` mediante fixture/patch.
6. Forma más estable de capturar pegado de imagen y crear `File` adjunto al ENC.
7. Implementación de usuario Website + rol `ShopperFRA` y página Portal sin Desk.
8. Qué parte de recepción puede reutilizar lógica estándar de Barcode/Item y qué parte necesita Page custom.

Si alguna de estas verificaciones obliga a cambiar una decisión de negocio congelada, detener el plan y señalar la contradicción a Miguel.

---

## 26. Modelo mínimo de DocType Encargo

Crear DocType custom **Encargo** dentro de `erpn_custom`.

Campos mínimos funcionales:

### Origen comercial

- `sales_order` — Link Sales Order, obligatorio;
- `sales_order_item` — identificador estable de la fila de Sales Order;
- `customer` — Link Customer, read-only derivado;
- `sales_person` — Link Sales Person, si existe;
- `requested_qty` — Float > 0;
- `source_type` — Select: `KNOWN_ITEM` / `UNKNOWN_ITEM`.

### Identidad solicitada

- `expected_item` — Link Item, opcional;
- `resolved_item` — Link Item, opcional hasta recepción;
- `description` — obligatorio;
- `reference_image` — Attach Image;
- `brand` — Data;
- `suggested_store` — Data;
- `model` — Data;
- `size` — Data;
- `color` — Data;
- `reference_url` — Data;
- `notes` — Small Text;
- `sale_rate` — Currency informativa del valor vendido.

### Compra Miami

- `purchase_status` — Select: `PENDING`, `PURCHASED`, `NOT_FOUND`;
- `shopper_user` — Link User;
- `purchased_on` — Datetime.

### Recepción / resolución

- `reception_status` — Select: `PENDING`, `RECEIVED`, `RESOLVED_TO_ENC`, `RESOLVED_TO_STOCK`;
- `received_on` — Datetime;
- `resolved_by` — Link User.

### Estado operacional

No usar un único Status para reemplazar `purchase_status` y `reception_status`. Puede existir un estado derivado para filtros, pero la fuente de verdad debe mantener separadas ambas dimensiones.

Naming series:

```text
ENC-.YYYY.-.#####
```

o la sintaxis equivalente validada para Frappe v16 que produzca `ENC-2026-00001`.

---

## 27. Permisos

### ComercialFRA

Debe poder:

- crear ENC desde Sales Order;
- ver/editar ENC de operación;
- completar referencia de compra;
- ver estado de shopper y recepción.

No obtiene permisos contables adicionales.

### ShopperFRA

Crear rol específico **ShopperFRA** para Website User.

El shopper:

- no entra al Desk;
- no recibe permiso general de escritura sobre Encargo;
- consume una página/API limitada;
- sólo puede listar ENC elegibles para compra y cambiar `purchase_status` mediante métodos server-side controlados;
- no ve Customer, saldo, margen, comisión, datos bancarios ni módulos ERP.

### Recepción / Comercial autorizado

La conciliación final ENC ↔ Item exige usuario interno FRA con permiso explícito.

---

## 28. Página shopper

Crear una página Portal autenticada, ruta propuesta:

```text
/encargos-shopper
```

Debe mostrar únicamente ENC en estados de compra operables.

Orden/grouping inicial:

1. `suggested_store`;
2. `brand`;
3. fecha/ENC.

Cada tarjeta/fila muestra:

- ENC;
- miniatura;
- descripción;
- marca;
- tienda;
- modelo/talla/color;
- cantidad;
- URL si existe;
- observación necesaria para comprar.

Acciones:

```text
[ COMPRADO ]
[ NO ENCONTRADO ]
```

`COMPRADO` registra usuario y timestamp.

La página no necesita crear/editar Items.

---

## 29. Recepción Chile — alcance de esta Spec

Implementar el **punto de conciliación**, no un WMS completo.

La interfaz de recepción debe permitir:

1. abrir/buscar un ENC comprado pendiente;
2. escanear o ingresar barcode del producto recibido;
3. buscar Item existente por barcode/identificadores;
4. si existe, proponerlo;
5. si no existe, permitir iniciar creación controlada del Item real con datos mínimos;
6. mostrar la referencia original del ENC al lado del producto físico;
7. usuario FRA confirma:
   - `SATISFACE ENC`, o
   - `NO SATISFACE / STOCK`;
8. guardar `resolved_item`, usuario y fecha;
9. una compra equivocada destinada a stock deja el ENC pendiente de compra nuevamente.

Esta Spec **no debe inventar un Warehouse virtual ENC**.

El documento exacto que realiza el ingreso contable/Stock Ledger (Purchase Receipt, Stock Entry u otro flujo de recepción definitivo) se mantiene desacoplado de la clasificación ENC/Stock y no debe falsearse sin costo/documentación suficiente.

---

## 30. Orden de implementación solicitado

El Programador debe proponer y luego ejecutar, tras OK, en este orden:

### Fase A — inspección y plan

1. leer README + Spec 013;
2. inspeccionar Sales Order, Sales Order Item, Bin y Stock Reservation en ERPNext/Frappe v16 instalado;
3. verificar hooks existentes de `erpn_custom` sobre Sales Order para no interferir con Spec 012 ni saldo a favor;
4. presentar archivos a crear/modificar;
5. presentar estrategia de idempotencia, concurrencia y rollback;
6. presentar pruebas;
7. esperar OK de Miguel.

### Fase B — modelo y Sales Order

1. crear DocType Encargo;
2. crear Custom Fields en Sales Order Item;
3. crear Item técnico `ENCARGO-PENDIENTE` no-stock de forma idempotente;
4. implementar botón `Agregar Encargo`;
5. implementar captura/pegado de imagen;
6. implementar split stock/ENC server-side;
7. enlazar OV ↔ fila ↔ ENC;
8. integrar reserva estándar de la parte disponible;
9. tests unitarios.

### Fase C — shopper

1. rol `ShopperFRA`;
2. acceso Website/Portal;
3. lista agrupable por tienda/marca;
4. métodos server-side para `PURCHASED` / `NOT_FOUND`;
5. auditoría de usuario/fecha;
6. pruebas de seguridad y permisos.

### Fase D — recepción

1. interfaz de conciliación;
2. búsqueda por barcode/Item;
3. resolución a Item existente o creación controlada;
4. asignación a ENC o stock;
5. reapertura de ENC por compra incorrecta;
6. pruebas end-to-end.

---

## 31. Casos mínimos de prueba obligatorios

1. Item conocido, stock 5, venta 2 -> ENC 0.
2. Item conocido, stock 1 libre, venta 3 -> stock committed 1 + ENC 2.
3. Item conocido, stock 0, venta 1 -> ENC 1 con mismo Item.
4. Producto desconocido -> fila `ENCARGO-PENDIENTE` + ENC con imagen/descripción.
5. Submit repetido/reintento -> no duplica ENC.
6. Dos filas del mismo Item/Warehouse -> cálculo agregado correcto.
7. Dos Sales Orders concurrentes -> no comprometen la misma unidad dos veces.
8. Shopper ve sólo datos de compra permitidos.
9. Shopper marca COMPRADO -> timestamp/user, ENC no queda satisfecho.
10. Recepción barcode conocido -> reutiliza Item.
11. Recepción barcode nuevo -> permite resolver nuevo Item sin duplicar identificador.
12. Producto correcto -> ENC satisfecho.
13. Producto incorrecto -> Item a stock y ENC vuelve a compra pendiente.
14. Resolver Item no modifica destructivamente Sales Order submitted.
15. Cancelar Sales Order antes de comprar -> ENC asociado no puede quedar activo para shopper.
16. Cancelar/cerrar una OV con compra ya declarada debe bloquear automatismos destructivos y exigir resolución explícita.

---

## 32. Rollback

El rollback debe poder:

- ocultar/desactivar botones y páginas custom;
- retirar hooks de Sales Order;
- conservar documentos ENC ya creados como evidencia;
- no borrar Stock Reservation estándar válida de otras funciones;
- no modificar core ERPNext/Frappe;
- no borrar Items reales creados en recepción;
- dejar `ENCARGO-PENDIENTE` deshabilitado si la funcionalidad se retira.

No implementar migraciones destructivas para rollback.
