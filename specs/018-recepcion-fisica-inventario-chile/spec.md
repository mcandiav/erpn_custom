# Spec 018 - Recepción física e inventario Chile

Estado: CERRADA POR MIGUEL EL 2026-10-15; programada en 16.0.119 y validación operativa parcial aceptada en 16.0.122
Prioridad: BASE DE RECEPCION; alineada por Spec 020 para demanda multifuente
Fecha: 2026-10-06
Rol solicitante: Arquitecto
Proyecto: ERPNext Custom / FRAgallardo

## 1. Tesis

La apertura de cajas desaduanadas en Chile es el punto de verdad físico.

Cada escaneo representa UNA unidad física recibida. El sistema debe:

1. identificar la unidad;
2. determinar si satisface un Encargo;
3. crear o resolver el Item real cuando corresponda;
4. ingresar la unidad al inventario mediante movimiento ERPNext;
5. apartarla para cliente cuando existe demanda válida o dejarla como stock normal;
6. dejar trazabilidad unitaria e idempotente.

El usuario `FRAreceptor` escanea y nada más. No clasifica, no elige cliente, no decide Item, no selecciona bodega y no opera Stock Entry manualmente.

## 2. Dependencia real

Esta Spec define la recepción física. La asignación de una unidad a demanda abierta debe seguir el modelo de **Spec 020**.

Regla corregida:

- un Encargo compatible puede recibir una unidad aunque no exista compra Shopper previa;
- `purchase_status = PURCHASED` NO es requisito para que recepción detecte y aparte una unidad contra demanda;
- Spec 017 interviene solo cuando existe una excepción barcode que requiera decisión comercial;
- Spec 019 materializa la línea únicamente para `UNKNOWN_ITEM`.

## 3. Fuera de alcance

- landed cost definitivo;
- courier, aduana e impuestos finales;
- facturación o despacho al cliente;
- edición manual libre de Stock Entry por FRAreceptor;
- reemplazo definitivo de la línea técnica `ENCARGO-PENDIENTE` dentro de una OV ya validada.

## 4. Unidad de recepción e idempotencia

Cada lectura válida equivale a UNA unidad.

El barcode NO identifica una unidad única: varias unidades del mismo producto pueden compartirlo.

Por tanto, la idempotencia NO se implementa por barcode.

Cada intento de recepción debe generar un `scan_event_id` / UUID único desde el cliente de recepción y persistirlo en la bitácora.

Reglas:

- un mismo `scan_event_id` solo puede consumirse una vez;
- reintento de la misma petición no crea un segundo movimiento;
- dos escaneos distintos con el mismo barcode representan dos unidades válidas;
- el backend debe proteger la operación transaccionalmente.

Eliminar la regla anterior “barcode ya recibido = duplicado”.

`DUPLICADO` significa exclusivamente que se recibió nuevamente el mismo `scan_event_id` o la misma transacción de recepción.

## 5. Cantidades de Encargo

Un Encargo puede tener `requested_qty > 1`.

Esta Spec conserva `received_qty` como verdad física de recepción, pero la necesidad residual de abastecimiento se calcula según Spec 020.

Contadores relevantes:

- `requested_qty`: demanda original;
- `sourced_qty`: definido por Spec 020;
- `pending_supply_qty`: definido por Spec 020;
- `received_qty`: unidades físicamente recibidas y vinculadas a esa demanda;
- `pending_receive_qty`: cantidad abastecida que aún espera recepción, cuando corresponda.

Cada escaneo asignado al Encargo incrementa la recepción física una sola vez y genera/reconcilia el Supply Event correspondiente.

La recepción completa no debe inferirse únicamente de `received_qty >= requested_qty` si parte de la demanda fue resuelta por stock u otra fuente; debe reconciliarse con Spec 020.

La asignación entre Encargos compatibles usa FIFO: demanda compatible más antigua primero.

## 6. Creación automática de Item para UNKNOWN_ITEM

Decisión arquitectónica: se adopta la opción automática.

Cuando un `UNKNOWN_ITEM` comprado llega a Chile y todavía no tiene Item real, el backend debe crear el Item antes del Stock Entry usando la información consolidada en el Encargo y las reglas de Spec 014.

Fuentes mínimas:

- marca;
- Grupo;
- Familia;
- Tipo/Departamento según modelo vigente de Spec 014;
- descripción/nombre de producto;
- color;
- talla y otros atributos aplicables;
- género cuando corresponda;
- barcode real comprado;
- evidencias disponibles.

El barcode real debe agregarse a `Item Barcode`.

El Item creado se vincula al Encargo antes de generar inventario.

### 6.1 Código del Item creado automáticamente

Regla determinística:

