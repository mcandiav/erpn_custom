# Plan — Spec 017 Excepciones de abastecimiento y trazabilidad desde OV

Estado: PAUSADA por Spec 020 desde 2026-10-07.

Fuente: `spec.md` de esta carpeta. Programador: no continuar E5/E6 hasta implementar y revalidar `020-abastecimiento-multifuente-demanda-residual`.

Spec 020 reemplaza cualquier supuesto de compra monolítica, `purchase_status` como fuente de verdad de demanda y recepción exclusiva de Encargos PURCHASED.

## Decisiones de Miguel (hilo de programación)

| Tema | Decisión |
|---|---|
| Compra errada | El Shopper siempre completa la compra; el vendedor decide (aprobar/rechazar, anular OV o nueva compra) |
| Modal Validar | Diálogo con Continuar / Cancelar |
| Estado por línea | Recuadro "Abastecimiento por línea" en la OV validada |
| Vista de excepciones | Pestaña "Excepciones barcode" de Recepción Comercial + botones en el Encargo |
| Gate de pago en aumento | Igual que Spec 015 (pago aplicado > 0) |
| Ajustar cantidad de Encargo | Vendedor responsable, supervisor = rol Sales Manager, System Manager override |
| Submit sin modal (lista / API) | Fuera de alcance: sin cifra confirmada no se compara (limitación conocida) |
| Resuelto por stock | Se registra al validar la Delivery Note en un campo nuevo del Encargo (opción 4a); anulación de esa NE: propuesta pendiente |

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| E1 | Modelo: `barcode_exception_status`, `expected_barcode`, resolución (fecha/usuario/comentario) en Encargo; intento `BARCODE_REJECTED` con evidencia; `rejected_encargo` en Recepcion Unidad | Hecho 16.0.102 |
| E2 | Compra Shopper: MATCH / adopción / PENDING_APPROVAL + ToDo; aprobar, rechazar, solicitar nueva compra; responsable por Sales Team → Employee → User ComercialFRA, owner, System Manager | Hecho 16.0.102 |
| E3 | Recepción reacciona (aprobar reanuda la unidad, rechazar la deriva a stock/clasificación); vista Excepciones barcode; botones en Encargo; anular OV con compra rechazada | Hecho 16.0.102 |
| E4 | Estado por línea (cantidades que reconcilian) y modal Validar con recálculo en servidor | Hecho 16.0.102 |
| E5 | Bloqueo de "Actualizar artículos" con Encargo y acción "Ajustar cantidad de Encargo" (línea → Encargo 1:N) | Pendiente (revisión de solo lectura de Update Items primero) |
| E6 | Entrega: unidades no entregables, stock libre del mismo Item resuelve el Encargo | Pendiente |
| E7 | Cierre: piloto, README, tasks | Pendiente |

## Interpretaciones y límites conocidos

- La cifra del modal cuenta solo faltantes de Items conocidos; las líneas `ENCARGO-PENDIENTE` ya van al Shopper y no dependen del stock.
- Unidades de Encargo `UNKNOWN_ITEM` en `PENDING_BARCODE_APPROVAL` no tienen Item esperado contra el cual aprobar: la migración no las toca. Pendiente de definición del Arquitecto.
- El formulario Encargo pide comentario en Aprobar al System Manager sin ComercialFRA (override probable); el servidor aplica la regla exacta.
