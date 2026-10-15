# Tasks - Spec 018 Recepción física e inventario Chile

Estado: EN CIERRE (16.0.98 etapas 1-3; 16.0.99 etapas 4-5 y ajustes del piloto). Falta: deploy 16.0.99, ícono como ComercialFRA y escaneo real en celular
Fecha: 2026-10-06

## Etapa 1 - Modelo y configuración

- [x] Crear DocType Recepción Unidad.
- [x] Crear unicidad de scan_event_id.
- [x] Agregar estados y vínculos definidos en Spec.
- [x] Agregar received_qty a Encargo.
- [x] Agregar purchase_currency a Encargo con default USD.
- [x] Crear patch/backfill de purchase_currency.
- [x] Crear Configuración Recepción FRA.
- [x] Agregar campo cuenta transitoria.
- [x] Agregar tasa USD->CLP de respaldo.
- [x] Crear patch de bodega Recepcion Encargos - FRAG.
- [x] Validar que no se cree cuenta contable automáticamente.
- [x] Pruebas unitarias del modelo y configuración.
- [x] Confirmar Patch Log tras migrate (v0_0_40, 2026-10-06 11:17:09).

## Etapa 2 - Backend recepción

- [x] Implementar receive_scan(code, scan_event_id).
- [x] Implementar idempotencia transaccional.
- [x] Resolver FIFO de Encargos comprados con recepción pendiente (implementación legacy 16.0.98/99).
- [ ] CORRECCIÓN SPEC 020: ampliar FIFO a demanda compatible aunque `purchase_status != PURCHASED`; vincular, mostrar APARTAR y reconciliar cantidad residual.
- [x] Implementar contador unitario received_qty.
- [x] Implementar creación automática de UNKNOWN_ITEM.
- [x] Implementar regla de item_code limpio <= 40.
- [x] Implementar serie FRA-##### para barcode no apto como item_code.
- [x] Mantener barcode original en Item Barcode.
- [x] Implementar PENDING_CLASSIFICATION para datos insuficientes.
- [x] Implementar barcode desconocido sin Encargo.
- [x] Implementar resolución KNOWN_ITEM.
- [x] Implementar bloqueo por mismatch pendiente.
- [x] Implementar costo Shopper.
- [x] Consultar Currency Exchange por purchased_on.
- [x] Implementar tasa de respaldo.
- [x] Implementar PENDING_COST / pendiente de valorización.
- [x] Implementar Material Receipt controlado.
- [x] Encargo -> Recepcion Encargos - FRAG.
- [x] Stock normal -> Matriz - FRAG.
- [x] Verificar mecanismo estándar de reserva ERPNext para KNOWN_ITEM.
- [x] Documentar fallback si la reserva estándar no aplica a la bodega de apartados.
- [x] Ejecutar pruebas 1-17 y 20-24 de Spec §20 (unittests con ERPNext simulado; integración real cubierta por el piloto).

## Etapa 3 - UI FRAreceptor

- [x] Generar scan_event_id por lectura.
- [x] Implementar mensajes A-E y B2.
- [x] Mantener Cliente y OV de solo lectura junto con ENC.
- [x] Implementar historial de sesión.
- [x] Validar sintaxis JS.
- [x] Probar lectura real en celular (ENC-2026-00001, producto desconocido; faltó grupo de producto en el Encargo; al completarlo, RCU-2026-00002 POSTED, IQNR94465, 8.762,94 CLP).

## Etapa 4 - UI ComercialFRA

- [x] Crear navegación MCV Chile > Recepción (ícono Recepción Comercial, 16.0.99).
- [x] Crear Apartados.
- [x] Crear Pendientes de clasificación.
- [x] Crear Excepciones barcode.
- [x] Crear Pendientes de valorización.
- [x] Implementar Resolver.
- [x] Implementar Reintentar valorización.
- [x] Implementar Devolver a stock.
- [x] Liberar reserva cuando corresponda.
- [x] Transferir Recepcion Encargos - FRAG -> Matriz - FRAG.
- [x] Motivo obligatorio y auditoría.
- [x] Pruebas de permisos ComercialFRA/FRAreceptor/System Manager (TestPermissions, 16.0.99).

## Etapa 5 - Regularización

