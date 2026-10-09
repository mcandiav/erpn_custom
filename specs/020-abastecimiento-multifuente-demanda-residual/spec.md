# Spec 020 - Abastecimiento multifuente y demanda residual

Estado: CERRADA (2026-10-09, aceptación documental del Arquitecto; implementación 16.0.109)
Evidencia de cierre: `tasks.md` y `checklists/acceptance.md` (30 criterios §23), piloto E4 OV-2026-00330 / ENC-2026-00405, reconciliación E5 y Nota de Entrega NE-2026-00003.
Alcance: la edición de compras Shopper es una mejora independiente posterior (ver `ERPnext-custom/shopper-edicion-compras.md`), no parte de los criterios de cierre originales de 020.
Fecha: 2026-10-07
Rol solicitante: Arquitecto
Proyecto: ERPNext Custom / FRAgallardo
Prioridad: CORRECCION ARQUITECTONICA INMEDIATA
Dependencias: Specs 013, 015, 017, 018, 019

## 1. Incidente que origina esta Spec

La prueba operativa con:

- Item `191267529486`;
- OV `OV-2026-00328`;
- Encargo `ENC-2026-00403`;
- cantidad OV = 5;
- cobertura inicial = 1 stock + 4 demanda;
- cuatro unidades escaneadas posteriormente por `FRAreceptor` sin compra Shopper previa;

demostró una desalineación estructural:

1. las cuatro unidades ingresaron físicamente al inventario;
2. el Encargo siguió con `purchase_status = PENDING`;
3. la cola Shopper siguió mostrando necesidad por 4;
4. la OV siguió mostrando `1 cubierto por stock / 4 demanda pendiente`;
5. no apareció el warning `APARTAR - ENC-2026-00403`;
6. la recepción no vinculó las unidades al Encargo porque el código vigente exige `purchase_status = PURCHASED` para considerar un Encargo recepcionable.

La causa no es visual. El modelo vigente confunde:

- necesidad de abastecimiento;
- compra Shopper;
- recepción física;
- cobertura/reserva de la OV.

Esta Spec corrige esa premisa.

## 2. Tesis

Un `Encargo` representa una **demanda pendiente de satisfacer**, no una compra Shopper.

Shopper es una fuente posible de abastecimiento, pero no la única.

Una misma demanda puede satisfacerse de forma parcial y concurrente mediante:

- múltiples Shoppers;
- distintas tiendas/proveedores;
- stock libre que aparece posteriormente;
- recepción física desde otra procedencia;
- otras fuentes futuras explícitamente soportadas.

El sistema debe conservar una única verdad cuantitativa de demanda residual y, a la vez, mantener separadas:

1. cantidad original solicitada;
2. cantidad cuya fuente de abastecimiento ya está comprometida;
3. cantidad todavía pendiente de conseguir;
4. cantidad físicamente recibida;
5. cantidad efectivamente reservada/cubierta en la OV.

## 3. Principio cuantitativo

Agregar al Encargo los conceptos:

- `requested_qty`: cantidad original de la demanda;
- `sourced_qty`: cantidad para la cual ya existe una fuente válida comprometida;
- `pending_supply_qty = max(requested_qty - sourced_qty, 0)`;
- `received_qty`: cantidad físicamente recibida en Chile para esa demanda;
- `covered_qty`: cantidad actualmente cubierta para la OV, calculada sin doble conteo entre SRE y unidades físicamente apartadas;
- `pending_receive_qty`: cantidad abastecida pero todavía no recibida cuando aplique.

### 3.1 Fuente de verdad para Shopper

La cola Shopper usa:

`pending_supply_qty`

NO usa `purchase_status = PENDING` como criterio suficiente.

Cuando `pending_supply_qty = 0`, el Encargo desaparece de la cola Shopper aunque nunca haya existido una compra Shopper.

### 3.2 Fuente de verdad para recepción

Recepción busca demanda compatible con:

- Encargo `Open`;
- Item/barcode compatible;
- cantidad de demanda todavía no cubierta físicamente;
- sin exigir que la fuente previa sea una compra Shopper.

`purchase_status` NO es prerequisito para vincular una unidad física a una demanda.

### 3.3 Fuente de verdad para OV

