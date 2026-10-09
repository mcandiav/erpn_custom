# Plan - Spec 020 Abastecimiento multifuente y demanda residual

Estado: CERRADA (aceptación arquitectónica 2026-10-09; implementación reportada 16.0.109)
Fecha: 2026-10-07
Prioridad: inmediata

## Etapa 1 - Investigación y modelo
- Inventariar uso actual de purchase_status, requested_qty, received_qty y custom_encargo_qty.
- Confirmar todos los puntos que asumen una sola compra por Encargo.
- Crear Encargo Supply Event.
- Definir cálculos sourced_qty, pending_supply_qty, received_qty y covered_qty.

## Etapa 2 - Migración
- Migrar legacy PENDING/PURCHASED sin inventar datos.
- Relacionar Recepcion Unidad cuando sea determinístico.
- Dejar patch idempotente.
- Preparar regularizador especial con preview para OV-328/ENC-403.

## Etapa 3 - Shopper multiusuario
- Cambiar cola a pending_supply_qty.
- Permitir compra parcial.
- Crear evento por compra.
- Evitar sobrescritura de evidencia.
- Proteger concurrencia.
- Refrescar cantidad residual después de cada compra.

## Etapa 4 - Recepción multifuente
Estado: CERRADA. Piloto real 2026-10-08: OV-2026-00330 / ENC-2026-00405 / RCU-2026-00253, RECEPTION_DIRECT, SRE MAT-SRE-2026-00245; salida de cola Shopper.
- [x] Quitar PURCHASED como requisito para asignar demanda.
- [x] Buscar demanda compatible FIFO por Encargo.creation + name.
- [x] Mostrar APARTAR por compromiso, no por origen de compra.
- [x] Crear/completar Supply Event correcto: SHOPPER_PURCHASE en tránsito o RECEPTION_DIRECT si no había fuente.
- [x] Mantener STOCK NORMAL solo sin demanda compatible.
- [x] Piloto nuevo KNOWN_ITEM sin compra Shopper: recepción directa, APARTAR, vínculo de unidad y reducción de cola (evidencia en tasks.md y checklists/acceptance.md).

## Etapa 5 - Reconciliación
Estado: CERRADA en 16.0.109 según tasks.md, reservations.py y matriz de aceptación.
- [x] Existe `demand.reconcile_encargo_supply` y es idempotente sobre eventos/unidades.
- [x] Shopper y resumen visual de OV consumen cantidades derivadas.
- [x] Reconciliación por Sales Order Item / SRE incorporada en `encargo/reservations.py` (16.0.109); UI «Revisar reservas».
- [x] `covered_qty` distingue cobertura/reserva física válida; caso «Reserva inválida» implementado (16.0.109).
- [x] Desalineación entre bodega y SRE detectada; «Corregir reservas» la repara con privilegio System Manager, sin reconstrucción global (16.0.109).
- [x] Validación de reservas y cobertura sin doble conteo; evidencia en tasks.md, test_reservations y matriz de aceptación.
- [x] Corrección limitada a SRE propias del flujo, preservando SRE ajenas.

## Etapa 6 - Stock libre posterior
Estado: CERRADA. Asignación de stock elegible a demanda con `STOCK_REALLOCATION` y acción «Asignar stock a demanda»; evidencia en `tasks.md` (UI ComercialFRA) y matriz de aceptación, caso 19.
- [x] Detectar/asignar stock elegible solo mediante acción/regla determinística.
- [x] Crear STOCK_REALLOCATION.
- [x] Resolver demanda residual sin duplicar compra.

## Etapa 7 - Integraciones
Estado: CERRADA. Integraciones marcadas completas en `tasks.md`; Nota de Entrega NE-2026-00003 documentada el 2026-10-09.
- [x] Spec 017: barcode por evento/cantidad.
- [x] Spec 018: recepción y warning.
- [x] Spec 019: materialización solo UNKNOWN_ITEM.
- [x] Delivery Note y reservas.

## Etapa 8 - Piloto
Estado: CERRADA. Regularización OV-2026-00328 / ENC-2026-00403 (tasks.md y matriz §23, casos 12–13); cuatro Shoppers 1+1+1+1 (`TestFourShoppers`, matriz casos 1–5).
- [x] Regularizar OV-2026-00328 / ENC-2026-00403.
- [x] Confirmar 5 cubierto, pendiente 0, Shopper sin ENC-403 (matriz 12–13).
- [x] Probar demanda x4 con cuatro Shoppers distintos (matriz 1–5).

## Cierre y evidencia (2026-10-09)
- Decisión del Arquitecto: cierre documental aceptado a partir de `tasks.md` CERRADA 16.0.109 y `checklists/acceptance.md` (30 casos §23), sin ejecutar nuevamente pruebas en esta revisión.
- E4: piloto 2026-10-08 OV-2026-00330 / ENC-2026-00405 / RCU-2026-00253; RECEPTION_DIRECT y salida de cola.
- E5: `encargo/reservations.py`, detección de `invalid_qty` / reserva inválida, acciones «Revisar reservas» / «Corregir reservas», SRE ajenas preservadas.
- Delivery Note: NE-2026-00003, 2026-10-09, desde `Recepcion Encargos - FRAG`.
- Matriz: `checklists/acceptance.md` enumera los 30 criterios y sus pruebas asociadas. Commit de cierre verificado por el Programador en `origin/version-16`: `919f307` — `[16.0.109] Spec 020: pruebas de aceptacion y matriz de los 30 casos`. Incluye tests de aceptación, matriz `checklists/acceptance.md`, `tasks.md` y README.
- La versión 16.0.112 tiene despliegue **confirmado por Miguel** el 2026-10-09; es distinto del cierre funcional de 020 en 16.0.109.
- Edición de compras del Shopper: requisito posterior formalizado en `ERPnext-custom/specs/021-edicion-compras-shopper/spec.md`; **Spec 021 vigente para handoff**, independiente del cierre de 020.