- si el barcode contiene únicamente letras, números y guion, y su longitud es de hasta 40 caracteres, puede utilizarse como `item_code`;
- si el barcode contiene URL, caracteres especiales, espacios, una longitud mayor a 40 caracteres o cualquier formato no apropiado como identificador maestro, NO debe utilizarse como `item_code`;
- en esos casos se utilizará una serie propia de FRA, por ejemplo `FRA-00001`, `FRA-00002`, etc.;
- el valor físico escaneado se conserva íntegro en `Item Barcode`, aunque sea una URL o QR.

El `item_code` es un identificador maestro interno. El barcode es un identificador físico y ambos no deben confundirse.

### 6.2 Datos incompletos

El FRAreceptor nunca completa maestros.

Si excepcionalmente faltan datos obligatorios para crear un Item válido según Spec 014:

- registrar el escaneo como `PENDING_CLASSIFICATION`;
- no generar un Item defectuoso;
- no generar Stock Entry todavía;
- mostrar al receptor únicamente `APARTAR - REQUIERE CLASIFICACION` junto con el código `ENC-2026-XXXXX`;
- enviar el caso a una cola `Pendientes de clasificación` para ComercialFRA.

ComercialFRA completa los datos faltantes y ejecuta `Resolver`. El backend crea Item, genera el movimiento y conserva el `scan_event_id` original.

Este caso es una excepción; el flujo normal de UNKNOWN_ITEM debe ser automático.

### 6.3 Barcode desconocido sin Encargo

Si el barcode escaneado:

- no existe en ningún `Item Barcode`;
- no corresponde a un Encargo pendiente;
- y por tanto no existe Item identificable automáticamente,

el receptor NO debe crear ni elegir un Item.

Se debe:

- registrar la unidad como `PENDING_CLASSIFICATION` sin Encargo;
- mostrar `STOCK NORMAL - REQUIERE CLASIFICACION`;
- no generar Stock Entry todavía;
- enviar el caso a `Recepción > Pendientes de clasificación`.

ComercialFRA debe poder:

1. seleccionar un Item existente o crear uno nuevo;
2. asociar el barcode al Item;
3. ejecutar `Resolver`;
4. completar el ingreso a `Matriz - FRAG` utilizando el mismo `scan_event_id`.

## 7. KNOWN_ITEM

Orden de resolución:

1. si barcode existe en `Item Barcode`, usar ese Item;
2. si Encargo `KNOWN_ITEM` define Item esperado y el barcode coincide, usar ese Item;
3. para compras nuevas posteriores a Spec 017, la adopción del primer barcode ocurre al comprar;
4. para compras históricas anteriores a Spec 017, si el Item esperado aún no tiene barcode y no existe excepción pendiente, recepción puede adoptar el primer barcode único como fallback de compatibilidad;
5. si hay mismatch pendiente de aprobación, NO ingresar ni asignar automáticamente;
6. si mismatch está aprobado, usar el Item aprobado;
7. si mismatch está rechazado, la unidad deja de satisfacer el Encargo y se procesa como stock normal: Item identificable -> `Matriz - FRAG`; Item no identificable -> `PENDING_CLASSIFICATION` sin Encargo.

Si una unidad quedó previamente en `PENDING_BARCODE_APPROVAL`:

- aprobar la excepción debe reintentar automáticamente esa misma `Recepción Unidad`, sin nuevo escaneo;
- rechazar debe reanudarla automáticamente por la ruta de stock normal/clasificación, sin esperar otra decisión comercial para reconocer la existencia física.

### 7.1 Asignación a demanda abierta sin compra previa

Para `KNOWN_ITEM`, una unidad físicamente escaneada debe buscar demanda compatible aunque el Encargo todavía no tenga compra Shopper.

Criterios mínimos:

- Encargo `Open`;
- Item esperado compatible con el Item/barcode escaneado;
- necesidad residual/cobertura pendiente según Spec 020;
- sin excepción comercial que prohíba esa asignación.

No filtrar candidatos exclusivamente por `purchase_status = PURCHASED`.

Si existe demanda compatible:

1. vincular `Recepcion Unidad` al Encargo;
2. destino `Recepcion Encargos - FRAG` cuando corresponda;
3. mostrar `APARTAR - ENC-2026-XXXXX`;
4. crear/reconciliar el Supply Event `RECEPTION_DIRECT`;
5. actualizar demanda residual, reservas y resumen de la OV mediante Spec 020.

Solo si no existe demanda compatible la unidad puede seguir como `STOCK NORMAL`.

## 8. Bodegas

Decisión arquitectónica:

### 8.1 Unidades que satisfacen Encargo

Crear mediante patch:

`Recepcion Encargos - FRAG`

Uso: inventario físicamente recibido y apartado para un cliente/demanda.

