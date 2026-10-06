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
- [x] Ejecutar pruebas 1-17 y 20-24 de Spec §20 (unittests con ERPNext simulado; integración real cubierta por el piloto).

## Etapa 3 - UI FRAreceptor

- [x] Generar scan_event_id por lectura.
- [x] Implementar mensajes A-E y B2.
- [x] Mantener Cliente y OV de solo lectura junto con ENC.
- [x] Implementar historial de sesión.
- [x] Validar sintaxis JS.
- [ ] Probar lectura real en celular.

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
- [ ] Piloto final en celular.

## Precondiciones operativas antes de producción

- [x] Configurador crea Compras Shopper por regularizar - FRAG en el padre contable correcto (Inventarios por pagar - FRAG).
- [x] Configurador selecciona la cuenta en Configuración Recepción FRA.
- [x] Confirmar Currency Exchange USD->CLP operativo o cargar tasa de respaldo (frankfurter.dev - v2; respaldo 980).
