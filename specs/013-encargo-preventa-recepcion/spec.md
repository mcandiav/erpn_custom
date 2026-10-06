# Feature Specification: ENC — Encargos, compra Miami y conciliación en recepción Chile

**Feature Branch**: `[013-encargo-preventa-recepcion]`

**Created**: 2026-09-23

**Status**: **ACTIVE — DEFINICIÓN FUNCIONAL CERRADA / PLANIFICACIÓN TÉCNICA AUTORIZADA**. Spec vigente después del cierre aceptado de `012-sales-person-auto-commission`. El Programador debe inspeccionar ERPNext/Frappe v16, presentar plan técnico y pruebas contra esta Spec y esperar OK explícito de Miguel antes de escribir código.

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

### 5.1 Principio de captura operacional y gobierno de maestros

Aplica el principio rector del proyecto:

> **Los usuarios operativos pueden capturar realidad nueva, pero no deben contaminar automáticamente los datos maestros. La operación no se bloquea; el maestro se gobierna.**

Si el Shopper encuentra un lugar/proveedor no existente, puede registrar el nombre observado y continuar la compra. Esa observación queda vinculada a la operación y pendiente de gobierno; **no crea Supplier, Brand, Item ni otro maestro automáticamente**.

El administrador ERP decide posteriormente si normaliza contra un maestro existente, crea uno nuevo o conserva el dato únicamente como evidencia histórica.

### 5.2 Responsabilidad del Shopper

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

Su función es **resolver la compra física del Encargo y capturar evidencia objetiva de esa compra**. El Shopper no gobierna datos maestros: puede registrar realidad nueva observada durante la operación, pero esa captura no crea automáticamente maestros ERP.

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

Estados operacionales para shopper:

```text
PENDIENTE DE COMPRA
COMPRADO
NO ENCONTRADO
```

No existe un paso obligatorio `TOMAR ENCARGO`. Abrir un ENC no cambia su estado ni lo asigna al Shopper. Si se requiere protección de concurrencia, debe resolverse mediante bloqueo técnico temporal al confirmar, no mediante una etapa operacional adicional.

`COMPRADO` sólo puede confirmarse cuando existe evidencia mínima completa: **barcode escaneado + foto del producto + foto de la etiqueta + precio**. El shopper no debe cerrar el ENC comercial.

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

Registrar como mínimo y de forma atómica al confirmar la compra:

- ENC;
- barcode capturado;
- foto del producto comprado;
- foto de etiqueta/tag;
- precio capturado (un único valor operacional);
- Shopper autenticado;
- fecha/hora de compra;
- Supplier seleccionado o referencia operacional de lugar de compra;
- Supplier propuesto, si el lugar observado no existe en el maestro;
- estado de compra = `PURCHASED`.

El barcode queda asociado al **Encargo comprado**, no se incorpora automáticamente al maestro Item. La asociación definitiva barcode/Item queda bajo control FRA durante recepción/normalización.

Un Encargo puede representar `requested_qty > 1`, pero la unidad operativa de compra sigue siendo el **ENC individual**. Si existen dos ENC distintos —aunque correspondan al mismo producto, variante y barcode— el Shopper debe completar la captura y confirmar cada ENC por separado. Cada ENC conserva su propia evidencia: barcode escaneado, foto de producto, foto de etiqueta, precio, Shopper y timestamp.

Ejemplo: dos clientes distintos generan dos ENC iguales. El Shopper compra dos unidades idénticas. Debe procesar ENC-001 y ENC-002 como compras separadas, repitiendo escaneo y fotos para cada uno. No se permite dar de baja múltiples ENC mediante una sola captura compartida.

