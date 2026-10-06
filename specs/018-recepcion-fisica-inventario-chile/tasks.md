# Tasks - Spec 018 Recepción física e inventario Chile

Estado: EN EJECUCION (16.0.98 programada: etapas 1-3 y acciones de etapas 4-5)
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
- [ ] Confirmar Patch Log tras migrate.

## Etapa 2 - Backend recepción

- [x] Implementar receive_scan(code, scan_event_id).
- [x] Implementar idempotencia transaccional.
- [x] Resolver FIFO de Encargos comprados con recepción pendiente.
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
- [ ] Ejecutar pruebas 1-17 y 20-24 de Spec §20.

## Etapa 3 - UI FRAreceptor

- [x] Generar scan_event_id por lectura.
- [x] Implementar mensajes A-E y B2.
- [x] Mantener Cliente y OV de solo lectura junto con ENC.
- [x] Implementar historial de sesión.
- [x] Validar sintaxis JS.
- [ ] Probar lectura real en celular.

## Etapa 4 - UI ComercialFRA

- [ ] Crear navegación MCV Chile > Recepción.
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
- [ ] Pruebas de permisos ComercialFRA/FRAreceptor/System Manager.

## Etapa 5 - Regularización

- [x] Crear acción Regularizar recepciones previas para System Manager.
- [x] Reutilizar servicio de recepción.
- [x] Generar scan_event_id de migración.
- [x] Bloquear acción si falta cuenta transitoria.
- [ ] Regularizar ENC-2026-00401.
- [ ] Verificar Item.
- [ ] Verificar Stock Entry.
- [ ] Verificar received_qty = 1 para caso piloto.
- [ ] Verificar bitácora completa.
- [ ] Ejecutar prueba 19 y 25 de Spec §20.
- [ ] Actualizar README y bitácora técnica.
- [ ] Piloto final en celular.

## Precondiciones operativas antes de producción

- [ ] Configurador crea Compras Shopper por regularizar - FRAG en el padre contable correcto.
- [ ] Configurador selecciona la cuenta en Configuración Recepción FRA.
- [ ] Confirmar Currency Exchange USD->CLP operativo o cargar tasa de respaldo.