- [x] Crear acción Regularizar recepciones previas para System Manager.
- [x] Reutilizar servicio de recepción.
- [x] Generar scan_event_id de migración.
- [x] Bloquear acción si falta cuenta transitoria.
- [x] Regularizar ENC-2026-00401 (RCU-2026-00001, APARTAR).
- [x] Verificar Item (FRA-00001 creado).
- [x] Verificar Stock Entry (MOV-2026-00001, 4.936,25 CLP; importe del documento corregido en 16.0.99 para nuevos movimientos).
- [x] Verificar received_qty = 1 para caso piloto.
- [x] Verificar bitácora completa (evento de regularización con nota y usuario desde 16.0.99).
- [x] Ejecutar prueba 19 y 25 de Spec §20.
- [x] Actualizar README y bitácora técnica.
- [x] Piloto final en celular (16.0.99): receptor escanea, ComercialFRA resuelve clasificación, unidad pasa a Apartados con stock.

## Precondiciones operativas antes de producción

- [x] Configurador crea Compras Shopper por regularizar - FRAG en el padre contable correcto (Inventarios por pagar - FRAG).
- [x] Configurador selecciona la cuenta en Configuración Recepción FRA.
- [x] Confirmar Currency Exchange USD->CLP operativo o cargar tasa de respaldo (frankfurter.dev - v2; respaldo 980).


## Etapa 6 - Cambio arquitectónico: borrador por caja (CERRADA 2026-10-15 POR DECISIÓN DE MIGUEL; código 16.0.119)

> **Cierre:** Miguel ordenó cerrar la Spec 018 el 2026-10-15 con la evidencia de pruebas automáticas. Desalineación registrada: la orden del Arquitecto (plan.md, 2026-10-14) pedía no declarar cierre sin piloto en celular. Al cierre **no hay evidencia** de migrate en el sitio, workers/scheduler activos ni piloto físico; las casillas abiertas abajo quedan como deuda operativa, no como pruebas realizadas.

> Alcance nuevo definido el 2026-10-10, no incluido en la evidencia ni entregas 16.0.98/16.0.99. §23 de Spec sustituye la anulación inmediata poscontabilización. Las casillas históricas de Etapas 1-5 no acreditan esta mejora.

- [x] Revisar implementación vigente de `receive_scan`, `Recepción Unidad`, UI y permisos para identificar cambios mínimos y prevenir doble contabilización.
- [x] Cabecera de recepción BOX persistente con identificador y estado DRAFT / FINALIZING / FINALIZED / FINALIZED_WITH_EXCEPTIONS; referencia externa opcional.
- [x] Guardar cada escaneo como línea persistente de borrador con scan_event_id único y enlace a BOX; soporte de reanudación tras desconexión.
- [x] Acción Quitar lectura antes de finalizar, sin motivo, conservando auditoría de descarte y sin revertir stock.
- [x] Cambiar UI: Abrir caja / Continuar caja, historial, lectura, contador, advertencia no bloqueante de repetición, Quitar, Finalizar y resultado.
- [x] Implementar cierre idempotente y concurrente, sin efectos de inventario ni de Encargo hasta finalizar; verificar FIFO con Spec 020 al cierre.
- [x] Procesamiento individual después de confirmación física, con excepciones pendientes por unidad, reintento seguro y estado FINALIZED_WITH_EXCEPTIONS.
- [x] Vincular Recepción Unidad al BOX y conservar búsqueda inversa desde Item/ENC/OV, sin agregar caja al maestro Item; legado sin cajas inventadas.
- [x] Revisar permisos ReceptorFRA, ComercialFRA y System Manager y bloquear edición de cajas cerradas.
- [ ] Ejecutar 12 casos obligatorios de §23.6 (unittests hechos para 1, 2, 4, 5, 8, 9 y 11; resto y piloto real en celular pendientes) y aportar evidencia.
- [x] Actualizar README / especificaciones de UI y verificar no regresión de Etapas 1-5 (suite local).
### Desglose operativo E1-E6 autorizado (2026-10-14)