Si un único ENC tiene `requested_qty > 1`, la cantidad visible pertenece a ese ENC y la implementación debe exigir una confirmación explícita de que se compró la cantidad completa antes de pasarlo a `PURCHASED`; esta Spec no convierte automáticamente una sola evidencia en cierre de otros ENC.

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
**When** el Shopper completa para ese ENC barcode, foto del producto, foto de etiqueta y precio, y confirma la compra,  
**Then** se registra atómicamente la evidencia, Shopper y fecha/hora,  
**And** ese ENC pasa a `PURCHASED`,  
**But** el ENC todavía no se considera satisfecho ni recibido.

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
- `brand` — referencia controlada al maestro/lista de Marca definido por el modelo de producto; no texto libre cuando exista valor gobernado;
- `suggested_supplier` — Link Supplier, opcional; representa un Supplier maestro ya validado y sugerido para buscar;
- `model` — Data descriptivo cuando corresponda;
- `size` — atributo controlado según Familia/tipo de producto; no texto libre cuando aplique;
- `color` — atributo controlado según el modelo de producto; no texto libre cuando aplique;
- `reference_url` — Data;
- `notes` — Small Text;
- `sale_rate` — Currency informativa del valor vendido.

### Compra Miami

- `purchase_status` — Select: `PENDING`, `PURCHASED`, `NOT_FOUND`;
- `purchase_barcode` — Data, requerido para confirmar `PURCHASED`;
- `purchase_product_image` — Attach Image, requerido para confirmar `PURCHASED`;
- `purchase_label_image` — Attach Image, requerido para confirmar `PURCHASED`;
- `purchase_price` — Currency, requerido para confirmar `PURCHASED`;
- `purchase_supplier` — Link Supplier, opcional cuando existe maestro validado;
- `proposed_supplier_name` — Data, opcional para capturar un lugar/proveedor todavía no gobernado;
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

La entrada es **mobile-first**. Antes de mostrar la cola, el Shopper selecciona el Supplier/lugar donde está comprando o `TODOS`. Esa selección permanece activa mientras trabaja y puede cambiarse sin alterar ENC.

Filtros/agrupación operacionales:

1. Supplier/lugar seleccionado;
2. marca;
3. tipo/familia de producto cuando esté disponible;
4. talla/atributos relevantes;
5. fecha/ENC.

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

La lista representa **oportunidades de compra en el lugar actual**, no asignaciones personales. Cada tarjeta prioriza foto, descripción reconocible, marca, variante/color, talla y **cantidad requerida**; códigos internos y datos administrativos quedan en segundo plano. La cantidad debe ser visible sin abrir el ENC, porque un mismo Encargo puede requerir más de una unidad.

Al encontrar el producto, la acción principal abre una captura secuencial:

```text
1/4 ESCANEAR BARCODE
2/4 FOTO DEL PRODUCTO
3/4 FOTO DE ETIQUETA / TAG
4/4 PRECIO
        ↓
[ CONFIRMAR COMPRA ]
```

`CONFIRMAR COMPRA` permanece deshabilitado mientras falte cualquiera de las cuatro evidencias. La confirmación guarda todo y cambia a `PURCHASED` en una única operación server-side; si falla una parte, no debe existir un `PURCHASED` parcial. Después vuelve al mismo Supplier/filtro y el ENC comprado desaparece de `Por comprar`.

Debe existir `+ Registrar supplier/lugar no listado`. Esta acción **no crea un Supplier maestro**: captura `proposed_supplier_name`, usuario/fecha/ENC y permite continuar. La validación, asociación o creación posterior del maestro corresponde a administración ERP.

La página no crea ni edita Items ni Suppliers maestros.

---

## Addendum A — presentación de la ficha Encargo

Este addendum es **no disruptivo** respecto de la implementación ya iniciada. No cambia modelo, estados, validaciones ni contratos existentes; únicamente fija la organización visual esperada del formulario `Encargo`.

La ficha del Encargo debe agrupar visualmente la información del Shopper en una sección claramente identificable como **Shopper** o **Compra Shopper**, separada de la solicitud original del cliente.

Debe mostrar, cuando existan:

- estado de compra;
- Shopper;
- fecha/hora de compra;
- Supplier validado;
- Supplier/lugar propuesto;
- barcode capturado;
- precio;
- foto del producto comprado;
- foto de la etiqueta/tag;
- historial de intentos `NO ENCONTRADO`.

La Sales Order no duplica estos campos: mantiene el vínculo al ENC y desde ese vínculo se consulta la ficha completa.

