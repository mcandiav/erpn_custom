# Spec 017 - Excepciones de abastecimiento y trazabilidad desde OV

Estado: DEFINITIVA PARA IMPLEMENTACION
Fecha: 2026-10-06
Rol solicitante: Arquitecto
Proyecto: ERPNext Custom / FRAgallardo
Orden: implementar después de Specs 018, 019 y 020. La Spec 020 es prerequisito para toda lógica cuantitativa/multi-Shopper.

## 1. Tesis

La Spec 013, complementada por la 015, ya implementa la generación de Encargos desde Orden de Venta, el split entre stock disponible y faltante, los tipos `KNOWN_ITEM` / `UNKNOWN_ITEM`, la idempotencia, la cancelación y la cola operativa del Shopper.

Esta Spec NO vuelve a implementar esa lógica.

La Spec 017 completa únicamente:

1. comparación entre barcode esperado y barcode realmente comprado para `KNOWN_ITEM`;
2. resolución comercial de diferencias;
3. estado de abastecimiento visible por línea de OV;
4. confirmación previa a validar cuando se generará demanda Shopper;
5. ajuste seguro de cantidades sin destruir reservas;
6. coordinación con recepción de Spec 018 y materialización de Spec 019.

## 2. Fuera de alcance

- Recrear la lógica base de Encargo de 013/015.
- Crear un DocType alternativo de demanda.
- Reemplazar los estados actuales de Encargo por una única máquina de estados.
- Recepción física en Chile.
- Movimiento de inventario.
- Materialización de `ENCARGO-PENDIENTE` en Item real: corresponde a Spec 019.
- Costos, landed cost, courier, aduana o contabilidad.

## 3. Modelo vigente y dependencia de Spec 020

El DocType `Encargo` continúa siendo la cola de demanda.

Se mantienen:

- `source_type = KNOWN_ITEM | UNKNOWN_ITEM`;
- `status = Draft | Open | Cancelled`;
- `purchase_status` solo como compatibilidad/histórico de compra;
- `reception_status`;
- relación con Sales Order y línea origen;
- historial de `No encontrado`;
- bloqueo de cancelación cuando existe compra.

La definición cuantitativa de demanda residual, compras parciales, múltiples Shoppers y fuentes alternativas pertenece a **Spec 020**.

Esta Spec 017 NO debe volver a definir `fulfilled_qty` ni usar un único `purchase_status` como fuente de verdad. Consume los valores y eventos definidos por Spec 020 (`requested_qty`, `sourced_qty`, `pending_supply_qty`, recepción/cobertura y Supply Events).

No crear `demand_type`.

## 4. No se crea estado TAKEN

No se implementará `TAKEN`.

La compra parcial multi-Shopper, la concurrencia y la reducción 4->3->2->1->0 se rigen por Spec 020.

Spec 017 solo agrega las reglas de excepción barcode y resolución comercial sobre cada evento de compra correspondiente.

## 5. No encontrado

`No encontrado` NO es estado.

El Encargo permanece `purchase_status = PENDING` y cada intento registra:

- fecha/hora;
- Shopper;
- supplier / proposed_supplier_name;
- comentario opcional.

Al tercer intento se genera el aviso comercial vigente, sin sacar el Encargo de la cola.

## 6. Estado específico de excepción de barcode

Agregar campo:

`barcode_exception_status`

Valores:

- vacío / `NOT_APPLICABLE`;
- `MATCH`;
- `PENDING_APPROVAL`;
- `APPROVED`;
- `REJECTED`.

Campos auxiliares:

- `expected_barcode`;
- `purchase_barcode`;
- fecha/usuario de resolución;
- comentario de resolución.

Este estado NO sustituye `status`, `purchase_status` ni `reception_status`.

## 7. Reglas de comparación

### 7.1 UNKNOWN_ITEM

No tiene barcode esperado.

El barcode comprado identifica físicamente el producto y no genera mismatch. El Item real se resuelve por Spec 018 y la transformación de la OV por Spec 019.

### 7.2 KNOWN_ITEM con barcode esperado

Si `purchase_barcode == expected_barcode`:

- `purchase_status = PURCHASED`;
- `barcode_exception_status = MATCH`.

Si difiere:

- el Shopper puede completar la compra;
- `purchase_status = PURCHASED`;
- `barcode_exception_status = PENDING_APPROVAL`;
- se conserva toda la evidencia;
- la cantidad afectada NO satisface todavía la demanda;
- no puede ser recibida/apartada como unidad comprometida hasta resolución comercial.

Comprar físicamente y satisfacer la demanda son decisiones distintas.

## 8. Resolución comercial

### 8.1 Quién resuelve

Aprobar, rechazar y solicitar nueva compra corresponden al **vendedor responsable de la OV** con rol `ComercialFRA`.

Criterio:

- el vendedor responsable se determina por la Sales Team / Sales Person de la OV;
- otros usuarios `ComercialFRA` pueden consultar la excepción, pero no resolverla;
- `System Manager` puede resolver excepcionalmente como override, exigiendo motivo y dejando auditoría.

Si técnicamente existe más de un Sales Person responsable de la misma OV, cualquiera de los vinculados a esa OV y con rol `ComercialFRA` puede resolver.

### 8.1.1 Fallback cuando Sales Person no tiene usuario

La ausencia de Employee/User asociado NO debe dejar la excepción sin responsable operativo.

Orden de fallback:

1. usuario vinculado al Sales Person responsable, si existe y tiene `ComercialFRA`;
2. propietario de la OV (`owner`), únicamente si ese usuario tiene `ComercialFRA`;
3. `System Manager` como responsable de excepción.

El ToDo debe asignarse al primer usuario válido de ese orden.

Si cae en `System Manager`, la UI debe indicar `Sin vendedor resoluble - escalado a System Manager`.

No crear excepciones sin asignatario.

### 8.2 Aprobar equivalencia

Al aprobar:

- `barcode_exception_status = APPROVED`;
- la compra queda habilitada para satisfacer la demanda;
- el barcode se agrega a `Item Barcode` del Item esperado si no pertenece a otro Item;
- se registra usuario, fecha/hora y comentario.

Si la unidad ya está esperando en recepción como `PENDING_BARCODE_APPROVAL`, la aprobación debe disparar automáticamente el reintento del flujo de Spec 018. Si todas las demás condiciones están satisfechas, la unidad se ingresa y aparta sin requerir un nuevo escaneo físico.

### 8.3 Barcode perteneciente a otro Item

No se permite asociar silenciosamente el mismo barcode a dos Items.

Mientras exista conflicto, el Encargo queda en `PENDING_APPROVAL`.

Resoluciones permitidas:

1. **Rechazar equivalencia**, porque efectivamente corresponde a otro producto.
2. **Corregir maestro de Item**, solo si la asociación del barcode al otro Item era errónea. Esa corrección corresponde a `System Manager` / Configurador o a quien tenga permisos explícitos de maestro de Item. Una vez eliminado/corregido el conflicto, el vendedor responsable puede aprobar.

ComercialFRA no debe reasignar barcodes entre Items desde la pantalla de excepción.

### 8.4 Rechazar equivalencia

Al rechazar:

- `purchase_status` permanece `PURCHASED`;
- `barcode_exception_status = REJECTED`;
- la compra rechazada NO satisface la demanda;
- NO se borra ni altera la evidencia de compra;
- el Encargo queda detenido en estado visual:
  `Compra rechazada - decide el vendedor`.

El rechazo NO devuelve automáticamente el Encargo a PENDING.

El vendedor decide entre:

#### A. Cancelar/modificar la venta

Aplicar el flujo estándar permitido para la OV, sujeto a las protecciones de esta Spec y de 019.

#### B. Solicitar nueva compra

Acción explícita:

`Solicitar nueva compra`

Debe:

1. copiar/preservar barcode, precio, fotos, supplier, Shopper, fecha y resolución rechazada en historial inmutable;
2. limpiar únicamente los campos activos de compra requeridos para una nueva ejecución;
3. dejar `purchase_status = PENDING`;
4. dejar `barcode_exception_status = NOT_APPLICABLE` o vacío;
5. devolver el Encargo a la cola Shopper;
6. mantener la trazabilidad de la compra anterior como intento rechazado.

### 8.5 Sin decisión del vendedor

Si el vendedor no hace nada:

- el Encargo permanece detenido;
- no existe vencimiento automático ni SLA que cambie el estado;
- queda visible en la misma vista de excepciones, filtro `Rechazada - decide el vendedor`;
- se crea un ToDo/notificación persistente al responsable resuelto por §8.1.

