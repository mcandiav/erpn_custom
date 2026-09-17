# Implementation Plan: Chilexpress vinculado a Shipment

**Branch**: `version-16` | **Date**: 2026-09-17 | **Spec**: [`spec.md`](./spec.md)

**Estado**: plan técnico contrastado con Shipment ERPNext v16 + Chilexpress; **implementado en código** `16.0.11` (pendiente migrate + OT Test real).

## Summary

Implementar el primer Adapter real de courier sobre el `Shipment` estándar de ERPNext, usando la configuración multi-courier ya cerrada en Spec 008.

Flujo:

```text
Shipment
  -> Courier Configuration
  -> preflight
  -> ChilexpressAdapter
  -> cotización
  -> servicio seleccionado
  -> creación OT Test
  -> etiqueta
  -> tracking
  -> Shipment actualizado
```

## Technical Context

**Stack**: Python 3 / Frappe 16 / ERPNext 16 / app `erpn_custom`

**Configuración existente**:

- `Courier Provider`
- `Courier Configuration`
- `Courier Credential`
- keys estándar: `coverage_api_key`, `rating_api_key`, `shipping_api_key`
- endpoint por servicio en configuración
- helpers vigentes para resolver API key/endpoint

**Target inicial**: `derp.at-once.cl`, Chilexpress `Test` exclusivamente.

## Architecture gates

| Gate | Resultado esperado |
|---|---|
| Shipment estándar como fuente logística | PASS |
| Delivery Note conserva verdad de inventario | PASS |
| No core modifications | PASS |
| Configuración tomada de Spec 008 | PASS |
| Sin secrets duplicados en Shipment | PASS |
| Adapter específico por provider | PASS |
| Cotizar separado de Crear OT | PASS |
| Idempotencia antes de creación externa | PASS |
| Production fuera de alcance | PASS |

## Evidence gate obligatorio

Antes de código, el Programador debe documentar:

1. metadata/código estándar real de `Shipment` v16;
2. campos estándar reutilizables para carrier, servicio, importe, external id/AWB y tracking;
3. tablas estándar de paquetes y Delivery Notes;
4. comportamiento de docstatus/save/submit del Shipment;
5. creación estándar de Shipment desde Delivery Note si existe;
6. forma estándar de adjuntar `File`;
7. documentación oficial vigente Chilexpress de Coberturas, Cotizador, Envíos, etiqueta y tracking;
8. requerimiento exacto de TCC/account reference en Test;
9. si Chilexpress acepta referencia de cliente/idempotencia/reconsulta;
10. semántica exacta de OT vs tracking/AWB.

Si la evidencia contradice un campo propuesto, usar el estándar real y actualizar plan antes de código.

## Componentes previstos

### 1. Adapter registry / factory

Un punto central resuelve:

```text
provider_code -> Adapter class
```

Inicialmente:

```text
chilexpress -> ChilexpressAdapter
```

No implementar otros providers.

### 2. Base contract

Módulo conceptual esperado:

```text
erpn_custom/chile/couriers/base.py
```

con contrato estable para validar/cotizar/crear/etiqueta/tracking.

### 3. ChilexpressAdapter

Módulo conceptual esperado:

```text
erpn_custom/chile/couriers/chilexpress.py
```

Responsable de payloads y respuestas específicas Chilexpress.

### 4. Shipment service/controller

La lógica de orquestación del Shipment no debe vivir dentro del Client Script.

Debe existir una capa Python server-side para:

- obtener Shipment;
- obtener Courier Configuration;
- ejecutar preflight;
- invocar Adapter;
- persistir resultados;
- controlar estado/idempotencia.

### 5. UI Shipment

Client Script / JS de app solo para:

- campos/botones;
- dialogs de selección de cotización;
- mensajes de validación;
- llamadas whitelisted al servicio server-side.

No construir payloads Chilexpress en JavaScript.

## Modelo mínimo previsto

### Custom Field obligatorio candidato

```text
Shipment.custom_courier_configuration
  Link -> Courier Configuration
```

### Campos técnicos potenciales

Solo crear tras comprobar brecha estándar:

```text
custom_courier_service_code
custom_courier_creation_state
custom_courier_creation_key
custom_courier_created_at
custom_last_tracking_at
custom_last_tracking_event
```

El plan final debe justificar cada uno.

## Preflight design

Validación server-side reutilizable.

Salida normalizada:

```text
{
  ok: bool,
  errors: [
    {section, field, message, parcel_index?}
  ]
}
```

