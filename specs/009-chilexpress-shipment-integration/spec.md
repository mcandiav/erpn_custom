# Feature Specification: Chilexpress vinculado a Shipment

**Feature Branch**: `[009-chilexpress-shipment-integration]`

**Created**: 2026-09-17

**Status**: Implementada en código (`16.0.11`). Pendiente migrate sandbox + prueba OT Test + aceptación operativa.

**Parent context**: `008-courier-configuration`, `../despachos_transportistas.md`

## 0. Regla de trabajo

Esta Spec implementa el primer Adapter real de courier y lo vincula al `Shipment` estándar de ERPNext.

Flujo cumplido hasta código:

1. leer `README.md`, esta Spec, Spec 008 y el documento conceptual `despachos_transportistas.md`;
2. inspeccionar el DocType `Shipment` real de ERPNext v16;
3. contrastar documentación Chilexpress vigente;
4. presentar plan técnico a Miguel;
5. OK explícito de Miguel (`prosiga`);
6. implementar.

No se modifica Frappe/ERPNext core.

## 1. Objetivo

Permitir que un `Shipment` estándar de ERPNext pueda seleccionar una `Courier Configuration = Chilexpress / Test`, validar que contiene todos los datos logísticos requeridos, cotizar servicios Chilexpress, seleccionar uno, crear una Orden de Transporte (OT), obtener la etiqueta y persistir la trazabilidad resultante en el propio Shipment.

Flujo objetivo:

```text
Delivery Note(s)
      ↓
Shipment ERPNext
      ↓
Courier Configuration = Chilexpress / Test
      ↓
Preflight local
      ↓
ChilexpressAdapter
      ├── cobertura
      ├── cotizar
      ├── crear_envio
      ├── obtener_etiqueta
      └── consultar_tracking
      ↓
Shipment actualizado
```

## 2. Decisión arquitectónica congelada

### 2.1 Fuente de verdad

- `Sales Order`: compromiso comercial.
- `Delivery Note`: salida física del inventario.
- `Shipment`: fuente de verdad del despacho y courier.
- `Courier Configuration`: provider, ambiente, credenciales, endpoints y referencia de cuenta.
- `ChilexpressAdapter`: protocolo específico de Chilexpress.

No agregar campos Chilexpress a Sales Order ni Delivery Note salvo que una necesidad futura lo justifique mediante otra Spec.

### 2.2 Vinculación

`Shipment` tendrá un único vínculo explícito hacia la configuración utilizada:

```text
Courier Configuration -> Link a Courier Configuration
```

El Shipment no almacenará API keys ni endpoints.

Al seleccionar `Chilexpress / Test`, el sistema resolverá:

```text
provider_code = chilexpress
environment   = Test
account_reference = TCC/referencia comercial cuando aplique
coverage_api_key + endpoint
rating_api_key   + endpoint
shipping_api_key + endpoint
```

La implementación debe reutilizar el boundary ya existente de Spec 008 (`get_courier_api_key()` / `get_courier_endpoint()` o equivalente vigente), no duplicar resolución de secretos/endpoints dentro del Adapter.

## 3. Shipment estándar primero

Antes de crear Custom Fields, el Programador debe mapear y documentar los campos estándar existentes del `Shipment` real.

Campos observados en sandbox que deben evaluarse para reutilización:

- `carrier`
- `carrier_service`
- `service_provider`
- `shipment_id`
- `shipment_amount`
- `awb_number`
- `tracking_status`
- tabla de paquetes (`Shipment Parcel`): largo, ancho, alto, peso, cantidad
- tabla de Delivery Notes relacionadas
- origen/dirección/contacto
- destino/dirección/contacto
- valor de bienes
- descripción del contenido

Regla:

```text
Standard -> Custom Field -> código custom -> DocType auxiliar
```

No crear un DocType paralelo `Despacho`.

## 4. Preflight obligatorio

Seleccionar Chilexpress NO crea todavía una OT ni consume la API de Envíos.

Antes de cotizar o crear el envío debe ejecutarse una validación local clara y determinística.

### 4.1 Configuración courier

Debe existir una `Courier Configuration` habilitada con:

