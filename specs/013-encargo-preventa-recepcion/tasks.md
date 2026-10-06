# Tasks — Spec 013 Fase D: Recepción Chile 16.0.96

## Gate técnico

- [x] D001 Leer README + Spec 013 §34.21 + este plan.
- [x] D002 Escáner: no se usa `frappe.ui.Scanner`; la página carga la misma librería que el Shopper (`/assets/frappe/node_modules/html5-qrcode/html5-qrcode.min.js`), ya operativa en el celular.
- [x] D003 Filtro del ícono verificado en el código de Frappe `version-16` (`desktop_icon.py`): un ícono Link aparece si su barra lateral tiene algún enlace permitido para el usuario y, si tiene tabla `roles`, el usuario debe tener uno de ellos. Confirmar en el sitio con D068/D069.
- [x] D004 OK funcional de Miguel para el corte 16.0.96: recibido el 2026-10-06.
- [x] D005 No reabrir Fases B/C ni Spec 016.

## Backend

- [x] D010 Implementar `receive_scan(code)`.
- [x] D011 Autorizar `receive_scan` sólo para `FRAreceptor` y `System Manager`.
- [x] D012 Buscar por `purchase_barcode` exacto, con trim técnico de extremos.
- [x] D013 Bloquear Encargos elegibles y tomar el pendiente más antiguo.
- [x] D014 Marcar `RECEIVED`, receptor y hora.
- [x] D015 Registrar evento en bitácora.
- [x] D016 Devolver respuesta `encargo` con número ENC o `stock`.
- [x] D017 Implementar `return_to_stock(encargo, notes)`.
- [x] D018 Autorizar `return_to_stock` sólo para `ComercialFRA` y `System Manager`.
- [x] D019 Exigir Encargo recibido y motivo obligatorio para devolver a stock.
- [x] D020 Pasar Encargo a `RESOLVED_TO_STOCK` sin tocar OV.
- [x] D021 Eliminar `not_matching`, `resolve_to_encargo`, `annul_purchase` y bitácora "Compra anulada" del contrato vigente.

## UI Recepción Chile

- [x] D030 Crear Page `Recepción Chile` mobile-first.
- [x] D031 Campo de código compatible con lector Bluetooth.
- [x] D032 Botón `ESCANEAR` con cámara (librería del Shopper, ver D002).
- [x] D033 Cerrar escáner después de cada lectura.
- [x] D034 Resultado `APARTAR / ENC-YYYY-#####` en ámbar.
- [x] D035 Resultado `STOCK NORMAL` en azul.
- [x] D036 Lista `Comprados no recibidos`.
- [x] D037 Lista `Recibidos hoy`.

## Acceso y permisos

- [x] D040 Crear `desktop_icon/recepcion_chile.json` dentro de MCV Chile para `FRAreceptor` y `System Manager`.
- [x] D041 Crear `workspace_sidebar/recepcion_chile.json`.
- [x] D042 Quitar `Recepción Chile` de la barra lateral de Encargo.
- [x] D043 Patch `v0_0_39`: quitar a `FRAreceptor` permisos directos de DocType.
- [ ] D044 Verificar Patch Log después del migrate.

## ComercialFRA

- [x] D050 Botón `DEVOLVER A STOCK` en Encargo recibido.
- [x] D051 Visible sólo para `ComercialFRA` y `System Manager`.
- [x] D052 Motivo obligatorio.
- [ ] D053 Confirmar que la OV no cambia.

## Pruebas

- [x] D060 Unittests: 4 unidades idénticas y 3 Encargos van a los 3 más antiguos y la cuarta da stock.
- [x] D061 Código sin Encargo da stock.
- [x] D062 Usuario sin rol es rechazado.
- [x] D063 Devolver a stock exige Encargo recibido y motivo.
- [x] D064 ComercialFRA puede devolver; FRAreceptor no.
- [x] D065 Sintaxis JS con node.
- [ ] D066 Piloto `https://qrgo.page.link/JsDVr`: primer escaneo muestra `APARTAR ENC-2026-00401`.
- [ ] D067 Segundo escaneo del piloto, sin Encargos pendientes restantes, muestra `STOCK NORMAL`.
- [ ] D068 Usuario sólo `FRAreceptor`: ve ícono y no abre Encargos ni Items.
- [ ] D069 ComercialFRA sin rol `FRAreceptor`: no ve ícono.
- [ ] D070 ComercialFRA ve `DEVOLVER A STOCK` en Encargo recibido.

## Fuera de alcance documentado

- [x] D080 Transformación automática `ENCARGO-PENDIENTE` -> Item real queda como fase posterior de Arquitectura.
- [x] D081 Creación automática de Item con clasificación Spec 014 queda fuera de este corte.
- [x] D082 Reemplazo/corrección automática de línea de OV enviada queda fuera de este corte.