No es stock libre para nuevas ventas.

### 8.2 Stock normal

Cuando una unidad no satisface ningún Encargo pendiente y su Item está correctamente identificado:

destino directo:

`Matriz - FRAG`

No se crea una bodega intermedia `Recepcion Stock - FRAG`.

Razón: una unidad ya identificada y sin demanda pendiente es stock normal; crear una bodega transitoria obligaría a un segundo movimiento sin agregar decisión operativa.

### 8.3 Excepciones

No crear bodega de cuarentena en esta fase.

Una excepción no aprobada NO genera Stock Entry. Queda como evento de recepción pendiente y la unidad debe apartarse físicamente según el mensaje de pantalla.

## 9. Documento de inventario

Usar `Stock Entry` tipo `Material Receipt` para la entrada inicial.

El backend crea y envía el documento con elevación controlada.

`FRAreceptor` no recibe permisos generales para crear/editar Stock Entry.

Cada movimiento debe enlazar la bitácora de recepción y, cuando aplique:

- Encargo;
- Sales Order;
- Sales Order Item;
- Item;
- scan_event_id.

## 10. Contrapartida contable

Crear/configurar la cuenta:

`Compras Shopper por regularizar - FRAG`

Clasificación contable objetivo: cuenta transitoria / clearing de corto plazo utilizada como contrapartida provisional del ingreso de inventario hasta que el costo/pago se regularice por el proceso financiero correspondiente.

La cuenta NO debe ir directamente a una cuenta de gasto/resultado de ajuste de stock.

La cuenta NO será creada por patch.

El Configurador debe crearla una sola vez desde la interfaz de ERPNext, dentro del padre contable correcto del plan FRAG, y luego seleccionarla en `Configuración Recepción FRA`.

Mientras la cuenta no esté configurada:

- el sistema puede registrar el escaneo;
- debe mostrar un aviso de configuración pendiente;
- NO debe generar movimiento de inventario.

El nombre y propósito de la cuenta son parte de esta Spec; el Configurador/contador solo valida su ubicación contable técnica, no redefine el flujo.

## 11. Moneda y costo provisional

### 11.1 Compra Shopper

El campo actual `purchase_price` se interpreta como monto en moneda de compra.

Para las compras Shopper de Miami, la moneda por defecto es:

`USD`.

Agregar `purchase_currency` si no existe, con valor por defecto `USD`, dejando explícita la moneda y evitando inferencias futuras.

### 11.2 Tipo de cambio

Para convertir a CLP:

1. usar el tipo de cambio vigente de ERPNext para `USD -> CLP` correspondiente a la fecha de compra del Shopper (`purchased_on`), aunque el Stock Entry se registre en la fecha de recepción en Chile;
2. guardar el exchange rate efectivamente utilizado en la bitácora;
3. si ERPNext no dispone de tasa válida, usar una tasa provisional configurada explícitamente en una configuración FRA;
4. si tampoco existe tasa provisional, bloquear solo la contabilización de ese evento y mostrarlo en una cola de configuración; no inventar tasa.

No usar una tasa fija hardcodeada.

### 11.3 Costo de unidad comprada por Shopper

Costo provisional de entrada:

`purchase_price * exchange_rate`.

Courier, aduana, impuestos y otros costos se incorporan después por landed cost/proceso posterior.

### 11.4 Stock normal sin compra Shopper asociada

Si el barcode corresponde a un Item conocido pero no hay Encargo/precio Shopper:

1. usar `valuation_rate` vigente del Item;
2. si es 0/no disponible, usar el último incoming rate válido;
3. si tampoco existe, dejar el evento en `PENDING_COST` y no inventar valorización cero.

Valorización cero NO es el comportamiento normal permitido para una unidad física con costo desconocido.

## 12. Destino y mensaje al FRAreceptor

### Caso A - satisface Encargo

Pantalla:

`APARTAR - ENC-2026-XXXXX`

Puede mostrar además descripción/Item, Cliente y número de Orden de Venta como información operativa de solo lectura.

Se mantiene la UI vigente del receptor mostrando Cliente y OV junto al ENC. El receptor no puede elegirlos ni editarlos. El sistema los determina automáticamente y el dato principal para separación física continúa siendo el código ENC.

Destino:

`Recepcion Encargos - FRAG`.

### Caso B - no existe Encargo pendiente y el Item es conocido

Pantalla:

`STOCK NORMAL`

Destino:

`Matriz - FRAG`.

### Caso B2 - no existe Encargo y el barcode no identifica un Item

Pantalla:

`STOCK NORMAL - REQUIERE CLASIFICACION`

No Stock Entry hasta que ComercialFRA seleccione o cree el Item y ejecute `Resolver`.

### Caso C - excepción de barcode pendiente

Pantalla:

