# Spec 019 - Materialización progresiva de Encargo en Orden de Venta

Estado: DEFINITIVA PARA IMPLEMENTACION
Fecha: 2026-10-06
Rol solicitante: Arquitecto
Proyecto: ERPNext Custom / FRAgallardo
Dependencias: Specs 013, 014, 015, 018

## 0. Alcance (corrección 2026-10-06, Miguel)

Esta Spec aplica **solo a líneas `ENCARGO-PENDIENTE`**, es decir, a Encargos `source_type = UNKNOWN_ITEM`.

- Los Encargos `KNOWN_ITEM` ya tienen el Item real en la OV desde su creación (Spec 015); la Spec 018 los reserva directamente sobre esa línea. **Quedan fuera de esta Spec**; la sección 12 "KNOWN/real line" no genera desarrollo.
- Criterio de implementación: usar lo más default posible de ERPNext; solo se reemplaza lo que rompe las reservas parciales (ver `plan.md`).

## 1. Tesis

`ENCARGO-PENDIENTE` es una línea técnica y transitoria que representa una obligación comercial cuyo Item real todavía no está determinado.

Cuando una unidad física llega a Chile, es identificada o creada como Item real por la Spec 018 e ingresa a inventario. Si esa unidad está comprometida con un Encargo, en ese mismo momento la obligación deja de ser abstracta para esa cantidad.

La Orden de Venta debe materializar progresivamente esa cantidad:

- reducir la cantidad aún indeterminada en `ENCARGO-PENDIENTE`;
- crear o incrementar una línea con el Item real recibido;
- conservar la trazabilidad completa hacia el Encargo de origen;
- utilizar desde entonces el Item real para reserva, entrega, facturación e inventario.

La personalización existe mientras el producto es desconocido. Una vez materializado, el flujo debe volver al estándar de ERPNext tanto como sea posible.

## 2. Principio de negocio

La Orden de Venta debe terminar representando lo que realmente se entregará al cliente.

El Encargo conserva la historia de cómo se llegó a esa realidad.

Por tanto:

- `ENCARGO-PENDIENTE` no debe permanecer como línea activa cuando su cantidad ya fue completamente materializada;
- no se mantienen simultáneamente una línea técnica y una línea real para representar la misma cantidad;
- la trazabilidad histórica vive en vínculos explícitos con el Encargo y en auditoría, no duplicando cantidades comerciales.

## 3. Momento de materialización

La materialización ocurre exclusivamente durante la recepción física en Chile, después de que:

1. FRAreceptor escanea una unidad;
2. Spec 018 identifica o crea el Item real;
3. la unidad ingresa a inventario;
4. el sistema determina que está comprometida con un Encargo;
5. se muestra el warning de separación física;
6. se ejecuta la materialización progresiva en la OV.

NO materializar:

- al crear el Encargo;
- al comprar el Shopper;
- al registrar barcode/fotos/precio;
- antes de que exista recepción física en Chile.

## 4. Split progresivo

La cantidad de `ENCARGO-PENDIENTE` representa únicamente lo que todavía no se ha materializado.

Ejemplo inicial:

`ENCARGO-PENDIENTE x3`

Llega una unidad de Item A:

- `Item A x1`
- `ENCARGO-PENDIENTE x2`

Llega otra unidad de Item A:

- `Item A x2`
- `ENCARGO-PENDIENTE x1`

Llega una unidad de Item B:

- `Item A x2`
- `Item B x1`

En ese momento desaparece la línea `ENCARGO-PENDIENTE` porque su cantidad pendiente llegó a cero.

El split debe soportar variantes distintas para una misma obligación original.

## 5. Regla por unidad recibida

Cada unidad de recepción comprometida produce una operación lógica de:

`materialize_encargo_unit(reception_unit)`

La operación debe:

1. identificar Encargo;
2. identificar Sales Order y Sales Order Item técnico de origen;
3. identificar Item real recibido;
4. verificar que aún exista cantidad pendiente por materializar;
5. reducir en 1 la cantidad técnica pendiente;
6. crear una nueva línea real o incrementar una línea real compatible;
7. vincular la cantidad materializada con Encargo y Recepción Unidad;
8. conservar condiciones comerciales;
9. actualizar estado de materialización del Encargo;
10. garantizar idempotencia.

## 6. Compatibilidad para incrementar una línea existente

