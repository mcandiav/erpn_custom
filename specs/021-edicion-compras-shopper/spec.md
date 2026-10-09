# Spec 021 — Edición de compras del Shopper

**Estado:** DEFINITIVA PARA REVISIÓN; PENDIENTE DE AUTORIZACIÓN DE PROGRAMACIÓN  
**Fecha:** 2026-10-09  
**Autor:** Arquitecto  
**Proyecto:** ERPNext Custom / FRAgallardo  
**Repositorio documental:** ACER / ERPnext-custom  
**Dependencias:** Specs 013, 017, 018 y 020 (esta última cerrada).  
**Versión desplegada confirmada por Miguel:** 16.0.112. Esta Spec todavía no está implementada.

## 1. Objetivo

Permitir que el Shopper corrija los datos de compras que él mismo ingresó, únicamente antes de que la correspondiente unidad sea recibida físicamente en Chile. No modificar decisiones arquitectónicas previas, ni el flujo de compras, recepción, abastecimiento, reservas o la moneda por usuario.

## 2. Decisiones aprobadas que esta Spec DEBE respetar

1. El Shopper puede editar **lo que él ingresó**, de compras registradas **por él**; no puede editar datos aportados por otro usuario, por el sistema o por otros módulos.
2. El derecho de edición termina **al recibirse físicamente la unidad en Chile**. La UI y el backend deben prohibir modificaciones posteriores.
3. **Moneda:** es un atributo de cada usuario Shopper. La moneda se obtiene de su configuración; **si el usuario no tiene moneda configurada, se usa USD**, como ya funciona en el código. El Shopper **no puede editar la moneda** desde compra ni edición. No cambiar el fallback USD ni la configuración existente.
4. La edición corrige evidencia/datos de la misma compra: no crea una compra adicional ni modifica cantidades, stock, OV o reservas.
5. No reabrir Spec 020; esta funcionalidad tiene alcance autónomo bajo Spec 021.

## 3. Matriz obligatoria de campos

| Campo | Shopper puede editar antes de recepción | Motivo / condición |
| --- | --- | --- |
| Precio pagado (`purchase_price`) | Sí | Capturado por Shopper |
| Tienda/Proveedor elegido o propuesto (`supplier`, `proposed_supplier_name`) | Sí | Capturado por Shopper |
| Barcode o QR escaneado (`purchase_barcode`) | Sí, sujeto a mantener integridad | Capturado por Shopper |
| Foto producto (`purchase_product_image`) | Sí | Capturada por Shopper; preservar evidencia histórica |
| Foto etiqueta (`purchase_label_image`) | Sí | Capturada por Shopper; preservar evidencia histórica |
| Precio de etiqueta, observaciones, fecha de compra **manualmente ingresada**, si dichos datos forman parte del formulario existente | Sí | Solo si de hecho los ingresó Shopper; **no crear campos nuevos como parte de esta Spec sin validación arquitectónica** |
| Moneda (`purchase_currency`) | **No** | Atributo de usuario, fallback USD; valor de compra no modificable |
| Cantidad, estado del Supply Event, origen, responsable, fecha/hora automática, Encargo, OV, cliente, ítem, reservas, stock, recepción | **No** | No ingresados por Shopper o datos estructurales de otros procesos |

En el sistema vigente `confirm_purchase` crea un `Encargo Supply Event` con `purchase_price`, `purchase_currency`, `purchase_barcode`, tienda y fotos. La fecha `purchased_on` proviene de `now_datetime()`, por lo que **no es editable**. No dar por existentes entradas opcionales no presentes en la UI.

## 4. UI móvil obligatoria

**Ruta:** App Shopper → **Mis compras** → tarjeta de compra propia → **Editar compra**.

- En *Mis compras*, mantener filtros, tarjetas, foto, tienda, precio y código existentes. Añadir **Editar compra** a compras cuyas unidades sean elegibles. No cambiar el módulo *Compras* ni la secuencia de registro inicial salvo lo estrictamente necesario.
- Vista o panel de edición mobile-first, precargado con precio, tienda, barcode/QR y fotos propios; moneda visible junto al precio como texto **no editable** (p. ej. `USD 89,90`). Conservar método de captura/reescaneo de barcode y fotografías.
- Controles: **Guardar cambios** y **Cancelar**. Después de guardar, volver a *Mis compras* y refrescar tarjeta y total en la moneda correspondiente.
- Al recibirse la unidad en Chile, **Editar compra** deja de estar disponible; compra consultable en solo lectura.
- Si se intenta guardar cuando otra operación acaba de registrar recepción, mostrar: **«Esta unidad ya fue recibida en Chile. No se pueden modificar los datos de compra.»**, sin guardar.
- Si una edición concurrente hizo obsoleto el formulario, no sobrescribir silenciosamente: pedir actualización de datos.
- Si un código QR/barcode no puede corregirse sin desalinear referencias de caja o recepción, mostrar: **«No se puede cambiar el código porque está vinculado a otra operación. No se guardaron cambios.»**
- No exponer cliente, OV o precio de venta mediante estas pantallas o nuevos endpoints. Respetar la privacidad vigente de la app Shopper.

## 5. Propiedad y nivel de bloqueo

**Identidad de compra:** actualizar el mismo `Encargo Supply Event` (de tipo compra Shopper), nunca crear otro.