`APARTAR - REQUIERE COMERCIAL`

No Stock Entry mientras siga `PENDING_APPROVAL`.

Cuando ComercialFRA aprueba, el backend reintenta la misma recepción automáticamente. Cuando rechaza, la unidad se desvincula de esa demanda y continúa por stock normal o clasificación.

### Caso D - datos insuficientes para UNKNOWN_ITEM

Pantalla:

`APARTAR - REQUIERE CLASIFICACION - ENC-2026-XXXXX`

No Stock Entry hasta resolución.

### Caso E - problema de costo/tipo de cambio

Pantalla:

`RECIBIDO - PENDIENTE DE VALORIZACION`

El evento queda retenido para resolución controlada. No se crea un Stock Entry con datos inventados.

## 13. Reserva para el cliente

### KNOWN_ITEM

Cuando una unidad `KNOWN_ITEM` satisface un Encargo y entra en `Recepcion Encargos - FRAG`:

- incrementar recepción del Encargo;
- crear o actualizar la reserva estándar de stock de ERPNext para la línea correspondiente de la Sales Order, cuando el mecanismo estándar lo permita;
- la reserva debe apuntar a la unidad/cantidad ya recibida y apartada;
- evitar doble reserva de la cantidad que ya estaba cubierta antes de crear el Encargo.

### UNKNOWN_ITEM

Mientras la OV conserve la línea técnica `ENCARGO-PENDIENTE`, no es correcto crear una Stock Reservation Entry estándar contra un Item diferente de la línea.

Por tanto:

- el apartado se garantiza mediante la bodega `Recepcion Encargos - FRAG` + vínculo exclusivo con Encargo/OV;
- el Item real queda vinculado al Encargo;
- la futura transformación de la línea OV a Item real deberá convertir ese apartado en reserva estándar sin duplicar cantidades.

## 14. Devolver a stock

Acción exclusiva de ComercialFRA desde la vista de unidades apartadas:

`Devolver a stock`.

Debe:

1. validar que la unidad/cantidad pueda liberarse;
2. cancelar/liberar la reserva estándar cuando exista;
3. quitar la asignación exclusiva del Encargo;
4. ejecutar `Material Transfer` desde `Recepcion Encargos - FRAG` hacia `Matriz - FRAG`;
5. actualizar el Encargo con el estado de resolución vigente, incluyendo `RESOLVED_TO_STOCK` cuando corresponda;
6. exigir motivo;
7. dejar auditoría completa.

No devolver al Shopper.

## 15. UI - FRAreceptor

Pantalla mobile-first.

Elementos:

- campo/lector principal;
- resultado grande tras cada lectura;
- código ENC cuando deba apartar;
- descripción/Item como apoyo;
- mensajes definidos en §12;
- historial inmediato de las últimas lecturas de la sesión.

No mostrar controles para:

- elegir bodega;
- crear Item;
- elegir OV;
- elegir cliente;
- definir costo;
- resolver mismatch;
- operar Stock Entry.

## 16. UI - ComercialFRA

Entradas de navegación explícitas:

### Recepción > Apartados

Lista de unidades recibidas y vinculadas a Encargo.

Acciones:

- abrir Encargo;
- abrir Item;
- revisar trazabilidad;
- `Devolver a stock`.

### Recepción > Pendientes de clasificación

Solo excepciones donde no fue posible crear Item automáticamente.

Acciones:

- completar datos requeridos;
- `Resolver`.

### Recepción > Excepciones barcode

Casos pendientes de Spec 017.

### Recepción > Pendientes de valorización

Casos sin exchange rate/costo provisional suficiente.

ComercialFRA no obtiene permisos para Stock Entry libre; las acciones invocan servicios backend controlados.

## 17. Bitácora de recepción

Persistir por evento:

- `scan_event_id`;
- fecha/hora;
- FRAreceptor;
- barcode;
- Item;
- Encargo;
- Sales Order / Sales Order Item cuando aplique;
- resultado;
- Stock Entry;
- bodega destino;
- `purchase_currency`;
- `purchase_price`;
- exchange rate usado;
- valuation/incoming rate usado cuando corresponda;
- estado de clasificación;
- estado de valorización;
- usuario/fecha de cualquier resolución posterior.

## 18. Regularización inicial

Regularizar explícitamente los eventos creados antes de esta Spec que registraron recepción pero no inventario.

Caso piloto obligatorio:

- `ENC-2026-00401`;
- `OV-2026-00326`;
- Cliente Kevin Quijada Candia;
- recepción previa realizada por receptor de prueba.

La regularización debe reutilizar la misma lógica de negocio de esta Spec:

- resolver/crear Item;
- registrar scan/evento de migración;
- generar Stock Entry;
- vincular Encargo;
- establecer received_qty correcto;
- dejar auditoría.