Una unidad recibida puede incrementar una línea real previamente creada por el mismo Encargo solo cuando coincidan al menos:

- Sales Order;
- Encargo de origen;
- Item;
- precio de venta;
- descuento;
- UOM;
- almacén/destino comercial que corresponda;
- impuestos o atributos de línea relevantes.

Si no coinciden, crear una línea separada.

No fusionar automáticamente líneas de Encargos diferentes aunque el Item sea el mismo, porque se perdería trazabilidad de origen.

## 7. Condiciones comerciales heredadas

La materialización es logística, no una renegociación comercial.

La nueva línea real debe heredar de la línea técnica original:

- precio de venta;
- descuento;
- rate;
- price list rate cuando corresponda;
- UOM;
- comisión / Sales Team que derive de la OV;
- centro de costo/proyecto si existiera;
- impuestos que dependan de la línea;
- cualquier campo comercial relevante definido en personalizaciones FRA.

El costo real de compra del Shopper NO modifica automáticamente el precio vendido al cliente.

## 8. Relación con el Encargo

Cada línea real creada por materialización debe guardar un vínculo explícito al Encargo de origen.

Campo lógico requerido en Sales Order Item:

`custom_encargo_origin`

Además debe conservarse referencia a la línea técnica original:

`custom_encargo_source_row`

El Encargo debe mantener:

- Sales Order;
- línea técnica original;
- líneas reales materializadas;
- cantidad solicitada;
- cantidad materializada;
- cantidad pendiente;
- Recepción Unidad relacionadas.

La trazabilidad esperada debe permitir reconstruir:

`OV -> ENCARGO-PENDIENTE original -> ENC -> compra Shopper -> recepción -> Item real -> línea real OV -> entrega`.

## 9. Línea técnica ENCARGO-PENDIENTE

### 9.1 Materialización parcial

Mientras quede cantidad pendiente:

- la línea técnica permanece visible;
- su cantidad debe representar solo la cantidad todavía indeterminada;
- debe mostrar estado `Pendiente de materializar`.

### 9.2 Materialización total

Cuando cantidad pendiente = 0:

- la línea `ENCARGO-PENDIENTE` deja de ser una línea comercial activa;
- debe eliminarse de la colección activa de Items de la OV si ERPNext permite hacerlo correctamente mediante el mecanismo soportado;
- si ERPNext no permite eliminación segura en una OV submitted, debe marcarse como línea técnica cerrada/no entregable y cantidad operativa cero mediante el mecanismo compatible con ERPNext;
- nunca debe poder participar en Delivery Note, facturación, reserva ni cálculo de disponibilidad después de materialización total.

La decisión técnica exacta debe respetar las restricciones de ERPNext para Sales Orders submitted, pero el comportamiento funcional anterior es obligatorio.

## 10. Orden de Venta submitted

La OV normalmente ya estará validada/submitted cuando llegue la mercadería.

La implementación NO debe modificar directamente tablas SQL ni saltarse las reglas documentales de ERPNext.

El programador debe verificar el mecanismo estándar disponible para:

- Update Items / actualización de artículos;
- modificación de cantidades;
- inserción de líneas en Sales Order submitted;
- preservación de delivered_qty / billed_qty y referencias posteriores.

Si ERPNext no permite alguna parte del split mediante API estándar, implementar una acción backend controlada que replique las validaciones necesarias y deje auditoría explícita.

No cancelar/recrear automáticamente la OV como estrategia por defecto.

## 11. Cantidades ya entregadas o facturadas

La materialización solo puede operar sobre cantidad técnica todavía no entregada ni facturada.

Debe bloquearse cualquier transformación inconsistente si:

- la línea técnica ya fue usada erróneamente en Delivery Note;
- existe delivered_qty contra `ENCARGO-PENDIENTE`;
- existe billed_qty contra `ENCARGO-PENDIENTE`;
- la cantidad pendiente calculada no coincide con la trazabilidad del Encargo.

Mensaje:

`La línea ENCARGO-PENDIENTE tiene movimientos posteriores incompatibles. Requiere revisión de ComercialFRA/System Manager antes de materializar.`

## 12. Reserva y apartado

Después de materializar una unidad:

### KNOWN/real line

Fuera de alcance (ver sección 0): la línea KNOWN ya es real y Spec 018 la reserva directamente.

La nueva cantidad del Item real pasa a ser la representación comercial entregable.

