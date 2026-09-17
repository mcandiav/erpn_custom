# Tasks: Chilexpress vinculado a Shipment

> **Estado de cierre (2026-09-17):** Spec 009 implementada (`16.0.11`→`16.0.21`), validada en Chilexpress Test (`SHIPMENT-00001`, OT `712678881073`, tracking, **etiqueta de envío OK**, reintento Crear bloqueado) y aceptada por Miguel. Nota no bloqueante: reprint API Test 404 (File del create). Esta lista queda como trazabilidad histórica; la cola vigente es `../../README.md`.

**Input**: `spec.md`, `plan.md`, `data-model.md`

**Estado**: cerrado.

## Phase 1 — Evidence gate

- [ ] T001 Leer README, Spec 008, Spec 009 y `despachos_transportistas.md`.
- [ ] T002 Inspeccionar `Shipment` estándar ERPNext v16: campos, tablas, docstatus, JS/controlador y creación desde Delivery Note.
- [ ] T003 Documentar mapping candidato de `carrier`, `carrier_service`, `service_provider`, `shipment_id`, `shipment_amount`, `awb_number`, `tracking_status`.
- [ ] T004 Inspeccionar `Shipment Parcel` real y confirmar fields de largo/ancho/alto/peso/count.
- [ ] T005 Inspeccionar tabla de Delivery Notes del Shipment.
- [ ] T006 Confirmar mecanismo estándar `File` attachment para etiqueta.
- [ ] T007 Revisar documentación oficial vigente Chilexpress Coberturas/Cotizador/Envíos.
- [ ] T008 Confirmar payload/response de cotización, creación OT, etiqueta y tracking.
- [ ] T009 Confirmar TCC/account reference requerido en Test y dónde se enviará.
- [ ] T010 Investigar referencia cliente/idempotencia/reconciliación disponible en Chilexpress.
- [ ] T011 Presentar a Miguel evidencia, mapping definitivo, Custom Fields estrictamente necesarios y estrategia de idempotencia.
- [ ] T012 Esperar OK explícito de Miguel.

## Phase 2 — Contrato multi-courier

- [ ] T013 Crear contrato/base `CourierAdapter` server-side.
- [ ] T014 Crear registry/factory central `provider_code -> Adapter`.
- [ ] T015 Registrar únicamente `chilexpress`.
- [ ] T016 Crear tests de registry y capacidades.

## Phase 3 — Vínculo Shipment -> Courier Configuration

- [ ] T017 Crear `custom_courier_configuration` Link en Shipment mediante mecanismo versionado de app.
- [ ] T018 Filtrar configuraciones habilitadas en UI.
- [ ] T019 Mostrar provider/ambiente de forma inequívoca; Test debe ser visible.
- [ ] T020 No duplicar credenciales/endpoints/provider/environment como campos editables en Shipment.
- [ ] T021 Crear test de vínculo y carga de configuración.

## Phase 4 — Preflight

- [ ] T022 Implementar validación server-side de Courier Configuration.
- [ ] T023 Validar API keys/endpoints requeridos sin exponer valores.
- [ ] T024 Validar TCC/account reference cuando Chilexpress lo requiera.
- [ ] T025 Validar origen y contacto según contrato API.
- [ ] T026 Validar destino y contacto según contrato API.
- [ ] T027 Validar cada Shipment Parcel: weight/length/width/height/count > 0 para mercadería.
- [ ] T028 Validar valor de bienes y descripción del contenido.
- [ ] T029 Validar estado del Shipment e inexistencia de OT confirmada previa.
- [ ] T030 Devolver lista completa de errores accionables.
- [ ] T031 Tests de preflight completo/incompleto/múltiples paquetes.

## Phase 5 — Cobertura Chilexpress

- [ ] T032 Implementar resolución de cobertura origen.
- [ ] T033 Implementar resolución de cobertura destino.
- [ ] T034 No hardcodear códigos de comunas.
- [ ] T035 Manejar cero/múltiples coincidencias de forma explícita.
- [ ] T036 Tests con HTTP mock y errores de cobertura.

## Phase 6 — Cotización

- [ ] T037 Implementar `ChilexpressAdapter.cotizar()` usando rating config de Spec 008.
- [ ] T038 Construir payload desde Shipment + cobertura + paquetes.
- [ ] T039 Normalizar respuesta a contrato CourierQuote.
- [ ] T040 Implementar acción UI `Cotizar envío`.
- [ ] T041 Presentar alternativas al usuario.
- [ ] T042 Persistir servicio/código/costo seleccionados usando estándar y mínimo custom necesario.
- [ ] T043 Asegurar que cotizar no crea OT.
- [ ] T044 Tests quote success/zero services/API validation/auth/timeout.

## Phase 7 — Idempotencia

