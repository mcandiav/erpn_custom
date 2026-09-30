# Tasks — Spec 015

## T01 — Inspección previa
- [ ] Confirmar meta efectivo de `Sales Order.items`.
- [ ] Confirmar validaciones core adicionales sobre Sales Order sin items.
- [ ] Confirmar secuencia de hooks vigente.
- [ ] Confirmar fuente única de pago aplicado.
- [ ] Presentar hallazgos antes de escribir código si aparece una contradicción con la Spec.

## T02 — Permitir Draft sin líneas
- [ ] Crear patch idempotente.
- [ ] Establecer `Sales Order.items.reqd = 0`.
- [ ] No afectar otros DocTypes.
- [ ] Probar creación y segundo guardado de OV Draft vacía.

## T03 — Gate de líneas en Submit
- [ ] Agregar validación R1 al inicio de `before_submit`.
- [ ] Mensaje en español definido en la Spec.
- [ ] Probar que el documento permanece Draft tras el bloqueo.

## T04 — Gate de pago en Submit
- [ ] Reutilizar/refactorizar cálculo de Payment Entry Reference.
- [ ] Agregar validación R2.
- [ ] Saldo disponible no aplicado debe fallar.
- [ ] Pago aplicado parcial > 0 debe superar este gate.
- [ ] No confiar solo en `advance_paid`.

## T05 — Regresión Encargo
- [ ] Agregar Encargo desde OV vacía guardada.
- [ ] Verificar exactamente una fila `ENCARGO-PENDIENTE`.
- [ ] Verificar vínculo `custom_encargo`.
- [ ] Verificar que Encargo permanezca Draft antes del Submit.

## T06 — Regresión Shopper
- [ ] Submit sin pago: Encargo no aparece en Shopper.
- [ ] Aplicar pago y Submit: Encargo pasa Open/PENDING.
- [ ] Verificar visibilidad en lista Shopper.
- [ ] Verificar que compra Shopper no cambió.

## T07 — Regresión stock
- [ ] OV con Item conocido y stock.
- [ ] Pago 0 bloquea Submit.
- [ ] Pago > 0 permite continuar.
- [ ] Reserva estándar sigue funcionando.

## T08 — Regresión faltante conocido
- [ ] Item conocido con faltante.
- [ ] Submit válido crea/actualiza Encargo de faltante.
- [ ] No crear Encargo antes de superar los gates.
- [ ] Reserva parcial mantiene comportamiento anterior.

## T09 — Caso OV-2026-00076
- [ ] Reproducir el flujo desde cero.
- [ ] No crear fila temporal.
- [ ] Guardar OV vacía.
- [ ] Agregar Crossbody.
- [ ] Aplicar pago.
- [ ] Submit.
- [ ] Resultado final: una sola línea comercial.

## T10 — Documentación y cierre
- [ ] Actualizar README/bitácora con versión implementada.
- [ ] Registrar archivos modificados.
- [ ] Registrar pruebas automáticas.
- [ ] Registrar evidencia sandbox.
- [ ] Marcar Spec cerrada solo tras aceptación.