La OV muestra estados derivados de eventos reales:

- stock/reserva válida;
- compra comprometida en tránsito;
- recepción pendiente;
- recibido/apartado;
- excepción;
- demanda todavía sin fuente.

`covered_qty` debe derivarse de cobertura física única. Si una unidad apartada ya posee una SRE válida para la misma OV/línea, cuenta una sola vez. No sumar ciegamente `reservado + apartado`; reconciliar por unidad/vínculo para evitar doble cobertura.

No debe depender de valores históricos congelados al submit.

## 4. Modelo de eventos de abastecimiento

Los campos singulares actuales del Encargo no son suficientes para múltiples Shoppers.

Crear un registro hijo o DocType transaccional:

`Encargo Supply Event`

Nombre funcional en UI: `Abastecimientos`.

Cada evento representa una cantidad abastecida por una fuente concreta.

Campos mínimos:

- `encargo`;
- `source_type`;
- `qty`;
- `status`;
- `shopper_user` cuando corresponda;
- `supplier`;
- `proposed_supplier_name`;
- `purchase_barcode`;
- `purchase_price`;
- `purchase_currency`;
- `purchased_on`;
- fotos/evidencias de compra;
- `reception_unit` cuando exista;
- `item`;
- `sales_order`;
- `sales_order_item`;
- fecha/hora;
- usuario/servicio originador;
- comentario/motivo;
- campos de excepción barcode cuando sean específicos de esa compra.

### 4.1 source_type del evento

Valores mínimos:

- `SHOPPER_PURCHASE`;
- `RECEPTION_DIRECT`;
- `STOCK_REALLOCATION`;
- `MIGRATION`.

No confundir con `Encargo.source_type = KNOWN_ITEM | UNKNOWN_ITEM`.

### 4.2 status del evento

Valores mínimos:

- `COMMITTED`: ya consume demanda residual;
- `RECEIVED`: físicamente recibido;
- `REJECTED`: no satisface la demanda;
- `CANCELLED`: dejó de consumir demanda;
- `RESOLVED_TO_STOCK`: compra/recepción histórica que ya no está comprometida con esa demanda.

La implementación puede agregar estados técnicos si son necesarios, pero no debe volver a mezclar todos los eventos en un único `purchase_status`.

## 5. Múltiples Shoppers y compras parciales

No existe apropiación exclusiva del Encargo completo por un Shopper.

Ejemplo:

Demanda original = 4.

- Shopper A compra 1 en tienda A -> `pending_supply_qty = 3`.
- Shopper B compra 1 en tienda B -> `pending_supply_qty = 2`.
- Shopper C compra 1 -> `pending_supply_qty = 1`.
- Shopper D compra 1 -> `pending_supply_qty = 0`.

Cada compra debe crear su propio `Encargo Supply Event`.

No sobrescribir:

- Shopper;
- tienda;
- barcode;
- precio;
- fotografías;
- fecha;
- evidencia de otra compra parcial.

### 5.1 Compra de más de una unidad

Un Shopper puede confirmar `qty > 1` si realmente compró varias unidades.

El backend debe:

1. bloquear el Encargo;
2. recalcular `pending_supply_qty`;
3. impedir comprar más que lo pendiente;
4. crear el evento por la cantidad confirmada;
5. reducir la cola inmediatamente.

### 5.2 Concurrencia

Si dos Shoppers confirman al mismo tiempo la última unidad:

- solo una transacción puede consumirla;
- la otra debe recibir mensaje de que la demanda ya fue satisfecha o que la cantidad pendiente cambió;
- nunca puede quedar `sourced_qty > requested_qty`.

## 6. Recepción directa sin compra Shopper previa

Para `KNOWN_ITEM`, si el receptor escanea un Item que coincide con una demanda abierta:

1. buscar el Encargo compatible más antiguo que todavía tenga una unidad de demanda físicamente no cubierta;
2. NO exigir `purchase_status = PURCHASED`;
3. distinguir si esa unidad corresponde a una fuente ya comprometida o a demanda todavía sin fuente;
4. si corresponde a un `SHOPPER_PURCHASE` ya comprometido y compatible, completar/recibir ese Supply Event en vez de crear otro evento que vuelva a consumir demanda;
5. si corresponde a demanda todavía sin fuente, vincular la `Recepcion Unidad` al Encargo y crear `RECEPTION_DIRECT`, consumiendo una unidad de `pending_supply_qty`;
6. mostrar `APARTAR - ENC-2026-XXXXX`;
7. ingresar la unidad al flujo de inventario de Spec 018;
8. aumentar la cobertura física de esa demanda;
9. reconciliar Shopper, Encargo y OV.