- [ ] T045 Implementar estado/clave de creación según plan aprobado.
- [ ] T046 Proteger doble click y concurrencia server-side.
- [ ] T047 Bloquear nueva creación si existe OT confirmada.
- [ ] T048 Implementar estado `Uncertain` o equivalente para timeout ambiguo.
- [ ] T049 Prohibir auto-reintento POST cuando el resultado sea incierto.
- [ ] T050 Implementar reconciliación si la API ofrece mecanismo verificable.
- [ ] T051 Tests de doble llamada, timeout antes/después y OT preexistente.

## Phase 8 — Crear OT

- [ ] T052 Implementar `ChilexpressAdapter.crear_envio()` con shipping config de Spec 008.
- [ ] T053 Revalidar preflight/servicio antes del POST.
- [ ] T054 Traducir Shipment al payload oficial Chilexpress.
- [ ] T055 Persistir OT/external id inmediatamente en éxito.
- [ ] T056 Mapear costo, carrier, servicio, AWB/tracking según semántica confirmada.
- [ ] T057 Normalizar errores sin secrets/headers.
- [ ] T058 Tests create success/API error/auth error/timeout.

## Phase 9 — Etiqueta

- [ ] T059 Implementar `obtener_etiqueta()` según API vigente.
- [ ] T060 Guardar etiqueta como `File` adjunto a Shipment.
- [ ] T061 Permitir reobtener/reimprimir sin crear nueva OT.
- [ ] T062 Tests label success/not available/retry.

## Phase 10 — Tracking

- [ ] T063 Implementar `consultar_tracking()`.
- [ ] T064 Acción UI `Actualizar tracking` solo cuando exista identificador externo.
- [ ] T065 Mapear al `tracking_status` estándar cuando corresponda.
- [ ] T066 Persistir timestamp/detalle adicional solo si el estándar es insuficiente.
- [ ] T067 Tests tracking success/no events/error.

## Phase 11 — UI / estados

- [ ] T068 Botones visibles/habilitados según estado lógico.
- [ ] T069 Sin paquete completo -> bloquear Cotizar.
- [ ] T070 Sin servicio seleccionado -> bloquear Crear envío.
- [ ] T071 OT creada -> bloquear Crear envío normal.
- [ ] T072 OT creada -> habilitar etiqueta/tracking.
- [ ] T073 Ambiente Test claramente visible.
- [ ] T074 No construir payload Chilexpress ni manejar secrets en JS.

## Phase 12 — Seguridad y regresión

- [ ] T075 Buscar secrets accidentalmente versionados/logueados.
- [ ] T076 Confirmar uso de helpers de Courier Configuration, sin duplicación.
- [ ] T077 Confirmar que no se modificó core.
- [ ] T078 Confirmar que no se agregó lógica courier a Sales Order/Delivery Note.
- [ ] T079 Confirmar que fallas API no modifican pagos/facturas/Customer.
- [ ] T080 Ejecutar tests Spec 009 + regresión Spec 008.

## Phase 13 — Release sandbox

- [ ] T081 Usar siguiente patch/version disponible real; no asumir `v0_0_9` porque ese patch ya existe.
- [ ] T082 Bump semver según regla de repo.
- [ ] T083 Commit/push.
- [ ] T084 Deploy sandbox + migrate.
- [ ] T085 Crear Shipment Test completo con dirección y paquete realista.
- [ ] T086 Seleccionar Chilexpress/Test.
- [ ] T087 Demostrar preflight y error por dimensiones faltantes.
- [ ] T088 Completar dimensiones y cotizar real.
- [ ] T089 Seleccionar servicio.
- [ ] T090 Crear una OT real Chilexpress Test.
- [ ] T091 Verificar OT/costo/servicio persistidos.
- [ ] T092 Obtener etiqueta.
- [ ] T093 Consultar tracking.
- [ ] T094 Intentar Crear nuevamente y demostrar no duplicación.

## Phase 14 — Aceptación

- [ ] T095 Presentar resultado punta a punta a Miguel.
- [ ] T096 Corregir desviaciones de aceptación sin ampliar alcance.
- [ ] T097 Tras aceptación, cerrar Spec 009 en README/spec.

## Checkpoints críticos

- **CP1 después de T011**: no programar sin OK de Miguel.
- **CP2 después de T044**: cotización funciona sin crear OT antes de avanzar.
- **CP3 después de T051**: idempotencia aprobada antes de habilitar creación real.
- **CP4 después de T084**: no usar Producción; prueba externa solo Chilexpress Test.
- **CP5 después de T094**: no cerrar sin demostrar no duplicación.

## Regla de alcance

Esta Spec termina cuando un Shipment estándar puede completar punta a punta una operación Chilexpress Test segura. No incorporar Starken, FAZT, cotizador comercial multi-courier, consolidación de OVs ni dimensiones maestras de Item.