- provider Chilexpress;
- ambiente Test para esta Spec;
- servicio Cobertura configurado;
- servicio Cotización configurado;
- servicio Envío configurado;
- API keys recuperables;
- endpoint de cada servicio presente;
- `account_reference`/TCC cuando el contrato de Envíos lo requiera.

### 4.2 Origen

Según el contrato Chilexpress vigente, verificar como mínimo cuando aplique:

- compañía/remitente;
- dirección;
- comuna/ciudad/región;
- teléfono;
- contacto;
- RUT/documento requerido;
- código de cobertura Chilexpress resoluble.

### 4.3 Destino

Verificar como mínimo cuando aplique:

- Customer;
- destinatario;
- dirección;
- comuna/ciudad/región;
- teléfono;
- email cuando lo requiera Chilexpress;
- código de cobertura Chilexpress resoluble.

### 4.4 Paquetes

Para mercadería, cada bulto utilizado para Chilexpress debe tener:

- `weight > 0`;
- `length > 0`;
- `width > 0`;
- `height > 0`;
- `count > 0`.

Si falta cualquiera, bloquear cotización/creación y mostrar un mensaje accionable, por ejemplo:

```text
No se puede cotizar Chilexpress: el paquete #1 no tiene ancho y peso completos.
```

Las dimensiones reales del `Shipment Parcel` son la fuente para el envío físico. Las dimensiones de Item, si se agregan en una Spec futura, serán solo referencia/estimación comercial.

### 4.5 Datos del envío

Verificar:

- valor declarado / valor de bienes cuando corresponda;
- descripción del contenido;
- Delivery Note(s) relacionadas según flujo estándar elegido;
- Shipment no cancelado;
- no existir ya un envío externo creado para el mismo intento lógico.

## 5. Resolución de cobertura

Chilexpress requiere códigos propios para origen/destino.

El Adapter debe usar la API de Coberturas para traducir los datos del Shipment a códigos válidos Chilexpress antes de cotizar/crear OT.

Reglas:

- no hardcodear códigos de comunas;
- no asumir que el nombre textual de ERPNext coincide exactamente con el código Chilexpress;
- si no puede resolverse de forma inequívoca, detener la operación y mostrar el dato problemático;
- no persistir códigos Chilexpress en `Address` como requisito de esta Spec salvo que el plan técnico demuestre una ventaja clara y Miguel lo apruebe.

## 6. Contrato `CourierAdapter`

Crear un contrato interno común que permita adapters futuros sin acoplar Shipment a Chilexpress.

Interfaz mínima conceptual:

```text
validate_shipment(shipment)
cotizar(shipment)
crear_envio(shipment, selected_service)
obtener_etiqueta(shipment)
consultar_tracking(shipment)
```

Capacidades opcionales futuras:

```text
cancelar_envio()
solicitar_retiro()
```

La selección de Adapter debe resolverse de forma central por `provider_code`; no dispersar `if provider == ...` por distintos módulos.

## 7. `ChilexpressAdapter`

Primera implementación del contrato.

Responsabilidades:

- traducir Shipment -> payload Chilexpress;
- resolver cobertura origen/destino;
- utilizar la API key correcta según operación;
- usar endpoint configurado en Courier Configuration;
- interpretar errores Chilexpress;
- normalizar cotizaciones;
- crear OT;
- obtener etiqueta;
- consultar tracking;
- mapear respuestas a campos estándar/custom aprobados del Shipment;
- nunca exponer secrets en logs o excepciones.

## 8. Cotización dentro de Shipment

Una vez aprobado el preflight, el Shipment debe ofrecer una acción visible equivalente a:

```text
Cotizar envío
```

Para Spec 009 se consulta únicamente Chilexpress.

La respuesta debe normalizarse a una estructura interna con al menos:

```text
provider
service_code
service_name
price
estimated_delivery_days / plazo informado disponible
raw_reference opcional para auditoría técnica segura
```

La UI debe permitir seleccionar una alternativa.

Después de seleccionar:

- persistir el código técnico de servicio requerido para crear la OT;
- mostrar el nombre legible;
- persistir el valor cotizado seleccionado;
- NO crear todavía una OT automáticamente por el solo hecho de cotizar.

Si `carrier_service` estándar no permite conservar de forma segura código + nombre, crear el mínimo Custom Field técnico requerido después de documentar la brecha.

