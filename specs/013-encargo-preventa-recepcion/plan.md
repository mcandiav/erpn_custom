# Plan técnico — Spec 013 Fase D: Recepción Chile

## Objetivo

Implementar únicamente la Fase D de la Spec 013: recepción física, identificación por escaneo, recuperación del Encargo comprado, resolución del Item y clasificación final ENC o STOCK.

Caso piloto obligatorio:

- OV: `OV-2026-00326`
- Encargo: `ENC-2026-00401`
- purchase_barcode: `https://qrgo.page.link/JsDVr`
- estado actual: `PURCHASED / PENDING / resolved_item vacío`

## Invariantes

1. El valor del escáner es opaco: EAN, UPC, QR, URL, código interno u otro formato son válidos.
2. El primer lookup es `Encargo.purchase_barcode`, no Item.
3. Escanear una unidad que pertenece a un Encargo debe producir warning inmediato con el número ENC dominante.
4. El receptor debe poder apartar físicamente la unidad antes de resolver Item.
5. Resolver Item y clasificar ENC/STOCK son pasos posteriores y humanos.
6. No modificar Sales Order submitted.
7. No crear Warehouse virtual de Encargos.
8. No tocar Frappe/ERPNext core.
9. No usar System Manager como rol operacional de recepción.

## UI

Ruta operacional interna:

`Encargo -> Recepción Chile`

La Page debe iniciar con foco en escaneo.

### Estado inicial

```text
RECEPCIÓN CHILE

[ ESCANEAR PRODUCTO ]

Pendientes de recepción
ENC              Marca          Descripción
ENC-2026-00401   Michael Kors   Cinturon masculino mk
```

### Match único

Al encontrar un solo Encargo elegible:

```text
ENCARGO DETECTADO

ENC-2026-00401

APARTAR / CLASIFICAR ENCARGO

Cinturon masculino mk · Michael Kors
OV-2026-00326
```

El warning no desaparece por timeout.

Acciones:

- `APARTADO / CONTINUAR` — principal;
- `VER DETALLE` — secundaria;
- `NO CORRESPONDE` — secundaria.

### Múltiples Encargos con el mismo código

Mostrar todos los ENC candidatos y exigir selección humana. No asignar automáticamente.

### Sin Encargo

Mostrar:

```text
PRODUCTO SIN ENCARGO IDENTIFICADO
Código: <valor>

[ BUSCAR ITEM ]
[ INGRESAR A STOCK ]
[ BUSCAR ENCARGO MANUALMENTE ]
```

## Backend mínimo esperado

El Programador debe proponer nombres finales, pero conceptualmente se requieren métodos equivalentes a:

- `find_reception_candidate(scanned_code)`
- `mark_received(encargo)`
- `resolve_item(encargo, item_code, scanned_code)`
- `resolve_to_encargo(encargo, item_code)`
- `resolve_to_stock(encargo, item_code)`

Todo cambio de estado debe validar estado previo y ejecutarse server-side.

## Lookup de recepción

Buscar Encargo con:

- `status = Open`
- `purchase_status = PURCHASED`
- `purchase_barcode = scanned_code`
- `reception_status in (PENDING, RECEIVED)`

No normalizar ni transformar el código antes de comparar, salvo trim técnico de extremos si el escáner pudiera introducir espacios.

## Resolución de Item

Después de recuperar el Encargo:

1. buscar Item Barcode por valor exacto;
2. si existe uno, proponer Item;
3. si no existe, permitir búsqueda manual;
4. si no existe Item correcto, permitir creación controlada;
5. si FRA confirma que el código es identificador estable, asociarlo al Item validando unicidad.

## Estados

### APARTADO / CONTINUAR

- reception_status -> RECEIVED
- received_on -> now
- dejar resolved_item vacío si todavía no se resolvió Item

### SATISFACE ENCARGO

- resolved_item = Item
- resolved_by = usuario
- reception_status = RESOLVED_TO_ENC

### NO SATISFACE — STOCK

- no forzar Item como solución del ENC
- conservar historial de compra y recepción
- derivar la unidad al flujo normal de stock
- devolver/reabrir la obligación de compra del ENC mediante transición auditable

## Permisos

Crear o reutilizar un rol operacional semántico para Recepción Chile.

Debe poder:

- acceder a la Page;
- escanear;
- marcar recibido;
- buscar/proponer Item;
- iniciar creación controlada de Item;
- resolver a ENC o STOCK.

ShopperFRA: sin acceso.
VendedorFRA / ComercialFRA: consulta del resultado según permisos, sin facultad implícita de conciliación.

## Pruebas críticas

1. Código QR/URL del caso real localiza ENC-2026-00401.
2. Warning muestra el ENC completo en primer plano.
3. Confirmar apartado cambia a RECEIVED.
4. Reload conserva estado/fecha.
5. Código compartido por varios ENC exige selección.
6. Código sin ENC no genera asignación.
7. Item existente por barcode se propone.
8. Código nuevo puede asociarse a Item controladamente.
9. Un código maestro no puede quedar en dos Items.
10. SATISFACE ENCARGO exige Item válido.
11. Doble click/reintento no duplica ni resuelve dos veces.
12. ShopperFRA no accede.
13. OV submitted queda intacta.
14. Caso piloto termina en RESOLVED_TO_ENC si el producto es correcto.

## Fuera de alcance

- documento definitivo de Stock Ledger;
- WMS;
- recepción de cajas completa;
- facturación/contabilidad de compra;
- automatizar asignación de varios Encargos por similitud;
- modificar Fase C Shopper salvo regresión demostrada.
