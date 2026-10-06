# Plan técnico — Spec 013 Fase D: Recepción Chile 16.0.96

## Objetivo

Implementar el corte vigente de Recepción Chile: el receptor escanea una unidad física, el sistema decide si debe apartarse para un Encargo o si corresponde a stock normal, y ComercialFRA puede devolver a stock un Encargo recibido que no satisface.

Caso piloto obligatorio:

- OV: `OV-2026-00326`
- Encargo: `ENC-2026-00401`
- purchase_barcode: `https://qrgo.page.link/JsDVr`
- expectativa: primer escaneo muestra `APARTAR ENC-2026-00401`; cuando no queden Encargos pendientes para ese código, el siguiente escaneo muestra `STOCK NORMAL`.

## Invariantes

1. El valor escaneado es opaco: EAN, UPC, QR, URL, código interno u otro formato son válidos.
2. El primer lookup es `Encargo.purchase_barcode`, no Item.
3. Cada escaneo representa una unidad física.
4. El receptor no resuelve Item ni decide si el producto satisface; escanea y aparta.
5. Si hay Encargo pendiente para el código, se toma el pendiente más antiguo.
6. Si no hay Encargo pendiente, la unidad es stock normal.
7. La OV no se modifica en este corte.
8. No crear Warehouse virtual de Encargos.
9. No tocar Frappe/ERPNext core.
10. No usar System Manager como rol operacional normal, aunque puede operar como administrador.

## Verificación técnica previa

Antes de programar, hacer lectura de servidor para confirmar:

- existencia y uso de `frappe.ui.Scanner` en Frappe 16.28.0;
- forma correcta de filtrar el ícono de escritorio por rol.

Esta verificación no reabre la planificación funcional.

## Backend

Métodos vigentes:

- `receive_scan(code)`
  - roles: `FRAreceptor`, `System Manager`;
  - hace trim técnico de extremos;
  - bloquea Encargos elegibles con ese código;
  - elige el Encargo pendiente más antiguo;
  - marca `RECEIVED`, receptor y hora;
  - registra bitácora;
  - devuelve tipo `encargo` con número ENC o tipo `stock`.

- `return_to_stock(encargo, notes)`
  - roles: `ComercialFRA`, `System Manager`;
  - exige Encargo recibido;
  - exige motivo obligatorio;
  - pasa a `RESOLVED_TO_STOCK`;
  - registra usuario, motivo y bitácora;
  - no toca la OV.

Eliminar del contrato vigente:

- `not_matching`;
- `resolve_to_encargo`;
- `annul_purchase`;
- sección de bitácora "Compra anulada".

## UI Recepción Chile

Ruta operacional:

`MCV Chile -> Recepción Chile`

Requisitos:

- Page mobile-first para celular y lector Bluetooth;
- campo de código siempre listo;
- botón `ESCANEAR` usando el escáner Desk si está disponible;
- cerrar escáner después de cada lectura para evitar doble lectura;
- resultado grande y claro;
- listas: `Comprados no recibidos` y `Recibidos hoy`.

Resultado con Encargo:

```text
APARTAR
ENC-2026-00401
```

Usar señal ámbar y número ENC como dato dominante.

Resultado sin Encargo pendiente:

```text
STOCK NORMAL
```

Usar señal azul.

## Accesos y permisos

- `desktop_icon/recepcion_chile.json`: ícono dentro de `MCV Chile`, sólo para `FRAreceptor` y `System Manager`.
- `workspace_sidebar/recepcion_chile.json`: barra lateral propia del ícono.
- Quitar `Recepción Chile` de la barra lateral de Encargo.
- Patch `v0_0_39`: quitar a `FRAreceptor` permisos directos de DocType; opera por página/endpoints.
- `ComercialFRA` no ve el ícono de recepción.

## ComercialFRA

En formulario Encargo:

- botón `DEVOLVER A STOCK`;
- visible sólo con Encargo recibido;
- visible sólo para `ComercialFRA` y `System Manager`;
- motivo obligatorio;
- llama `return_to_stock`;
- no cambia la OV.

## Fuera de alcance

- transformación automática de la línea `ENCARGO-PENDIENTE` al Item real;
- creación automática de Item desde compra Shopper;
- reglas de clasificación Spec 014 para Item nuevo;
- reemplazar o corregir automáticamente una línea de OV ya enviada;
- documento definitivo de Stock Ledger;
- WMS o recepción completa de cajas;
- facturación/contabilidad de compra;
- modificar Fase C Shopper salvo regresión demostrada;
- reabrir Spec 016.

## Pruebas críticas

1. Cuatro unidades idénticas y tres Encargos: los tres primeros escaneos van a los tres Encargos más antiguos; el cuarto da `STOCK NORMAL`.
2. Código sin Encargo da `STOCK NORMAL`.
3. Usuario sin rol es rechazado.
4. `FRAreceptor` puede escanear pero no devolver a stock.
5. `ComercialFRA` puede devolver a stock un Encargo recibido.
6. Devolver a stock exige Encargo recibido y motivo obligatorio.
7. Piloto `https://qrgo.page.link/JsDVr` muestra `APARTAR ENC-2026-00401`.
8. Un segundo escaneo del piloto, si ya no quedan Encargos pendientes con ese código, muestra `STOCK NORMAL`.
9. Después del migrate, `v0_0_39` aparece en Patch Log.
10. Usuario sólo `FRAreceptor`: ve el ícono dentro de MCV Chile y no abre Encargos ni Items.
11. `ComercialFRA` sin `FRAreceptor`: no ve el ícono.
12. ComercialFRA ve `DEVOLVER A STOCK` en Encargo recibido y la OV no cambia.