La implementación será una acción explícita `Regularizar recepciones previas`, disponible únicamente para `System Manager`.

La acción:

- se ejecuta después de configurar la cuenta transitoria;
- genera un `scan_event_id` de migración por unidad;
- reutiliza exactamente el mismo servicio de recepción, sin una segunda lógica paralela;
- debe permitir regularizar `ENC-2026-00401` y cualquier otra recepción histórica que tenga evidencia suficiente y no tenga movimiento de inventario;
- no se ejecuta automáticamente en migrate ni mediante patch.

No resolver mediante edición manual directa de stock.

## 19. Patches / configuración

La implementación debe incluir:

1. patch para crear `Recepcion Encargos - FRAG` si no existe;
2. campos nuevos requeridos por contador de recepción, scan_event_id, moneda y trazabilidad;
3. DocType/configuración `Configuración Recepción FRA` con selección obligatoria de la cuenta transitoria y tasa USD->CLP de respaldo;
4. validación bloqueante si la cuenta transitoria no está configurada;
5. configuración de tipo de cambio provisional de respaldo, sin hardcode;
6. índices/constraints necesarios para unicidad de `scan_event_id`;
7. acción `Regularizar recepciones previas` para System Manager.

No crear `Recepcion Stock - FRAG` ni cuarentena en esta fase.

## 20. Pruebas mínimas

1. UNKNOWN_ITEM con clasificación completa crea Item automáticamente y barcode.
2. UNKNOWN_ITEM incompleto queda PENDING_CLASSIFICATION sin intervención del receptor.
3. KNOWN_ITEM normal usa Item esperado.
4. Dos unidades iguales con mismo barcode y dos scan_event_id distintos crean dos recepciones válidas.
5. Repetir el mismo scan_event_id no duplica movimiento.
6. requested_qty=3 requiere tres escaneos antes de recepción completa.
7. FIFO asigna primero al Encargo compatible más antiguo.
8. Demanda satisfecha ingresa a Recepcion Encargos - FRAG.
9. Unidad sin demanda ingresa directamente a Matriz - FRAG.
10. Barcode mismatch pendiente no genera Stock Entry.
11. KNOWN_ITEM recibido crea/actualiza reserva sin duplicar stock previamente reservado.
12. Devolver a stock libera reserva y transfiere a Matriz.
13. purchase_price USD usa Currency Exchange y registra tasa.
14. falta de tasa usa fallback configurado.
15. ausencia de ambas deja pendiente y no inventa tasa.
16. stock normal sin precio usa valuation rate / incoming rate.
17. costo desconocido no entra con cero silenciosamente.
18. FRAreceptor completa flujo sin permisos amplios de Stock Entry.
19. Regularización ENC-2026-00401 deja Item, movimiento, contador y auditoría correctos.
20. Barcode desconocido sin Encargo queda PENDING_CLASSIFICATION y luego puede resolverse a Item + Matriz.
21. Barcode URL/QR no se usa como item_code y queda únicamente en Item Barcode.
22. Barcode limpio de hasta 40 caracteres puede utilizarse como item_code.
23. Tipo de cambio corresponde a purchased_on, no a la fecha de recepción.
24. Sin cuenta transitoria configurada no se genera Stock Entry.
25. Acción Regularizar recepciones previas solo está disponible para System Manager.

## 21. Orden de implementación

Orden aprobado por Arquitectura:

1. Spec 018 primero: cerrar el vacío actual entre recepción física e inventario.
2. Spec 019 después: materializar progresivamente ENCARGO-PENDIENTE en Item real dentro de la OV.
3. Spec 017 después: completar excepción de barcode, aprobación comercial, estado por línea OV y advertencia previa.

La 018 debe apoyarse en el modelo real ya existente de 013/015, no esperar una reimplementación de demanda.

La transformación de la Orden de Venta NO pertenece a esta Spec. Si una unidad recibida está comprometida con Encargo, la 018 deja inventario, trazabilidad y apartado físico; la Spec 019 realiza el split progresivo de la línea comercial.

## 22. Criterio de cierre

La Spec 018 se considera terminada cuando un FRAreceptor puede abrir una caja y escanear cada unidad una sola vez, y el ERP deja esa unidad representada de manera determinística como inventario real apartado o stock normal, o como excepción explícita pendiente, sin decisiones manuales del receptor y sin perder trazabilidad contable u operativa.

## 23. Recepción provisional por caja (decisión D, 2026-10-10)