---

## Addendum B — intentos `NO ENCONTRADO`

`NO ENCONTRADO` deja de ser un estado terminal y pasa a representar un **intento fallido de compra**.

Cuando el Shopper marca `NO ENCONTRADO`:

1. el ENC **permanece en `PENDIENTE DE COMPRA`**;
2. sigue apareciendo en la lista de compras futuras;
3. se registra un intento auditable con:
   - Shopper;
   - Supplier/lugar en el que se buscó;
   - fecha/hora;
   - resultado = `NOT_FOUND`;
   - observación opcional;
4. el intento no modifica la solicitud original del cliente;
5. el mismo ENC puede volver a buscarse otro día o en otro Supplier.

Debe existir un historial visible de intentos por ENC.

Al alcanzar **3 intentos `NOT_FOUND`**, el sistema no cancela automáticamente el ENC. Debe generar una condición de **revisión comercial / contacto con cliente**, mediante una bandera o estado derivado equivalente, por ejemplo `requires_customer_contact = 1`.

La responsabilidad posterior pertenece a ComercialFRA, que decidirá si continuar buscando, ofrecer alternativa, esperar reposición, cancelar o resolver financieramente con el cliente.

Principio: **el Shopper reporta disponibilidad física; Comercial decide la respuesta al cliente**.

---

## Addendum C — navegación mobile-first multi-módulo para Shopper

La experiencia Shopper debe concebirse como una **aplicación móvil con varios módulos operativos**, no como una única página aislada.

`Compras` es el primer módulo. Módulos futuros —por ejemplo `Cajas`, `Recepción Miami`, armado o revisión de cajas— deben poder incorporarse sin abandonar el diseño mobile-first.

La navegación principal debe usar un patrón móvil persistente y simple, preferentemente **barra inferior con iconos** o navegación equivalente de acceso inmediato. Ejemplo conceptual:

```text
[ Compras ]   [ Cajas ]   [ Más ]
```

Reglas:

- no replicar la barra lateral densa del Desk de ERPNext;
- máximo acceso directo a las funciones operativas frecuentes;
- iconos y etiquetas breves;
- cada módulo conserva contexto y filtros cuando el usuario vuelve;
- los flujos de captura deben seguir optimizados para uso con una mano;
- la incorporación de nuevos módulos no debe reducir el espacio útil de la vista principal de Compras;
- información administrativa o poco frecuente debe ir a `Más` o vistas secundarias.

La arquitectura de navegación debe permitir añadir nuevos módulos Shopper sin rediseñar la aplicación completa.

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
2. acceso Website/Portal mobile-first;
3. selector inicial Supplier/lugar + opción `TODOS` y persistencia del contexto;
4. lista filtrable por Supplier, marca, tipo/familia, talla y atributos disponibles;
5. captura obligatoria de barcode, foto producto, foto etiqueta y precio;
6. captura de Supplier/lugar propuesto sin crear maestro;
7. método server-side atómico para `PURCHASED` y método controlado para `NOT_FOUND`;
8. asociación barcode -> ENC comprado sin modificar Item;
9. auditoría de usuario/fecha;
10. pruebas de concurrencia, seguridad y permisos.

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
8. Shopper entra desde móvil, selecciona Supplier/lugar o `TODOS` y ve sólo datos de compra permitidos.
9. Shopper no puede confirmar COMPRADO sin barcode + foto producto + foto etiqueta + precio.
10. Confirmar COMPRADO guarda evidencia + timestamp/user de forma atómica, asocia barcode al ENC y el ENC no queda satisfecho.
11. Supplier/lugar no listado puede registrarse como propuesta sin crear Supplier maestro.
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

---

## 33. Addendum compatible posterior al inicio de programación

Este addendum amplía la experiencia de usuario y la trazabilidad del Shopper sin invalidar el núcleo funcional ya iniciado. Debe tratarse como ajuste compatible de la Spec 013, no como reinicio del desarrollo.

### 33.1 Sección visible `Shopper` en la ficha Encargo