- [x] **E1 Modelo:** Recepcion Caja (DRAFT/FINALIZING/FINALIZED/FINALIZED_WITH_EXCEPTIONS/CANCELLED), Recepcion Caja Linea autónoma (scan_event_id único, autor, estado DISCARDED), box/box_line en Recepcion Unidad, serie anual y permisos; tests de unicidad y roles.
- [x] **E2 Borrador:** abrir/continuar entre FRAreceptores, agregar/Quitar lectura, Anular caja DRAFT incluso vacía, vista preliminar estrictamente read-only; tests de dos barcodes iguales, cero efectos de stock, desconexión, cambio de turno y auditoría.
- [x] **E3 Cierre:** finalize_box con job de cola y procesamiento idempotente con commit por línea, reanudación automática de FINALIZING interrumpidos y sin duplicados; protección de concurrencia y FIFO Spec 020; receive_scan inaccesible directamente a FRAreceptor; bloqueo conservador de update_purchase por barcode actual/nuevo para líneas no procesadas FINALIZING y liberación al terminar; pruebas de carrera con Shopper y de rechazo del endpoint anterior.
- [ ] **E4 UI Receptor:** Mis cajas abiertas / Continuar / Abrir / lector / Quitar / Anular borrador / Finalizar / progreso / resultado por unidad / Historial de cajas, mobile-first; pruebas navegador y celular. *(Programada; pruebas navegador/celular pendientes.)*
- [x] **E5 Comercial y trazabilidad:** Recepción > Cajas con incidencias y detalle BOX con botón Reintentar para ComercialFRA/System Manager solo en líneas no consumadas; ReceptorFRA solo consulta; BOX en Recepcion Unidad e historial Item/ENC/OV, búsqueda BOX/barcode/ENC/OV, LEGACY sin migraciones destructivas; pruebas de regresión Specs 018, 020, 021.
- [ ] **E6 Cierre:** piloto de duplicado, desconexión, dos cajas simultáneas, excepción parcial, cierre repetido y worker interrumpido; evidencia en tasks.md/README, versión validada, commit/push por Programador.

**Nota de aceptación:** un match por barcode durante FINALIZING bloquea la edición Shopper temporalmente aunque no se haya vinculado aún una compra; no declarar que ya fue recibida. Tras concluir el procesamiento, solo las asociaciones reales justifican la restricción definitiva de Spec 021. No bloquear compras no vinculadas permanentemente por compartir barcode.

### Pruebas adicionales §23.8 (unittests locales, 16.0.119)

- [x] Anular caja vacía y caja con lecturas (CANCELLED, usuario/fecha, sin efectos; no reabre).
- [x] Cambio de receptor/turno: otro FRAreceptor continúa y finaliza; autor por lectura/descarte y usuario finalizador.
- [x] Reanudar job interrumpido: scheduler re-encola FINALIZING sin avance > 10 min y procesa solo líneas no consumadas; sin duplicar unidad (scan_event_id).
- [x] Carrera con edición Shopper: `update_purchase` rechaza con el mensaje exacto de la orden si el barcode actual o el nuevo coincide con línea ACTIVA/ERROR de caja FINALIZING; libre en DRAFT y tras terminar.
- [x] Autorización backend del endpoint anterior: `receive_scan` rechaza a todo rol; el cierre usa la función interna `process_scan`.
- [x] Historial por autor de lectura ("Con mis lecturas") y búsqueda por BOX/barcode/ENC/OV/Item/cliente.
- [x] Vista previa read-only: nunca llama `_resolve_item` ni escribe.

### Evidencia 16.0.119 (local)

- `test_box_reception.py` nuevo + `test_reception.py` / `test_shopper.py` ajustados: 95 tests OK.
- Suite completa: 481 tests, sin fallas nuevas (9 fallas y 1 error previos, ajenos: contact mirror, brand supplier, sales person, sales order encargo).
- JS `recepcion_chile.js` y `recepcion_comercial.js` verificados con `node --check`; JSON de DocTypes válidos.
- Decisión de implementación: el bloqueo Shopper considera también líneas ERROR (aún no consumadas) de cajas FINALIZING; se libera al pasar la caja a FINALIZED/FINALIZED_WITH_EXCEPTIONS.
- Pendiente E6: migrate en el sitio, confirmar RQ workers (cola `long`) y scheduler activos, piloto en celular (duplicado, desconexión, dos cajas simultáneas, excepción parcial, cierre repetido, worker interrumpido).

