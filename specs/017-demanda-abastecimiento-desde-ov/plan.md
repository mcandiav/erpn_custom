# Plan — Spec 017 Excepciones de abastecimiento y trazabilidad desde OV

Estado: EN CURSO desde 2026-10-09 (estuvo pausada por Spec 020 entre 2026-10-07 y 2026-10-09).

Fuente: `spec.md` de esta carpeta.

Spec 020 reemplaza cualquier supuesto de compra monolítica, `purchase_status` como fuente de verdad de demanda y recepción exclusiva de Encargos PURCHASED. Donde 017 y 020 difieren manda la 020:

- Rechazo de barcode: el cupo vuelve de inmediato a la cola del Shopper (020 §13), no queda detenido esperando "Solicitar nueva compra" (017 §8.4).
- Aumento de cantidad: sube `requested_qty` del mismo Encargo aunque ya tenga compras (020 §18); no se crea un segundo Encargo por el delta (017 §13.3). Una línea mantiene un Encargo abierto.
- Stock disponible al entregar: no se resuelve solo al validar la Nota de Entrega (017 §15.2); se reserva antes con "Asignar stock a demanda" (020 §14).

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
| Resuelto por stock | Reemplazado 2026-10-09 (opción A): la Nota de Entrega solo entrega lo reservado; el stock disponible se reserva antes con "Asignar stock a demanda" |
| Aumento con compras | Sube la cantidad del mismo Encargo (2026-10-09) |
| Líneas sin Encargo en OV con Encargos | También se ajustan con "Ajustar cantidad"; el faltante crea Encargo (2026-10-09) |
| Motivo del ajuste | Obligatorio siempre (2026-10-09) |
| Pilotos | Bastan pruebas automáticas (2026-10-09) |
| Términos | stock disponible, reservado, faltante (no "stock libre") |

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| E1 | Modelo: `barcode_exception_status`, `expected_barcode`, resolución (fecha/usuario/comentario) en Encargo; intento `BARCODE_REJECTED` con evidencia; `rejected_encargo` en Recepcion Unidad | Hecho 16.0.102 |
| E2 | Compra Shopper: MATCH / adopción / PENDING_APPROVAL + ToDo; aprobar, rechazar, solicitar nueva compra; responsable por Sales Team → Employee → User ComercialFRA, owner, System Manager | Hecho 16.0.102 |
| E3 | Recepción reacciona (aprobar reanuda la unidad, rechazar la deriva a stock/clasificación); vista Excepciones barcode; botones en Encargo; anular OV con compra rechazada | Hecho 16.0.102 |
| E4 | Estado por línea (cantidades que reconcilian) y modal Validar con recálculo en servidor | Hecho 16.0.102 |
| E5 | Bloqueo de "Actualizar artículos" con Encargo y acción "Ajustar cantidad" | Hecho 16.0.110 |
| E6 | Entrega: solo lo reservado; unidades de compras en excepción no entregables | Hecho 16.0.111 |
| E7 | Cierre: piloto, README, tasks | Pendiente |

## Interpretaciones y límites conocidos

- La cifra del modal cuenta solo faltantes de Items conocidos; las líneas `ENCARGO-PENDIENTE` ya van al Shopper y no dependen del stock.
- Unidades de Encargo `UNKNOWN_ITEM` en `PENDING_BARCODE_APPROVAL` no tienen Item esperado contra el cual aprobar: la migración no las toca. Pendiente de definición del Arquitecto.
- El formulario Encargo pide comentario en Aprobar al System Manager sin ComercialFRA (override probable); el servidor aplica la regla exacta.