## 9. Crear envío / OT

La creación debe ser una acción explícita separada, por ejemplo:

```text
Crear envío en Chilexpress
```

Precondiciones:

- preflight OK;
- servicio cotizado/seleccionado;
- Shipment guardado con identificador estable;
- configuración Chilexpress Test habilitada;
- no existir ya OT válida asociada.

La llamada utilizará la API de Envíos y deberá persistir inmediatamente, cuando la respuesta lo entregue:

- provider/carrier = Chilexpress;
- servicio seleccionado;
- costo contratado;
- OT / identificador externo;
- AWB/tracking si es distinto y existe;
- estado inicial;
- referencia de etiqueta;
- timestamp de creación externa.

El plan técnico debe cerrar exactamente qué dato Chilexpress corresponde a `shipment_id`, `awb_number` y otros campos estándar antes de implementar.

## 10. Idempotencia y estado incierto

Reintentar no puede crear dos OTs para el mismo Shipment por accidente.

Requisitos mínimos:

1. generar una clave/referencia estable por intento lógico;
2. persistir estado de creación antes/durante/después de la llamada de forma segura;
3. si Chilexpress devuelve una OT, guardarla inmediatamente;
4. si hay timeout o corte de red después de enviar el request y el resultado es incierto, NO crear automáticamente otra OT;
5. dejar el Shipment en estado técnico `resultado incierto` o equivalente y exigir reconciliación;
6. investigar si la API Chilexpress soporta una referencia del cliente que permita consultar/reconciliar el intento sin duplicarlo.

El Programador debe presentar la estrategia concreta de idempotencia antes del OK de implementación.

## 11. Etiqueta

Cuando Chilexpress entregue/genera una etiqueta:

- obtenerla usando la API oficial;
- asociarla al Shipment mediante `File`/Attachment estándar cuando sea viable;
- no guardar binarios/base64 largos en campos Data/Small Text;
- permitir reimpresión/recuperación sin crear una nueva OT;
- nombre de archivo debe permitir identificar Shipment + OT sin exponer secretos.

## 12. Tracking

El Shipment debe ofrecer una acción equivalente a:

```text
Actualizar tracking
```

El Adapter consulta Chilexpress y actualiza:

- `tracking_status` estándar cuando exista equivalencia;
- último estado/evento relevante;
- fecha/hora de actualización;
- otros campos mínimos solo si el estándar no alcanza.

No se implementa todavía polling automático/cron en esta Spec. Solo consulta manual y contrato preparado para automatización futura.

## 13. UI esperada

Sobre el `Shipment` estándar, con impacto mínimo:

```text
Courier
├── Courier Configuration  [Chilexpress / Test]
├── ambiente visible       [TEST]
├── servicio seleccionado
├── costo cotizado
└── estado integración

Acciones según estado:
[Validar / Preflight]
[Cotizar envío]
[Crear envío en Chilexpress]
[Obtener/Reimprimir etiqueta]
[Actualizar tracking]
```

No mostrar botones que no correspondan al estado actual.

Ejemplos:

- sin paquetes completos -> no permitir Cotizar;
- sin cotización seleccionada -> no permitir Crear envío;
- con OT creada -> no permitir crear otra OT normal;
- con OT creada -> permitir etiqueta/tracking.

El ambiente `Test` debe ser visualmente evidente para evitar confusión operacional.

## 14. Datos estándar/custom candidatos

El plan debe inspeccionar el estándar y decidir el mapping final.

Único Custom Field conceptualmente obligatorio salvo evidencia de alternativa estándar:

```text
custom_courier_configuration: Link -> Courier Configuration
```

Candidatos adicionales SOLO si el estándar no alcanza:

```text
custom_courier_service_code
custom_courier_creation_state
custom_courier_creation_key
custom_courier_created_at
custom_last_tracking_at
custom_last_tracking_event
```

No crear todos por defecto. Cada uno debe justificarse contra Shipment estándar.

## 15. Seguridad

- API keys solo mediante Password/Frappe de Courier Configuration;
- endpoints solo mediante configuración vigente de Spec 008;
- no secretos en Git;
- no secretos en logs;
- no payloads completos si contienen información sensible innecesaria;
- errores de usuario deben ser legibles y no mostrar headers de autenticación;
- Test y Producción deben permanecer separados;
- Spec 009 acepta operaciones externas únicamente contra ambiente Chilexpress Test.