**Estado: CERRADA CON VALIDACION OPERATIVA PARCIAL ACEPTADA POR MIGUEL.** Esta sección sustituye íntegramente la propuesta previa de anulación inmediata de escaneos ya contabilizados. Donde las secciones 1, 4, 5, 7, 9, 12, 13, 15, 17, 20 y el plan hablen de contabilizar por cada lectura, léanse como comportamiento del **cierre**, no del escaneo provisional. La lógica transaccional existente de `receive_scan` se reutiliza/adapta en el cierre, no debe dispararse al agregar una línea al borrador.

### 23.1 Alcance y límites

Resolver errores de escaneo inmediatos sin reversas contables: una recepción provisional corresponde a **una caja física identificada por Chile**, sin exigir embalaje ni registro de cajas al Shopper. No construir ahora módulo de Aduana, gestión internacional de cajas, seguimiento, impresora de etiquetas ni DocType Caja independiente. La referencia de caja es permanente y servirá a su futura asociación con envíos/documentos aduaneros.

No añadir `box_id` al maestro Item: un mismo Item puede venir en múltiples cajas. Conservar vínculo Caja/Recepción -> Recepción Unidad (por cada unidad) -> Item, Encargo y Stock Entry, cuando existan. El historial de un Item podrá consultarlo usando esos vínculos.

### 23.2 Modelo mínimo

- Usar una **cabecera persistente** `Recepcion Caja` (nombre técnico ajustable a convención, una recepción por caja) o extender un DocType de sesión si ya existe y soporta el contrato completo; decidir tras inspección técnica y documentar elección. No crear además una entidad `Caja` separada.
- Cabecera: `name`/identificador interno `BOX-YYYY-NNNNN` único e inmutable, `status` DRAFT / FINALIZING / FINALIZED / FINALIZED_WITH_EXCEPTIONS, receptor, timestamps de apertura y cierre, fecha, referencia externa opcional (etiqueta de transportista tal como llegó), observaciones y totales.
- Cada línea de borrador representa **una unidad**: `scan_event_id` único, ordinal, barcode bruto (incluye QR/URL), timestamp, receptor, estado de la línea y posterior vínculo a `Recepcion Unidad`; nunca usar barcode como clave única. Una relectura del mismo scan_event_id no inserta otra línea; escaneos separados de barcode idéntico sí pueden ser unidades legítimas.
- Las líneas descartadas antes del cierre quedan excluidas del procesamiento; para auditoría conservar evento de descarte en la bitácora de borrador con usuario y fecha, sin crear `Recepcion Unidad` contabilizada.
- `Recepcion Unidad` final debe referenciar `BOX-...` y su línea/evento de origen. La referencia nunca se modifica silenciosamente después de finalizar.
- La cabecera y líneas se guardan en **servidor** después de cada lectura; el navegador/celular no es fuente única de verdad. Permitir reabrir una caja DRAFT tras desconexión.

### 23.3 Flujo UI ReceptorFRA (mobile-first)

Acceso: workspace/ícono **Recepción** -> **Abrir caja / Continuar caja**; listar solo borradores autorizados al usuario (con acceso de supervisión para System Manager). En **Abrir caja**, generar BOX automáticamente sin exigir código de origen; permitir anotar etiqueta externa opcional. Abrir lector con encabezado BOX, estado BORRADOR, contador y lista cronológica de escaneos. Mostrar barcode, Item/ENC/Cliente/OV solo como **vista preliminar no comprometida** cuando pueda inferirse, nunca prometer reserva ni ubicación definitiva.

**Corrección de implementación 16.0.123:** la UI de 16.0.119 conservó datos preliminares en cada línea, pero eliminó el aviso inmediato y destacado de destino. Fue un error de implementación entre dos requisitos simultáneos de este contrato, no una redefinición funcional. Durante DRAFT cada lectura debe mostrar `DESTINO PREVISTO: APARTAR - ENC-...`, `DESTINO PREVISTO: STOCK NORMAL` o `DESTINO PREVISTO: SIN COINCIDENCIA`, identificado expresamente como preliminar y sujeto al recálculo definitivo al finalizar. Mostrar esta previsión no autoriza escrituras sobre Item, inventario, reserva, Supply Event ni demanda.

Acción **Quitar lectura** en cada fila borrador con confirmación ligera y recuperación de escaneo mediante nueva lectura. No pedir motivo para esta corrección operativa. Ofrecer aviso *posible doble lectura consecutiva* sin eliminar ni bloquear automáticamente barcodes repetidos. Acciones: **Continuar escaneando**, **Finalizar recepción**, **Volver a mis cajas abiertas**. Nunca elegir Item, bodega, OV o cliente. No exponer botón Quitar después del cierre.