Una recepción nunca puede crear un segundo consumo de demanda sobre una cantidad que ya estaba comprometida por un Supply Event activo.

Si la recepción directa satisface la última unidad:

- `pending_supply_qty = 0`;
- el Encargo deja de aparecer en Shopper;
- la OV deja de mostrar esa cantidad como demanda pendiente.

## 7. Diferencia KNOWN_ITEM vs UNKNOWN_ITEM

### 7.1 KNOWN_ITEM

El Item real ya existe en la línea de OV.

Cuando llega una unidad compatible:

- se aparta para el Encargo;
- se reserva/cubre la línea real;
- NO se sustituye ninguna línea de la OV;
- se actualizan cantidades de abastecimiento y cobertura.

### 7.2 UNKNOWN_ITEM / ENCARGO-PENDIENTE

La misma regla de demanda residual aplica.

Cuando llega una unidad:

- se identifica/crea Item por Spec 018;
- se aparta para el Encargo;
- se reduce demanda residual;
- Spec 019 materializa progresivamente `ENCARGO-PENDIENTE` hacia el Item real.

La diferencia entre KNOWN y UNKNOWN es la materialización de la línea, no la apropiación de la demanda.

## 8. Prioridad de asignación en recepción

Al escanear una unidad conocida:

1. identificar Item/barcode;
2. buscar Encargos abiertos compatibles con necesidad todavía no cubierta;
3. asignar FIFO al Encargo compatible más antiguo;
4. solo cuando no exista demanda compatible, tratar la unidad como `STOCK NORMAL`.

La fecha FIFO de demanda es la **`creation` del Encargo**. Esa fecha representa cuándo nació la necesidad en el ERP y funciona tanto si hubo compra Shopper como si no. `purchased_on` no debe usarse como clave FIFO general porque puede estar vacío o ser posterior al nacimiento de la demanda.

Si dos Encargos tienen la misma `creation`, desempatar por `name` ascendente para obtener un orden determinístico.

Una unidad comprometible con demanda NO debe entrar silenciosamente como stock libre.

## 9. Warning del Receptor

La decisión del warning depende de si la unidad quedó comprometida con una demanda, no de si el Item era conocido ni de si Shopper compró antes.

### Unidad comprometida

`APARTAR - ENC-2026-XXXXX`

### Unidad comprometida con clasificación pendiente

`APARTAR - REQUIERE CLASIFICACION - ENC-2026-XXXXX`

### Excepción comercial barcode

`APARTAR - REQUIERE COMERCIAL - ENC-2026-XXXXX`

### Sin demanda compatible

`STOCK NORMAL`

o:

`STOCK NORMAL - REQUIERE CLASIFICACION`

según Spec 018.

## 10. Reconciliación automática de OV

Después de cada evento que cambie abastecimiento o cobertura ejecutar una rutina única, conceptualmente:

`reconcile_encargo_supply(encargo)`

y, cuando corresponda:

`reconcile_sales_order_item_supply(sales_order_item)`.

Debe recalcular desde datos reales y no incrementar/decrementar campos a ciegas.

Eventos disparadores mínimos:

- compra parcial Shopper;
- cancelación/rechazo de compra;
- recepción física;
- resolución de clasificación;
- aprobación/rechazo barcode;
- asignación de stock libre;
- devolución a stock;
- materialización Spec 019;
- ajuste de cantidad de OV de Spec 017.

### 10.1 OV-2026-00328 como caso de aceptación

Estado inicial:

- Item `191267529486` x5;
- 1 cubierto;
- ENC-403 x4 pendiente.

Después de cuatro recepciones directas compatibles:

- 5 cubierto;
- 0 demanda pendiente;
- ENC-403 ya no visible en cola Shopper;
- las cuatro `Recepcion Unidad` vinculadas a ENC-403;
- cada escaneo mostró `APARTAR - ENC-2026-00403`.

