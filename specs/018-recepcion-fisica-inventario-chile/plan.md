# Plan - Spec 018 Recepción física e inventario Chile

Estado: APROBADO PARA PROGRAMACION
Fecha: 2026-10-06
Dependencia: Specs 013/015 vigentes; alineación obligatoria con Spec 020
Orden actual: la base 018 está implementada, pero la selección de demanda debe corregirse por Spec 020 antes de continuar 017

## Etapa 1 - Modelo y configuración

- Crear DocType `Recepción Unidad`, un registro por unidad física escaneada.
- Índice/constraint único sobre `scan_event_id`.
- Estados mínimos: ingresada, pendiente de clasificación, pendiente de valorización, pendiente de aprobación de código, devuelta a stock.
- Vincular Encargo, Sales Order, Sales Order Item, Item, Stock Entry, bodega, moneda, precio, tasa y costo.
- Agregar `received_qty` y `purchase_currency` en Encargo.
- Backfill de `purchase_currency = USD` para Encargos existentes cuando corresponda.
- Crear `Configuración Recepción FRA` con:
  - cuenta transitoria obligatoria;
  - tasa USD->CLP de respaldo.
- Patch para crear `Recepcion Encargos - FRAG`.
- No crear la cuenta contable por patch.
- No crear `Recepcion Stock - FRAG`.

## Etapa 2 - Servicio de escaneo

Implementar servicio transaccional `receive_scan(code, scan_event_id)`.

Orden de resolución:

1. idempotencia por scan_event_id;
2. buscar demanda/Encargo compatible usando FIFO según Spec 020, exista o no compra Shopper previa;
3. resolver Item;
4. crear Item automático para UNKNOWN_ITEM cuando existan datos suficientes;
5. dejar PENDING_CLASSIFICATION cuando falten datos o barcode desconocido sin Encargo;
6. resolver costo/tipo de cambio;
7. generar Material Receipt;
8. destino:
   - Encargo -> Recepcion Encargos - FRAG;
   - stock normal identificado -> Matriz - FRAG;
9. incrementar received_qty en una unidad;
10. completar Encargo solo al llegar a requested_qty;
11. para KNOWN_ITEM intentar reserva estándar sin duplicación.

Reglas especiales:

- barcode URL/QR nunca debe convertirse automáticamente en item_code;
- barcode limpio alfanumérico/guion de hasta 40 caracteres sí puede usarse como item_code;
- los demás Items automáticos usan serie FRA-#####;
- tipo de cambio Shopper: fecha `purchased_on`;
- sin cuenta transitoria configurada no hay Stock Entry.

## Etapa 3 - UI FRAreceptor

- Mobile-first.
- Cada lectura genera scan_event_id.
- Sin controles de decisión.
- Mostrar:
  - APARTAR - ENC-...
  - STOCK NORMAL
  - STOCK NORMAL - REQUIERE CLASIFICACION
  - APARTAR - REQUIERE COMERCIAL
  - APARTAR - REQUIERE CLASIFICACION - ENC-...
  - RECIBIDO - PENDIENTE DE VALORIZACION
- Mantener Cliente y OV como información de solo lectura en la tarjeta vigente.
- Historial inmediato de lecturas.

## Etapa 4 - UI ComercialFRA

Workspace MCV Chile > Recepción:

- Apartados.
- Pendientes de clasificación.
- Excepciones barcode.
- Pendientes de valorización.

Acciones:

- Resolver clasificación.
- Reintentar valorización.
- Devolver a stock.
- Abrir Encargo/Item y trazabilidad.

Sin permisos generales de Stock Entry.

## Etapa 5 - Regularización y cierre

- Acción `Regularizar recepciones previas` solo para System Manager.
- Reutilizar el mismo servicio de recepción.
- Generar scan_event_id de migración por unidad.
- Regularizar ENC-2026-00401 como piloto obligatorio.
- Ejecutar solo después de configurar la cuenta transitoria.
- No ejecutar regularización vía patch/migrate.
- Piloto final en celular.


## Orden explícita del Arquitecto al Programador — 2026-10-14

**AUTORIZADA LA PROGRAMACIÓN DE LA SPEC 018, ETAPA 6 (E1–E6).** No se requiere una nueva ronda de aprobación para comenzar. El alcance es exclusivamente la recepción provisional por caja BOX, aprovechando el código vigente de recepción; no reimplementar las etapas 1–5 ni reabrir las Specs 017, 020 o 021.