## 16. User Stories & Acceptance

### US1 - Vincular courier al Shipment

Como operador quiero seleccionar `Chilexpress / Test` en un Shipment para que el despacho use una configuración concreta y auditable.

**Acceptance**:

1. Shipment tiene Link a Courier Configuration.
2. Solo configuraciones habilitadas son seleccionables.
3. El provider/ambiente se derivan del Link y no se duplican manualmente.

### US2 - Detectar Shipment incompleto

Como operador quiero saber antes de llamar a Chilexpress qué datos faltan.

**Acceptance**:

1. paquete sin peso/dimensiones bloquea cotización;
2. origen/destino incompletos bloquean según requisitos API;
3. mensaje indica exactamente qué falta;
4. no se consume API Envíos si el preflight local falla.

### US3 - Cotizar Chilexpress

Como operador quiero obtener servicios/precios Chilexpress desde el Shipment.

**Acceptance**:

1. usa Cobertura + Cotizador según contrato vigente;
2. presenta alternativas normalizadas;
3. permite elegir servicio;
4. guarda servicio/costo seleccionados;
5. cotizar no crea OT.

### US4 - Crear OT

Como operador quiero crear el envío Chilexpress únicamente después de validar y elegir servicio.

**Acceptance**:

1. usa shipping_api_key/endpoint configurados;
2. crea OT Test;
3. persiste inmediatamente identificador externo;
4. reintento normal no duplica una OT ya creada;
5. timeout incierto no dispara segundo envío automático.

### US5 - Etiqueta

Como operador quiero obtener la etiqueta del envío y encontrarla desde Shipment.

**Acceptance**:

1. etiqueta vinculada/adjunta al Shipment;
2. recuperarla nuevamente no crea otra OT;
3. no se guardan secretos ni blobs impropios en campos de texto.

### US6 - Tracking

Como operador quiero consultar el estado Chilexpress desde Shipment.

**Acceptance**:

1. acción manual consulta tracking;
2. actualiza estado normalizado y timestamp;
3. no altera Sales Order, Delivery Note, pagos ni contabilidad.

## 17. Functional Requirements

- **FR-001**: Shipment MUST vincularse a una `Courier Configuration` habilitada.
- **FR-002**: la integración MUST resolver adapter por `provider_code`.
- **FR-003**: Spec 009 MUST implementar `ChilexpressAdapter`.
- **FR-004**: MUST existir preflight antes de cotización/creación.
- **FR-005**: para mercadería, cada paquete MUST validar peso, largo, ancho, alto y count > 0.
- **FR-006**: MUST resolver cobertura Chilexpress sin códigos hardcodeados.
- **FR-007**: MUST permitir cotizar y seleccionar servicio sin crear OT.
- **FR-008**: MUST crear OT solo mediante acción explícita.
- **FR-009**: MUST persistir OT/identificador externo inmediatamente al recibirlo.
- **FR-010**: MUST implementar estrategia de idempotencia/reconciliación de resultado incierto.
- **FR-011**: MUST obtener/asociar etiqueta al Shipment.
- **FR-012**: MUST permitir tracking manual.
- **FR-013**: MUST reutilizar campos estándar de Shipment antes de Custom Fields.
- **FR-014**: MUST NOT modificar Frappe/ERPNext core.
- **FR-015**: MUST NOT guardar API keys/endpoints duplicados en Shipment.
- **FR-016**: MUST usar Courier Configuration de Spec 008 como única fuente de configuración técnica.
- **FR-017**: MUST operar solo contra Chilexpress Test durante aceptación de esta Spec.
- **FR-018**: errores Chilexpress MUST normalizarse sin exponer secretos.
- **FR-019**: una falla del courier MUST NOT modificar stock, pagos, Customer ni facturación.
- **FR-020**: la implementación MUST quedar preparada para Starken/Fazt mediante el contrato común, sin implementarlos.

## 18. Fuera de alcance

