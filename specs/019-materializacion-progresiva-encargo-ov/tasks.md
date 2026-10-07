# Tasks - Spec 019 Materialización progresiva de Encargo en OV

Estado: CERRADA 2026-10-06 (16.0.100 + bodega por defecto `Matriz - FRAG`; piloto OK)
Fecha: 2026-10-06
Alcance: solo líneas ENCARGO-PENDIENTE (Encargo UNKNOWN_ITEM). KNOWN_ITEM fuera de alcance.

## Investigación ERPNext
- [x] Verificar Update Items en Sales Order submitted.
- [x] Verificar inserción de nueva línea en OV submitted.
- [x] Verificar reducción/eliminación segura de ENCARGO-PENDIENTE.
- [x] Verificar efectos sobre delivered_qty y billed_qty.
- [x] Verificar Stock Reservation Entry y cambio de línea/bodega.
- [x] Documentar estrategia seleccionada (plan.md, Resultado Etapa 1).

## Modelo
- [x] Agregar custom_encargo_origin a Sales Order Item.
- [x] Agregar custom_encargo_source_row.
- [x] Agregar materialization_status a Recepción Unidad.
- [x] Guardar línea real generada/incrementada.
- [x] Exponer cantidad materializada y pendiente en Encargo.
- [x] Crear bitácora de materialización (Encargo Materializacion).

## Backend
- [x] Implementar materialize_encargo_unit() (`materialization.materialize`).
- [x] Idempotencia por Recepción Unidad.
- [x] Validar OV submitted y no cancelada.
- [x] Validar pendiente > 0.
- [x] Crear línea real compatible.
- [x] Incrementar línea compatible del mismo ENC.
- [x] No fusionar Encargos distintos.
- [x] Heredar precio/descuento/UOM/campos comerciales.
- [x] Reducir ENCARGO-PENDIENTE.
- [x] Cerrar/eliminar línea técnica cuando pendiente = 0.
- [x] Ajustar reserva sin duplicación (1 SRE por unidad sobre la línea real).
- [x] Manejar error posterior a recepción sin revertir inventario.
- [x] Implementar reintento seguro.
- [x] Bloquear materialización excedente.
- [x] Bloquear delivered_qty/billed_qty incompatibles.

## UI ComercialFRA
- [x] Mostrar Encargo/link en líneas reales OV.
- [x] Mostrar cantidad pendiente/materializada (resumen bajo la tabla de Items de la OV).
- [x] Crear sección Materialización en Encargo.
- [x] Crear lista Pendientes de vincular a OV.
- [x] Acción Reintentar materialización.
- [x] Links OV / ENC / Recepción Unidad / Item.

## Entrega y reversión
- [x] Impedir ENCARGO-PENDIENTE en Delivery Note.
- [x] Confirmar Delivery Note estándar con Item real (piloto: `NE-2026-00003`).
- [x] Restaurar pendiente cuando una unidad materializada se devuelve a stock.
- [ ] Confirmar flujo estándar de devolución/liberación en el sitio (cubierto por pruebas unitarias; sin caso real en el piloto).

## Pruebas
- [x] Pruebas unitarias de Spec §21 (`test_materialization.py`, `test_reception.py`).
- [x] Ejecutar piloto ENC-2026-00401 / OV-2026-00326 (`RCU-2026-00001`).
- [x] Confirmar Item real en OV (`FRA-00001` x1 a $9.990, `ENCARGO-PENDIENTE` eliminada).
- [x] Confirmar reserva/apartado (`MAT-SRE-2026-00015`, 1 u en `Recepcion Encargos - FRAG`).
- [x] Confirmar Delivery Note (`NE-2026-00003`) y envío courier (`SHIPMENT-00010`, Chilexpress, guía 712678899391).

## Requisito de configuración descubierto en el piloto
- Configuración de existencias > Almacén predeterminado = `Matriz - FRAG`. Sin él, ERPNext no crea filas nuevas en una OV validada para Items sin bodega por defecto (los creados en la recepción).

## Pendiente para demostración
- `RCU-2026-00002` (`ENC-2026-00001` / `SAL-ORD-2026-00016`) queda en "Pendientes de vincular a OV" a propósito.