La ficha del DocType **Encargo** debe agrupar visualmente en una sección claramente identificable como `Shopper` o `Compra Shopper` todos los datos generados durante la compra física.

La sección debe mostrar, al menos:

- estado de compra;
- Shopper;
- fecha/hora de compra;
- Supplier validado, si existe;
- Supplier/lugar propuesto, si fue capturado durante la operación;
- barcode escaneado;
- precio capturado;
- foto del producto comprado;
- foto de etiqueta/tag.

Esta agrupación es de presentación y trazabilidad. No modifica los contratos de datos, estados, validaciones ni endpoints ya definidos.

Debe permitir que, desde la Sales Order, al abrir el Encargo vinculado, un usuario autorizado pueda comparar claramente **solicitud original** vs **compra Shopper** sin mezclar ambos conjuntos de evidencia.

### 33.2 `NO ENCONTRADO` como intento histórico, no estado terminal

Cuando el Shopper busca un Encargo en un Supplier/lugar y no encuentra el producto, debe poder registrar `NO ENCONTRADO`.

Cada intento debe registrar de forma auditable:

- Encargo;
- Shopper;
- Supplier/lugar donde se buscó;
- fecha/hora;
- resultado = `NOT_FOUND`;
- observación opcional.

Registrar `NO ENCONTRADO` **no elimina el Encargo de la lista de compras** y no lo convierte en estado terminal. El ENC permanece disponible para ser buscado otro día, en el mismo Supplier o en otro Supplier.

Debe existir un historial de intentos asociado al ENC. Este historial no debe sobrescribirse ni reducirse a un único contador sin evidencia de cada búsqueda.

### 33.3 Escalamiento al tercer intento no encontrado

Al alcanzar **3 intentos `NOT_FOUND`** para el mismo ENC, el sistema debe marcarlo para revisión comercial, por ejemplo mediante una bandera derivada `requires_customer_contact = 1` o mecanismo equivalente definido técnicamente por el Programador.

El tercer intento no cancela automáticamente el ENC. Debe generar una señal clara para Comercial de que corresponde evaluar comunicación con el cliente y decidir una acción posterior, por ejemplo:

- continuar buscando;
- esperar reposición;
- ofrecer alternativa;
- cancelar el encargo;
- devolver/aplicar saldo según flujo comercial vigente.

El Shopper informa realidad operacional; **Comercial decide la relación con el cliente**.

### 33.4 Criterios de aceptación adicionales del addendum

1. Los campos de compra Shopper aparecen agrupados en una sección visible del Encargo.
2. Desde la OV puede abrirse el ENC y distinguir solicitud original de compra Shopper.
3. `NO ENCONTRADO` registra un intento histórico con Shopper, Supplier/lugar y timestamp.
4. Registrar `NO ENCONTRADO` mantiene el ENC en la lista de compras.
5. El mismo ENC puede acumular intentos en fechas y Suppliers distintos.
6. Al tercer `NOT_FOUND`, el sistema genera una señal de revisión comercial sin cancelar automáticamente el ENC.
7. El historial de intentos permanece auditable y no se sobrescribe.

## 34. Fase D — Recepción Chile concretada con caso real OV-2026-00326

### 34.1 Caso de aceptación real

- Sales Order: `OV-2026-00326`.
- Customer: `kevin quijada candia`.
- Sales Order Item: `42n26msh71`.
- Encargo: `ENC-2026-00401`.
- Producto: Cinturon masculino mk / Michael Kors / Cinturones / Hombre / Brown.
- `purchase_status = PURCHASED`.
- Shopper: `shopper@fragallardo.com`.
- Supplier compra: `MK Outlet`.
- Código escaneado por Shopper: `https://qrgo.page.link/JsDVr`.
- `reception_status = PENDING`.
- `resolved_item = vacío`.

La Fase C termina correctamente con la compra y su evidencia. La Fase D comienza cuando FRA recibe físicamente la unidad en Chile.

### 34.2 Regla arquitectónica del código escaneado