- StarkenAdapter;
- FaztAdapter;
- comparación multi-courier para vendedor;
- cotización automática desde Sales Order/Quotation;
- dimensiones/peso maestros de Item para estimación comercial;
- consolidación automática de múltiples Sales Orders;
- reglas automáticas de elección de courier;
- cron/polling automático de tracking;
- Production Chilexpress;
- solicitud automática de retiro si la API/contrato no la soporta;
- rediseñar Courier Configuration de Spec 008.

## 19. Edge Cases obligatorios

- Courier Configuration deshabilitada después de ser seleccionada;
- falta API key de una operación;
- falta endpoint;
- falta TCC/account_reference cuando es requerido;
- comuna no resoluble en Coberturas;
- paquete con peso 0;
- paquete con una dimensión vacía;
- múltiples paquetes;
- Shipment sin Delivery Note según flujo aprobado;
- cotización devuelve cero servicios;
- servicio cotizado deja de estar disponible al crear OT;
- Chilexpress devuelve error de validación;
- timeout antes de respuesta;
- timeout después de que Chilexpress pudo crear la OT;
- botón Crear presionado dos veces;
- OT ya existente;
- etiqueta temporalmente no disponible;
- tracking sin eventos;
- Shipment cancelado.

## 20. Success Criteria

- **SC-001**: un Shipment Test válido puede seleccionar Chilexpress.
- **SC-002**: Shipment incompleto falla antes de enviar operación externa incompatible.
- **SC-003**: se obtiene y selecciona una cotización Chilexpress real Test.
- **SC-004**: se crea una OT real en Chilexpress Test sin duplicación por doble acción normal.
- **SC-005**: OT/costo/servicio quedan trazables desde Shipment.
- **SC-006**: etiqueta queda accesible desde Shipment.
- **SC-007**: tracking manual funciona y actualiza el Shipment.
- **SC-008**: ningún secreto aparece en UI/logs/tests/repositorio.
- **SC-009**: no se altera la semántica de Sales Order, Delivery Note, pagos ni inventario fuera del comportamiento estándar del Shipment/Delivery Note.
- **SC-010**: el siguiente courier puede implementar el mismo contrato sin reescribir el flujo central de Shipment.

## 21. Decisiones NO abiertas

1. `Shipment` estándar será la fuente de verdad logística.
2. No se creará DocType paralelo `Despacho`.
3. Chilexpress será el primer Adapter real.
4. Courier Configuration será la fuente de provider/ambiente/credenciales/endpoints.
5. Dimensiones reales se toman de Shipment Parcel.
6. Cotizar y Crear envío son acciones separadas.
7. No se crea OT al seleccionar courier.
8. No se crea OT si el preflight falla.
9. Test únicamente para aceptación inicial.
10. Starken/FAZT quedan fuera.

## 22. Decisiones que el Plan debe cerrar antes de implementar

- mapping exacto de campos estándar `Shipment` ↔ respuesta Chilexpress;
- nombres definitivos de Custom Fields estrictamente necesarios;
- ubicación UI de Courier Configuration y botones;
- contrato Python exacto de adapters;
- payloads/paths oficiales vigentes de Cobertura, Cotizador, creación OT, etiqueta y tracking;
- formato/campo de TCC y demás datos de cuenta;
- algoritmo de resolución de cobertura;
- estrategia concreta de idempotencia y reconciliación de timeout incierto;
- cómo persiste código + nombre del servicio seleccionado;
- formato de File/Attachment para etiqueta;
- normalización de estados de tracking;
- comportamiento respecto a docstatus de Shipment y Delivery Note;
- pruebas unitarias vs pruebas reales Test;
- tratamiento de múltiples paquetes en el payload Chilexpress.

## 23. Orden esperado después del OK

1. evidencia del Shipment estándar + documentación Chilexpress;
2. cerrar plan/data model/contrato Adapter;
3. presentar plan a Miguel;
4. OK explícito;
5. tests de preflight y adapter;
6. Link Courier Configuration en Shipment;
7. preflight;
8. cobertura;
9. cotización;
10. selección de servicio;
11. creación OT idempotente;
12. persistencia en Shipment;
13. etiqueta;
14. tracking manual;
15. pruebas de errores/reintentos;
16. deploy sandbox;
17. prueba real punta a punta contra Chilexpress Test;
18. aceptación Miguel;
19. cierre Spec 009.