**Propiedad:** exigir `shopper_user == frappe.session.user` al recuperar y guardar.

**Unidad física:** la recepción en Chile se valida con las relaciones de `Recepcion Unidad` del proceso vigente. En una compra de varias unidades, bloquear solo datos que afecten unidades ya recibidas. Si un evento con `qty > 1` tiene una mezcla de unidades recibidas y no recibidas, **no sobrescribir los atributos compartidos de todo el evento**, ni alterar unidad recibida; bloquear esa edición hasta que exista un mecanismo seguro de edición por unidad. No inventar split de compra/eventos como parte de la 021.

**Momento:** el backend valida recepción inmediatamente antes de persistir la edición, con bloqueo/concurrencia sobre registros afectados. Nunca confiar únicamente en el estado mostrado por frontend.

## 6. Datos y reglas de integridad

- Mantener moneda fijada a la compra: desde `User.custom_shopper_currency` o USD si no existe; `purchase_currency` es de solo lectura en edición, sin recalcularla ni sustituirla por la moneda que el usuario pueda tener hoy.
- La suma de compras por moneda y los importes visibles en *Mis compras* se actualizan luego de una corrección de precio, utilizando la moneda guardada de esa compra.
- No cambiar `qty`, `source_type`, `status`, `shopper_user`, vínculos Encargo/OV, ni recalcular cantidades por una simple corrección. Conservan la lógica de Spec 020.
- Cambiar barcode requiere aplicar las validaciones/gestión de excepciones ya vigentes de Spec 017 y proteger vínculos existentes. No inventar comportamiento de caja, recepción o resolución de excepciones.
- Archivos/fotos reemplazados mantienen histórico y permisos de acceso. No hacer pública evidencia privada.
- Validar datos numéricos, formatos de imagen y códigos con el mismo rigor de la captura original.
- Usar versión/modificación del evento para rechazar escrituras obsoletas; fallos deben ser atómicos (sin cambios parciales).

## 7. API, permisos y auditoría

**Programador:** en `ERPnext-custom/erpn_custom`, reutilizar funciones y convenciones vigentes de `erpn_custom/encargo/shopper.py` y `erpn_custom/www/encargos-shopper.html`. Exponer una operación POST específica para modificar una compra propia identificada por `supply_event`, no aceptar nombre de Shopper/moneda/estado/cantidad como nuevos valores, y comprobar propiedad + recepción en el backend. Filtrar por allowlist exacta de campos aprobados.

**Auditoría:** registrar evento/unidad, campo cambiado, valor previo, valor nuevo, usuario autenticado y sello horario; para fotos guardar referencias a evidencia anterior y nueva. No borrar rastro ni sobrescribir sin historial. Mostrar historial solo conforme a permisos existentes; no exponerlo a otros Shoppers.

## 8. Casos de aceptación

1. Shopper A modifica precio, tienda, QR/barcode y fotos de compra propia no recibida; ve cambios al volver a *Mis compras*.
2. Shopper A no puede editar compra de B mediante URL ni POST forjado.
3. Moneda visible de la compra es la persistida; no existe selector editable ni parámetro permitido para modificarla.
4. Usuario sin moneda configurada compra en **USD** (fallback vigente); sigue sin poder editar moneda.
5. Compra recibida en Chile no tiene botón y POST rechaza sin alteraciones.
6. Recepción confirmada durante edición: guardar bloquea atómicamente sin escribir cambios.
7. Un Encargo con unidades de distintas compras permite editar las no recibidas aunque otras compras ya estén recibidas.
8. Compra multiunidad parcialmente recibida: atributos compartidos no se modifican accidentalmente para ninguna unidad recibida; presentar bloqueo seguro.
9. Cambio de barcode respeta vínculos/validaciones Spec 017 o bloquea la operación de forma íntegra.
10. Reemplazo de fotos conserva evidencia anterior en auditoría.
11. Corrección de precio actualiza visualización y total de *Mis compras*, sin conversión errónea ni cambio de moneda.
12. Dos ediciones concurrentes no se pisan silenciosamente.
13. La corrección no crea otro evento, no suma abastecimiento, no modifica inventario, cobertura ni SRE.
14. API rechaza modificación de `qty`, moneda, estado, Encargo/OV, propietario y recepción.
15. UI y API mantienen ocultos los datos comerciales que Shopper no podía consultar antes.

## 9. Exclusiones

No permitir edición después de recepción; no habilitar cambio de moneda; no cambiar configuración de moneda por usuario ni fallback USD; no crear nuevos tipos de compra; no reasignar compras entre Shoppers; no alterar cantidades; no crear procedimientos de reversión de recepción; no reabrir ni reinterpretar Spec 020.

## 10. Entrega, control y responsabilidades

**Arquitecto:** define y mantiene esta Spec. **Programador:** verifica los contratos actuales, presenta plan técnico y pruebas, implementa después de autorización, documenta los cambios y verifica en sandbox. La especificación no es evidencia de implementación ni equivale a orden de cambiar decisiones previas.

**Estado de activación:** se propone como siguiente Spec 021. Declararla vigente en el README del repositorio de programación requiere autorización expresa de Miguel y handoff; no activar ni modificar el README del Programador implícitamente.

**Cierre:** todos los casos de §8 deben estar verificados; no declarar cerrada la Spec por solo tener UI visible.