No generar recordatorios repetitivos automáticos en esta fase.

### 8.6 Unidad física de compra rechazada

Una compra rechazada deja de estar comprometida con la demanda original.

Cuando la unidad llegue a Chile:

- si el barcode identifica un Item real, entra como `STOCK NORMAL` a `Matriz - FRAG`;
- si el barcode no identifica ningún Item, queda `STOCK NORMAL - REQUIERE CLASIFICACION` según Spec 018;
- no espera la decisión del vendedor para ingresar físicamente a inventario;
- no se aparta para el Encargo rechazado.

La decisión del vendedor afecta la demanda comercial, no la existencia física del producto rechazado.

## 9. KNOWN_ITEM sin barcode registrado

### 9.1 Flujo nuevo posterior a Spec 017

Cuando el Item esperado no tenga barcode:

- el primer barcode comprado se adopta durante la compra;
- si es único, se agrega a `Item Barcode`;
- `barcode_exception_status = MATCH`;
- si pertenece a otro Item, pasa a `PENDING_APPROVAL`.

### 9.2 Compatibilidad con compras anteriores a Spec 017

Para Encargos ya comprados antes del despliegue de esta Spec:

- Spec 018 mantiene como fallback la adopción del primer barcode en recepción cuando el Item esperado aún no tiene barcode y no existe una excepción pendiente;
- este fallback es de compatibilidad histórica, no el flujo primario nuevo.

## 10. Migración de datos existentes

Al desplegar:

- Encargos comprados anteriores a 017 quedan con `barcode_exception_status = NOT_APPLICABLE`/vacío, sin inferir retroactivamente una decisión;
- registros/unidades actualmente en `PENDING_BARCODE_APPROVAL` deben mapearse a Encargo `barcode_exception_status = PENDING_APPROVAL`;
- cada excepción migrada a `PENDING_APPROVAL` debe crear su ToDo idempotente usando la misma regla de responsable de §8.1;
- no reescribir evidencia histórica ni marcar automáticamente MATCH salvo que una migración futura se defina de forma separada.

## 11. UI - Shopper

La cola, compra parcial y múltiples Shoppers se implementan según Spec 020.

Spec 017 agrega únicamente la experiencia de excepción barcode sobre el evento de compra afectado.

El Shopper NO ve:

- Cliente;
- OV;
- precio de venta;
- vendedor.

Cuando una compra parcial tenga barcode distinto, mostrar:

`Compra registrada. El código difiere del esperado y quedó pendiente de aprobación comercial.`

La excepción de una unidad no debe ocultar ni bloquear las demás unidades residuales que otro Shopper todavía pueda abastecer, salvo que exista una regla comercial explícita de bloqueo.

No revelar información comercial adicional.

## 12. UI - Sales Order / ComercialFRA

### 12.1 Estado por línea

La UI debe mostrar cantidades y estados, no reducir una línea mixta a una sola etiqueta.

Estados visuales posibles:

- `Cubierto por stock`;
- `Demanda pendiente`: Encargo aún no comprado;
- `Comprado`: compra confirmada por Shopper y todavía en tránsito, sin escaneo en Chile;
- `Excepción barcode`;
- `Compra rechazada - decide el vendedor`;
- `Recepción pendiente`: la unidad ya fue escaneada en Chile pero aún no puede completar ingreso/apartado por clasificación, valorización u otra resolución de recepción;
- `Recibido / apartado`;
- `Cancelado`.

Para línea mixta, usar resumen cuantitativo.

Ejemplo:

`1 cubierto por stock / 2 comprado`

o:

`1 cubierto por stock / 1 aprobado / 1 pendiente aprobación`.

La suma visible debe reconciliar siempre con la cantidad de la línea.

### 12.2 Confirmación antes de validar

Al presionar **Validar**, si existen faltantes que generarán Encargo, mostrar modal:

`Esta Orden de Venta enviará X unidad(es) al Shopper por falta de stock.`

Cuando corresponda, mostrar desglose por línea.

Botones obligatorios:

- `Continuar`
- `Cancelar`

`Continuar` confirma expresamente la cifra mostrada y solicita el submit.

Antes de crear reservas/Encargos, el servidor debe recalcular nuevamente stock y faltante.

Si el faltante recalculado difiere del valor confirmado en el modal:

- bloquear el submit;
- no crear reservas ni Encargos;
- informar `El stock cambió. Revise nuevamente la cantidad que irá al Shopper.`;
- obligar al usuario a presionar Validar otra vez y confirmar la cifra actualizada.

`Cancelar` vuelve a la OV sin validarla.

Este modal SÍ constituye una segunda confirmación explícita.

### 12.3 Vista Excepciones barcode

MCV Chile / ComercialFRA debe tener una única vista `Excepciones barcode` basada en **Encargos**, porque la excepción nace al comprar y puede existir antes de la recepción física.

La vista debe ofrecer al menos dos filtros/tabs:

- `Pendiente aprobación` -> `PENDING_APPROVAL`;
- `Rechazada - decide el vendedor` -> `REJECTED`.

Debe mostrar:

- Encargo;
- Item esperado;
- expected barcode;
- purchase barcode;
- evidencia;
- estado;
- vendedor/responsable resuelto;
- acciones permitidas según rol.

### 12.4 Aviso al vendedor

Cuando se genera `PENDING_APPROVAL`:

- aparece en `Excepciones barcode`;
- además se crea un ToDo/notificación para el responsable calculado por §8.1;
- un único aviso por excepción; no duplicarlo en cada refresh.

Las excepciones migradas desde `PENDING_BARCODE_APPROVAL` también generan el ToDo si no existe ya uno equivalente.

Al resolver la excepción, cerrar/completar el ToDo asociado.

## 13. Cambios de cantidad en OV validada

### 13.1 Regla general

ERPNext `Actualizar artículos` anula y recrea TODAS las reservas de la OV aunque se modifique una línea sin Encargo. Eso puede destruir reservas por unidad creadas por Specs 018/019.

Por tanto:

**si una OV tiene al menos un Encargo vinculado, bloquear completamente el flujo estándar `Actualizar artículos` para toda la OV.**

Implementar una acción propia controlada:

`Ajustar cantidad de Encargo`

Esta acción cubre únicamente ajustes de cantidad de líneas existentes y debe preservar las SRE ajenas.

En una OV submitted con Encargos:

- agregar nuevas líneas queda fuera de alcance de esta Spec y no se permite mediante `Actualizar artículos`;
- cambiar precio/rate/descuento de líneas existentes queda fuera de alcance de esta Spec y no se permite mediante `Actualizar artículos`;
- si se requiere vender unidades o productos adicionales que no corresponden a un ajuste de cantidad de una línea ya existente, crear una nueva OV;
- si se requiere una renegociación de precio posterior al submit, debe resolverse mediante el flujo documental/comercial estándar que corresponda, no alterando esta OV con Encargos.

Las OV sin Encargos mantienen el flujo estándar de ERPNext.

### 13.2 Aumento antes de compra

Todo aumento de cantidad vuelve a pasar por el gate comercial/pago de Spec 015.

Antes de confirmar el ajuste:

1. validar que el pago/saldo aplicado sea suficiente para la nueva obligación según Spec 015;
2. recalcular disponibilidad real para el delta;
3. reservar mediante SRE la parte del delta que pueda cubrirse con stock disponible;
4. crear/ajustar Encargo solo por el faltante restante;
5. mantener idempotencia.

El delta NO va completo a Encargo si existe stock disponible y reservable.

### 13.3 Aumento después de compra

Una compra existente es histórica y no debe ampliarse artificialmente.

Todo aumento vuelve a pasar por el gate de pago de Spec 015.

Para el delta:

1. recalcular stock disponible;
2. reservar por SRE la parte cubierta por stock;
3. crear **un nuevo Encargo solo por el faltante del delta**;
4. vincularlo a la misma línea comercial de OV;
5. preservar intacto el Encargo ya comprado.

La relación lógica Sales Order Item -> Encargo pasa a ser **1:N**.

No asumir desde 017 que una línea puede tener un solo Encargo.

### 13.4 Disminución antes de compra

En una línea mixta KNOWN_ITEM, reducir en este orden:

1. primero cantidad de Encargo todavía `PENDING` y no comprada;
2. después cantidad cubierta por stock reservado, liberando las SRE correspondientes;
3. nunca tocar automáticamente cantidades ya compradas, recibidas, apartadas, materializadas, entregadas o facturadas.

No dejar Encargos huérfanos ni reservas excedentes.

### 13.5 Disminución con compra/recepción/materialización

No reducir por debajo de cantidad:

- comprada;
- recibida;
- apartada;
- materializada;
- o ya entregada/facturada.

Debe bloquearse y requerir primero resolución/liberación correspondiente.

### 13.6 Aplicación a KNOWN_ITEM y UNKNOWN_ITEM

La regla de ajuste seguro aplica a ambos.

#### KNOWN_ITEM

La acción ajusta faltante y Encargos asociados sin destruir reservas existentes.

#### UNKNOWN_ITEM / ENCARGO-PENDIENTE

La acción solo puede modificar la porción todavía pendiente/no materializada.

Las cantidades ya materializadas en Items reales por Spec 019 no se reescriben mediante esta acción; para ellas se usa devolución/liberación/cancelación según estado documental.

Si se aumenta una línea UNKNOWN_ITEM cuyo Encargo original ya fue comprado, crear un nuevo Encargo por el delta.

## 14. Relación con Spec 018

### 14.1 Aprobar mientras la unidad espera recepción

Aprobación -> reintento automático de la misma `Recepción Unidad`.

No exigir nuevo escaneo.

### 14.2 Rechazar mientras la unidad espera recepción

La unidad deja de pertenecer a la demanda original.

- Item identificable -> stock normal / Matriz.
- Item desconocido -> PENDING_CLASSIFICATION sin Encargo.
- la demanda comercial queda en REJECTED hasta que el vendedor decida.

### 14.3 Fallback histórico de primer barcode

Se mantiene solo para compras realizadas antes de 017, según §9.2.

## 15. Entrega y cantidad entregable

### 15.1 Regla

La **unidad/compra específica** asociada a un Encargo con:

- `barcode_exception_status = PENDING_APPROVAL`, o
- `barcode_exception_status = REJECTED`

NO es entregable ni puede utilizarse para satisfacer la demanda.

Esto no impide que, en un `KNOWN_ITEM`, otra unidad libre y elegible del mismo Item satisfaga la línea según §15.2.

### 15.2 Línea mixta KNOWN_ITEM

No bloquear toda la línea si parte de la cantidad es válida.

Para KNOWN_ITEM, el Item es fungible: **stock libre del mismo Item puede satisfacer la obligación aunque el Encargo original siga pendiente de compra o la unidad comprada esté en tránsito**.

Por tanto, la cantidad máxima entregable se calcula con stock válido disponible/reservable del mismo Item, respetando lo ya entregado y cualquier cantidad bloqueada por otras reservas.

Si se usa stock libre para satisfacer una cantidad que estaba cubierta conceptualmente por un Encargo:

- esa cantidad del Encargo deja de estar comprometida al cliente;
- debe quedar marcada como resuelta por stock (`RESOLVED_BY_STOCK` o equivalente);
- si la compra Shopper todavía no ocurrió, cancelar/reducir la demanda correspondiente;
- si la compra ya ocurrió y está en tránsito, no se cancela la compra histórica; cuando llegue, esa unidad entra como stock normal y no se aparta para esa demanda ya satisfecha.

Ejemplo:

OV x3:
- 1 stock originalmente reservado;
- 2 Encargo pendientes;
- aparecen 2 unidades libres adicionales del mismo Item en Matriz.

Puede entregarse hasta 3 si esas unidades siguen libres/eligibles al crear el Delivery Note.

La validación de Delivery Note debe impedir superar la cantidad realmente disponible/elegible.

### 15.3 UNKNOWN_ITEM

Se mantiene la regla de Spec 019: `ENCARGO-PENDIENTE` nunca es entregable. Solo los Items reales materializados pueden pasar a Delivery Note.

## 16. Roles

- `ComercialFRA`: crea/gestiona OV y consulta excepciones.
- vendedor responsable `ComercialFRA`: aprueba, rechaza o solicita nueva compra.
- `Shopper`: compra y registra evidencia.
- `FRAreceptor`: recibe físicamente según Spec 018.
- `System Manager`: override excepcional y fallback cuando no existe vendedor resoluble.

### Comentario de resolución

- aprobación normal: comentario opcional;
- rechazo: comentario/motivo obligatorio;
- override de `System Manager`: comentario/motivo obligatorio, tanto para aprobar como rechazar;
- `Solicitar nueva compra`: motivo obligatorio si nace después de un rechazo.

## 17. Pruebas mínimas

