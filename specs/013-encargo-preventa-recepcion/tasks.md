# Tasks — Spec 013 Fase D: Recepción Chile 16.0.96

## Gate técnico

- [ ] D001 Leer README + Spec 013 §34.21 + este plan.
- [ ] D002 Confirmar en servidor Frappe 16.28.0 la disponibilidad/uso de `frappe.ui.Scanner`.
- [ ] D003 Confirmar cómo filtra por rol el ícono de escritorio.
- [x] D004 OK funcional de Miguel para el corte 16.0.96: recibido el 2026-10-06.
- [ ] D005 No reabrir Fases B/C ni Spec 016.

## Backend

- [ ] D010 Implementar `receive_scan(code)`.
- [ ] D011 Autorizar `receive_scan` sólo para `FRAreceptor` y `System Manager`.
- [ ] D012 Buscar por `purchase_barcode` exacto, con trim técnico de extremos.
- [ ] D013 Bloquear Encargos elegibles y tomar el pendiente más antiguo.
- [ ] D014 Marcar `RECEIVED`, receptor y hora.
- [ ] D015 Registrar evento en bitácora.
- [ ] D016 Devolver respuesta `encargo` con número ENC o `stock`.
- [ ] D017 Implementar `return_to_stock(encargo, notes)`.
- [ ] D018 Autorizar `return_to_stock` sólo para `ComercialFRA` y `System Manager`.
- [ ] D019 Exigir Encargo recibido y motivo obligatorio para devolver a stock.
- [ ] D020 Pasar Encargo a `RESOLVED_TO_STOCK` sin tocar OV.
- [ ] D021 Eliminar `not_matching`, `resolve_to_encargo`, `annul_purchase` y bitácora "Compra anulada" del contrato vigente.

## UI Recepción Chile

- [ ] D030 Crear Page `Recepción Chile` mobile-first.
- [ ] D031 Campo de código compatible con lector Bluetooth.
- [ ] D032 Botón `ESCANEAR` con cámara mediante escáner Desk si aplica.
- [ ] D033 Cerrar escáner después de cada lectura.
- [ ] D034 Resultado `APARTAR / ENC-YYYY-#####` en ámbar.
- [ ] D035 Resultado `STOCK NORMAL` en azul.
- [ ] D036 Lista `Comprados no recibidos`.
- [ ] D037 Lista `Recibidos hoy`.

## Acceso y permisos

- [ ] D040 Crear `desktop_icon/recepcion_chile.json` dentro de MCV Chile para `FRAreceptor` y `System Manager`.
- [ ] D041 Crear `workspace_sidebar/recepcion_chile.json`.
- [ ] D042 Quitar `Recepción Chile` de la barra lateral de Encargo.
- [ ] D043 Patch `v0_0_39`: quitar a `FRAreceptor` permisos directos de DocType.
- [ ] D044 Verificar Patch Log después del migrate.

## ComercialFRA

- [ ] D050 Botón `DEVOLVER A STOCK` en Encargo recibido.
- [ ] D051 Visible sólo para `ComercialFRA` y `System Manager`.
- [ ] D052 Motivo obligatorio.
- [ ] D053 Confirmar que la OV no cambia.

## Pruebas

- [ ] D060 Unittests: 4 unidades idénticas y 3 Encargos van a los 3 más antiguos y la cuarta da stock.
- [ ] D061 Código sin Encargo da stock.
- [ ] D062 Usuario sin rol es rechazado.
- [ ] D063 Devolver a stock exige Encargo recibido y motivo.
- [ ] D064 ComercialFRA puede devolver; FRAreceptor no.
- [ ] D065 Sintaxis JS con node.
- [ ] D066 Piloto `https://qrgo.page.link/JsDVr`: primer escaneo muestra `APARTAR ENC-2026-00401`.
- [ ] D067 Segundo escaneo del piloto, sin Encargos pendientes restantes, muestra `STOCK NORMAL`.
- [ ] D068 Usuario sólo `FRAreceptor`: ve ícono y no abre Encargos ni Items.
- [ ] D069 ComercialFRA sin rol `FRAreceptor`: no ve ícono.
- [ ] D070 ComercialFRA ve `DEVOLVER A STOCK` en Encargo recibido.

## Fuera de alcance documentado

- [x] D080 Transformación automática `ENCARGO-PENDIENTE` -> Item real queda como fase posterior de Arquitectura.
- [x] D081 Creación automática de Item con clasificación Spec 014 queda fuera de este corte.
- [x] D082 Reemplazo/corrección automática de línea de OV enviada queda fuera de este corte.