Si Spec 018 ya creó una reserva estándar compatible, reutilizarla/ajustarla.

Si el mecanismo estándar requiere que la reserva apunte a la nueva línea de Sales Order, actualizar el vínculo de manera controlada.

No crear doble reserva.

### UNKNOWN_ITEM materializado

La recepción inicialmente pudo quedar apartada por:

- bodega `Recepcion Encargos - FRAG`;
- vínculo exclusivo con Encargo.

Una vez creada la línea real en la OV, convertir ese apartado en la reserva estándar de ERPNext cuando sea técnicamente posible.

El objetivo final es que el Item real y la línea real de OV sean suficientes para el flujo estándar de entrega.

## 13. Entrega

Después de la materialización:

- Delivery Note debe usar exclusivamente los Items reales;
- `ENCARGO-PENDIENTE` no debe aparecer como producto entregable;
- la salida de inventario debe descontar el Item real;
- la trazabilidad a ENC se conserva desde la línea real.

La Spec 017 agrega además la regla de elegibilidad por excepción de barcode: cantidades `PENDING_APPROVAL` o `REJECTED` no son entregables. Para líneas KNOWN_ITEM mixtas puede entregarse únicamente la porción elegible; esta validación pertenece a Spec 017.

Para el caso de Kevin, no se debe realizar entrega desde ERPNext hasta que la cantidad correspondiente haya sido materializada en la OV.

## 14. Producto recibido que finalmente no satisface al cliente

No crear un flujo especial de devolución por Encargo.

Si un Item ya recibido/materializado debe liberarse porque ComercialFRA determina que no satisface al cliente:

1. aplicar devolución/liberación estándar según el estado documental;
2. liberar reserva/apartado;
3. mover la unidad a stock normal cuando corresponda;
4. revertir la satisfacción de esa cantidad del Encargo;
5. restaurar esa cantidad como pendiente de materializar/comprar cuando la obligación comercial siga vigente;
6. mantener toda la auditoría del intento anterior.

No devolver automáticamente al Shopper.

Si la venta fue formalmente cancelada o modificada, se aplican las reglas estándar de ERPNext más la actualización del Encargo.

## 15. Idempotencia

Cada `Recepción Unidad` solo puede materializarse una vez.

Agregar vínculo/estado mínimo:

- `materialization_status`: PENDING / MATERIALIZED / REVERSED / ERROR;
- Sales Order Item real generado o incrementado;
- fecha/hora;
- usuario/servicio;
- cantidad materializada (=1 por Recepción Unidad).

Reintentar el mismo evento no debe volver a reducir `ENCARGO-PENDIENTE` ni duplicar Item real.

## 16. UI - FRAreceptor

El FRAreceptor no participa en decisiones comerciales.

Después del escaneo, la pantalla continúa mostrando el warning definido por Spec 018:

`APARTAR - ENC-2026-XXXXX`

El receptor no ve botones para:

- transformar OV;
- elegir Item;
- elegir línea;
- decidir cantidades;
- aprobar split.

La materialización ocurre automáticamente en backend después de una recepción exitosa y comprometida.

Si materialización falla después de que el inventario entró, mostrar:

`APARTAR - ENC-2026-XXXXX - PENDIENTE DE VINCULAR A OV`

El receptor igualmente separa físicamente la unidad. El error va a ComercialFRA/System Manager; nunca se revierte silenciosamente el ingreso físico a inventario.

## 17. UI - ComercialFRA

### 17.1 Sales Order

Cada línea derivada de Encargo debe mostrar:

- Item real;
- cantidad;
- indicador `Encargo`;
- link navegable a `ENC-2026-XXXXX`;
- estado de reserva/recepción cuando sea útil.

La línea `ENCARGO-PENDIENTE` parcial debe mostrar:

- cantidad todavía pendiente;
- Encargo;
- cantidad ya materializada.

### 17.2 Encargo

Agregar sección `Materialización en OV`:

- cantidad solicitada;
- cantidad materializada;
- cantidad pendiente;
- Items reales materializados;
- links a líneas reales de OV;
- recepciones que originaron cada materialización.

### 17.3 Excepciones

MCV Chile > Recepción > Pendientes de vincular a OV

Debe listar casos donde:

- inventario fue recibido/apartado;
- existe Encargo;
- materialización automática falló.

Acciones:

- revisar causa;
- reintentar materialización;
- abrir OV;
- abrir Encargo;
- abrir Recepción Unidad.

ComercialFRA no edita cantidades manualmente desde esta lista; el reintento usa la misma lógica determinística.

## 18. Auditoría

Por cada materialización registrar:

- Recepción Unidad;
- scan_event_id;
- Encargo;
- Sales Order;
- Sales Order Item técnico de origen;
- Sales Order Item real;
- Item real;
- cantidad;
- cantidad técnica antes/después;
- cantidad materializada acumulada;
- fecha/hora;
- resultado;
- error si existe;
- reversión posterior si aplica.

## 19. Casos especiales

### 19.1 Variantes distintas

Permitido.

Un Encargo de cantidad 3 puede terminar en tres Items distintos.

### 19.2 Mismo Item recibido varias veces

Incrementar línea real compatible del mismo Encargo.

### 19.3 Dos Encargos distintos para mismo Item y misma OV

Mantener líneas separadas si es necesario para preservar origen.

### 19.4 Recepción superior a cantidad pendiente

Bloquear materialización adicional para ese Encargo.

La unidad física ya recibida no desaparece; debe quedar como stock normal o excepción a resolver, pero no puede consumir una demanda inexistente.

### 19.5 OV cancelada

No materializar.

La unidad recibida pasa por la regla de stock normal/resolución comercial de Spec 018.

## 20. Permisos

- `FRAreceptor`: solo escanea; no ejecuta acciones comerciales.
- `ComercialFRA`: consulta materialización, excepciones y puede reintentar procesos controlados.
- `System Manager`: soporte excepcional/regularización.
- backend: realiza split con permisos controlados y validaciones.
- Shopper: no interviene.

## 21. Pruebas mínimas

1. ENCARGO-PENDIENTE x1 + recepción Item A -> línea Item A x1 y sin línea técnica activa.
2. ENCARGO-PENDIENTE x3 + primera recepción Item A -> Item A x1 + pendiente x2.
3. segunda recepción mismo Item -> Item A x2 + pendiente x1.
4. tercera recepción Item B -> Item A x2 + Item B x1 + pendiente 0.
5. dos variantes distintas conservan vínculo al mismo ENC.
6. misma Recepción Unidad reintentada no materializa dos veces.
7. precio de venta heredado no cambia por purchase_price.
8. descuentos/impuestos relevantes se conservan.
9. Item real queda vinculado a Encargo.
10. OV permite navegar desde línea real al Encargo.
11. Delivery Note propone/usa Item real y nunca ENCARGO-PENDIENTE materializado.
12. reserva no se duplica.
13. falla posterior al Stock Entry deja unidad apartada y caso pendiente de vincular a OV.
14. reintento resuelve el mismo caso sin duplicar cantidades.
15. recepción excedente no reduce pendiente bajo cero.
16. OV cancelada no se materializa.
17. devolución/liberación restaura cantidad pendiente cuando la obligación continúa.
18. delivered_qty/billed_qty incompatibles bloquean transformación.
19. ComercialFRA ve cantidades solicitada/materializada/pendiente.
20. Kevin/ENC-2026-00401 queda con Item real en OV antes de Delivery Note.

## 22. Relación con Spec 018

Spec 018 termina conceptualmente cuando:

- la unidad física fue escaneada;
- existe Item real;
- existe movimiento de inventario o estado explícito pendiente;
- se determinó si está comprometida con Encargo.

Spec 019 comienza cuando una unidad ya ingresada y comprometida debe convertirse en parte real de la Orden de Venta.

La recepción no debe duplicar lógica comercial. La materialización no debe duplicar lógica de inventario.

## 23. Orden de ejecución

1. Completar Spec 018.
2. Implementar Spec 019.
3. Ejecutar piloto ENC-2026-00401 / OV-2026-00326.
4. Confirmar que la OV contiene el Item real.
5. Solo entonces probar Delivery Note/entrega.
6. Spec 017 puede continuar después según prioridad acordada.

## 24. Criterio de cierre

La Spec queda cumplida cuando cada unidad comprometida que entra físicamente a Chile transforma de forma idempotente una unidad de `ENCARGO-PENDIENTE` en un Item real dentro de la misma Orden de Venta, soportando materialización parcial y variantes, conservando condiciones comerciales y trazabilidad, y dejando la venta preparada para reserva y entrega estándar de ERPNext.