El sistema no debe interpretar ni restringir el formato del código. Para la operación, el identificador es el valor bruto que devuelve el lector/cámara, sea EAN, UPC, GTIN, QR, URL contenida en QR, código interno del proveedor u otro formato.

Principio:

`Shopper escanea -> purchase_barcode -> Recepción escanea la misma etiqueta -> coincidencia exacta -> recuperar Encargo`.

Por lo tanto `https://qrgo.page.link/JsDVr` es un identificador operacional válido y no debe rechazarse por ser URL o QR.

### 34.3 Prioridad de búsqueda en Recepción

El primer objetivo del escaneo en Chile es reconocer la unidad comprada y recuperar su Encargo, no resolver inmediatamente el Item maestro.

Orden:

1. Escanear producto recibido.
2. Buscar Encargo abierto con `purchase_status = PURCHASED`, `purchase_barcode = valor escaneado` y `reception_status` PENDING o RECEIVED.
3. Si existe coincidencia, abrir directamente la conciliación de ese Encargo.
4. Si no existe, ofrecer búsqueda de Item o recepción sin Encargo.

### 34.4 UI obligatoria

La función vive en Desk interno: `Encargo -> Recepción Chile`.

La pantalla debe estar orientada al escaneo y mostrar por defecto Encargos comprados pendientes de recepción. Filtros mínimos: Encargo, OV, Customer, código escaneado, marca, Supplier de compra, fecha de compra y estado de recepción.

Al abrir un caso debe mostrar lado a lado `Solicitud original` y `Compra Shopper`, con imágenes, descripción, atributos, Supplier, código y precio.

### 34.5 Recepción física

Acción visible: `MARCAR RECIBIDO`.

Al confirmar:
- `reception_status = RECEIVED`;
- `received_on = now`;
- registrar usuario receptor mediante auditoría/campo definido;
- no completar `resolved_item` hasta resolver la identidad del Item.

### 34.6 Resolución del Item

Después de recuperar el Encargo por `purchase_barcode`:

1. buscar si ese mismo identificador ya pertenece a un Item;
2. si existe, proponerlo;
3. si no existe, permitir buscar un Item existente;
4. si tampoco existe, permitir creación controlada del Item real;
5. la confirmación final siempre es humana FRA.

Un QR/URL puede ser un identificador maestro válido si el proveedor lo usa de forma estable y FRA confirma esa identidad. Cuando se asocie por primera vez a un Item, debe validarse unicidad para impedir que el mismo valor identifique dos Items distintos.

### 34.7 Decisión de destino

Una vez resuelto el Item, la UI ofrece exclusivamente:

- `SATISFACE ENCARGO`;
- `NO SATISFACE — STOCK`.

Si satisface: guardar `resolved_item`, `resolved_by`, `reception_status = RESOLVED_TO_ENC`, conservar la evidencia Shopper y no reescribir destructivamente la OV submitted.

Si no satisface: la unidad sigue el flujo normal de stock; no satisface el Encargo original; la compra equivocada permanece como evidencia y el Encargo vuelve o permanece pendiente mediante transición auditable.

### 34.8 Permisos

`ShopperFRA` no ejecuta Recepción Chile. Comercial/Vendedor pueden consultar según permisos. La conciliación debe ser ejecutada por un rol interno FRA explícito, con permiso para escanear, marcar recibido, resolver/crear Item controlado y confirmar ENC o STOCK. No usar `System Manager` como diseño operacional.

### 34.9 Validaciones

1. No resolver Encargo no `PURCHASED`.
2. Comparar exactamente el valor escaneado con `purchase_barcode`.
3. Aceptar QR/URL y otros formatos sin imponer EAN/UPC.
4. Un identificador maestro no puede pertenecer a dos Items.
5. `RESOLVED_TO_ENC` exige `resolved_item` válido.
6. No permitir doble resolución silenciosa.
7. No asignar la misma unidad física a dos Encargos.
8. No modificar la solicitud original para hacerla coincidir con lo recibido.

### 34.10 Caso end-to-end obligatorio