El botón **Finalizar recepción** muestra BOX, cantidad de líneas activas, descartadas y confirmación explícita. Una caja sin líneas activas no puede finalizarse como recepción. Tras confirmar, bloquear nuevos escaneos y presentar resultado por unidad: **APARTAR - ENC-...**, **STOCK NORMAL** o las excepciones existentes de §12; indicar totales y vínculos. La caja queda consultable en **Recepción > Historial de cajas**, con filtros BOX, fecha, receptor, barcode, ENC, OV, estado y enlaces a detalle de unidad/Item/Encargo.

Permisos: FRAreceptor crea cajas DRAFT, puede continuar cajas DRAFT de otros usuarios FRAreceptor autorizados por cambio de turno, escanea, descarta lecturas y finaliza; se audita cada autor. No edita cajas cerradas ni Stock Entry. System Manager consulta todas y gestiona excepciones supervisadas. ComercialFRA conserva las colas de resolución de §16. Validaciones reales en backend.

### 23.4 Confirmación y efectos (backend)

- **Escaneo DRAFT:** solo persistir la línea, sin crear Item, Stock Entry, Stock Reservation Entry, Supply Event, contadores de Encargo ni movimientos contables; no marcar demanda como satisfecha.
- **Finalizar:** bloquear cabecera y líneas de esa caja; usar clave idempotente del cierre y bloquear cada `scan_event_id` para evitar doble contabilización con reintentos/concurrencia. Recuperar el conjunto inmutable de líneas activas.
- Procesar por unidad mediante los servicios actuales de la Spec 018, conciliando con Spec 020 y demanda FIFO **al momento del cierre**, no al escanear. Aplicar entonces clasificación, creación de Item, costo, Stock Entry, Encargo/reserva y resultados existentes.
- **Fallo de una unidad** por clasificación, mismatch, costo o configuración: conservar evento final de esa unidad como pendiente según los estados ya definidos, sin inventar stock; no bloquear las demás unidades correctas. Fallos técnicos transitorios no deben duplicar movimientos: registrar progreso/errores y permitir **Reintentar procesamiento** únicamente de líneas no consumadas, de manera idempotente y bajo control backend; el receptor no altera el contenido de la caja cerrada.
- `FINALIZED` significa todas las líneas con resultado definitivo, y `FINALIZED_WITH_EXCEPTIONS` significa recepción física confirmada con excepciones pendientes. Una caja cerrada nunca regresa a DRAFT.
- Revalidar saldos y demanda bajo los mismos bloqueos/contratos de Spec 020 al procesar cada unidad; no ofrecer a dos cajas una misma cantidad demandada. Mantener la separación entre confirmación física y contabilización de unidades pendientes.
- No exigir que finalicen todos los Encargos asociados para cerrar la caja. Registrar de forma auditable resultados y documento(s) generados por línea, con recuperación segura ante interrupciones.

### 23.5 Fuera de alcance y migración

- La anulacion **posterior al cierre** no se convierte en acción cotidiana del receptor; queda bajo regularización excepcional supervisada con reversión estándar si aplica. **No implementar el mecanismo de reversión completo propuesto anteriormente para el error de escaneo inmediato.**
- No obligar al Shopper a registrar caja, envío ni contenido físico. Su compra, precio, barcode y fotos permanecen como evidencia comercial.
- No cambiar ni recontabilizar automáticamente `Recepcion Unidad` históricas creadas antes de esta mejora: pueden quedar con caja no informada / referencia LEGACY y continúan consultables. Nunca inventar una caja histórica.
- La asociación futura con envío internacional, documentación y costos aduaneros tendrá su propio diseño cuando se implemente Aduana. No asignar esos datos a Item maestro.

### 23.6 Pruebas obligatorias de aceptación

1. Abrir BOX sin etiqueta externa y registrar 3 lecturas del mismo barcode con scan_event_id diferentes; no crea Stock Entry ni altera Encargo antes de finalizar.
2. Quitar solo la lectura duplicada elegida: quedan 2 unidades y 1 descarte auditado; no se requiere reversa contable.
3. Cerrar navegador y reabrir BOX DRAFT: permanecen líneas y descartes.
4. Enviar dos veces el mismo scan_event_id y luego repetir cierre: no aparecen nuevas líneas ni dobles Stock Entries.
5. Finalizar con 2 unidades válidas: se generan solo 2 recepciones y sus efectos estándar; ambas conservan BOX y línea de origen.
6. Una unidad requiere clasificación/costo/aprobación: las demás procesan, la pendiente queda identificada dentro de BOX en FINALIZED_WITH_EXCEPTIONS y se resuelve sin reescanear.
7. Dos receptores/cajas compiten por el último ENC compatible: solo uno consume la demanda; otro se procesa según política de demanda residual/stock vigente.
8. Intentar quitar una línea tras cierre: backend rechaza; no exponer edición de caja cerrada.
9. Usuarios sin permiso no pueden editar cajas ajenas ni crear Stock Entry manual.
10. Desde Item, Recepcion Unidad y ENC puede reconstruirse la caja de recepción (si el evento no es LEGACY); búsqueda por BOX/barcode/ENC funciona.
11. Corte de conexión durante cierre y reintento: no hay movimientos huérfanos, dobles reservas ni doble incremento de received_qty.
12. La ausencia de etiqueta de origen no impide operar; el Shopper continúa sin tareas de cajas.

