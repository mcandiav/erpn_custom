# Data Model: Chilexpress Shipment Integration

## 1. Principio

La fuente logística es `Shipment`. La configuración técnica se referencia, no se duplica.

```text
Shipment
   ├── Delivery Note(s)
   ├── Shipment Parcel(s)
   ├── Courier Configuration -> Chilexpress / Test
   ├── servicio seleccionado
   ├── costo
   ├── external id / OT / AWB
   ├── tracking
   └── File attachment etiqueta

Courier Configuration
   └── provider/environment/credentials/endpoints/account_reference

ChilexpressAdapter
   └── traduce entre ambos contratos
```

## 2. Shipment: campos estándar a reutilizar

Mapping definitivo (inspección ERPNext v16 + plan aprobado):

| Campo estándar | Uso Spec 009 |
|---|---|
| `carrier` | `Chilexpress` |
| `service_provider` | `erpn_custom` |
| `carrier_service` | nombre legible del servicio cotizado |
| `shipment_id` | OT Chilexpress (`transportOrderNumber`) |
| `awb_number` | `trackingNumber` (o OT si coincide) |
| `shipment_amount` | costo cotizado/contratado |
| `tracking_status` | `In Progress` / `Delivered` / `Returned` / `Lost` |
| `tracking_status_info` | último evento textual |
| `status` | `Booked` al crear OT |
| Shipment Parcel | `length/width/height/weight/count` |
| `value_of_goods` | valor declarado |
| `description_of_content` | contenido declarado |

## 3. Custom Field mínimo

### `custom_courier_configuration`

- DocType: Shipment
- Type: Link
- Options: Courier Configuration
- Required: no al crear borrador; sí antes de operaciones courier
- Filter UI: `enabled = 1`

Es el único campo custom asumido como necesario porque Shipment estándar no tiene vínculo hacia la configuración multi-courier propia de `erpn_custom`.

## 4. Custom Fields condicionales

Crear solo si la inspección estándar lo justifica.

### `custom_courier_service_code`

Código técnico Chilexpress elegido en cotización. Necesario si `carrier_service` debe conservar nombre legible y la API exige código separado.

### `custom_courier_creation_state`

Select conceptual:

```text
Not Requested
Creating
Created
Uncertain
Failed
```

Solo si no existe estado estándar adecuado para seguridad/idempotencia.

### `custom_courier_creation_key`

Data/UUID estable para el intento lógico, si la estrategia de idempotencia lo requiere.

### `custom_courier_created_at`

Datetime de creación externa.

### `custom_last_tracking_at`

Datetime de última consulta exitosa.

### `custom_last_tracking_event`

Small Text/Data para detalle que no quepa en `tracking_status`.

## 5. Courier Configuration existente

No modificar arquitectura de Spec 008.

Para Chilexpress/Test se espera:

```text
provider = chilexpress
environment = Test
enabled = 1
account_reference = <TCC cuando aplique>

credentials rows:
coverage_api_key + API Key + Endpoint URL
rating_api_key   + API Key + Endpoint URL
shipping_api_key + API Key + Endpoint URL
```

El Adapter no accede directamente al child table si ya existen helpers públicos para resolver endpoint/key.

## 6. Contrato de cotización normalizado

Objeto conceptual no necesariamente persistido como DocType:

```text
CourierQuote
- provider
- environment
- service_code
- service_name
- price
- currency
- estimated_delivery_days?
- estimated_delivery_date?
- provider_reference?
```

Spec 009 persiste solo la opción elegida en Shipment.

## 7. Contrato de creación normalizado

Objeto conceptual de retorno del Adapter:

```text
CourierCreateResult
- provider
- external_shipment_id
- transport_order_number (OT)
- tracking_number?
- awb_number?
- service_code
- service_name
- amount
- initial_status
- label_available
- provider_reference?
```

El servicio de Shipment traduce ese objeto a campos estándar/custom aprobados.

## 8. Etiqueta

Persistencia preferida:

```text
File
attached_to_doctype = Shipment
attached_to_name    = <Shipment name>
file_name           = <shipment>-<OT>-chilexpress-label.pdf
```

No persistir Base64 de etiqueta en campos del Shipment.

## 9. Idempotencia

Modelo conceptual mínimo:

```text
Shipment + Courier Configuration + logical creation key
    -> máximo una OT confirmada
```

Si el resultado HTTP es incierto:

```text
state = Uncertain
external id = desconocido o parcial
```

No volver a POSTear hasta reconciliar.

El plan técnico debe decidir si los campos en Shipment bastan o si un registro auxiliar de intento es imprescindible. Preferir campos en Shipment para el primer corte si permiten auditoría y seguridad suficientes.

## 10. Cobertura

Los códigos Chilexpress son datos derivados de la operación API y no deben contaminar el maestro `Address` en esta Spec salvo aprobación posterior.

Entrada:

```text
Shipment address -> comuna/ciudad/región
```

Salida runtime:

```text
origin_coverage_code
destination_coverage_code
```

## 11. Relaciones

```text
Sales Order(s)
     ↓ estándar
Delivery Note(s)
     ↓
Shipment
     ├── Parcel(s)
     ├── Courier Configuration
     └── Chilexpress external shipment
```

No existe relación directa API Courier -> Sales Order como fuente de verdad.