## 11. Cola Shopper

La consulta de pendientes debe ser conceptualmente:

- Encargo `Open`;
- `pending_supply_qty > 0`;
- sin bloqueo comercial que impida nueva compra.

No utilizar únicamente:

`status = Open AND purchase_status = PENDING`.

La tarjeta muestra:

- cantidad original;
- cantidad ya abastecida;
- **cantidad pendiente de comprar** destacada;
- historial de intentos no encontrados pertinente;
- datos de producto permitidos.

No muestra Cliente, OV, precio de venta ni vendedor.

## 12. Estado de compra histórico

`purchase_status` deja de ser la máquina de estados de toda la demanda.

Puede mantenerse temporalmente por compatibilidad, pero debe derivarse o reinterpretarse:

- no debe decidir si el Encargo aparece al Shopper;
- no debe decidir por sí solo si recepción puede asignar una unidad;
- no debe representar múltiples compras como un único registro mutable.

La verdad de compras vive en `Encargo Supply Event`.

## 13. Barcode y Spec 017

La excepción de barcode se evalúa por **evento de compra/unidad**, no necesariamente por todo el Encargo.

Ejemplo:

Demanda 4:

- Shopper A compra 1 barcode correcto;
- Shopper B compra 1 barcode distinto y queda `PENDING_APPROVAL`;
- todavía faltan 2 sin fuente.

Resultado:

- 1 unidad abastecida válida;
- 1 unidad en excepción **sí ocupa temporalmente un cupo de la demanda** mientras espera resolución;
- `sourced_qty = 2` y `pending_supply_qty = 2`;
- las otras 2 siguen visibles al Shopper;
- ningún otro Shopper puede comprar ese cupo mientras el evento esté `PENDING_APPROVAL`.

Si ComercialFRA aprueba, el evento conserva el cupo y continúa como fuente válida. Si rechaza, ese evento deja de consumir demanda, `sourced_qty` disminuye y el cupo vuelve inmediatamente a `pending_supply_qty` y a la cola Shopper.

Una excepción de una unidad no debe congelar automáticamente las demás unidades de la demanda.

Spec 017 conserva la decisión comercial sobre equivalencias, pero consume este modelo unitario/parcial.

## 14. Stock libre que aparece después

Para `KNOWN_ITEM`, el stock libre elegible puede satisfacer **solo demanda todavía sin fuente**.

En este corte la asignación de stock libre posterior es **manual y controlada**, no automática.

Acción disponible para `ComercialFRA` y `System Manager`:

`Asignar stock a demanda`

Comportamiento:

1. seleccionar Item/stock libre elegible;
2. el backend propone la demanda abierta compatible más antigua usando FIFO por `Encargo.creation`;
3. el usuario confirma la asignación;
4. crear evento `STOCK_REALLOCATION`;
5. reducir `pending_supply_qty`;
6. crear/ajustar únicamente la reserva SRE necesaria;
7. actualizar OV y cola Shopper;
8. NO generar Material Receipt ni segundo ingreso de inventario.

La UI no debe permitir elegir arbitrariamente una demanda más nueva mientras exista una compatible más antigua, salvo override de `System Manager` con motivo.

Si una compra Shopper ya estaba comprometida para esa misma cantidad, no reasignar automáticamente ese cupo a stock: aplicar §15 y requerir liberación explícita del evento Shopper.

La reconciliación debe distinguir cantidades ya sourced de las todavía sin fuente.

## 15. Compra en tránsito después de que la demanda fue satisfecha por otra vía

Si una compra Shopper ya ocurrió y posteriormente la demanda se satisface legítimamente por otra unidad antes de que esa compra llegue:

- no borrar ni cancelar la compra histórica;
- **no desplazar automáticamente** una compra Shopper ya comprometida solo porque apareció otra unidad física o stock libre;
- mientras `pending_supply_qty = 0`, una unidad adicional no asociada a una fuente comprometida entra como `STOCK NORMAL`;
- sacar una compra ya comprometida de la OV requiere decisión explícita de `ComercialFRA`;
- esa decisión se ejecuta desde el propio `Encargo Supply Event` mediante acción `Liberar compromiso` (nombre UI permitido: `Resolver a stock` si el Programador mantiene nomenclatura existente);
- la acción exige motivo, deja auditoría y cambia el evento a `RESOLVED_TO_STOCK` o equivalente no comprometido;
- al liberarse, la demanda se reconcilia: si no existe otra cobertura válida, el cupo vuelve a `pending_supply_qty`;
- cuando esa compra llegue físicamente después de haber sido liberada, se trata como stock normal;
- conservar Shopper, precio, tienda, barcode, fotos y costo.

Recepción y stock NO disparan por sí solos esta liberación de una compra Shopper ya comprometida.

No contar la misma obligación dos veces.

## 16. UI ComercialFRA

### 16.1 Encargo

Agregar sección:

`Abastecimiento`

Mostrar:

- Solicitado;
- Abastecido/comprometido;
- Pendiente de abastecer;
- Recibido;
- Cubierto/reservado;
- lista cronológica de eventos de abastecimiento.

Cada evento muestra fuente:

- Shopper;
- Recepción directa;
- Stock;
- Migración.

### 16.2 Sales Order

El resumen por línea debe recalcularse con la nueva verdad cuantitativa.

Ejemplos:

`1 stock / 3 pendiente / 1 comprado`

`3 cubierto / 2 pendiente`

`5 cubierto`

No dejar la línea roja por un Encargo cuya demanda ya quedó satisfecha.

### 16.3 Shopper

La tarjeta muestra la cantidad residual actual.

La actualización después de una compra debe ser inmediata.

## 17. No encontrado

Los intentos `No encontrado` siguen siendo eventos de búsqueda, no satisfacción.

Con múltiples Shoppers:

- distintos Shoppers pueden registrar intentos en distintas tiendas;
- no disminuyen `pending_supply_qty`;
- el conteo de tres intentos sigue generando revisión comercial según regla vigente;
- el historial debe identificar Shopper, tienda y fecha.

## 18. Ajustes de cantidad de OV

Spec 017 mantiene el gate y la acción segura.

Spec 020 agrega:

- el aumento incrementa `requested_qty` o crea demanda delta según modelo 017;
- la disminución solo puede consumir primero cantidad no abastecida;
- no puede borrar eventos Shopper/recepción históricos;
- cualquier reducción debe reconciliar `pending_supply_qty`, sourced y covered sin destruir SRE ajenas.

## 19. Migración

Crear patch explícito después de implementar el modelo.

No inferir información que no exista.

### 19.1 Encargos actuales PENDING sin compra

Inicializar:

- `sourced_qty` desde cobertura verificable;
- `pending_supply_qty` por diferencia;
- no crear compra ficticia.

### 19.2 Encargos PURCHASED actuales

Crear uno o más eventos `SHOPPER_PURCHASE` desde los campos históricos existentes.

Si el registro histórico solo permite saber una compra agregada:

- migrar como un único evento por la cantidad históricamente comprada;
- marcar `MIGRATED_FROM_LEGACY`;
- no inventar división por unidad/Shopper.

### 19.3 Recepciones existentes

Vincular eventos desde `Recepcion Unidad` cuando la relación sea determinística.

### 19.4 Caso OV-2026-00328 / ENC-2026-00403

Las cuatro recepciones ya realizadas quedaron como stock normal y no vinculadas por el defecto descubierto.

NO corregirlas por heurística global en el patch.

Incluir una regularización controlada y auditable para este caso piloto:

- localizar las cuatro `Recepcion Unidad` correspondientes;
- validar Item, fechas, disponibilidad y ausencia de otro compromiso;
- vincularlas a ENC-403;
- crear eventos `RECEPTION_DIRECT`;
- reconciliar reserva/cobertura;
- dejar ENC-403 con pendiente 0;
- actualizar resumen OV;
- registrar auditoría de regularización.

Debe requerir acción System Manager y mostrar preview antes de aplicar.

## 20. Idempotencia y concurrencia

Obligatorio:

- cada Supply Event tiene identificador único;
- compra parcial no puede consumir más que cantidad residual;
- recepción no puede satisfacer dos Encargos con la misma unidad;
- una Recepcion Unidad solo puede originar un evento de satisfacción activo;
- reconciliación repetida produce el mismo resultado;
- ninguna carrera puede dejar cantidades negativas o superiores a requested_qty.