### 23.7 Criterio de cierre

No dar por implementada esta ampliación hasta probar en celular recepción DRAFT por caja, eliminación de errores sin impacto contable, cierre idempotente, procesamiento parcial con excepciones y trazabilidad BOX -> unidad -> Item / ENC / Stock Entry. La ejecución corresponde al programador: el presente documento define contrato funcional, no afirma implementación.

### 23.8 Decisiones aprobadas del Arquitecto (2026-10-13)

Estas decisiones prevalecen sobre reglas incompatibles de §23.2-23.4:

1. **Borradores:** sin vencimiento automático. Acción "Anular caja borrador" disponible incluso con cero lecturas; confirmación explícita, estado CANCELLED, usuario/fecha de anulación, sin efectos sobre stock o Encargos. No se borra físicamente ni se reabre.
2. **Reintentos:** job automático ante fallos técnicos recuperables; ComercialFRA y System Manager pueden ejecutar "Reintentar procesamiento" solo sobre líneas no consumadas desde Recepción > Cajas con incidencias y desde el detalle BOX. ReceptorFRA solo visualiza. Las excepciones de negocio se resuelven por las colas vigentes, no mediante reintento indiscriminado.
3. **Volumen:** sin límite arbitrario de unidades por caja. Finalizar en job en cola con avance persistente y commit por línea; cada línea conserva idempotencia scan_event_id. Un mecanismo recupera jobs interrumpidos, evitando FINALIZING perpetuo, y retoma solo líneas no procesadas. No bloquear el HTTP ni depender del celular conectado.
4. **Cambio de turno:** otro usuario FRAreceptor autorizado puede continuar una caja DRAFT y finalizarla. Registrar creador, autor de cada lectura/descarte y usuario que finaliza. Validar permisos y concurrencia en backend; nadie modifica contenido FINALIZED.
5. **Numeración:** BOX-YYYY-NNNNN, secuencia que reinicia cada año bajo la convención central FRA, sin renombrar cajas anteriores.
6. **receive_scan:** retirar acceso público directo de FRAreceptor; autorizar solo llamadas internas protegidas para el cierre y regularizaciones vigentes, sin perder integraciones permitidas ni dejar un bypass.
7. **DocTypes:** aprobar Recepcion Caja (cabecera) y Recepcion Caja Linea (registro independiente, no tabla hija), con scan_event_id único, vínculo BOX y descarte en la misma línea (DISCARDED, usuario y fecha). No crear un tercer maestro Caja.
8. **Previsualización:** servicio separado exclusivamente de solo lectura. No invocar _resolve_item, ni crear barcode, Item, excepción, reserva o evento antes del cierre.
9. **Spec 021 Shopper:** escaneo en DRAFT no bloquea edición de compra. Al pulsar "Finalizar", iniciar FINALIZING bajo protección de concurrencia. Durante FINALIZING, `update_purchase` rechaza una edición si **barcode actual o barcode nuevo** de esa compra coincide con una línea ACTIVA todavía no procesada de cualquier caja FINALIZING. Mensaje: "No se puede modificar esta compra mientras se procesa una recepción en Chile que contiene el mismo código de producto. Inténtelo cuando finalice el procesamiento." La coincidencia temporal por barcode no prueba que la unidad pertenezca a esa compra: al terminar el procesamiento, liberar el bloqueo preventivo y aplicar únicamente las restricciones definitivas de Spec 021 por vínculos reales de recepción, incluyendo unidades pendientes asociadas; jamás mantener bloqueo global por barcode después de terminar FINALIZING. La verificación del cierre y la edición deben serializarse respecto de los Encargos afectados, releyendo compra/barcode/costo bajo bloqueo para evitar una carrera entre FINALIZING y `update_purchase`. No cambiar moneda, propiedad ni reglas restantes de 021.
10. **Legado:** mostrar "Sin caja (LEGACY)" cuando Recepcion Unidad histórica carece de BOX, sin reconstrucción inventada ni migración destructiva.

**Agregar pruebas:** anular caja vacía y con lecturas; cambio de receptor/turno; reanudar job interrumpido; carrera con edición de compra Shopper; autorización backend del endpoint anterior; historial por autor de lectura. En §23.6 caso 9 "caja ajena" significa fuera del rol autorizado, no caja creada por un compañero del mismo rol.