Usar `OV-2026-00326 / ENC-2026-00401`: Recepción escanea el QR físico, obtiene `https://qrgo.page.link/JsDVr`, ERP localiza el Encargo por `purchase_barcode`, muestra solicitud y evidencia, marca recibido, resuelve/crea el Item, permite asociar el QR al Item si FRA confirma que es identificador estable y finalmente confirma `SATISFACE ENCARGO`.

### 34.11 Estado

Fase B y Fase C están implementadas para este caso. Fase D — Recepción Chile — permanece pendiente. Los campos base existen; falta UI y lógica server-side de conciliación. El siguiente corte técnico de la Spec 013 debe concentrarse exclusivamente en Fase D.

### 34.12 UI operacional de Recepción Chile

La pantalla de Recepción Chile debe diseñarse como una estación de escaneo y clasificación física. El receptor no debe tener que interpretar una ficha ERP completa para saber qué hacer con la unidad.

Estado inicial:

```text
RECEPCIÓN CHILE

[ ESCANEAR PRODUCTO ]

Últimos recibidos
------------------------------------------------
ENC-2026-00401   Michael Kors   RECIBIDO
...
```

El cursor/foco debe permanecer preparado para el siguiente escaneo. Después de procesar una unidad, la pantalla vuelve automáticamente al modo escáner.

### 34.13 Warning inmediato cuando el producto pertenece a un Encargo

Si el valor escaneado coincide exactamente con `purchase_barcode` de un Encargo elegible, la UI debe mostrar inmediatamente un aviso visual dominante antes de cualquier otra acción.

Formato conceptual:

```text
┌──────────────────────────────────────────────┐
│              ENCARGO DETECTADO              │
│                                              │
│              ENC-2026-00401                 │
│                                              │
│         APARTAR / CLASIFICAR ENCARGO        │
│                                              │
│  Cinturon masculino mk · Michael Kors       │
│  OV-2026-00326                              │
└──────────────────────────────────────────────┘
```

El identificador `ENC-2026-xxxxx` debe ser el elemento de mayor jerarquía visual. El objetivo operacional es que el receptor pueda leerlo a distancia corta, separar físicamente la unidad y clasificarla inmediatamente.

El warning debe:

- aparecer automáticamente al escanear;
- no depender de abrir manualmente el Encargo;
- mostrar siempre el número de Encargo completo;
- mostrar descripción corta y marca como ayuda secundaria;
- mantener visible el código hasta que el receptor confirme una acción;
- ofrecer una acción principal `APARTADO / CONTINUAR` o equivalente;
- permitir abrir el detalle del Encargo como acción secundaria, no como requisito para seguir trabajando.

### 34.14 Flujo de una coincidencia única

Cuando existe un único Encargo elegible para el código escaneado:

```text
Escanear
   ↓
match exacto con purchase_barcode
   ↓
WARNING: ENC-2026-00401
   ↓
receptor aparta físicamente la unidad
   ↓
[ APARTADO / CONTINUAR ]
   ↓
marcar RECEIVED
   ↓
resolver Item ahora o dejar pendiente de conciliación
```

Confirmar `APARTADO / CONTINUAR` debe dejar trazabilidad de recepción física y permitir volver rápidamente al siguiente escaneo.

### 34.15 Caso de varios Encargos con el mismo barcode

El mismo producto puede haber sido comprado para varios clientes y, por lo tanto, varios Encargos pueden compartir el mismo `purchase_barcode`.

En ese caso el sistema no debe asignar silenciosamente la unidad a uno de ellos.

Debe mostrar:

```text
┌──────────────────────────────────────────────┐
│       PRODUCTO CON ENCARGOS PENDIENTES      │
│                                              │
│  Se encontraron 3 Encargos para este código │
│                                              │
│  ENC-2026-00401                             │
│  ENC-2026-00418                             │
│  ENC-2026-00427                             │
│                                              │
│      SELECCIONAR ENCARGO PARA ESTA UNIDAD   │
└──────────────────────────────────────────────┘
```

Cada unidad física escaneada se asigna a un solo Encargo mediante confirmación humana. Después de confirmar uno, ese Encargo deja de estar disponible para otra unidad si ya quedó resuelto.

