# Lista de verificación — Spec 021 (para entrega al Programador)
**Estado:** PROGRAMADA en 16.0.113. Piloto en sandbox pendiente. No cerrada.

- [x] Inventariar campos y relaciones de compra, recepción física y `qty > 1`.
- [x] Confirmar moneda de usuario y fallback USD sin cambiarlos.
- [x] Diseñar API POST de edición por `supply_event`, con owner y allowlist.
- [x] Bloquear edición al recibir la unidad en Chile; verificar backend transaccionalmente.
- [x] Manejar compra multiunidad parcialmente recibida sin mutar unidades recibidas.
- [x] Preservar histórico de fotos y auditoría de todos los cambios.
- [x] Validar cambios de barcode/QR frente a referencias de caja y excepciones.
- [x] Evitar escrituras concurrentes obsoletas.
- [x] Añadir botón y panel Editar compra en Mis compras.
- [x] Mostrar moneda inmutable de compra y actualizar totales.
- [x] Mantener prohibiciones sobre cliente, OV, inventario, reservas y cantidades.
- [x] Ejecutar y registrar los 15 casos de `spec.md` §8. Cubiertos por `erpn_custom/encargo/test_shopper.py` (`TestPurchaseEdit`) y las reglas ya probadas de moneda USD.
- [ ] Hacer piloto de compra antes y después de recepción.
- [ ] Actualizar documentación y cerrar únicamente tras evidencia y aprobación.
