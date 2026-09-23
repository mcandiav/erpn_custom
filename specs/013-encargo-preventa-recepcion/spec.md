# Feature Specification: ENC — Encargos, compra Miami y conciliación en recepción Chile

**Feature Branch**: `[013-encargo-preventa-recepcion]`

**Created**: 2026-09-23

**Status**: **DRAFT / FUTURA / NO IMPLEMENTAR**. Esta Spec queda registrada para diseño posterior. **No es la Spec activa del Programador y no debe desplazar, interrumpir ni mezclarse con `012-sales-person-auto-commission` hasta OK explícito de Miguel.**

**Parent context**: arquitectura FRAgallardo, flujo Encargo/Preventa, Sales Order, compras Miami, recepción de cajas Chile, Item/Barcode de ERPNext/Frappe v16.

## 0. Propósito de este documento

Registrar la decisión arquitectónica del proceso de **Encargos (ENC)** sin iniciar todavía su implementación.

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

## 18. Relación con Sales Order

El ENC debe estar trazablemente vinculado a la venta que originó la obligación.

Decisión congelada:

- no convertir posteriormente un Item ficticio de una OV confirmada en un Item real mediante mutaciones destructivas;
- preservar el registro de qué se vendió y cómo se resolvió.

Decisión todavía **abierta para diseño** antes de implementación:

- cómo representar exactamente en Sales Order un ENC cuyo Item todavía no existe;
- si la línea comercial utiliza un Item genérico no-stock, un mecanismo custom u otra estrategia compatible con ERPNext;
- cómo se comportará stock reservation para encargos conocidos vs desconocidos.

Esta decisión debe resolverse antes de promover la Spec a implementación.

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

## 23. Criterios de aceptación conceptuales

Antes de promover esta Spec a programación debe quedar validado que:

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
15. Se define antes de programar cómo se representa en Sales Order un ENC sin Item.
16. Se define antes de programar la integración exacta con recepción de cajas.
17. ENC no se implementa como Warehouse ni como stock virtual.
18. Una falta parcial de stock genera ENC únicamente por la cantidad faltante.
19. Un Item existente sin stock genera ENC referenciado al mismo Item, no un producto nuevo.
20. Cantidades ENC pendientes/compradas/en tránsito no incrementan stock disponible.

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
- requerimiento futuro de pegar imagen desde portapapeles;
- no implementar esta Spec hasta cierre/OK explícito del corte vigente.

---

## 25. Preguntas deliberadamente pendientes

Estas preguntas deben resolverse cuando Miguel decida activar la Spec:

1. Representación exacta del ENC dentro de Sales Order cuando no existe Item.
2. Campos obligatorios mínimos del ENC.
3. Si se permiten múltiples imágenes estructuradas además de adjuntos.
4. Mecanismo de autenticación/autorización del shopper externo.
5. Si el shopper necesita registrar tienda real donde finalmente compró.
6. Si el shopper registra precio/costo o si eso pertenece a otro proceso.
7. Diseño exacto de recepción de cajas.
8. Warehouse transitorio y momento contable del ingreso.
9. Manejo de cantidades parciales de un mismo ENC.
10. Cómo se integra ENC satisfecho con Empaque.

---

## 26. Regla de secuencia / protección contra implementación accidental

**Esta sección es obligatoria mientras la Spec esté en DRAFT.**

- La Spec activa continúa siendo la indicada en el `README.md` raíz técnico.
- Al momento de creación de este documento, la Spec activa es `012-sales-person-auto-commission`.
- La existencia de la carpeta `013-encargo-preventa-recepcion` **NO autoriza implementación**.
- El Programador no debe tomar “la Spec de número más alto” como siguiente trabajo.
- No crear código, hooks, DocTypes, patches, fixtures ni migraciones de ENC hasta que Miguel diga explícitamente que la 013 pasa a activa.
- Cuando se active, primero revisar estas decisiones y cerrar las preguntas pendientes; recién después presentar plan técnico y esperar OK de Miguel.