El sistema puede ordenar candidatos por fecha de compra o antigüedad, pero no debe decidir automáticamente qué Encargo recibe la unidad.

### 34.16 Caso sin Encargo asociado

Si el código escaneado no coincide con ningún Encargo comprado pendiente de recepción, el warning debe ser diferente y no ambiguo:

```text
PRODUCTO SIN ENCARGO IDENTIFICADO

Código: <valor escaneado>

[ BUSCAR ITEM ]
[ INGRESAR A STOCK ]
[ BUSCAR ENCARGO MANUALMENTE ]
```

No usar el mismo color/señal visual que `ENCARGO DETECTADO`, para evitar que el receptor aparte por error una unidad destinada a stock.

### 34.17 Jerarquía visual y comportamiento

La UI debe priorizar la decisión física sobre la información administrativa:

1. número de Encargo;
2. instrucción física (`APARTAR / CLASIFICAR ENCARGO`);
3. descripción / marca;
4. OV y Customer como contexto secundario;
5. datos técnicos y trazabilidad en detalle expandible.

El aviso debe ser suficientemente grande y contrastante para uso en una mesa de recepción con escáner/celular. No depender únicamente de color: siempre debe contener texto explícito `ENCARGO DETECTADO` y el número `ENC-...`.

### 34.18 Regla de cierre del warning

El warning de Encargo no desaparece por timeout. Permanece hasta que el receptor realice una acción explícita:

- `APARTADO / CONTINUAR`;
- `VER DETALLE`;
- `NO CORRESPONDE`.

`NO CORRESPONDE` no resuelve el Encargo; devuelve la unidad al flujo de revisión manual y conserva el escaneo como evento auditable.

### 34.19 Caso de aceptación visual OV-2026-00326

Para `ENC-2026-00401`, al escanear en Chile:

```text
https://qrgo.page.link/JsDVr
```

la primera respuesta visible debe ser:

```text
ENCARGO DETECTADO
ENC-2026-00401
APARTAR / CLASIFICAR ENCARGO
```

sin exigir previamente abrir la ficha del Encargo ni resolver el Item.

### 34.20 Decisiones de Miguel al aprobar el plan de Fase D (2026-10-06)

1. **Rol operativo:** `FRAreceptor` (creado inicialmente como `ReceptorFRA` y renombrado en `16.0.94`), creado por patch dentro de esta Spec. `System Manager` también puede operar. `ComercialFRA` (vendedor) no recibe. Regla general: cuando una Spec necesita un rol nuevo de ERPNext, la Spec lo crea mediante patch. Los roles futuros se nombran `FRA` + rol en minúscula (`FRAempaque`); `ComercialFRA` y `ShopperFRA` no se renombran.
2. **Varios Encargos con el mismo código (reemplaza la selección humana de §34.15):** cada escaneo es una unidad física y se asigna automáticamente al Encargo de compra más antigua que aún no tiene unidad recibida. Si llegan 4 unidades para 4 Encargos se escanean 4 veces. Un Encargo comprado sin unidad recibida queda visible como "comprado no recibido" (huérfano). Los Encargos pueden venir de distintos lugares y shoppers.
3. **Cantidad:** no se reciben cantidades de productos iguales; la recepción es unitaria y por escaneo.
4. **Compra equivocada:** `ANULAR COMPRA / ITEM A STOCK`. La evidencia de la compra (shopper, fecha, lugar, código, precio, fotos) y el Item real de la unidad quedan en la bitácora de recepción del Encargo; el Encargo vuelve a `purchase_status = PENDING` / `reception_status = PENDING` y reaparece para el Shopper. La unidad sigue el flujo normal de stock.
5. **Escaneo sin Encargo:** es una recepción normal de artículos de stock (una caja trae artículos de stock y de Encargo). En este corte la UI solo lo identifica; el documento de ingreso a stock queda fuera de alcance (§29).
6. **Usuario receptor:** queda identificado en cada acción del escaneo (`received_by` y bitácora con usuario, fecha y código).
