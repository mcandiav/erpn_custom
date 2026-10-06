# Tasks — Spec 013 Fase D: Recepción Chile

## Gate de arquitectura

- [x] D001 Leer README + Spec 013 §29, §34 y este plan.
- [x] D002 Inspeccionar Frappe/ERPNext v16 y código actual de Encargo/Shopper.
- [x] D003 Presentar archivos a crear/modificar, rol propuesto y estrategia de idempotencia.
- [x] D004 Esperar OK explícito de Miguel antes de programar.

## Backend

- [x] D010 Implementar búsqueda exacta por `purchase_barcode` sobre Encargos PURCHASED pendientes.
- [x] D011 Soportar match cero, uno y múltiples.
- [x] D012 Implementar transición PENDING -> RECEIVED con timestamp y usuario.
- [x] D013 Implementar búsqueda/propuesta de Item por identificador.
- [x] D014 Validar unicidad del identificador al asociarlo a Item.
- [x] D015 Implementar resolución RECEIVED -> RESOLVED_TO_ENC.
- [x] D016 Implementar ruta explícita NO SATISFACE -> STOCK sin destruir historia.
- [x] D017 Proteger doble click, reintento y doble resolución.

## UI

- [x] D020 Crear acceso `Encargo -> Recepción Chile`.
- [x] D021 Crear Page orientada a escaneo con foco persistente.
- [x] D022 Mostrar pendientes PURCHASED/PENDING.
- [x] D023 Match único: warning dominante `ENCARGO DETECTADO / ENC-YYYY-##### / APARTAR`.
- [x] D024 Warning no desaparece por timeout.
- [x] D025 Acciones: APARTADO / CONTINUAR, VER DETALLE, NO CORRESPONDE.
- [x] D026 Múltiples ENC con mismo código: asignación automática al de compra más antigua (decisión Miguel, Spec §34.20).
- [x] D027 Sin match: PRODUCTO SIN ENCARGO IDENTIFICADO + acciones Item/Stock/Buscar ENC.
- [x] D028 Conciliación lado a lado Solicitud original vs Compra Shopper.
- [x] D029 Después de completar una unidad, volver automáticamente al modo escáner.

## Permisos

- [x] D030 Definir rol interno de recepción o justificar reutilización de uno existente.
- [x] D031 ShopperFRA sin acceso.
- [x] D032 VendedorFRA/ComercialFRA sólo consulta salvo permiso explícito adicional.
- [x] D033 No depender de System Manager para operación normal.

## Caso piloto

- [ ] D040 Abrir Recepción Chile.
- [ ] D041 Escanear `https://qrgo.page.link/JsDVr`.
- [ ] D042 Confirmar que localiza únicamente/correctamente `ENC-2026-00401` según candidatos vigentes.
- [ ] D043 Confirmar warning visual con número ENC dominante.
- [ ] D044 Marcar APARTADO / CONTINUAR -> RECEIVED.
- [ ] D045 Resolver Item.
- [ ] D046 Confirmar SATISFACE ENCARGO.
- [ ] D047 Verificar resolved_item + resolved_by + received_on + RESOLVED_TO_ENC.
- [ ] D048 Verificar OV-2026-00326 sin reescritura destructiva.

## Regresión

- [ ] D050 Compra Shopper continúa igual.
- [ ] D051 Barcode EAN/UPC continúa funcionando.
- [ ] D052 QR/URL funciona como valor opaco.
- [ ] D053 Dos ENC con mismo código no se asignan solos.
- [ ] D054 Código sin ENC no contamina ningún Encargo.
- [ ] D055 Reload/reintento conserva consistencia.

## Cierre

- [ ] D060 Evidencia visual del caso piloto.
- [ ] D061 Tests server-side y JS/UI aprobados.
- [x] D062 Versionar patch de producto y documentar README técnico.
- [ ] D063 Aceptación de Miguel.