1. KNOWN_ITEM + barcode coincidente -> MATCH.
2. KNOWN_ITEM + barcode diferente -> PURCHASED + PENDING_APPROVAL.
3. Shopper recibe mensaje de pendiente de aprobación sin datos comerciales.
4. PENDING_APPROVAL crea ToDo único al vendedor.
5. PENDING_APPROVAL no puede satisfacer recepción.
6. Vendedor responsable aprueba -> APPROVED.
7. Otro ComercialFRA no responsable no puede resolver.
8. System Manager puede override con motivo.
9. Aprobación agrega Item Barcode si es único.
10. Barcode perteneciente a otro Item bloquea aprobación.
11. Corrección de maestro por usuario autorizado permite luego aprobar.
12. Rechazo deja PURCHASED + REJECTED.
13. Rechazo muestra `Compra rechazada - decide el vendedor`.
14. Rechazo no vuelve automáticamente a PENDING.
15. `Solicitar nueva compra` preserva evidencia histórica y vuelve a PENDING.
16. Sin decisión, caso permanece detenido y ToDo abierto.
17. Unidad rechazada identificada entra a stock normal.
18. Unidad rechazada desconocida queda PENDING_CLASSIFICATION.
19. Aprobación de unidad ya esperando recepción reanuda Spec 018 sin nuevo scan.
20. Rechazo de unidad esperando recepción la deriva a stock normal/clasificación.
21. Migración deja históricos en NOT_APPLICABLE y pendientes de recepción en PENDING_APPROVAL.
22. Modal Validar muestra Continuar/Cancelar.
23. Cancelar modal no valida OV.
24. Continuar genera Encargos y valida.
25. Línea mixta muestra resumen cuantitativo correcto.
26. Estado incluye `Compra rechazada - decide el vendedor`.
27. OV con Encargo bloquea ajuste estándar peligroso.
28. Acción propia ajusta cantidad sin recrear reservas ajenas.
29. Aumento posterior a compra crea segundo Encargo para el delta.
30. Relación línea -> Encargo soporta 1:N.
31. Disminución no baja de cantidades compradas/recibidas/materializadas.
32. Regla de ajuste aplica a KNOWN_ITEM.
33. Regla de ajuste aplica a UNKNOWN_ITEM solo sobre pendiente.
34. Delivery Note de línea mixta permite solo cantidad elegible.
35. PENDING_APPROVAL no es entregable.
36. REJECTED no es entregable.
37. UNKNOWN_ITEM sigue reglas de entrega de Spec 019.
38. OV con cualquier Encargo bloquea completamente `Actualizar artículos`.
39. En OV con Encargos no se permite agregar línea nueva ni cambiar precio/rate mediante Update Items.
40. Aumento de cantidad vuelve a ejecutar gate de pago Spec 015.
41. Delta con stock disponible crea SRE por esa parte y Encargo solo por el faltante.
42. Disminución KNOWN_ITEM reduce primero Encargo PENDING y luego stock reservado.
43. Cambio de stock entre modal y submit bloquea y exige reconfirmación.
44. Sales Person sin usuario asigna excepción al owner ComercialFRA o, en último término, System Manager.
45. Vista Excepciones barcode muestra tabs Pendiente aprobación y Rechazada - decide el vendedor.
46. Migración de PENDING_BARCODE_APPROVAL crea ToDo idempotente.
47. Rechazo exige comentario.
48. Override System Manager exige comentario.
49. Aprobación normal permite comentario opcional.
50. Stock libre del mismo KNOWN_ITEM puede satisfacer la OV aun con Encargo pendiente/en tránsito y el Encargo queda resuelto por stock.

## 18. Dependencias

- Spec 013: Encargo y flujo Shopper.
- Spec 014: clasificación.
- Spec 015: split stock/faltante y reglas de OV.
- Spec 018: recepción física e inventario.
- Spec 019: materialización de UNKNOWN_ITEM en OV.

## 19. Criterio de cierre

La Spec 017 queda cumplida cuando:

- la diferencia de barcode tiene una resolución comercial determinística;
- el vendedor responsable controla rechazo/nueva compra;
- recepción reacciona correctamente a aprobar/rechazar;
- la OV informa cantidades por estado;
- la validación previa informa y exige Continuar/Cancelar;
- los cambios de cantidad no destruyen reservas;
- una línea puede manejar múltiples Encargos;
- Delivery Note solo permite cantidad realmente elegible.