## 21. Contabilidad e inventario

Esta Spec no redefine la contabilidad de Spec 018.

El evento de abastecimiento comercial y el movimiento de inventario son conceptos separados.

- compra Shopper puede existir sin Stock Entry todavía;
- recepción genera inventario según Spec 018;
- stock reallocation no debe duplicar ingreso de inventario;
- reconciliación de demanda nunca crea stock ficticio.

## 22. Roles

- `Shopper`: registra compras parciales e intentos; ve solo cantidad residual.
- `FRAreceptor`: escanea; no decide a qué cliente asignar manualmente.
- `ComercialFRA`: consulta trazabilidad, resuelve excepciones y acciones comerciales permitidas.
- `System Manager`: regularización/migración excepcional.
- backend: asignación FIFO, transacciones, reconciliación y reservas.

## 23. Pruebas mínimas

1. Encargo x4 aparece Shopper como 4.
2. Shopper A compra 1 -> cola muestra 3.
3. Shopper B compra 1 desde otra tienda -> cola muestra 2.
4. Shopper C compra 1 -> cola muestra 1.
5. Shopper D compra 1 -> desaparece de pendientes.
6. Cada compra conserva Shopper, tienda, barcode, precio, fotos y fecha independientes.
7. Dos Shoppers concurrentes no pueden sobrecomprar última unidad.
8. Compra parcial qty=2 consume solo 2.
9. Receptor recibe KNOWN_ITEM con Encargo PENDING y sin compra -> asigna Encargo.
10. Caso anterior muestra `APARTAR - ENC-...`.
11. Recepción directa reduce cantidad residual Shopper.
12. Cuatro recepciones directas de ENC-403 eliminan la necesidad Shopper.
13. OV-328 pasa de 1/4 a 5 cubierto.
14. Recepción directa KNOWN_ITEM no sustituye línea OV.
15. UNKNOWN_ITEM sigue materialización Spec 019.
16. Sin demanda compatible -> STOCK NORMAL.
17. FIFO elige Encargo compatible más antiguo.
18. Una unidad no satisface dos Encargos.
19. Stock libre asignado reduce demanda residual.
20. Compra ya en tránsito desplazada por otra cobertura conserva historia y entra luego como stock normal.
21. Barcode exception de una compra parcial no bloquea las otras cantidades.
22. No encontrado de un Shopper no reduce demanda.
23. Tres intentos siguen disparando revisión.
24. Reconciliación repetida es idempotente.
25. Migración legacy PURCHASED crea Supply Event sin inventar detalle.
26. Regularización OV-328/ENC-403 exige preview System Manager.
27. Shopper nunca ve Cliente/OV/precio venta/vendedor.
28. Inventario no se duplica durante reconciliación.
29. SRE no se recrean globalmente.
30. Totales sourced/pending/received/covered nunca exceden requested_qty salvo estados históricos explícitos de excedente que deben resolverse.

## 24. Orden de implementación

Esta Spec corrige la base común y debe implementarse antes de continuar cerrando la lógica pendiente de 017.

Orden:

1. modelo Supply Event + cantidades derivadas;
2. migración compatible de datos actuales;
3. compra parcial multi-Shopper;
4. recepción contra demanda aunque no exista compra;
5. reconciliación OV/Encargo/Shopper;
6. stock reallocation;
7. regularización controlada OV-328/ENC-403;
8. revalidar integración 017 barcode;
9. revalidar 018 recepción;
10. revalidar 019 materialización.

## 25. Criterio de cierre

La Spec 020 queda cumplida cuando la misma demanda puede ser satisfecha parcialmente por varias fuentes sin contradicciones entre Shopper, Encargo, recepción, inventario y OV.

La prueba principal es:

- una demanda de 4 puede ser comprada 1+1+1+1 por cuatro Shoppers distintos, reduciendo la cola 4->3->2->1->0;
- o puede ser satisfecha por cuatro recepciones directas sin compra Shopper previa, también reduciendo 4->3->2->1->0;
- en ambos casos la OV y el Encargo reflejan inmediatamente la misma realidad y el receptor recibe el warning correcto de apartado.