Debe permitir mostrar todos los problemas relevantes de una vez, no obligar al usuario a corregir uno por llamada.

Primera cobertura:

- courier config;
- credenciales/endpoints;
- TCC/account reference;
- origen;
- destino;
- paquetes;
- valor/descripcion;
- estado/idempotencia.

## Quote design

`ChilexpressAdapter.cotizar()` devuelve lista normalizada:

```text
[
  {
    provider,
    service_code,
    service_name,
    price,
    estimated_delivery_days,
    estimated_delivery_date?,
    provider_reference?
  }
]
```

Persistir solo la alternativa seleccionada en el Shipment para esta Spec. No crear aún histórico de múltiples cotizaciones salvo que la evidencia muestre que es necesario para crear la OT.

## Create shipment design

`crear_envio()` debe:

1. volver a ejecutar preflight relevante;
2. confirmar que existe servicio seleccionado;
3. adquirir/proteger estado de creación para evitar doble click concurrente;
4. construir request Chilexpress;
5. ejecutar request;
6. persistir external id/OT inmediatamente;
7. persistir costo/servicio/estado;
8. obtener o dejar preparada etiqueta;
9. manejar resultado incierto sin auto-reintento peligroso.

## Idempotency strategy requirement

El Programador debe proponer mecanismo concreto. Preferencia arquitectónica:

- identificador técnico estable en Shipment por intento lógico;
- bloqueo transaccional antes de request externo;
- estado `creating/created/uncertain/failed` o equivalente;
- si `created`, botón Crear queda bloqueado;
- si `uncertain`, no se vuelve a POSTear automáticamente;
- reconciliación mediante referencia externa si Chilexpress lo permite.

No confiar únicamente en deshabilitar un botón en navegador.

## Label design

Preferencia:

```text
Chilexpress response -> bytes/PDF -> Frappe File attachment -> Shipment
```

No Data URI/Base64 persistido en Custom Field.

## Tracking design

Consulta manual desde Shipment. Normalización inicial a `tracking_status` estándar cuando corresponda y campo técnico adicional solo si hace falta preservar detalle/evento.

Automatización periódica queda para otra Spec.

## Project structure prevista

```text
specs/009-chilexpress-shipment-integration/
├── spec.md
├── plan.md
├── data-model.md
└── tasks.md

erpn_custom/
├── chile/
│   ├── couriers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   └── chilexpress.py
│   ├── shipment_service.py
│   ├── doctype/...                 # solo si realmente necesario
│   └── test_chilexpress_*.py
├── public/js/
│   └── shipment.js                 # ubicación real a confirmar
├── hooks.py                        # solo si se necesita incluir JS/events
├── patches/
│   └── <patch para Custom Fields>  # naming según release, NO según número de Spec
└── patches.txt
```

No asumir nombres de patch basados en Spec 009: el repo ya tiene patches `v0_0_9`/`v0_0_10` de Spec 008. El Programador debe usar el siguiente nombre/version real disponible.

## Testing strategy

### Unitario

- registry/factory;
- preflight completo e incompleto;
- mapping de paquetes;
- mapping addresses/cobertura;
- normalización de quotes;
- normalización errores;
- mapping create response;
- tracking mapping;
- idempotencia local.

### Mock HTTP

- 200 quote;
- 0 servicios;
- 400 validación;
- 401/403 credencial;
- 500 courier;
- timeout;
- create success;
- create uncertain timeout;
- label success/failure;
- tracking success/sin eventos.

### Sandbox real Chilexpress Test

Prueba punta a punta con Shipment de prueba:

1. paquete con dimensiones reales;
2. dirección origen/destino resoluble;
3. cotizar;
4. seleccionar servicio;
5. crear OT Test;
6. verificar identificador persistido;
7. obtener etiqueta;
8. tracking manual;
9. repetir acción Crear y demostrar que no duplica.

## Deployment

1. evidence gate;
2. revisión plan final;
3. OK Miguel;
4. código/tests;
5. bump semver según regla real del repo;
6. commit/push;
7. deploy sandbox;
8. migrate;
9. prueba real Test;
10. aceptación Miguel;
11. cerrar Spec 009.

## Out of scope

- Production;
- Starken/FAZT;
- multi-courier comparison;
- quotation from Sales Order;
- Item master logistics dimensions;
- consolidation rules;
- cron tracking;
- auto-selection cheapest/fastest;
- custom Despacho DocType.