**Contrato funcional inalterable:** en DRAFT cada lectura se guarda en servidor y puede descartarse sin afectar inventario, Encargo, reserva o contabilidad. Al pulsar Finalizar se congela el contenido, se pasa a FINALIZING y un job procesa cada unidad de forma idempotente; el receptor consulta el avance. Una caja cerrada nunca vuelve a DRAFT. Crear Recepcion Caja y Recepcion Caja Linea independientes (no tabla hija), con BOX-YYYY-NNNNN anual, y referencia BOX en Recepcion Unidad; no añadir campo de caja único al maestro Item. Permitir cambio de turno entre FRAreceptores, con autor por lectura y usuario finalizador. Permitir Anular caja en DRAFT, incluso vacía, sin eliminar historia. Los jobs interrumpidos se recuperan y ComercialFRA/System Manager reintentan solo líneas no consumadas; FRAreceptor no reintenta ni accede directamente al endpoint legacy receive_scan.

**Regla Shopper durante FINALIZING:** impedir temporalmente update_purchase cuando el barcode actual O el propuesto coincida con cualquier línea activa todavía no procesada de caja en FINALIZING. Utilizar el mensaje exacto: «No se puede modificar esta compra mientras se procesa una recepción en Chile que contiene el mismo código de producto. Inténtelo cuando finalice el procesamiento.» La coincidencia de barcode no acredita una compra recibida ni justifica bloquearla permanentemente. Al finalizar procesamiento, regirán solo las restricciones de Spec 021 basadas en recepciones realmente vinculadas, incluidas excepciones que sí estén asociadas. Proteger la carrera edición/cierre con bloqueo y relectura de información vigente. No usar funciones preliminares con efectos de escritura.

**Secuencia autorizada:** E1 modelo y permisos; E2 borrador; E3 cierre asíncrono, recuperación y protección Shopper; E4 UI receptor; E5 UI Comercial/trazabilidad y regresiones; E6 piloto, evidencia y publicación. Validar pruebas por etapa; confirmar workers y scheduler activos antes del piloto real, además de comprobar la versión vigente antes de asignar 16.0.119. El Programador actualiza tasks.md con resultados, fallos, evidencias, README de entrega, versión, commit y push. No declarar cierre mientras falten pruebas del celular, reintento tras interrupción, simultaneidad, duplicados y regresión de las Specs 020/021. **No desplegar automáticamente como consecuencia de esta edición documental:** despliegue corresponde al flujo de programación y pruebas.

**Prioridad de documentación:** Spec 018 §23.8 y esta orden prevalecen sobre textos anteriores incompatibles de Etapas 1–5. El desarrollador no debe reinterpretar el mecanismo de cierre, permisos, edición del Shopper o cajas a su criterio.

## Etapa 6 - Ampliación aprobada: caja provisional (2026-10-10)

Estado: **APROBADA PARA PROGRAMACIÓN 2026-10-13**. Consultar Spec §23.8 (diez decisiones vinculantes, incluido bloqueo temporal por barcode durante FINALIZING, y pruebas adicionales). Esta etapa modifica el punto de contabilización de la Etapa 2: `receive_scan` existente **no se invoca** al escanear en borrador; conservar y reutilizar su lógica de resolución/contabilización dentro del servicio de cierre idempotente. Consultar Spec §23, que prevalece ante instrucciones anteriores incompatibles.

1. Inspeccionar DocTypes y servicios actuales; crear `Recepcion Caja` como cabecera y `Recepcion Caja Linea` como DocType independiente de líneas, reutilizando los servicios actuales. No crear `Caja` como maestro adicional ni módulo Aduana.
2. Crear identificador interno BOX único, línea por lectura UUID y vínculo desde `Recepción Unidad` a BOX y línea; permitir referencia externa opcional y compatibilidad con históricos sin caja.
3. Implementar abrir/continuar borrador, persistir cada lectura, quitar una lectura previa al cierre y auditar descarte. No afectar Item/Stock Entry/Encargo/Supply Event/reserva en DRAFT.
4. Implementar **Finalizar recepción** con bloqueo e idempotencia por caja/evento. Revalidar demanda Spec 020 en el cierre y procesar líneas separadamente, sin doble movimiento ante reintentos y con excepciones por unidad.
5. Rediseñar UI ReceptorFRA mobile-first: caja abierta, contador, lista, quitar, finalizar, resultado, historial; navegación y permisos según §23.3. ComercialFRA mantiene colas de excepción.
6. Exponer trazabilidad BOX desde cada unidad recibida y consulta histórica por Item/ENC/OV, sin campo de caja en maestro Item.
7. Pruebas de Spec §23.6; piloto físico en celular incluyendo duplicado, desconexión, 2 cajas concurrentes, excepción parcial y cierre repetido.
8. Actualizar documentación técnica y evidencia. No declarar cerrada la ampliación sin validación completa.

**No hacer:** reversión genérica de Stock Entry por errores de lectura; requerir Shopper/empaque Miami; borrar recepciones contabilizadas; afectar Stock Ledger al escanear provisionalmente.
